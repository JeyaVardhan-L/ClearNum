"""Regression tests for Phase 7: Guided End-to-End Discovery Experience.

Validates:
1. Local MBOX file analysis creates actionable exposures and subscriptions.
2. Local SMS backup file analysis creates actionable exposures for commercial senders.
3. Finding details, match classifications (CONFIRMED_MATCH, POSSIBLE_MATCH, INCIDENTAL_MENTION), and evidence origin metadata.
4. End-to-end finding lifecycle: Finding -> Prepare Notice -> Record Submission -> History Timeline -> Live Re-check.
5. External search consent boundary enforcement.
"""

import io
import uuid
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import get_db_connection, utc_now_iso
from backend.app.engines.discovery.normalizer import parse_and_normalize
from backend.app.main import app

client = TestClient(app)


@pytest.fixture
def clean_synthetic_identity():
    """Sets up a clean synthetic test identity."""
    norm = parse_and_normalize("+14155552671", "US")
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = utc_now_iso()

    cursor.execute("""
        INSERT INTO identities (id, hmac_id, masked_phone, country_code, carrier_name, line_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(hmac_id) DO NOTHING
    """, (
        str(uuid.uuid4()),
        norm.hmac_id,
        norm.masked_display,
        str(norm.country_code),
        norm.carrier_name,
        norm.line_type,
        now_iso,
    ))
    conn.commit()

    yield norm

    # Clean up test records
    cursor.execute("DELETE FROM exposures WHERE identity_hmac = ?", (norm.hmac_id,))
    cursor.execute("DELETE FROM remediation_actions WHERE identity_hmac = ?", (norm.hmac_id,))
    cursor.execute("DELETE FROM subscriptions WHERE identity_hmac = ?", (norm.hmac_id,))
    cursor.execute("DELETE FROM identities WHERE hmac_id = ?", (norm.hmac_id,))
    conn.commit()
    conn.close()


def test_local_mbox_analysis_creates_exposures(clean_synthetic_identity):
    """Workflow 3 & 4: Uploading an MBOX email archive creates actionable exposures."""
    norm = clean_synthetic_identity

    mbox_content = b"""From MAILER-DAEMON Fri Oct 30 12:00:00 2026
From: alerts@spambroker.com
To: user@example.com
Subject: Notice regarding +14155552671
List-Unsubscribe: <https://spambroker.com/unsubscribe?token=abc999>

Hello, your telephone +1 415-555-2671 is listed on our public directory. Click here to unsubscribe.
"""

    response = client.post(
        "/api/import/mbox",
        files={"file": ("test_export.mbox", io.BytesIO(mbox_content), "application/mbox")},
        data={"identity_hmac": norm.hmac_id, "phone_number": norm.e164, "default_region": "US"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["success"] is True
    assert data["discovered_subscriptions_count"] == 1
    assert data["exposures_created"] >= 1

    # Verify exposure in database
    exp_res = client.get(f"/api/discovery/exposures?identity_hmac={norm.hmac_id}")
    assert exp_res.status_code == 200
    exposures = exp_res.json()
    assert len(exposures) >= 1

    finding = next((e for e in exposures if "spambroker.com" in e["url"]), None)
    assert finding is not None
    assert finding["evidence_origin"] == "FETCHED_PAGE"
    assert finding["match_type"] == "EXACT"
    assert finding["match_classification"] == "CONFIRMED_MATCH"
    assert finding["confidence"] >= 0.95
    assert finding["remediation_status"] == "ACTION_AVAILABLE"
    assert "+1 415-555-2671" in finding["snippet"]


def test_local_sms_backup_analysis_creates_exposures(clean_synthetic_identity):
    """Workflow 3 & 4: Uploading SMS backup XML creates actionable exposures."""
    norm = clean_synthetic_identity

    sms_xml = b"""<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<smses count="1">
  <sms protocol="0" address="VM-HDFCBK" date="1600000000000" type="1" subject="null" body="Pre-approved personal loan of Rs 5 Lakhs available now. Special low interest rate. Visit hdfcbank.com to apply." toa="null" sc_toa="null" service_center="null" read="1" status="-1" locked="0" date_sent="0" sub_id="1" readable_date="1 Jan 2026" contact_name="Unknown" />
</smses>"""

    response = client.post(
        "/api/import/sms",
        files={"file": ("sms_backup.xml", io.BytesIO(sms_xml), "text/xml")},
        data={"identity_hmac": norm.hmac_id, "phone_number": norm.e164, "default_region": "IN"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["success"] is True
    assert data["senders_count"] == 1
    assert data["exposures_created"] == 1

    # Verify exposure in database
    exp_res = client.get(f"/api/discovery/exposures?identity_hmac={norm.hmac_id}")
    assert exp_res.status_code == 200
    exposures = exp_res.json()

    sms_finding = next((e for e in exposures if "hdfcbk" in e["domain"] or "hdfcbk" in e["url"]), None)
    assert sms_finding is not None
    assert sms_finding["evidence_origin"] in ("FETCHED_PAGE", "LOCAL_SMS_BACKUP")
    assert sms_finding["match_type"] == "EXACT"
    assert sms_finding["remediation_status"] == "ACTION_AVAILABLE"


def test_end_to_end_remediation_workflow(clean_synthetic_identity):
    """Workflow 5 to 10: Finding details -> prepare -> submit -> history -> live verify."""
    norm = clean_synthetic_identity
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = utc_now_iso()

    # Create synthetic exposure
    exp_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO exposures (
            id, identity_hmac, source_id, url, canonical_url, evidence_origin,
            domain, title, match_type, confidence, snippet, discovered_at, last_checked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        exp_id,
        norm.hmac_id,
        "generic_web",
        "https://example.com/directory/profile",
        "https://example.com/directory/profile",
        "FETCHED_PAGE",
        "example.com",
        "Directory Profile",
        "EXACT",
        0.98,
        "Contact phone: +1 415 555 2671",
        now_iso,
        now_iso,
    ))

    action_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO remediation_actions (
            id, exposure_id, identity_hmac, source_id, status, official_url, notes, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        action_id,
        exp_id,
        norm.hmac_id,
        "generic_web",
        "DISCOVERED",
        "https://example.com/optout",
        "Initial discovery",
        now_iso,
    ))
    conn.commit()
    conn.close()

    # Step 5: Inspect finding details
    exp_res = client.get(f"/api/discovery/exposures?identity_hmac={norm.hmac_id}")
    assert exp_res.status_code == 200
    exps = exp_res.json()
    finding = next((e for e in exps if e["id"] == exp_id), None)
    assert finding is not None
    assert finding["match_classification"] == "CONFIRMED_MATCH"

    # Step 6: Prepare statutory removal request
    prep_res = client.post(
        "/api/remediation/prepare",
        json={
            "exposure_id": exp_id,
            "identity_hmac": norm.hmac_id,
            "request_type": "CCPA_DELETE",
            "submission_channel": "WEB_FORM",
            "statutory_basis": "STATUTORY",
            "expected_days": 45,
            "notes": "Generated CCPA deletion notice",
        },
    )
    assert prep_res.status_code == 200, prep_res.text
    prep_data = prep_res.json()
    assert prep_data["status"] == "REQUEST_PREPARED"

    # Step 7: Record simulated submission
    sub_res = client.post(
        "/api/remediation/submit",
        json={
            "exposure_id": exp_id,
            "identity_hmac": norm.hmac_id,
            "submission_channel": "WEB_FORM",
            "submission_ref": "OPT-77291",
            "notes": "Submitted via company webform",
        },
    )
    assert sub_res.status_code == 200, sub_res.text
    sub_data = sub_res.json()
    assert sub_data["status"] in ("SUBMITTED", "REQUEST_SUBMITTED")

    # Step 8: View history timeline
    hist_res = client.get(f"/api/remediation/history/{exp_id}?identity_hmac={norm.hmac_id}")
    assert hist_res.status_code == 200, hist_res.text
    hist = hist_res.json()
    assert hist["submission_ref"] == "OPT-77291"
    assert len(hist["events"]) >= 2  # PREPARED and SUBMITTED events

    # Step 9 & 10: Run local controlled URL verification (simulate 404 absence)
    with patch("backend.app.api.routes.verify_exposure_url", new_callable=AsyncMock) as mock_verify:
        from backend.app.engines.prevention.verifier import VerificationOutcome
        mock_verify.return_value = VerificationOutcome(
            url="https://example.com/directory/profile",
            status="NO_LONGER_VISIBLE_AT_CHECKED_URL",
            outcome="VERIFIED_ABSENT",
            http_status_code=404,
            evidence_notes="HTTP 404 Not Found confirms telephone number is absent at checked URL.",
            content_hash="abc123",
            verified_at=now_iso,
        )
        verify_res = client.post(
            "/api/remediation/verify",
            json={
                "exposure_id": exp_id,
                "url": "https://example.com/directory/profile",
                "phone_number": norm.e164,
                "default_region": "US",
            },
        )
        assert verify_res.status_code == 200, verify_res.text
        v_data = verify_res.json()
        assert v_data["status"] in ("VERIFIED_REMOVED", "NO_LONGER_VISIBLE_AT_CHECKED_URL")
        assert v_data["http_status_code"] == 404


def test_external_search_consent_boundary(clean_synthetic_identity):
    """External queries strictly require opt-in; without consent, no external calls are made."""
    norm = clean_synthetic_identity

    # Without consent: external search skipped
    no_consent_res = client.post(
        "/api/discovery/scan",
        json={
            "phone_number": norm.e164,
            "default_region": "US",
            "providers": ["duckduckgo", "searxng"],
            "consent": {"granted": False},
        },
    )
    assert no_consent_res.status_code == 200
    nc_data = no_consent_res.json()
    assert nc_data["consent_granted"] is False
    assert nc_data["external_search_conducted"] is False
    assert all(po["status"] == "unconfigured" for po in nc_data["provider_outcomes"])
