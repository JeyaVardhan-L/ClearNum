"""Tests for destructive purge safety hardening, validation, and isolation.
Ensures application data is never deleted accidentally or without explicit confirmation.
"""

import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings, DATA_DIR
from backend.app.core.database import (
    init_db,
    purge_all_data,
    validate_purge_targets,
    get_purge_impact,
)

client = TestClient(app)


def test_purge_requires_confirmation_code(tmp_path: Path):
    db_file = tmp_path / "test_shield.db"
    key_file = tmp_path / ".test_key"
    init_db(db_file)
    key_file.write_bytes(b"A" * 32)

    # 1. Unconfirmed attempt
    res = purge_all_data(db_file, key_file, confirmed=False, confirmation_code="")
    assert res["success"] is False
    assert "explicit user confirmation" in res["message"]
    assert db_file.exists()
    assert key_file.exists()

    # 2. Wrong code attempt
    res2 = purge_all_data(db_file, key_file, confirmed=True, confirmation_code="DELETE")
    assert res2["success"] is False
    assert db_file.exists()
    assert key_file.exists()

    # 3. Cancel code attempt
    res3 = purge_all_data(db_file, key_file, confirmed=True, confirmation_code="CANCEL")
    assert res3["success"] is False
    assert db_file.exists()
    assert key_file.exists()


def test_purge_rejects_source_directory_path():
    src_file = Path("backend/app/main.py").resolve()
    key_file = Path("backend/app/core/security.py").resolve()

    is_valid, reason = validate_purge_targets(src_file, key_file)
    assert is_valid is False
    assert "source code" in reason.lower() or "outside designated" in reason.lower()

    # Even with PURGE code, purge_all_data must reject it
    res = purge_all_data(src_file, key_file, confirmed=True, confirmation_code="PURGE")
    assert res["success"] is False
    assert "safety" in res["message"].lower()


def test_purge_rejects_non_sqlite_file(tmp_path: Path):
    fake_db = tmp_path / "fake.db"
    fake_db.write_text("THIS IS NOT A SQLITE DATABASE", encoding="utf-8")
    key_file = tmp_path / ".key"
    key_file.write_bytes(b"B" * 32)

    is_valid, reason = validate_purge_targets(fake_db, key_file)
    assert is_valid is False
    assert "not an authentic sqlite" in reason.lower() or "not a valid sqlite" in reason.lower()

    res = purge_all_data(fake_db, key_file, confirmed=True, confirmation_code="PURGE")
    assert res["success"] is False
    assert fake_db.exists()


def test_purge_rejects_foreign_sqlite_database(tmp_path: Path):
    foreign_db = tmp_path / "foreign.sqlite"
    conn = sqlite3.connect(foreign_db)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);")
    conn.execute("INSERT INTO users VALUES (1, 'Alice');")
    conn.commit()
    conn.close()

    key_file = tmp_path / ".key"
    key_file.write_bytes(b"C" * 32)

    is_valid, reason = validate_purge_targets(foreign_db, key_file)
    assert is_valid is False
    assert "foreign tables" in reason.lower() or "unrecognized" in reason.lower()

    res = purge_all_data(foreign_db, key_file, confirmed=True, confirmation_code="PURGE")
    assert res["success"] is False
    assert foreign_db.exists()


def test_purge_success_on_valid_temp_database(tmp_path: Path):
    db_file = tmp_path / "valid_test.db"
    key_file = tmp_path / ".valid_key"
    init_db(db_file)
    key_file.write_bytes(b"D" * 32)

    # Insert sample records
    conn = sqlite3.connect(db_file)
    conn.execute(
        "INSERT INTO identities (hmac_id, masked_phone, created_at) VALUES ('test_hmac_123', '+91 •••', '2026-10-29T12:00:00Z');"
    )
    conn.execute(
        "INSERT INTO exposures (id, identity_hmac, source_id, url, match_type, confidence, discovered_at, last_checked_at) "
        "VALUES ('exp_1', 'test_hmac_123', 'src_1', 'https://example.com', 'EXACT', 1.0, '2026-10-29T12:00:00Z', '2026-10-29T12:00:00Z');"
    )
    conn.commit()
    conn.close()

    # Inspect impact
    impact = get_purge_impact(db_file, key_file)
    assert impact["database_exists"] is True
    assert impact["key_exists"] is True
    assert impact["is_default_database"] is False
    assert impact["record_counts"]["identities"] == 1
    assert impact["record_counts"]["exposures"] == 1
    assert impact["total_records"] == 2

    # Execute valid purge
    res = purge_all_data(db_file, key_file, confirmed=True, confirmation_code="PURGE")
    assert res["success"] is True
    assert res["key_deleted"] is True
    assert "identities" in res["tables_dropped"]
    assert res["records_deleted"]["identities"] == 1
    assert not key_file.exists()

    # Post-purge state: DB is re-initialized empty
    impact_after = get_purge_impact(db_file, key_file)
    assert impact_after["total_records"] == 0


def test_purge_handles_missing_key_gracefully(tmp_path: Path):
    db_file = tmp_path / "missing_key.db"
    key_file = tmp_path / ".nonexistent_key"
    init_db(db_file)

    res = purge_all_data(db_file, key_file, confirmed=True, confirmation_code="PURGE")
    assert res["success"] is True
    assert res["key_deleted"] is False


def test_purge_api_status_and_execution_guard():
    # 1. Purge status API
    status_resp = client.get("/api/privacy/purge/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert "database_path" in status_data
    assert "allowed_to_purge" in status_data
    assert "warning" in status_data

    # 2. Reject unconfirmed POST
    reject_resp = client.post("/api/privacy/purge", json={"confirm": False, "confirmation_code": ""})
    assert reject_resp.status_code == 400
    assert "PURGE" in reject_resp.json()["detail"]

    # 3. Reject wrong confirmation code
    reject_wrong = client.post("/api/privacy/purge", json={"confirm": True, "confirmation_code": "CANCEL"})
    assert reject_wrong.status_code == 400

    # 4. Valid confirmed purge succeeds against test environment database
    success_resp = client.post("/api/privacy/purge", json={"confirm": True, "confirmation_code": "PURGE"})
    assert success_resp.status_code == 200
    assert success_resp.json()["success"] is True


def test_purge_cli_guard(tmp_path: Path, monkeypatch):
    from typer.testing import CliRunner
    from backend.app.cli.main import app as cli_app

    runner = CliRunner()
    db_file = tmp_path / "cli_test.db"
    key_file = tmp_path / ".cli_key"
    monkeypatch.setattr(settings, "db_path", db_file)
    monkeypatch.setattr(settings, "key_path", key_file)
    init_db(db_file)

    # 1. Purge with wrong code aborts
    result = runner.invoke(cli_app, ["purge", "--yes", "--code", "WRONG"])
    assert result.exit_code == 0
    assert "aborted" in result.stdout.lower()

    # 2. Purge with valid code PURGE succeeds
    result2 = runner.invoke(cli_app, ["purge", "--yes", "--code", "PURGE"])
    assert result2.exit_code == 0
    assert "complete" in result2.stdout.lower()
