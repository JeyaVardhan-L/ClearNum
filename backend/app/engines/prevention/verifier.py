"""Exposure Rescan and Verification Engine.
Performs safe HTTP rescans of known exposure URLs to verify whether personal numbers
have been removed (HTTP 404/410 or content cleared) or remain exposed.
"""

import hashlib
from dataclasses import dataclass
from typing import Optional
from backend.app.core.ssrf import safe_fetch_url, SSRFValidationError
from backend.app.core.database import get_db_connection, utc_now_iso
from backend.app.engines.discovery.normalizer import NormalizedPhone
from backend.app.engines.discovery.matcher import match_phone_in_text


@dataclass
class VerificationOutcome:
    url: str
    status: str  # "CONFIRMED_REMOVED", "STILL_EXPOSED", "UNABLE_TO_VERIFY"
    http_status_code: Optional[int]
    evidence_notes: str
    content_hash: str
    verified_at: str


async def verify_exposure_url(
    exposure_id: str,
    url: str,
    phone: NormalizedPhone,
    update_database: bool = True,
) -> VerificationOutcome:
    """Rescans an exposure URL safely, checks for phone presence, and updates action status."""
    now_iso = utc_now_iso()

    try:
        status_code, content, headers = await safe_fetch_url(url)
    except SSRFValidationError as e:
        return VerificationOutcome(
            url=url,
            status="UNABLE_TO_VERIFY",
            http_status_code=None,
            evidence_notes=f"URL verification blocked by SSRF defense: {e}",
            content_hash="",
            verified_at=now_iso,
        )
    except Exception as e:
        return VerificationOutcome(
            url=url,
            status="UNABLE_TO_VERIFY",
            http_status_code=None,
            evidence_notes=f"Network error during verification rescan: {e}",
            content_hash="",
            verified_at=now_iso,
        )

    content_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()

    # Check for HTTP 404 (Not Found) or 410 (Gone)
    if status_code in (404, 410):
        outcome = VerificationOutcome(
            url=url,
            status="CONFIRMED_REMOVED",
            http_status_code=status_code,
            evidence_notes=f"Confirmed removal: Server returned HTTP {status_code} (Resource Deleted/Gone).",
            content_hash=content_hash,
            verified_at=now_iso,
        )
    elif status_code == 200:
        # Page is accessible: check if phone number is still present
        match_res = match_phone_in_text(content, phone)
        if match_res.matched:
            outcome = VerificationOutcome(
                url=url,
                status="STILL_EXPOSED",
                http_status_code=200,
                evidence_notes=f"Still exposed: Found match ({match_res.match_type}): '{match_res.snippet}'",
                content_hash=content_hash,
                verified_at=now_iso,
            )
        else:
            outcome = VerificationOutcome(
                url=url,
                status="CONFIRMED_REMOVED",
                http_status_code=200,
                evidence_notes="Confirmed removal: Webpage is live, but target telephone number is no longer present.",
                content_hash=content_hash,
                verified_at=now_iso,
            )
    elif status_code in (403, 429, 503):
        outcome = VerificationOutcome(
            url=url,
            status="UNABLE_TO_VERIFY",
            http_status_code=status_code,
            evidence_notes=f"Automated verification challenged by anti-bot firewall (HTTP {status_code}). Manual inspection required.",
            content_hash=content_hash,
            verified_at=now_iso,
        )
    else:
        outcome = VerificationOutcome(
            url=url,
            status="UNABLE_TO_VERIFY",
            http_status_code=status_code,
            evidence_notes=f"Ambiguous response code HTTP {status_code}.",
            content_hash=content_hash,
            verified_at=now_iso,
        )

    if update_database:
        _update_remediation_action_record(exposure_id, outcome)

    return outcome


def _update_remediation_action_record(exposure_id: str, outcome: VerificationOutcome) -> None:
    """Updates the remediation_actions table with the verification outcome."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if outcome.status == "CONFIRMED_REMOVED":
        new_status = "VERIFIED_REMOVED"
        cursor.execute("""
            UPDATE remediation_actions
            SET status = ?, verified_at = ?, notes = ?, updated_at = ?
            WHERE exposure_id = ?
        """, (new_status, outcome.verified_at, outcome.evidence_notes, outcome.verified_at, exposure_id))
    elif outcome.status == "UNABLE_TO_VERIFY":
        new_status = "UNABLE_TO_VERIFY"
        cursor.execute("""
            UPDATE remediation_actions
            SET status = ?, notes = ?, updated_at = ?
            WHERE exposure_id = ? AND status != 'VERIFIED_REMOVED'
        """, (new_status, outcome.evidence_notes, outcome.verified_at, exposure_id))
    elif outcome.status == "STILL_EXPOSED":
        cursor.execute("""
            UPDATE remediation_actions
            SET notes = ?, updated_at = ?
            WHERE exposure_id = ? AND status != 'VERIFIED_REMOVED'
        """, (outcome.evidence_notes, outcome.verified_at, exposure_id))

    # Update last_checked_at on exposure
    cursor.execute("""
        UPDATE exposures
        SET last_checked_at = ?
        WHERE id = ?
    """, (outcome.verified_at, exposure_id))

    conn.commit()
    conn.close()
