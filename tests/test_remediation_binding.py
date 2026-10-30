"""Tests for Phase 6C: Exposure-Bound Remediation Requests.
Verifies binding templates to exposures, persisting prepared requests,
strict submission semantics, truthful deadline estimation vs statutory grounds,
idempotency, and identity isolation.
"""

import sqlite3
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.core.database import init_db, get_db_connection, utc_now_iso
from backend.app.core.security import compute_phone_hmac
from backend.app.engines.remediation.deadlines import calculate_remediation_deadline
from backend.app.main import app


@pytest.fixture
def test_env(tmp_path: Path):
    """Sets up a disposable temporary test environment with isolated DB and key."""
    db_file = tmp_path / "test_binding.db"
    key_file = tmp_path / ".test_key"
    key_file.write_bytes(b"test_key_seed_32_bytes_long_1234")
    init_db(db_file)
    with patch.object(settings, "db_path", db_file), patch.object(settings, "key_path", key_file):
        yield db_file, key_file


def _insert_test_identity(db_file: Path, phone_e164: str = "+919876543210") -> str:
    hmac_id = compute_phone_hmac(phone_e164)
    conn = get_db_connection(db_file)
    conn.execute("""
        INSERT INTO identities (id, hmac_id, masked_phone, country_code, carrier_name, line_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), hmac_id, "+91 ••• ••• •• 10", "IN", "TestCarrier", "MOBILE", utc_now_iso()))
    conn.commit()
    conn.close()
    return hmac_id


def _insert_test_exposure(
    db_file: Path,
    identity_hmac: str,
    source_id: str = "whitepages_in",
    url: str = "https://whitepages.co.in/directory/record/123",
    canonical_url: str = "https://whitepages.co.in/directory/record/123",
) -> str:
    exp_id = str(uuid.uuid4())
    conn = get_db_connection(db_file)
    now_iso = utc_now_iso()
    conn.execute("""
        INSERT INTO exposures (
            id, identity_hmac, source_id, url, canonical_url, evidence_origin, domain, title,
            match_type, confidence, snippet, discovered_at, last_checked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        exp_id, identity_hmac, source_id, url, canonical_url, "FETCHED_PAGE",
        "whitepages.co.in", "Whitepages India Record", "EXACT", 0.95, "Subscriber: +91 98765 43210", now_iso, now_iso
    ))
    conn.commit()
    conn.close()
    return exp_id


# 1. Preparing a request for a valid exposure
def test_prepare_request_for_valid_exposure(test_env):
    db_file, _ = test_env
    identity_hmac = _insert_test_identity(db_file)
    exposure_id = _insert_test_exposure(db_file, identity_hmac)

    client = TestClient(app)
    resp = client.post("/api/remediation/prepare", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "request_type": "DPDP_NOTICE",
        "submission_channel": "STATUTORY_EMAIL",
        "notes": "Generated notice for Grievance Officer",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["exposure_id"] == exposure_id
    assert data["status"] == "REQUEST_PREPARED"
    assert data["request_type"] == "DPDP_NOTICE"
    assert data["submission_channel"] == "STATUTORY_EMAIL"
    assert data["submitted_at"] is None
    assert data["deadline_basis"] in ("STATUTORY", "SOURCE_ESTIMATE")


# 2. Rejecting a nonexistent exposure
def test_reject_nonexistent_exposure(test_env):
    db_file, _ = test_env
    identity_hmac = _insert_test_identity(db_file)
    fake_exposure_id = str(uuid.uuid4())

    client = TestClient(app)
    resp = client.post("/api/remediation/prepare", json={
        "exposure_id": fake_exposure_id,
        "identity_hmac": identity_hmac,
        "request_type": "CCPA_DELETE",
    })

    assert resp.status_code == 404
    assert "Exposure not found" in resp.json()["detail"]


# 3. Rejecting a foreign-identity exposure
def test_reject_foreign_identity_exposure(test_env):
    db_file, _ = test_env
    identity_A = _insert_test_identity(db_file, "+919876543210")
    identity_B = _insert_test_identity(db_file, "+919876543211")
    exposure_id_A = _insert_test_exposure(db_file, identity_A)

    client = TestClient(app)
    # Identity B attempts to prepare a request on Identity A's exposure
    resp = client.post("/api/remediation/prepare", json={
        "exposure_id": exposure_id_A,
        "identity_hmac": identity_B,
        "request_type": "DPDP_NOTICE",
    })

    assert resp.status_code == 404
    assert "Exposure not found" in resp.json()["detail"]


# 4. Persisting request type and exposure association
def test_persist_request_type_and_exposure_association(test_env):
    db_file, _ = test_env
    identity_hmac = _insert_test_identity(db_file)
    exposure_id = _insert_test_exposure(db_file, identity_hmac, source_id="fastpeoplesearch_us")

    client = TestClient(app)
    resp = client.post("/api/remediation/prepare", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "request_type": "CCPA_DELETE",
        "submission_channel": "WEB_FORM",
        "expected_response_date": "2026-12-15",
        "follow_up_date": "2026-12-01",
        "deadline_basis": "STATUTORY",
        "notes": "Drafted CCPA deletion notice",
    })

    assert resp.status_code == 200
    action_id = resp.json()["action_id"]

    # Verify directly in SQLite
    conn = get_db_connection(db_file)
    row = conn.execute("SELECT * FROM remediation_actions WHERE id = ?", (action_id,)).fetchone()
    conn.close()

    assert row["exposure_id"] == exposure_id
    assert row["identity_hmac"] == identity_hmac
    assert row["status"] == "REQUEST_PREPARED"
    assert row["request_type"] == "CCPA_DELETE"
    assert row["submission_channel"] == "WEB_FORM"
    assert row["expected_response_date"] == "2026-12-15"
    assert row["deadline_basis"] == "STATUTORY"


# 5. Repeated save action does not create duplicate remediation actions
def test_repeated_save_action_prevents_duplicate_records(test_env):
    db_file, _ = test_env
    identity_hmac = _insert_test_identity(db_file)
    exposure_id = _insert_test_exposure(db_file, identity_hmac)

    client = TestClient(app)

    # First preparation
    resp1 = client.post("/api/remediation/prepare", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "request_type": "DPDP_NOTICE",
        "submission_channel": "WEB_FORM",
    })
    assert resp1.status_code == 200
    action_id_1 = resp1.json()["action_id"]

    # Second preparation (repeated click / adjustment)
    resp2 = client.post("/api/remediation/prepare", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "request_type": "DPDP_NOTICE",
        "submission_channel": "STATUTORY_EMAIL",
        "notes": "Updated notes with email details",
    })
    assert resp2.status_code == 200
    action_id_2 = resp2.json()["action_id"]

    # Invariant: Action ID must be identical (no duplicate rows created)
    assert action_id_1 == action_id_2

    conn = get_db_connection(db_file)
    count = conn.execute("SELECT COUNT(*) as c FROM remediation_actions WHERE exposure_id = ?", (exposure_id,)).fetchone()["c"]
    conn.close()
    assert count == 1


# 6. Prepared request strictly leaves submitted_at empty (None)
def test_prepared_request_leaves_submitted_at_empty(test_env):
    db_file, _ = test_env
    identity_hmac = _insert_test_identity(db_file)
    exposure_id = _insert_test_exposure(db_file, identity_hmac)

    client = TestClient(app)
    resp = client.post("/api/remediation/prepare", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "request_type": "GDPR_ERASURE",
    })
    assert resp.status_code == 200
    assert resp.json()["submitted_at"] is None

    conn = get_db_connection(db_file)
    row = conn.execute("SELECT submitted_at FROM remediation_actions WHERE exposure_id = ?", (exposure_id,)).fetchone()
    conn.close()
    assert row["submitted_at"] is None


# 7. Copying or generating draft does not mark it submitted
def test_generating_or_binding_template_does_not_mark_submitted(test_env):
    db_file, _ = test_env
    identity_hmac = _insert_test_identity(db_file)
    exposure_id = _insert_test_exposure(db_file, identity_hmac)

    client = TestClient(app)

    # Call template generation with bound exposure
    tpl_resp = client.post("/api/remediation/template", json={
        "template_type": "DPDP_NOTICE",
        "phone_number": "+919876543210",
        "default_region": "IN",
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
    })
    assert tpl_resp.status_code == 200
    tpl_data = tpl_resp.json()
    assert tpl_data["exposure_id"] == exposure_id
    assert tpl_data["canonical_url"] == "https://whitepages.co.in/directory/record/123"

    # Action table must either not have an action yet, or if it does, it's not SUBMITTED
    conn = get_db_connection(db_file)
    row = conn.execute("SELECT status, submitted_at FROM remediation_actions WHERE exposure_id = ?", (exposure_id,)).fetchone()
    conn.close()
    if row:
        assert row["status"] != "SUBMITTED"
        assert row["submitted_at"] is None


# 8. Explicit submission confirmation records channel and timestamp
def test_explicit_submission_confirmation(test_env):
    db_file, _ = test_env
    identity_hmac = _insert_test_identity(db_file)
    exposure_id = _insert_test_exposure(db_file, identity_hmac)

    client = TestClient(app)

    # 1. Prepare draft
    client.post("/api/remediation/prepare", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "request_type": "DPDP_NOTICE",
        "submission_channel": "STATUTORY_EMAIL",
    })

    # 2. Confirm external submission
    sub_resp = client.post("/api/remediation/submit", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "submission_channel": "STATUTORY_EMAIL",
        "submission_ref": "TICKET-DPDP-9981",
        "notes": "Sent from user email client with signed grievance notice",
    })

    assert sub_resp.status_code == 200
    sub_data = sub_resp.json()
    assert sub_data["status"] == "SUBMITTED"
    assert sub_data["submission_channel"] == "STATUTORY_EMAIL"
    assert sub_data["submission_ref"] == "TICKET-DPDP-9981"
    assert sub_data["submitted_at"] is not None

    conn = get_db_connection(db_file)
    row = conn.execute("SELECT status, submitted_at, submission_ref FROM remediation_actions WHERE exposure_id = ?", (exposure_id,)).fetchone()
    conn.close()
    assert row["status"] == "SUBMITTED"
    assert row["submitted_at"] is not None
    assert row["submission_ref"] == "TICKET-DPDP-9981"


# 9. Invalid deadline basis is rejected
def test_invalid_deadline_basis_rejected(test_env):
    db_file, _ = test_env
    identity_hmac = _insert_test_identity(db_file)
    exposure_id = _insert_test_exposure(db_file, identity_hmac)

    client = TestClient(app)
    resp = client.post("/api/remediation/prepare", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "request_type": "CCPA_DELETE",
        "deadline_basis": "IMAGINARY_BASIS",
    })
    assert resp.status_code == 400
    assert "Invalid deadline_basis" in resp.json()["detail"]


# 10. Estimated deadlines are not mislabeled as statutory
def test_deadlines_not_mislabeled_as_statutory():
    # CCPA applied in India is an out-of-jurisdiction estimate, NOT statutory!
    res_ccpa_india = calculate_remediation_deadline("CCPA_DELETE", jurisdiction="IN")
    assert res_ccpa_india.deadline_basis == "SOURCE_ESTIMATE"
    assert res_ccpa_india.is_estimate is True

    # CCPA applied in California / US IS statutory
    res_ccpa_us = calculate_remediation_deadline("CCPA_DELETE", jurisdiction="US")
    assert res_ccpa_us.deadline_basis == "STATUTORY"
    assert res_ccpa_us.is_estimate is False
    assert res_ccpa_us.days == 45

    # GDPR applied in US is an estimate, NOT statutory
    res_gdpr_us = calculate_remediation_deadline("GDPR_ERASURE", jurisdiction="US")
    assert res_gdpr_us.deadline_basis == "SOURCE_ESTIMATE"
    assert res_gdpr_us.is_estimate is True

    # GDPR applied in EU/GB IS statutory
    res_gdpr_eu = calculate_remediation_deadline("GDPR_ERASURE", jurisdiction="GB")
    assert res_gdpr_eu.deadline_basis == "STATUTORY"
    assert res_gdpr_eu.is_estimate is False
    assert res_gdpr_eu.days == 30

    # TRAI applied in India IS statutory
    res_trai_in = calculate_remediation_deadline("TRAI_1909", jurisdiction="IN")
    assert res_trai_in.deadline_basis == "STATUTORY"
    assert res_trai_in.is_estimate is False
    assert res_trai_in.days == 7


# 11. Audit history records preparation and submission separately
def test_audit_history_records_prep_and_submission_separately(test_env):
    db_file, _ = test_env
    identity_hmac = _insert_test_identity(db_file)
    exposure_id = _insert_test_exposure(db_file, identity_hmac)

    client = TestClient(app)

    # 1. Prepare
    client.post("/api/remediation/prepare", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "request_type": "CCPA_DELETE",
    })

    # 2. Submit
    client.post("/api/remediation/submit", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "submission_channel": "WEB_FORM",
        "submission_ref": "CONF-4432",
    })

    # Retrieve history
    hist_resp = client.get(f"/api/remediation/history/{exposure_id}?identity_hmac={identity_hmac}")
    assert hist_resp.status_code == 200
    events = hist_resp.json()["events"]
    assert len(events) == 2

    # Event 1: DRAFT_GENERATION
    assert events[0]["to_state"] == "REQUEST_PREPARED"
    assert events[0]["evidence_type"] == "DRAFT_GENERATION"

    # Event 2: SUBMISSION_RECORD
    assert events[1]["from_state"] == "REQUEST_PREPARED"
    assert events[1]["to_state"] == "SUBMITTED"
    assert events[1]["evidence_type"] == "SUBMISSION_RECORD"


# 12. No raw phone number or HMAC leakage in prepare or submit responses
def test_no_phone_or_hmac_leakage_in_prepare_and_submit(test_env):
    db_file, _ = test_env
    raw_phone = "+919876543210"
    identity_hmac = _insert_test_identity(db_file, raw_phone)
    exposure_id = _insert_test_exposure(db_file, identity_hmac)

    client = TestClient(app)
    prep_res = client.post("/api/remediation/prepare", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "request_type": "DPDP_NOTICE",
        "notes": f"Prepared notice containing phone number {raw_phone}",
    })
    prep_json = prep_res.json()
    assert "identity_hmac" not in prep_json
    assert "hmac_id" not in prep_json
    assert raw_phone not in str(prep_json)

    sub_res = client.post("/api/remediation/submit", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "submission_channel": "STATUTORY_EMAIL",
        "notes": f"Submitted email regarding {raw_phone}",
    })
    sub_json = sub_res.json()
    assert "identity_hmac" not in sub_json
    assert "hmac_id" not in sub_json
    assert raw_phone not in str(sub_json)


# 13. Existing Phase 6B history endpoint remains compatible with header authentication
def test_history_endpoint_compatible_with_header_auth(test_env):
    db_file, _ = test_env
    identity_hmac = _insert_test_identity(db_file)
    exposure_id = _insert_test_exposure(db_file, identity_hmac)

    client = TestClient(app)
    client.post("/api/remediation/prepare", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "request_type": "DPDP_NOTICE",
    })

    # Test with X-Identity-HMAC header instead of query param
    hist_resp = client.get(
        f"/api/remediation/history/{exposure_id}",
        headers={"X-Identity-HMAC": identity_hmac}
    )
    assert hist_resp.status_code == 200
    assert hist_resp.json()["exposure_id"] == exposure_id
    assert hist_resp.json()["total_events"] == 1

