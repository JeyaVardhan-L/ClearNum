"""Tests for Phase 6B: Remediation Schema Extensions and History API.
Verifies backward-compatible schema migrations, submission semantics,
strict identity isolation, forensic audit logging, and privacy sanitization.
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
from backend.app.main import app


@pytest.fixture
def test_env(tmp_path: Path):
    """Sets up a disposable temporary test environment with isolated DB and key."""
    db_file = tmp_path / "test_remediation.db"
    key_file = tmp_path / ".test_key"
    key_file.write_bytes(b"test_key_seed_32_bytes_long_1234")
    init_db(db_file)
    with patch.object(settings, "db_path", db_file), patch.object(settings, "key_path", key_file):
        yield db_file, key_file


def _insert_test_identity(db_file: Path, phone_e164: str = "+919876543210") -> str:
    """Inserts a test identity and returns its HMAC."""
    hmac_id = compute_phone_hmac(phone_e164)
    conn = get_db_connection(db_file)
    conn.execute("""
        INSERT INTO identities (id, hmac_id, masked_phone, country_code, carrier_name, line_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), hmac_id, "+91 ••• ••• •• 10", "IN", "TestCarrier", "MOBILE", utc_now_iso()))
    conn.commit()
    conn.close()
    return hmac_id


def _insert_test_exposure(db_file: Path, identity_hmac: str, url: str = "https://broker.example.com/p/1") -> str:
    """Inserts a test exposure and returns exposure_id."""
    exp_id = str(uuid.uuid4())
    conn = get_db_connection(db_file)
    now_iso = utc_now_iso()
    conn.execute("""
        INSERT INTO exposures (
            id, identity_hmac, source_id, url, canonical_url, evidence_origin, domain, title,
            match_type, confidence, snippet, discovered_at, last_checked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        exp_id, identity_hmac, "test_broker", url, url, "FETCHED_PAGE",
        "broker.example.com", "Data Profile", "EXACT", 0.95, "Contact info", now_iso, now_iso
    ))
    conn.commit()
    conn.close()
    return exp_id


def _insert_test_action(db_file: Path, exposure_id: str, identity_hmac: str, status: str = "CONFIRMED_EXPOSURE") -> str:
    """Inserts a test remediation action and returns action_id."""
    action_id = str(uuid.uuid4())
    conn = get_db_connection(db_file)
    conn.execute("""
        INSERT INTO remediation_actions (
            id, exposure_id, identity_hmac, source_id, status, official_url, notes, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        action_id, exposure_id, identity_hmac, "test_broker", status,
        "https://broker.example.com/opt-out", "Initial discovery", utc_now_iso()
    ))
    conn.commit()
    conn.close()
    return action_id


# 1. Fresh DB schema has all metadata columns
def test_fresh_db_schema_has_all_metadata_columns(tmp_path: Path):
    db_file = tmp_path / "fresh.db"
    init_db(db_file)

    conn = get_db_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(remediation_actions);")
    cols = {row["name"] for row in cursor.fetchall()}
    conn.close()

    expected = {
        "id", "exposure_id", "identity_hmac", "source_id", "status",
        "official_url", "submission_ref", "notes", "submitted_at", "verified_at", "updated_at",
        "request_type", "submission_channel", "expected_response_date", "follow_up_date", "deadline_basis"
    }
    assert expected.issubset(cols), f"Missing columns in fresh DB: {expected - cols}"


# 2. Migration of legacy database with existing records
def test_migration_of_legacy_database_with_existing_records(tmp_path: Path):
    legacy_db = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(legacy_db))
    # Create old table without the Phase 6B columns
    conn.execute("""
        CREATE TABLE remediation_actions (
            id TEXT PRIMARY KEY,
            exposure_id TEXT NOT NULL,
            identity_hmac TEXT NOT NULL,
            source_id TEXT NOT NULL,
            status TEXT NOT NULL,
            official_url TEXT,
            submission_ref TEXT,
            notes TEXT,
            submitted_at TEXT,
            verified_at TEXT,
            updated_at TEXT NOT NULL
        );
    """)
    conn.execute("""
        INSERT INTO remediation_actions (id, exposure_id, identity_hmac, source_id, status, updated_at)
        VALUES ('act_1', 'exp_1', 'hmac_1', 'source_1', 'CONFIRMED_EXPOSURE', '2026-10-30T10:00:00Z');
    """)
    conn.commit()
    conn.close()

    # Run init_db to trigger migration
    init_db(legacy_db)

    # Check migrated columns and preserved data
    conn = get_db_connection(legacy_db)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM remediation_actions WHERE id = 'act_1';")
    row = cursor.fetchone()
    conn.close()

    assert row["id"] == "act_1"
    assert row["status"] == "CONFIRMED_EXPOSURE"
    assert row["deadline_basis"] == "NONE"
    assert row["request_type"] is None
    assert row["submission_channel"] is None


# 3. Idempotent migration execution
def test_idempotent_migration_execution(tmp_path: Path):
    db_file = tmp_path / "idempotent.db"
    # Execute init_db 3 times
    init_db(db_file)
    init_db(db_file)
    init_db(db_file)

    conn = get_db_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(remediation_actions);")
    cols = [row["name"] for row in cursor.fetchall()]
    conn.close()

    # Verify no duplicate columns or corruption
    assert len(cols) == len(set(cols))
    assert "deadline_basis" in cols


# 4. Preservation of historical audit-log rows
def test_preservation_of_historical_audit_log_rows(tmp_path: Path):
    db_file = tmp_path / "audit_preserve.db"
    init_db(db_file)

    identity_hmac = _insert_test_identity(db_file)
    exposure_id = _insert_test_exposure(db_file, identity_hmac)
    action_id = _insert_test_action(db_file, exposure_id, identity_hmac)

    conn = get_db_connection(db_file)
    conn.execute("""
        INSERT INTO action_audit_log (
            id, action_id, identity_hmac, from_state, to_state, evidence_type, evidence_notes, created_at
        ) VALUES ('aud_1', ?, ?, 'DISCOVERED', 'CONFIRMED_EXPOSURE', 'USER_OR_SCAN_CONFIRMATION', 'Initial affirm', '2026-10-30T10:00:00Z');
    """, (action_id, identity_hmac))
    conn.commit()
    conn.close()

    # Re-run init_db
    init_db(db_file)

    conn = get_db_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM action_audit_log WHERE id = 'aud_1';")
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row["action_id"] == action_id
    assert row["from_state"] == "DISCOVERED"
    assert row["to_state"] == "CONFIRMED_EXPOSURE"


# 5. Missing or partial columns handled gracefully
def test_missing_or_partial_columns_handled(tmp_path: Path):
    partial_db = tmp_path / "partial.db"
    conn = sqlite3.connect(str(partial_db))
    # Partially migrated schema with request_type already present
    conn.execute("""
        CREATE TABLE remediation_actions (
            id TEXT PRIMARY KEY,
            exposure_id TEXT NOT NULL,
            identity_hmac TEXT NOT NULL,
            source_id TEXT NOT NULL,
            status TEXT NOT NULL,
            official_url TEXT,
            submission_ref TEXT,
            notes TEXT,
            submitted_at TEXT,
            verified_at TEXT,
            updated_at TEXT NOT NULL,
            request_type TEXT
        );
    """)
    conn.commit()
    conn.close()

    init_db(partial_db)

    conn = get_db_connection(partial_db)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(remediation_actions);")
    cols = {row["name"] for row in cursor.fetchall()}
    conn.close()

    assert "deadline_basis" in cols
    assert "submission_channel" in cols
    assert "expected_response_date" in cols
    assert "follow_up_date" in cols


# 6. Request metadata persistence
def test_request_metadata_persistence(test_env):
    db_file, _ = test_env
    identity_hmac = _insert_test_identity(db_file)
    exposure_id = _insert_test_exposure(db_file, identity_hmac)
    action_id = _insert_test_action(db_file, exposure_id, identity_hmac, status="CONFIRMED_EXPOSURE")

    client = TestClient(app)
    resp = client.post("/api/remediation/transition", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "next_state": "REQUEST_PREPARED",
        "request_type": "DPDP_NOTICE",
        "submission_channel": "STATUTORY_EMAIL",
        "expected_response_date": "2026-11-30",
        "follow_up_date": "2026-11-15",
        "deadline_basis": "STATUTORY",
        "notes": "Generated statutory notice draft for grievance officer.",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["request_type"] == "DPDP_NOTICE"
    assert data["submission_channel"] == "STATUTORY_EMAIL"
    assert data["deadline_basis"] == "STATUTORY"
    assert data["expected_response_date"] == "2026-11-30"
    assert data["follow_up_date"] == "2026-11-15"

    # Verify directly in SQLite
    conn = get_db_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM remediation_actions WHERE id = ?;", (action_id,))
    row = cursor.fetchone()
    conn.close()

    assert row["request_type"] == "DPDP_NOTICE"
    assert row["submission_channel"] == "STATUTORY_EMAIL"
    assert row["deadline_basis"] == "STATUTORY"
    assert row["expected_response_date"] == "2026-11-30"
    assert row["follow_up_date"] == "2026-11-15"


# 7. Submission semantics: draft (REQUEST_PREPARED) vs submitted (SUBMITTED)
def test_submission_semantics_draft_vs_submitted(test_env):
    db_file, _ = test_env
    identity_hmac = _insert_test_identity(db_file)
    exposure_id = _insert_test_exposure(db_file, identity_hmac)
    action_id = _insert_test_action(db_file, exposure_id, identity_hmac, status="CONFIRMED_EXPOSURE")

    client = TestClient(app)

    # Transition to REQUEST_PREPARED with an attempted submitted_at timestamp: must NOT be set
    resp_draft = client.post("/api/remediation/transition", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "next_state": "REQUEST_PREPARED",
        "submitted_at": "2026-10-30T12:00:00Z",
        "request_type": "WEB_FORM",
        "notes": "Draft generated locally",
    })
    assert resp_draft.status_code == 200
    assert resp_draft.json()["submitted_at"] is None

    conn = get_db_connection(db_file)
    row_draft = conn.execute("SELECT submitted_at, status FROM remediation_actions WHERE id = ?;", (action_id,)).fetchone()
    conn.close()
    assert row_draft["status"] == "REQUEST_PREPARED"
    assert row_draft["submitted_at"] is None

    # Now transition to SUBMITTED: submitted_at MUST be populated
    resp_sub = client.post("/api/remediation/transition", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "next_state": "SUBMITTED",
        "submission_ref": "REF-884920",
        "notes": "Dispatched via portal",
    })
    assert resp_sub.status_code == 200
    assert resp_sub.json()["submitted_at"] is not None

    conn = get_db_connection(db_file)
    row_sub = conn.execute("SELECT submitted_at, status FROM remediation_actions WHERE id = ?;", (action_id,)).fetchone()
    conn.close()
    assert row_sub["status"] == "SUBMITTED"
    assert row_sub["submitted_at"] is not None


# 8. Invalid deadline_basis rejected with 400
def test_invalid_deadline_basis_rejected(test_env):
    db_file, _ = test_env
    identity_hmac = _insert_test_identity(db_file)
    exposure_id = _insert_test_exposure(db_file, identity_hmac)
    _insert_test_action(db_file, exposure_id, identity_hmac, status="CONFIRMED_EXPOSURE")

    client = TestClient(app)
    resp = client.post("/api/remediation/transition", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "next_state": "REQUEST_PREPARED",
        "deadline_basis": "INVALID_DEADLINE_BASIS",
    })
    assert resp.status_code == 400
    assert "Invalid deadline_basis" in resp.json()["detail"]


# 9. Chronological history retrieval
def test_chronological_history_retrieval(test_env):
    db_file, _ = test_env
    identity_hmac = _insert_test_identity(db_file)
    exposure_id = _insert_test_exposure(db_file, identity_hmac)
    action_id = _insert_test_action(db_file, exposure_id, identity_hmac, status="CONFIRMED_EXPOSURE")

    client = TestClient(app)

    # Step 1: REQUEST_PREPARED
    client.post("/api/remediation/transition", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "next_state": "REQUEST_PREPARED",
        "request_type": "CCPA_DELETE",
        "notes": "Draft ready",
    })

    # Step 2: SUBMITTED
    client.post("/api/remediation/transition", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "next_state": "SUBMITTED",
        "submission_ref": "CCPA-123",
        "notes": "Sent via portal",
    })

    # Step 3: ACKNOWLEDGED
    client.post("/api/remediation/transition", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "next_state": "ACKNOWLEDGED",
        "submission_ref": "TICKET-999",
        "notes": "Broker acknowledged receipt",
    })

    # Fetch history
    resp = client.get(f"/api/remediation/history/{exposure_id}?identity_hmac={identity_hmac}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["exposure_id"] == exposure_id
    assert data["action_id"] == action_id
    assert data["current_status"] == "ACKNOWLEDGED"
    assert data["total_events"] == 3
    events = data["events"]
    assert len(events) == 3

    # Check chronological transitions
    assert events[0]["from_state"] == "CONFIRMED_EXPOSURE"
    assert events[0]["to_state"] == "REQUEST_PREPARED"
    assert events[0]["action_id"] == action_id

    assert events[1]["from_state"] == "REQUEST_PREPARED"
    assert events[1]["to_state"] == "SUBMITTED"

    assert events[2]["from_state"] == "SUBMITTED"
    assert events[2]["to_state"] == "ACKNOWLEDGED"

    # Verify timestamps are non-decreasing
    assert events[0]["created_at"] <= events[1]["created_at"] <= events[2]["created_at"]


# 10. Empty history for exposure without action
def test_empty_history_for_exposure_without_action(test_env):
    db_file, _ = test_env
    identity_hmac = _insert_test_identity(db_file)
    exposure_id = _insert_test_exposure(db_file, identity_hmac)
    # No action inserted

    client = TestClient(app)
    resp = client.get(f"/api/remediation/history/{exposure_id}?identity_hmac={identity_hmac}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["exposure_id"] == exposure_id
    assert data["total_events"] == 0
    assert data["events"] == []
    assert data["action_id"] is None


# 11. Missing exposure returns 404
def test_missing_exposure_returns_404(test_env):
    db_file, _ = test_env
    identity_hmac = _insert_test_identity(db_file)
    fake_exposure_id = str(uuid.uuid4())

    client = TestClient(app)
    resp = client.get(f"/api/remediation/history/{fake_exposure_id}?identity_hmac={identity_hmac}")
    assert resp.status_code == 404
    assert "Exposure not found" in resp.json()["detail"]


# 12. Strict identity isolation returns 404 for foreign identity
def test_strict_identity_isolation_returns_404_for_foreign_identity(test_env):
    db_file, _ = test_env
    identity_A = _insert_test_identity(db_file, "+919876543210")
    identity_B = _insert_test_identity(db_file, "+919876543211")

    # Exposure belongs to identity A
    exposure_id_A = _insert_test_exposure(db_file, identity_A)
    _insert_test_action(db_file, exposure_id_A, identity_A)

    client = TestClient(app)

    # Identity B attempts to read identity A's exposure history
    resp = client.get(f"/api/remediation/history/{exposure_id_A}?identity_hmac={identity_B}")
    # Must return 404 (not 403 or 200) to prevent enumeration of other users' data
    assert resp.status_code == 404
    assert "Exposure not found" in resp.json()["detail"]


# 13. Sanitization of evidence notes in history and audit
def test_sanitization_of_evidence_notes_in_history_and_audit(test_env):
    db_file, _ = test_env
    identity_hmac = _insert_test_identity(db_file)
    exposure_id = _insert_test_exposure(db_file, identity_hmac)
    action_id = _insert_test_action(db_file, exposure_id, identity_hmac, status="CONFIRMED_EXPOSURE")

    client = TestClient(app)
    raw_sensitive_note = "Submitted statutory removal for user telephone number +91 98765 43210 via web form"

    resp = client.post("/api/remediation/transition", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "next_state": "SUBMITTED",
        "submission_ref": "REF-9988",
        "notes": raw_sensitive_note,
    })
    assert resp.status_code == 200

    # Verify history response redacts phone numbers
    hist_resp = client.get(f"/api/remediation/history/{exposure_id}?identity_hmac={identity_hmac}")
    assert hist_resp.status_code == 200
    events = hist_resp.json()["events"]
    assert len(events) == 1
    evidence_notes = events[0]["evidence_notes"]
    assert "+91 98765 43210" not in evidence_notes
    assert "•••-••10" in evidence_notes or "••" in evidence_notes

    # Verify database audit row was also sanitized
    conn = get_db_connection(db_file)
    row = conn.execute("SELECT evidence_notes FROM action_audit_log WHERE action_id = ?;", (action_id,)).fetchone()
    conn.close()
    assert "+91 98765 43210" not in row["evidence_notes"]


# 14. No raw phone number or HMAC leakage in API response model
def test_no_hmac_or_phone_leakage_in_api_response(test_env):
    db_file, _ = test_env
    raw_phone = "+919876543210"
    identity_hmac = _insert_test_identity(db_file, raw_phone)
    exposure_id = _insert_test_exposure(db_file, identity_hmac)
    _insert_test_action(db_file, exposure_id, identity_hmac, status="CONFIRMED_EXPOSURE")

    client = TestClient(app)
    client.post("/api/remediation/transition", json={
        "exposure_id": exposure_id,
        "identity_hmac": identity_hmac,
        "next_state": "SUBMITTED",
        "request_type": "GDPR_ERASURE",
        "notes": "Formal deletion demand dispatched",
    })

    hist_resp = client.get(f"/api/remediation/history/{exposure_id}?identity_hmac={identity_hmac}")
    assert hist_resp.status_code == 200
    resp_json = hist_resp.json()

    # Invariant: identity_hmac must NOT be in the response dictionary keys
    assert "identity_hmac" not in resp_json
    assert "hmac_id" not in resp_json
    assert "phone_number" not in resp_json

    # Invariant: raw phone digits must NOT appear in stringified JSON
    assert "9876543210" not in str(resp_json)
    assert raw_phone not in str(resp_json)
    for event in resp_json["events"]:
        assert "identity_hmac" not in event
        assert raw_phone not in str(event)

