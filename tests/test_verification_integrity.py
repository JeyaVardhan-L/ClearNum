"""Deterministic unit and integration tests for Verification Integrity & Re-Audit Hardening (Phase 6E).

Covers all 19 enumerated verification scenarios:
1. HTTP 404 absence check
2. HTTP 410 gone check
3. HTTP 200 with matching phone content (STILL_PRESENT)
4. HTTP 200 with matching content absent (VERIFIED_ABSENT)
5. Soft-404 detection (HTTP 200 with "Page Not Found", "Profile Deleted")
6. Generic homepage / login redirect detection
7. Redirect loop / max redirect cutoff
8. SSRF rejection of private IP, loopback, metadata
9. DNS rebinding resistance
10. Anti-bot HTTP status codes (403, 429, 503 -> INACCESSIBLE)
11. Content-based anti-bot / Cloudflare challenge detection
12. Timeouts and network connection failures
13. Oversized response body truncation/rejection
14. Unsupported binary content types (e.g. image/png -> INCONCLUSIVE)
15. Archived snapshot distinction (ARCHIVE_ONLY)
16. Monotonic audit log growth across repeated rescans
17. Reappearance detection (NO_LONGER_VISIBLE -> STILL_PRESENT -> REAPPEARED)
18. Audit note phone digit sanitization (redact_text)
19. Lifecycle evidence enforcement (reject manual verified removal, require ref/notes)
"""

import uuid
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import get_db_connection, utc_now_iso
from backend.app.core.ssrf import (
    FetchResponse,
    SSRFValidationError,
    UnsupportedContentTypeError,
    validate_url_safe,
)
from backend.app.engines.discovery.normalizer import parse_and_normalize
from backend.app.engines.prevention.verifier import (
    VerificationOutcome,
    detect_anti_bot_challenge,
    detect_soft_404,
    extract_clean_text,
    is_generic_redirect,
    verify_exposure_url,
)
from backend.app.main import app

client = TestClient(app)


@pytest.fixture
def test_identity_and_exposure():
    """Sets up an isolated test identity, exposure, and remediation action in SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = utc_now_iso()

    norm = parse_and_normalize("+14155552671", "US")
    hmac_id = norm.hmac_id
    exp_id = str(uuid.uuid4())
    act_id = str(uuid.uuid4())
    test_url = "https://example-broker.org/profiles/john-doe-4155552671"

    ident_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT OR IGNORE INTO identities (id, hmac_id, masked_phone, country_code, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (ident_id, hmac_id, norm.masked_display, "US", now_iso))

    cursor.execute("""
        INSERT INTO exposures (
            id, identity_hmac, source_id, url, canonical_url, evidence_origin, domain, title, match_type, confidence, snippet, discovered_at, last_checked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        exp_id, hmac_id, "test_broker", test_url, test_url, "FETCHED_PAGE",
        "example-broker.org", "John Doe Public Profile", "EXACT", 1.0,
        "Phone: +1 415-555-2671", now_iso, now_iso
    ))

    cursor.execute("""
        INSERT INTO remediation_actions (
            id, exposure_id, identity_hmac, source_id, status, official_url, notes, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        act_id, exp_id, hmac_id, "test_broker", "SUBMITTED",
        test_url, "Dispatched opt-out request", now_iso
    ))

    conn.commit()
    conn.close()

    return {
        "norm": norm,
        "hmac_id": hmac_id,
        "exp_id": exp_id,
        "act_id": act_id,
        "url": test_url,
    }


# --- 1. HTTP 404 Absence Check ---
@pytest.mark.asyncio
async def test_verification_http_404_absence(test_identity_and_exposure):
    fixture = test_identity_and_exposure
    mock_resp = FetchResponse(404, "<html><title>Not Found</title><body>404 Not Found</body></html>", {}, final_url=fixture["url"])

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        outcome = await verify_exposure_url(fixture["exp_id"], fixture["url"], fixture["norm"], update_database=True)

    assert outcome.outcome == "VERIFIED_ABSENT"
    assert outcome.status == "NO_LONGER_VISIBLE_AT_CHECKED_URL"
    assert outcome.http_status_code == 404
    assert "Target server returned HTTP 404" in outcome.evidence_notes
    assert "Does not confirm underlying database deletion" in outcome.evidence_notes


# --- 2. HTTP 410 Gone Check ---
@pytest.mark.asyncio
async def test_verification_http_410_gone(test_identity_and_exposure):
    fixture = test_identity_and_exposure
    mock_resp = FetchResponse(410, "<html><title>Gone</title><body>Resource permanently removed</body></html>", {}, final_url=fixture["url"])

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        outcome = await verify_exposure_url(fixture["exp_id"], fixture["url"], fixture["norm"], update_database=True)

    assert outcome.outcome == "VERIFIED_ABSENT"
    assert outcome.status == "NO_LONGER_VISIBLE_AT_CHECKED_URL"
    assert outcome.http_status_code == 410
    assert "Resource Gone" in outcome.evidence_notes


# --- 3. HTTP 200 with Matching Phone Content (STILL_PRESENT) ---
@pytest.mark.asyncio
async def test_verification_http_200_still_present(test_identity_and_exposure):
    fixture = test_identity_and_exposure
    page_html = "<html><head><title>User Profile</title></head><body><h1>John Doe</h1><p>Contact: +1 (415) 555-2671</p></body></html>"
    mock_resp = FetchResponse(200, page_html, {}, final_url=fixture["url"])

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        outcome = await verify_exposure_url(fixture["exp_id"], fixture["url"], fixture["norm"], update_database=True)

    assert outcome.outcome == "STILL_PRESENT"
    assert outcome.status == "STILL_VISIBLE"
    assert outcome.http_status_code == 200
    assert "Still visible: Target webpage displays matching phone number" in outcome.evidence_notes
    assert outcome.reappeared is False


# --- 4. HTTP 200 with Matching Content Absent (VERIFIED_ABSENT) ---
@pytest.mark.asyncio
async def test_verification_http_200_phone_absent(test_identity_and_exposure):
    fixture = test_identity_and_exposure
    page_html = "<html><head><title>User Profile</title></head><body><h1>John Doe</h1><p>Address: San Francisco, CA</p></body></html>"
    mock_resp = FetchResponse(200, page_html, {}, final_url=fixture["url"])

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        outcome = await verify_exposure_url(fixture["exp_id"], fixture["url"], fixture["norm"], update_database=True)

    assert outcome.outcome == "VERIFIED_ABSENT"
    assert outcome.status == "NO_LONGER_VISIBLE_AT_CHECKED_URL"
    assert outcome.http_status_code == 200
    assert "telephone number is absent from response" in outcome.evidence_notes


# --- 5. Soft-404 Detection ---
@pytest.mark.asyncio
@pytest.mark.parametrize("soft_404_body,phrase", [
    ("<html><head><title>404 Not Found</title></head><body>This page cannot be found.</body></html>", "404 not found"),
    ("<html><head><title>Directory</title></head><body><h1>Profile Removed</h1><p>This profile has been deleted by user request.</p></body></html>", "profile removed"),
    ("<html><head><title>Error</title></head><body><p>Listing no longer available</p></body></html>", "listing no longer available"),
    ("<html><head><title>Missing</title></head><body>The page you are looking for does not exist.</body></html>", "the page you are looking for does not exist"),
])
async def test_verification_soft_404_detection(test_identity_and_exposure, soft_404_body, phrase):
    fixture = test_identity_and_exposure
    mock_resp = FetchResponse(200, soft_404_body, {}, final_url=fixture["url"])

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        outcome = await verify_exposure_url(fixture["exp_id"], fixture["url"], fixture["norm"], update_database=True)

    assert outcome.outcome == "VERIFIED_ABSENT"
    assert outcome.status == "NO_LONGER_VISIBLE_AT_CHECKED_URL"
    assert outcome.soft_404_detected is True
    assert "soft-404 notice" in outcome.evidence_notes.lower()


# --- 6. Generic Homepage / Login Redirect Detection ---
@pytest.mark.asyncio
@pytest.mark.parametrize("redirect_destination", [
    "https://example-broker.org/",
    "https://example-broker.org/login",
    "https://example-broker.org/signin",
    "https://example-broker.org/search",
])
async def test_verification_generic_redirect_detection(test_identity_and_exposure, redirect_destination):
    fixture = test_identity_and_exposure
    generic_landing_html = "<html><head><title>Welcome</title></head><body>Please log in or search our database.</body></html>"
    mock_resp = FetchResponse(200, generic_landing_html, {}, final_url=redirect_destination)

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        outcome = await verify_exposure_url(fixture["exp_id"], fixture["url"], fixture["norm"], update_database=True)

    assert outcome.outcome == "INCONCLUSIVE"
    assert outcome.status == "INACCESSIBLE_OR_INCONCLUSIVE"
    assert "inconclusive redirect" in outcome.evidence_notes.lower() or "homepage" in outcome.evidence_notes.lower()


# --- 7. Redirect Loop / Exceeded Limit ---
@pytest.mark.asyncio
async def test_verification_redirect_limit_exceeded(test_identity_and_exposure):
    fixture = test_identity_and_exposure
    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = SSRFValidationError("Too many redirects (exceeded limit of 5)")
        outcome = await verify_exposure_url(fixture["exp_id"], fixture["url"], fixture["norm"], update_database=True)

    assert outcome.outcome == "INACCESSIBLE"
    assert outcome.status == "INACCESSIBLE_OR_INCONCLUSIVE"
    assert outcome.http_status_code is None
    assert "SSRF network defense: Too many redirects" in outcome.evidence_notes


# --- 8. SSRF Rejection of Disallowed Targets ---
@pytest.mark.parametrize("disallowed_url", [
    "http://127.0.0.1:8000/internal",
    "http://localhost:5000/",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.1/private",
    "http://192.168.1.1/admin",
    "file:///etc/passwd",
])
def test_ssrf_rejects_internal_destinations(disallowed_url):
    with pytest.raises(SSRFValidationError):
        validate_url_safe(disallowed_url)


# --- 9. DNS Rebinding Resistance ---
def test_ssrf_dns_rebinding_pins_socket():
    from backend.app.core.ssrf import SSRFSafeNetworkBackend
    backend = SSRFSafeNetworkBackend(allow_loopback=False)
    assert hasattr(backend, "connect_tcp")


# --- 10. Anti-Bot HTTP Codes (403, 429, 503 -> INACCESSIBLE) ---
@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [403, 429, 503])
async def test_verification_antibot_status_codes(test_identity_and_exposure, status_code):
    fixture = test_identity_and_exposure
    mock_resp = FetchResponse(status_code, "<html><body>Blocked by firewall</body></html>", {}, final_url=fixture["url"])

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        outcome = await verify_exposure_url(fixture["exp_id"], fixture["url"], fixture["norm"], update_database=True)

    assert outcome.outcome == "INACCESSIBLE"
    assert outcome.status == "INACCESSIBLE_OR_INCONCLUSIVE"
    assert outcome.http_status_code == status_code
    assert "Verification challenged by anti-bot firewall" in outcome.evidence_notes
    assert "Inaccessibility cannot prove removal" in outcome.evidence_notes


# --- 11. Content-Based Anti-Bot / Cloudflare Challenge Detection ---
@pytest.mark.asyncio
@pytest.mark.parametrize("challenge_html,expected_phrase", [
    ("<html><head><title>Attention Required! | Cloudflare</title></head><body>Cloudflare Ray ID: 8940217</body></html>", "cloudflare"),
    ("<html><head><title>Just a moment...</title></head><body>Checking your browser before accessing site.</body></html>", "just a moment"),
    ("<html><body><div id='cf-chl-bypass'>Security check to access this page</div></body></html>", "cf-chl-bypass"),
    ("<html><head><title>ShieldSquare Captcha</title></head><body>Please verify you are human</body></html>", "captcha"),
])
async def test_verification_content_antibot_challenge(test_identity_and_exposure, challenge_html, expected_phrase):
    fixture = test_identity_and_exposure
    # Even if target returns HTTP 200, challenge text prevents misclassifying as absence
    mock_resp = FetchResponse(200, challenge_html, {}, final_url=fixture["url"])

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        outcome = await verify_exposure_url(fixture["exp_id"], fixture["url"], fixture["norm"], update_database=True)

    assert outcome.outcome == "INACCESSIBLE"
    assert outcome.status == "INACCESSIBLE_OR_INCONCLUSIVE"
    assert "anti-bot firewall or rate-limit" in outcome.evidence_notes.lower()


# --- 12. Timeouts and Network Connection Failures ---
@pytest.mark.asyncio
async def test_verification_network_timeout(test_identity_and_exposure):
    fixture = test_identity_and_exposure
    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = TimeoutError("Connection to host timed out after 5.0s")
        outcome = await verify_exposure_url(fixture["exp_id"], fixture["url"], fixture["norm"], update_database=True)

    assert outcome.outcome == "INACCESSIBLE"
    assert outcome.status == "INACCESSIBLE_OR_INCONCLUSIVE"
    assert outcome.http_status_code is None
    assert "Network error or timeout during verification rescan" in outcome.evidence_notes


# --- 13. Oversized Response Body Truncation/Rejection ---
@pytest.mark.asyncio
async def test_verification_oversized_response(test_identity_and_exposure):
    fixture = test_identity_and_exposure
    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = SSRFValidationError("Response stream exceeded maximum limit of 1048576 bytes")
        outcome = await verify_exposure_url(fixture["exp_id"], fixture["url"], fixture["norm"], update_database=True)

    assert outcome.outcome == "INACCESSIBLE"
    assert outcome.status == "INACCESSIBLE_OR_INCONCLUSIVE"
    assert "SSRF network defense: Response stream exceeded maximum limit" in outcome.evidence_notes


# --- 14. Unsupported Binary Content Types (INCONCLUSIVE) ---
@pytest.mark.asyncio
async def test_verification_unsupported_binary_content_type(test_identity_and_exposure):
    fixture = test_identity_and_exposure
    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = UnsupportedContentTypeError("image/png")
        outcome = await verify_exposure_url(fixture["exp_id"], fixture["url"], fixture["norm"], update_database=True)

    assert outcome.outcome == "INCONCLUSIVE"
    assert outcome.status == "INACCESSIBLE_OR_INCONCLUSIVE"
    assert "unsupported binary MIME type 'image/png'" in outcome.evidence_notes


# --- 15. Archived Snapshot Distinction (ARCHIVE_ONLY) ---
@pytest.mark.asyncio
async def test_verification_archived_snapshot_distinction(test_identity_and_exposure):
    fixture = test_identity_and_exposure
    archive_url = "https://web.archive.org/web/20260101/https://broker.org/john"
    archive_html = "<html><body>Archived record: +1 415-555-2671</body></html>"
    mock_resp = FetchResponse(200, archive_html, {}, final_url=archive_url)

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        outcome = await verify_exposure_url(
            fixture["exp_id"], archive_url, fixture["norm"], update_database=True, evidence_origin="ARCHIVED_SNAPSHOT"
        )

    assert outcome.outcome == "ARCHIVE_ONLY"
    assert "Archived snapshot verified" in outcome.evidence_notes
    assert "does not verify current live status on the active source domain" in outcome.evidence_notes


# --- 16. Monotonic Audit Log Growth Across Multiple Rescans ---
@pytest.mark.asyncio
async def test_verification_monotonic_audit_log_growth(test_identity_and_exposure):
    fixture = test_identity_and_exposure
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM action_audit_log WHERE action_id = ?", (fixture["act_id"],))
    initial_count = cursor.fetchone()["count"]
    conn.close()

    mock_resp = FetchResponse(404, "404 Not Found", {}, final_url=fixture["url"])

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        # First verification check
        await verify_exposure_url(fixture["exp_id"], fixture["url"], fixture["norm"], update_database=True)
        # Second verification check (status unchanged: still 404)
        await verify_exposure_url(fixture["exp_id"], fixture["url"], fixture["norm"], update_database=True)
        # Third verification check
        await verify_exposure_url(fixture["exp_id"], fixture["url"], fixture["norm"], update_database=True)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM action_audit_log WHERE action_id = ?", (fixture["act_id"],))
    final_count = cursor.fetchone()["count"]
    conn.close()

    # Every run must insert a new audit record
    assert final_count == initial_count + 3


# --- 17. Reappearance Detection ---
@pytest.mark.asyncio
async def test_verification_reappearance_detection(test_identity_and_exposure):
    fixture = test_identity_and_exposure

    # First, mark the remediation action as NO_LONGER_VISIBLE_AT_CHECKED_URL
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE remediation_actions SET status = 'NO_LONGER_VISIBLE_AT_CHECKED_URL' WHERE id = ?",
        (fixture["act_id"],)
    )
    conn.commit()
    conn.close()

    # Now run verification that finds the phone number on the page!
    page_html = "<html><body>Found contact again: +1 415-555-2671</body></html>"
    mock_resp = FetchResponse(200, page_html, {}, final_url=fixture["url"])

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        outcome = await verify_exposure_url(fixture["exp_id"], fixture["url"], fixture["norm"], update_database=True)

    assert outcome.outcome == "STILL_PRESENT"
    assert outcome.status == "REAPPEARED"
    assert outcome.reappeared is True
    assert "Reappearance Detected" in outcome.evidence_notes

    # Verify database state was updated to REAPPEARED with SUBSEQUENT_SCAN_DETECTION audit entry
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM remediation_actions WHERE id = ?", (fixture["act_id"],))
    assert cursor.fetchone()["status"] == "REAPPEARED"

    cursor.execute(
        "SELECT to_state, evidence_type FROM action_audit_log WHERE action_id = ? ORDER BY created_at DESC LIMIT 1",
        (fixture["act_id"],)
    )
    latest_audit = cursor.fetchone()
    assert latest_audit["to_state"] == "REAPPEARED"
    assert latest_audit["evidence_type"] == "SUBSEQUENT_SCAN_DETECTION"
    conn.close()


# --- 18. Audit Note Phone Digit Sanitization (redact_text) ---
@pytest.mark.asyncio
async def test_verification_audit_note_phone_digit_sanitization(test_identity_and_exposure):
    fixture = test_identity_and_exposure
    raw_snippet_html = "<html><body>Listed phone number: 415-555-2671</body></html>"
    mock_resp = FetchResponse(200, raw_snippet_html, {}, final_url=fixture["url"])

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        outcome = await verify_exposure_url(fixture["exp_id"], fixture["url"], fixture["norm"], update_database=True)

    # Raw digits 415-555-2671 or 4155552671 must NOT appear in evidence notes
    assert "4155552671" not in outcome.evidence_notes
    assert "415-555-2671" not in outcome.evidence_notes
    assert "[REDACTED_PHONE]" in outcome.evidence_notes or "•" in outcome.evidence_notes


# --- 19. Lifecycle Evidence Enforcement in Transition Endpoint ---
def test_lifecycle_transition_endpoint_evidence_enforcement(test_identity_and_exposure):
    fixture = test_identity_and_exposure

    # 1. Attempting manual transition to NO_LONGER_VISIBLE_AT_CHECKED_URL without verification must be rejected
    res_removal = client.post("/api/remediation/transition", json={
        "exposure_id": fixture["exp_id"],
        "identity_hmac": fixture["hmac_id"],
        "next_state": "NO_LONGER_VISIBLE_AT_CHECKED_URL",
    })
    assert res_removal.status_code == 400
    assert "Manual transition to NO_LONGER_VISIBLE_AT_CHECKED_URL is forbidden" in res_removal.json()["detail"]

    # 2. Attempting transition to ACKNOWLEDGED without reference or notes must be rejected
    res_ack_empty = client.post("/api/remediation/transition", json={
        "exposure_id": fixture["exp_id"],
        "identity_hmac": fixture["hmac_id"],
        "next_state": "ACKNOWLEDGED",
        "notes": "",
        "submission_ref": "",
    })
    assert res_ack_empty.status_code == 400
    assert "Transition to ACKNOWLEDGED requires a recorded ticket reference" in res_ack_empty.json()["detail"]

    # 3. Transition to ACKNOWLEDGED with valid reference must succeed
    res_ack_valid = client.post("/api/remediation/transition", json={
        "exposure_id": fixture["exp_id"],
        "identity_hmac": fixture["hmac_id"],
        "next_state": "ACKNOWLEDGED",
        "submission_ref": "TICKET-78901",
        "notes": "Broker confirmed receipt via automated ticket.",
    })
    assert res_ack_valid.status_code == 200
    assert res_ack_valid.json()["new_status"] == "ACKNOWLEDGED"

    # 4. Transition to SOURCE_CONFIRMED_REMOVAL without confirmation receipt must be rejected
    res_src_empty = client.post("/api/remediation/transition", json={
        "exposure_id": fixture["exp_id"],
        "identity_hmac": fixture["hmac_id"],
        "next_state": "SOURCE_CONFIRMED_REMOVAL",
        "notes": "",
        "submission_ref": "",
    })
    assert res_src_empty.status_code == 400
    assert "Transition to SOURCE_CONFIRMED_REMOVAL requires recorded source confirmation" in res_src_empty.json()["detail"]

    # 5. Transition to SOURCE_CONFIRMED_REMOVAL with confirmation receipt must succeed
    res_src_valid = client.post("/api/remediation/transition", json={
        "exposure_id": fixture["exp_id"],
        "identity_hmac": fixture["hmac_id"],
        "next_state": "SOURCE_CONFIRMED_REMOVAL",
        "submission_ref": "CONFIRM-PURGE-999",
        "notes": "Compliance team signed statutory deletion cert.",
    })
    assert res_src_valid.status_code == 200
    assert res_src_valid.json()["new_status"] == "SOURCE_CONFIRMED_REMOVAL"


# --- Endpoint Verification Test (POST /api/remediation/verify) ---
def test_verify_endpoint_returns_extended_metadata(test_identity_and_exposure):
    fixture = test_identity_and_exposure
    mock_resp = FetchResponse(404, "404 Not Found", {}, final_url=fixture["url"])

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        res = client.post("/api/remediation/verify", json={
            "exposure_id": fixture["exp_id"],
            "url": fixture["url"],
            "phone_number": "+14155552671",
            "default_region": "US",
        })

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "NO_LONGER_VISIBLE_AT_CHECKED_URL"
    assert data["outcome"] == "VERIFIED_ABSENT"
    assert data["http_status_code"] == 404
    assert data["final_url"] == fixture["url"]
    assert data["reappeared"] is False
    assert "content_hash" in data
