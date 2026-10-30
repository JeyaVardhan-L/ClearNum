"""Exposure Rescan and Verification Engine.
Performs safe HTTP rescans of known exposure URLs to verify whether personal numbers
have been removed (HTTP 404/410, soft-404, or content cleared) or remain exposed.

Enforces SSRF validation, anti-bot challenge detection, soft-404 classification,
generic redirect detection, truthful lifecycle states, reappearance detection,
and monotonic audit trail logging.
"""

import hashlib
import html
import re
import uuid
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from backend.app.core.database import get_db_connection, utc_now_iso
from backend.app.core.redactor import redact_text
from backend.app.core.ssrf import (
    safe_fetch_url,
    SSRFValidationError,
    UnsupportedContentTypeError,
)
from backend.app.engines.discovery.matcher import match_phone_in_text
from backend.app.engines.discovery.normalizer import NormalizedPhone


@dataclass
class VerificationOutcome:
    url: str
    status: str  # Canonical ActionState value
    outcome: str  # VERIFIED_ABSENT, STILL_PRESENT, INACCESSIBLE, INCONCLUSIVE, ARCHIVE_ONLY
    http_status_code: Optional[int]
    evidence_notes: str
    content_hash: str
    verified_at: str
    final_url: Optional[str] = None
    soft_404_detected: bool = False
    reappeared: bool = False
    evidence_origin: str = "FETCHED_PAGE"


# Common Soft-404 and deletion phrases
SOFT_404_PATTERNS = [
    r"\b404\s+not\s+found\b",
    r"\bpage\s+not\s+found\b",
    r"\berror\s+404\b",
    r"\bprofile\s+(?:has\s+been\s+)?(?:removed|deleted|no\s+longer\s+available)\b",
    r"\blisting\s+(?:has\s+been\s+)?(?:removed|deleted|no\s+longer\s+available)\b",
    r"\brecord\s+(?:has\s+been\s+)?(?:removed|deleted|not\s+found)\b",
    r"\buser\s+(?:has\s+been\s+)?(?:deleted|removed|not\s+found)\b",
    r"\baccount\s+(?:has\s+been\s+)?(?:deleted|removed|disabled)\b",
    r"\bpage\s+(?:does\s+not\s+exist|cannot\s+be\s+found|is\s+missing)\b",
    r"\bcontent\s+(?:is\s+)?unavailable\b",
    r"\bthis\s+page\s+has\s+been\s+removed\b",
    r"\bthe\s+page\s+you\s+are\s+looking\s+for\s+does\s+not\s+exist\b",
    r"\bno\s+longer\s+active\b",
]

# Anti-bot and challenge phrases
ANTI_BOT_PATTERNS = [
    r"\battention\s+required!\s*\|\s*cloudflare\b",
    r"\bcloudflare\s+ray\s+id\b",
    r"\bcf-chl-bypass\b",
    r"\bjust\s+a\s+moment\.\.\.\b",
    r"\bchecking\s+your\s+browser\b",
    r"\bdatadome\b",
    r"\bshieldsquare\s+captcha\b",
    r"\bplease\s+turn\s+javascript\s+on\s+and\s+reload\b",
    r"\bhuman\s+verification\b",
    r"\bverify\s+you\s+are\s+human\b",
    r"\bsecurity\s+check\s+to\s+access\b",
    r"\brobot\s+or\s+human\b",
]

ARCHIVE_DOMAINS = {
    "web.archive.org",
    "archive.today",
    "archive.is",
    "archive.ph",
    "archive.vn",
    "archive.li",
    "archive.md",
    "perma.cc",
    "webharvest.gov",
}


def extract_clean_text(html_content: str) -> tuple[str, str]:
    """Strips markup, scripts, and styles, returning (clean_text, page_title)."""
    if not html_content:
        return "", ""

    # Extract title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    title = html.unescape(title_match.group(1)).strip() if title_match else ""

    # Strip script, style, head blocks
    cleaned = re.sub(r"<(script|style|head)[^>]*>.*?</\1>", " ", html_content, flags=re.IGNORECASE | re.DOTALL)
    # Strip HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    # Unescape entities
    cleaned = html.unescape(cleaned)
    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned, title


def detect_soft_404(clean_text: str, title: str) -> Optional[str]:
    """Checks whether the page content represents a Soft-404 deletion notice."""
    search_scope = f"{title} {clean_text[:2000]}".lower()
    for pattern in SOFT_404_PATTERNS:
        match = re.search(pattern, search_scope, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def detect_anti_bot_challenge(clean_text: str, title: str, status_code: int) -> Optional[str]:
    """Detects anti-bot firewalls, captchas, and challenge screens."""
    search_scope = f"{title} {clean_text[:2500]}".lower()
    for pattern in ANTI_BOT_PATTERNS:
        match = re.search(pattern, search_scope, re.IGNORECASE)
        if match:
            return match.group(0)

    if status_code == 403 and any(w in search_scope for w in ("access denied", "forbidden", "blocked")):
        return "Access Denied / Forbidden (HTTP 403)"

    return None


def is_generic_redirect(initial_url: str, final_url: Optional[str]) -> tuple[bool, str]:
    """Detects if a deep exposure URL was redirected to a generic root or login landing page."""
    if not final_url:
        return False, ""

    init_parsed = urlparse(initial_url.strip())
    final_parsed = urlparse(final_url.strip())

    init_path = init_parsed.path.rstrip("/")
    final_path = final_parsed.path.rstrip("/")

    # If the initial path was a deep path (more than root)
    if init_path and init_path not in ("", "/"):
        # Redirected to root
        if final_path in ("", "/"):
            return True, "redirected to domain homepage"

        # Redirected to login / auth / search
        generic_endpoints = {"/login", "/signin", "/auth", "/session", "/search", "/portal"}
        if final_path in generic_endpoints:
            return True, f"redirected to generic landing page ('{final_path}')"

    return False, ""


def is_archive_url(url: str) -> bool:
    """Checks if a URL belongs to a known public web archiving service."""
    try:
        host = urlparse(url).hostname or ""
        return host.lower() in ARCHIVE_DOMAINS or any(host.lower().endswith("." + d) for d in ARCHIVE_DOMAINS)
    except Exception:
        return False


async def verify_exposure_url(
    exposure_id: str,
    url: str,
    phone: NormalizedPhone,
    update_database: bool = True,
    evidence_origin: Optional[str] = None,
) -> VerificationOutcome:
    """Rescans an exposure URL safely, validates content, and records a truthful verification outcome."""
    now_iso = utc_now_iso()

    # Determine evidence origin if not explicitly provided
    if not evidence_origin:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT evidence_origin FROM exposures WHERE id = ?", (exposure_id,))
        row = cursor.fetchone()
        evidence_origin = row["evidence_origin"] if row and row["evidence_origin"] else "FETCHED_PAGE"
        conn.close()

    # If evidence is an archived snapshot or the URL is an archive domain
    if evidence_origin == "ARCHIVED_SNAPSHOT" or is_archive_url(url):
        # We can still fetch the snapshot to see if phone is in the archive, but classify as ARCHIVE_ONLY
        try:
            fetch_res = await safe_fetch_url(url)
            status_code = fetch_res[0]
            content = fetch_res[1]
            final_url = getattr(fetch_res, "final_url", url) or url
            content_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
            clean_text, _ = extract_clean_text(content)
            match_res = match_phone_in_text(clean_text or content, phone)

            notes = (
                f"Archived snapshot verified (HTTP {status_code}). "
                f"{'Phone number identified in snapshot.' if match_res.matched else 'Phone number absent from snapshot.'} "
                "Archived evidence does not verify current live status on the active source domain."
            )
            outcome = VerificationOutcome(
                url=url,
                status="CONFIRMED_EXPOSURE" if match_res.matched else "NO_LONGER_VISIBLE_AT_CHECKED_URL",
                outcome="ARCHIVE_ONLY",
                http_status_code=status_code,
                evidence_notes=redact_text(notes),
                content_hash=content_hash,
                verified_at=now_iso,
                final_url=final_url,
                evidence_origin="ARCHIVED_SNAPSHOT",
            )
        except Exception as e:
            outcome = VerificationOutcome(
                url=url,
                status="INACCESSIBLE_OR_INCONCLUSIVE",
                outcome="ARCHIVE_ONLY",
                http_status_code=None,
                evidence_notes=redact_text(f"Archived snapshot inaccessible: {e}. Live domain status remains unverified."),
                content_hash="",
                verified_at=now_iso,
                final_url=url,
                evidence_origin="ARCHIVED_SNAPSHOT",
            )

        if update_database:
            _update_remediation_action_record(exposure_id, outcome)
        return outcome

    # Live Web Verification Flow
    try:
        fetch_res = await safe_fetch_url(url)
        status_code = fetch_res[0]
        content = fetch_res[1]
        headers = fetch_res[2] if len(fetch_res) > 2 else {}
        final_url = getattr(fetch_res, "final_url", url) or (headers.get("x-final-url") if isinstance(headers, dict) else url)
    except UnsupportedContentTypeError as e:
        outcome = VerificationOutcome(
            url=url,
            status="INACCESSIBLE_OR_INCONCLUSIVE",
            outcome="INCONCLUSIVE",
            http_status_code=None,
            evidence_notes=f"Inconclusive response: Target returned unsupported binary MIME type '{e.content_type}'. Only text/HTML documents can be verified.",
            content_hash="",
            verified_at=now_iso,
            final_url=url,
            evidence_origin="FETCHED_PAGE",
        )
        if update_database:
            _update_remediation_action_record(exposure_id, outcome)
        return outcome
    except SSRFValidationError as e:
        outcome = VerificationOutcome(
            url=url,
            status="INACCESSIBLE_OR_INCONCLUSIVE",
            outcome="INACCESSIBLE",
            http_status_code=None,
            evidence_notes=f"URL verification blocked by SSRF network defense: {e}",
            content_hash="",
            verified_at=now_iso,
            final_url=url,
            evidence_origin="FETCHED_PAGE",
        )
        if update_database:
            _update_remediation_action_record(exposure_id, outcome)
        return outcome
    except Exception as e:
        outcome = VerificationOutcome(
            url=url,
            status="INACCESSIBLE_OR_INCONCLUSIVE",
            outcome="INACCESSIBLE",
            http_status_code=None,
            evidence_notes=f"Network error or timeout during verification rescan: {e}",
            content_hash="",
            verified_at=now_iso,
            final_url=url,
            evidence_origin="FETCHED_PAGE",
        )
        if update_database:
            _update_remediation_action_record(exposure_id, outcome)
        return outcome

    content_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
    clean_text, page_title = extract_clean_text(content)

    # 1. Check for HTTP 404 (Not Found) or 410 (Gone)
    if status_code in (404, 410):
        outcome = VerificationOutcome(
            url=url,
            status="NO_LONGER_VISIBLE_AT_CHECKED_URL",
            outcome="VERIFIED_ABSENT",
            http_status_code=status_code,
            evidence_notes=(
                f"No longer visible: Target server returned HTTP {status_code} "
                f"({'Resource Gone' if status_code == 410 else 'Not Found'}). "
                "Verified absent at checked URL. Does not confirm underlying database deletion."
            ),
            content_hash=content_hash,
            verified_at=now_iso,
            final_url=final_url,
            evidence_origin="FETCHED_PAGE",
        )

    # 2. Check for anti-bot challenges or firewalls (HTTP 403, 429, 503 or content-based)
    elif status_code in (403, 429, 503) or detect_anti_bot_challenge(clean_text, page_title, status_code):
        challenge_desc = detect_anti_bot_challenge(clean_text, page_title, status_code) or f"HTTP {status_code}"
        outcome = VerificationOutcome(
            url=url,
            status="INACCESSIBLE_OR_INCONCLUSIVE",
            outcome="INACCESSIBLE",
            http_status_code=status_code,
            evidence_notes=(
                f"Verification challenged by anti-bot firewall or rate-limit ({challenge_desc}). "
                "Inaccessibility cannot prove removal. Manual inspection required."
            ),
            content_hash=content_hash,
            verified_at=now_iso,
            final_url=final_url,
            evidence_origin="FETCHED_PAGE",
        )

    # 3. Check HTTP 200 responses
    elif status_code == 200:
        # Check phone presence in clean text as well as raw content
        match_res = match_phone_in_text(clean_text, phone)
        if not match_res.matched:
            match_res = match_phone_in_text(content, phone)

        if match_res.matched:
            outcome = VerificationOutcome(
                url=url,
                status="STILL_VISIBLE",
                outcome="STILL_PRESENT",
                http_status_code=200,
                evidence_notes=redact_text(
                    f"Still visible: Target webpage displays matching phone number ({match_res.match_type}): '{match_res.snippet}'"
                ),
                content_hash=content_hash,
                verified_at=now_iso,
                final_url=final_url,
                evidence_origin="FETCHED_PAGE",
            )
        else:
            # Phone is not found. Check for Soft-404 or generic redirect
            soft_404_phrase = detect_soft_404(clean_text, page_title)
            is_redirected, redir_desc = is_generic_redirect(url, final_url)

            if soft_404_phrase:
                outcome = VerificationOutcome(
                    url=url,
                    status="NO_LONGER_VISIBLE_AT_CHECKED_URL",
                    outcome="VERIFIED_ABSENT",
                    http_status_code=200,
                    evidence_notes=(
                        f"No longer visible: Target server returned HTTP 200 with soft-404 notice "
                        f"('{soft_404_phrase}'). Telephone number absent from page. "
                        "Verified absent at checked URL; underlying database status unconfirmed."
                    ),
                    content_hash=content_hash,
                    verified_at=now_iso,
                    final_url=final_url,
                    soft_404_detected=True,
                    evidence_origin="FETCHED_PAGE",
                )
            elif is_redirected:
                outcome = VerificationOutcome(
                    url=url,
                    status="NO_LONGER_VISIBLE_AT_CHECKED_URL",
                    outcome="VERIFIED_ABSENT",
                    http_status_code=200,
                    evidence_notes=(
                        f"No longer visible: Specific profile URL {redir_desc} ('{final_url}'). "
                        "Telephone number absent from destination. Verified absent at checked URL."
                    ),
                    content_hash=content_hash,
                    verified_at=now_iso,
                    final_url=final_url,
                    evidence_origin="FETCHED_PAGE",
                )
            else:
                outcome = VerificationOutcome(
                    url=url,
                    status="NO_LONGER_VISIBLE_AT_CHECKED_URL",
                    outcome="VERIFIED_ABSENT",
                    http_status_code=200,
                    evidence_notes=(
                        "No longer visible: Webpage returned HTTP 200, but telephone number is absent from response. "
                        "Verified absent at checked URL. Underlying database deletion unconfirmed."
                    ),
                    content_hash=content_hash,
                    verified_at=now_iso,
                    final_url=final_url,
                    evidence_origin="FETCHED_PAGE",
                )

    # 4. Other HTTP status codes (e.g. 500, 502, 504)
    else:
        outcome = VerificationOutcome(
            url=url,
            status="INACCESSIBLE_OR_INCONCLUSIVE",
            outcome="INCONCLUSIVE",
            http_status_code=status_code,
            evidence_notes=f"Inconclusive response code HTTP {status_code}. Content could not be verified.",
            content_hash=content_hash,
            verified_at=now_iso,
            final_url=final_url,
            evidence_origin="FETCHED_PAGE",
        )

    if update_database:
        _update_remediation_action_record(exposure_id, outcome)

    return outcome


def _update_remediation_action_record(exposure_id: str, outcome: VerificationOutcome) -> None:
    """Updates the remediation_actions table with verification outcome and appends an immutable audit event."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, identity_hmac, status FROM remediation_actions WHERE exposure_id = ?", (exposure_id,))
    act_row = cursor.fetchone()
    if not act_row:
        conn.close()
        return

    action_id = act_row["id"]
    identity_hmac = act_row["identity_hmac"]
    current_status = act_row["status"] or "DISCOVERED"
    new_status = current_status
    evidence_type = "HTTP_LIVE_VERIFICATION"

    if outcome.outcome == "STILL_PRESENT":
        # Reappearance detection: was it previously marked removed?
        if current_status in ("NO_LONGER_VISIBLE_AT_CHECKED_URL", "VERIFIED_REMOVED", "SOURCE_CONFIRMED_REMOVAL"):
            new_status = "REAPPEARED"
            outcome.reappeared = True
            outcome.status = "REAPPEARED"
            evidence_type = "SUBSEQUENT_SCAN_DETECTION"
            outcome.evidence_notes = (
                f"⚠️ Reappearance Detected: Telephone number was detected again on a URL previously marked as removed. "
                f"{outcome.evidence_notes}"
            )
        elif current_status in ("DISCOVERED", "AWAITING_USER_REVIEW"):
            new_status = "CONFIRMED_EXPOSURE"
            evidence_type = "HTTP_PRESENCE_CHECK"
        else:
            new_status = "STILL_VISIBLE"
            evidence_type = "HTTP_PRESENCE_CHECK"

        cursor.execute("""
            UPDATE remediation_actions
            SET status = ?, notes = ?, updated_at = ?
            WHERE exposure_id = ?
        """, (new_status, outcome.evidence_notes, outcome.verified_at, exposure_id))

    elif outcome.outcome == "VERIFIED_ABSENT":
        evidence_type = "HTTP_ABSENCE_CHECK"
        if current_status in (
            "SUBMITTED", "ACKNOWLEDGED", "AWAITING_VERIFICATION", "PENDING",
            "AWAITING_USER_APPROVAL", "ACTION_AVAILABLE", "REQUEST_PREPARED",
            "STILL_VISIBLE", "REAPPEARED"
        ):
            new_status = "NO_LONGER_VISIBLE_AT_CHECKED_URL"
            cursor.execute("""
                UPDATE remediation_actions
                SET status = ?, verified_at = ?, notes = ?, updated_at = ?
                WHERE exposure_id = ?
            """, (new_status, outcome.verified_at, outcome.evidence_notes, outcome.verified_at, exposure_id))
        elif current_status in ("DISCOVERED", "AWAITING_USER_REVIEW"):
            # Target never contained number or was already dead; reject false-positive rather than claim deletion
            new_status = "REJECTED"
            cursor.execute("""
                UPDATE remediation_actions
                SET status = ?, notes = ?, updated_at = ?
                WHERE exposure_id = ?
            """, (new_status, f"Rejected as false positive: {outcome.evidence_notes}", outcome.verified_at, exposure_id))
        else:
            new_status = current_status
            cursor.execute("""
                UPDATE remediation_actions
                SET verified_at = ?, notes = ?, updated_at = ?
                WHERE exposure_id = ?
            """, (outcome.verified_at, outcome.evidence_notes, outcome.verified_at, exposure_id))

    elif outcome.outcome in ("INACCESSIBLE", "INCONCLUSIVE"):
        evidence_type = "FIREWALL_OR_ERROR_CHECK" if outcome.outcome == "INACCESSIBLE" else "INCONCLUSIVE_VERIFICATION"
        if current_status in ("SUBMITTED", "ACKNOWLEDGED", "AWAITING_VERIFICATION", "PENDING"):
            new_status = "INACCESSIBLE_OR_INCONCLUSIVE"
            cursor.execute("""
                UPDATE remediation_actions
                SET status = ?, notes = ?, updated_at = ?
                WHERE exposure_id = ? AND status != 'SOURCE_CONFIRMED_REMOVAL'
            """, (new_status, outcome.evidence_notes, outcome.verified_at, exposure_id))
        else:
            new_status = current_status
            cursor.execute("""
                UPDATE remediation_actions
                SET notes = ?, updated_at = ?
                WHERE exposure_id = ? AND status != 'SOURCE_CONFIRMED_REMOVAL'
            """, (outcome.evidence_notes, outcome.verified_at, exposure_id))

    elif outcome.outcome == "ARCHIVE_ONLY":
        evidence_type = "ARCHIVE_VERIFICATION"
        new_status = current_status
        cursor.execute("""
            UPDATE remediation_actions
            SET notes = ?, updated_at = ?
            WHERE exposure_id = ?
        """, (outcome.evidence_notes, outcome.verified_at, exposure_id))

    # AUDIT LOG MONOTONICITY: Always insert an immutable forensic audit trail entry
    audit_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO action_audit_log (
            id, action_id, identity_hmac, from_state, to_state, evidence_type, evidence_notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        audit_id,
        action_id,
        identity_hmac,
        current_status,
        new_status,
        evidence_type,
        redact_text(outcome.evidence_notes),
        outcome.verified_at,
    ))

    # Update last_checked_at and evidence_origin on exposures table
    if outcome.outcome == "STILL_PRESENT":
        cursor.execute("""
            UPDATE exposures
            SET last_checked_at = ?, evidence_origin = 'FETCHED_PAGE'
            WHERE id = ?
        """, (outcome.verified_at, exposure_id))
    else:
        cursor.execute("""
            UPDATE exposures
            SET last_checked_at = ?
            WHERE id = ?
        """, (outcome.verified_at, exposure_id))

    conn.commit()
    conn.close()
