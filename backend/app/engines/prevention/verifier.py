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
            status="NO_LONGER_VISIBLE_AT_CHECKED_URL",
            http_status_code=status_code,
            evidence_notes=f"No longer visible: Target server returned HTTP {status_code} (Resource Deleted/Gone). Does not confirm underlying database deletion until source confirms.",
            content_hash=content_hash,
            verified_at=now_iso,
        )
    elif status_code == 200:
        # Page is accessible: check if phone number is still present
        match_res = match_phone_in_text(content, phone)
        if match_res.matched:
            outcome = VerificationOutcome(
                url=url,
                status="STILL_VISIBLE",
                http_status_code=200,
                evidence_notes=f"Still visible: Found match ({match_res.match_type}): '{match_res.snippet}'",
                content_hash=content_hash,
                verified_at=now_iso,
            )
        else:
            outcome = VerificationOutcome(
                url=url,
                status="NO_LONGER_VISIBLE_AT_CHECKED_URL",
                http_status_code=200,
                evidence_notes="No longer visible: Webpage returned HTTP 200, but telephone number is absent from response. Underlying database deletion unconfirmed.",
                content_hash=content_hash,
                verified_at=now_iso,
            )
    elif status_code in (403, 429, 503):
        outcome = VerificationOutcome(
            url=url,
            status="INACCESSIBLE_OR_INCONCLUSIVE",
            http_status_code=status_code,
            evidence_notes=f"Verification challenged by anti-bot firewall or rate-limit (HTTP {status_code}). Manual inspection required.",
            content_hash=content_hash,
            verified_at=now_iso,
        )
    else:
        outcome = VerificationOutcome(
            url=url,
            status="INACCESSIBLE_OR_INCONCLUSIVE",
            http_status_code=status_code,
            evidence_notes=f"Inconclusive response code HTTP {status_code}.",
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

    cursor.execute("SELECT status FROM remediation_actions WHERE exposure_id = ?", (exposure_id,))
    act_row = cursor.fetchone()
    current_status = act_row["status"] if act_row else "DISCOVERED"

    if outcome.status == "NO_LONGER_VISIBLE_AT_CHECKED_URL":
        if current_status in ("SUBMITTED", "ACKNOWLEDGED", "AWAITING_VERIFICATION", "PENDING", "AWAITING_USER_APPROVAL", "ACTION_AVAILABLE"):
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
            cursor.execute("""
                UPDATE remediation_actions
                SET notes = ?, updated_at = ?
                WHERE exposure_id = ?
            """, (outcome.evidence_notes, outcome.verified_at, exposure_id))

    elif outcome.status == "INACCESSIBLE_OR_INCONCLUSIVE":
        if current_status in ("SUBMITTED", "ACKNOWLEDGED", "AWAITING_VERIFICATION", "PENDING"):
            new_status = "INACCESSIBLE_OR_INCONCLUSIVE"
            cursor.execute("""
                UPDATE remediation_actions
                SET status = ?, notes = ?, updated_at = ?
                WHERE exposure_id = ? AND status != 'SOURCE_CONFIRMED_REMOVAL'
            """, (new_status, outcome.evidence_notes, outcome.verified_at, exposure_id))
        else:
            cursor.execute("""
                UPDATE remediation_actions
                SET notes = ?, updated_at = ?
                WHERE exposure_id = ? AND status != 'SOURCE_CONFIRMED_REMOVAL'
            """, (outcome.evidence_notes, outcome.verified_at, exposure_id))

    elif outcome.status == "STILL_VISIBLE":
        if current_status in ("DISCOVERED", "AWAITING_USER_REVIEW"):
            # Live scan confirmed telephone number presence on page: upgrade to CONFIRMED_EXPOSURE
            cursor.execute("""
                UPDATE remediation_actions
                SET status = 'CONFIRMED_EXPOSURE', notes = ?, updated_at = ?
                WHERE exposure_id = ?
            """, (outcome.evidence_notes, outcome.verified_at, exposure_id))
        else:
            # If was previously NO_LONGER_VISIBLE, mark as REAPPEARED!
            if current_status in ("NO_LONGER_VISIBLE_AT_CHECKED_URL", "VERIFIED_REMOVED"):
                new_status = "REAPPEARED"
            else:
                new_status = "STILL_VISIBLE"
            cursor.execute("""
                UPDATE remediation_actions
                SET status = ?, notes = ?, updated_at = ?
                WHERE exposure_id = ? AND status != 'SOURCE_CONFIRMED_REMOVAL'
            """, (new_status, outcome.evidence_notes, outcome.verified_at, exposure_id))

    # Update last_checked_at on exposure
    cursor.execute("""
        UPDATE exposures
        SET last_checked_at = ?
        WHERE id = ?
    """, (outcome.verified_at, exposure_id))

    conn.commit()
    conn.close()
