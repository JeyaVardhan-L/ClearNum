"""Regression test suite for Phase 6G: Concrete Product Defect Fixes.

Covers:
1. Cross-Identity Verification Protection (POST /api/remediation/verify)
2. Legal Notice Exposure Binding Identity Enforcement (POST /api/remediation/template)
3. Non-Destructive Database Open & Corruption Rejection (get_db_connection, init_db)
4. Verification Outcome Semantics (Ambiguous Redirects -> INCONCLUSIVE, 404 -> Absent at URL, Match -> Still Present)
5. Remediation Action Uniqueness & Idempotent Migration Safety
"""

import sqlite3
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import (
    DatabaseCorruptionError,
    get_db_connection,
    init_db,
    utc_now_iso,
)
from backend.app.core.ssrf import FetchResponse
from backend.app.engines.discovery.normalizer import parse_and_normalize
from backend.app.engines.prevention.verifier import (
    is_generic_redirect,
    verify_exposure_url,
)
from backend.app.main import app

client = TestClient(app)


@pytest.fixture
def dual_identities_and_exposure():
    """Sets up two isolated test identities and an exposure belonging strictly to Identity A."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = utc_now_iso()

    # Identity A
    norm_a = parse_and_normalize("+14155550101", "US")
    ident_a_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT OR IGNORE INTO identities (id, hmac_id, masked_phone, country_code, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (ident_a_id, norm_a.hmac_id, norm_a.masked_display, "US", now_iso))

    # Identity B
    norm_b = parse_and_normalize("+14155550102", "US")
    ident_b_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT OR IGNORE INTO identities (id, hmac_id, masked_phone, country_code, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (ident_b_id, norm_b.hmac_id, norm_b.masked_display, "US", now_iso))

    # Exposure belonging to Identity A
    exp_id = str(uuid.uuid4())
    act_id = str(uuid.uuid4())
    test_url = "https://example-broker.org/profiles/user-0101"
    canonical_url = "https://example-broker.org/profiles/user-0101"

    cursor.execute("""
        INSERT INTO exposures (
            id, identity_hmac, source_id, url, canonical_url, evidence_origin, domain, title, match_type, confidence, snippet, discovered_at, last_checked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        exp_id, norm_a.hmac_id, "test_broker", test_url, canonical_url, "FETCHED_PAGE",
        "example-broker.org", "User 0101 Public Profile", "EXACT", 1.0,
        "Phone: +1 415-555-0101", now_iso, now_iso
    ))

    cursor.execute("""
        INSERT INTO remediation_actions (
            id, exposure_id, identity_hmac, source_id, status, official_url, notes, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        act_id, exp_id, norm_a.hmac_id, "test_broker", "SUBMITTED",
        test_url, "Dispatched opt-out request", now_iso
    ))

    conn.commit()
    conn.close()

    return {
        "norm_a": norm_a,
        "norm_b": norm_b,
        "exp_id": exp_id,
        "act_id": act_id,
        "url": test_url,
    }


# ============================================================================
# TASK 1: Cross-Identity Verification Protection
# ============================================================================

def test_verify_endpoint_authorized_identity_succeeds(dual_identities_and_exposure):
    fixture = dual_identities_and_exposure
    mock_resp = FetchResponse(404, "<html><body>Not Found</body></html>", {}, final_url=fixture["url"])

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        resp = client.post("/api/remediation/verify", json={
            "exposure_id": fixture["exp_id"],
            "url": fixture["url"],
            "phone_number": fixture["norm_a"].e164,
            "default_region": "US",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "NO_LONGER_VISIBLE_AT_CHECKED_URL"
    assert data["outcome"] == "VERIFIED_ABSENT"


def test_verify_endpoint_cross_identity_rejected_before_network(dual_identities_and_exposure):
    fixture = dual_identities_and_exposure

    # Identity B attempts to verify Identity A's exposure
    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock) as mock_fetch:
        resp = client.post("/api/remediation/verify", json={
            "exposure_id": fixture["exp_id"],
            "url": fixture["url"],
            "phone_number": fixture["norm_b"].e164,
            "default_region": "US",
        })

        # MUST be rejected with HTTP 403 Forbidden
        assert resp.status_code == 403
        assert "Access denied" in resp.json()["detail"] or "exposure does not belong" in resp.json()["detail"]

        # MUST NOT perform any outbound network request
        mock_fetch.assert_not_called()

    # Ensure database record was untouched
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status, identity_hmac FROM remediation_actions WHERE exposure_id = ?", (fixture["exp_id"],))
    row = cursor.fetchone()
    conn.close()
    assert row["status"] == "SUBMITTED"
    assert row["identity_hmac"] == fixture["norm_a"].hmac_id


def test_verify_endpoint_nonexistent_exposure_returns_404(dual_identities_and_exposure):
    fixture = dual_identities_and_exposure
    unknown_id = str(uuid.uuid4())

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock) as mock_fetch:
        resp = client.post("/api/remediation/verify", json={
            "exposure_id": unknown_id,
            "url": "https://example-broker.org/test",
            "phone_number": fixture["norm_a"].e164,
            "default_region": "US",
        })
        assert resp.status_code == 404
        mock_fetch.assert_not_called()


# ============================================================================
# TASK 2: Legal Notice Exposure Binding Ownership
# ============================================================================

def test_template_endpoint_authorized_identity_succeeds(dual_identities_and_exposure):
    fixture = dual_identities_and_exposure
    resp = client.post("/api/remediation/template", json={
        "template_type": "CCPA_DELETE",
        "phone_number": fixture["norm_a"].e164,
        "default_region": "US",
        "exposure_id": fixture["exp_id"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["canonical_url"] == fixture["url"]
    assert data["source_id"] == "test_broker"
    assert data["exposure_id"] == fixture["exp_id"]


def test_template_endpoint_cross_identity_rejected(dual_identities_and_exposure):
    fixture = dual_identities_and_exposure
    # Identity B tries to bind Identity A's exposure
    resp = client.post("/api/remediation/template", json={
        "template_type": "CCPA_DELETE",
        "phone_number": fixture["norm_b"].e164,
        "default_region": "US",
        "exposure_id": fixture["exp_id"],
    })
    assert resp.status_code == 403
    assert "Access denied" in resp.json()["detail"]


def test_template_endpoint_omitted_identity_fails(dual_identities_and_exposure):
    fixture = dual_identities_and_exposure
    resp = client.post("/api/remediation/template", json={
        "template_type": "CCPA_DELETE",
        "phone_number": "",
        "default_region": "US",
        "exposure_id": fixture["exp_id"],
    })
    assert resp.status_code == 400


def test_template_endpoint_unbound_generic_template_preserves_local_workflow():
    norm = parse_and_normalize("+14155552671", "US")
    resp = client.post("/api/remediation/template", json={
        "template_type": "CCPA_DELETE",
        "phone_number": norm.e164,
        "default_region": "US",
        "target_url": "https://example.com/optout",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "CCPA" in data["title"]
    assert "https://example.com/optout" in data["body_markdown"]


# ============================================================================
# TASK 3: Non-Destructive Database Opening & Corruption Rejection
# ============================================================================

def test_database_invalid_header_raises_corruption_and_preserves_file(tmp_path):
    corrupt_db = tmp_path / "corrupt_test.db"
    corrupt_bytes = b"NOT_A_VALID_SQLITE_HEADER_123456789"
    corrupt_db.write_bytes(corrupt_bytes)

    # get_db_connection must raise DatabaseCorruptionError
    with pytest.raises(DatabaseCorruptionError) as exc_info:
        get_db_connection(corrupt_db)

    assert "is corrupted or not a valid SQLite database" in str(exc_info.value)

    # File MUST NOT be deleted
    assert corrupt_db.exists()
    assert corrupt_db.read_bytes() == corrupt_bytes

    # init_db must also fail safely without overwriting or deleting
    with pytest.raises(DatabaseCorruptionError):
        init_db(corrupt_db)

    assert corrupt_db.exists()
    assert corrupt_db.read_bytes() == corrupt_bytes


# ============================================================================
# TASK 4: Verification Outcome Semantics
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("redirect_url", [
    "https://example-broker.org/",
    "https://example-broker.org/login",
    "https://example-broker.org/signin",
    "https://example-broker.org/portal",
    "https://example-broker.org/search",
])
async def test_redirect_to_generic_page_is_inconclusive(dual_identities_and_exposure, redirect_url):
    fixture = dual_identities_and_exposure
    mock_resp = FetchResponse(200, "<html><body>Please sign in to continue</body></html>", {}, final_url=redirect_url)

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        outcome = await verify_exposure_url(
            exposure_id=fixture["exp_id"],
            url=fixture["url"],
            phone=fixture["norm_a"],
            update_database=True,
        )

    # Must NOT claim removal
    assert outcome.outcome == "INCONCLUSIVE"
    assert outcome.status == "INACCESSIBLE_OR_INCONCLUSIVE"
    assert "does not prove deletion" in outcome.evidence_notes or "Inconclusive redirect" in outcome.evidence_notes


@pytest.mark.asyncio
async def test_empty_page_is_inconclusive(dual_identities_and_exposure):
    fixture = dual_identities_and_exposure
    mock_resp = FetchResponse(200, "<html><body></body></html>", {}, final_url=fixture["url"])

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        outcome = await verify_exposure_url(
            exposure_id=fixture["exp_id"],
            url=fixture["url"],
            phone=fixture["norm_a"],
            update_database=True,
        )

    assert outcome.outcome == "INCONCLUSIVE"
    assert outcome.status == "INACCESSIBLE_OR_INCONCLUSIVE"
    assert "empty text content" in outcome.evidence_notes


@pytest.mark.asyncio
async def test_http_404_honestly_states_checked_url_absence(dual_identities_and_exposure):
    fixture = dual_identities_and_exposure
    mock_resp = FetchResponse(404, "<html><body>Page Not Found</body></html>", {}, final_url=fixture["url"])

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        outcome = await verify_exposure_url(
            exposure_id=fixture["exp_id"],
            url=fixture["url"],
            phone=fixture["norm_a"],
            update_database=True,
        )

    assert outcome.outcome == "VERIFIED_ABSENT"
    assert outcome.status == "NO_LONGER_VISIBLE_AT_CHECKED_URL"
    assert "Verified absent at checked URL" in outcome.evidence_notes
    assert "Does not confirm underlying database deletion" in outcome.evidence_notes


@pytest.mark.asyncio
async def test_matching_phone_marked_still_visible(dual_identities_and_exposure):
    fixture = dual_identities_and_exposure
    content = "<html><body>Profile for user: phone is +1-415-555-0101</body></html>"
    mock_resp = FetchResponse(200, content, {}, final_url=fixture["url"])

    with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock, return_value=mock_resp):
        outcome = await verify_exposure_url(
            exposure_id=fixture["exp_id"],
            url=fixture["url"],
            phone=fixture["norm_a"],
            update_database=True,
        )

    assert outcome.outcome == "STILL_PRESENT"
    assert outcome.status == "STILL_VISIBLE"
    assert "Still visible" in outcome.evidence_notes


# ============================================================================
# TASK 5: Remediation Actions Uniqueness
# ============================================================================

def test_remediation_actions_unique_constraint_enforced(tmp_path):
    test_db = tmp_path / "unique_test.db"
    init_db(test_db)

    conn = get_db_connection(test_db)
    cursor = conn.cursor()

    exp_id = str(uuid.uuid4())
    act1_id = str(uuid.uuid4())
    act2_id = str(uuid.uuid4())
    now_iso = utc_now_iso()

    # Insert parent identity and exposure to satisfy foreign keys
    cursor.execute("""
        INSERT INTO identities (id, hmac_id, masked_phone, created_at)
        VALUES ('ident-1', 'hmac_test', '+1 ••• ••• •• 01', ?)
    """, (now_iso,))
    cursor.execute("""
        INSERT INTO exposures (id, identity_hmac, source_id, url, match_type, confidence, discovered_at, last_checked_at)
        VALUES (?, 'hmac_test', 'src', 'https://example.com/exp', 'EXACT', 1.0, ?, ?)
    """, (exp_id, now_iso, now_iso))
    conn.commit()

    # Insert first remediation action
    cursor.execute("""
        INSERT INTO remediation_actions (id, exposure_id, identity_hmac, source_id, status, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (act1_id, exp_id, 'hmac_test', 'src', 'DISCOVERED', now_iso))
    conn.commit()

    # Second insert with same exposure_id must violate unique constraint
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("""
            INSERT INTO remediation_actions (id, exposure_id, identity_hmac, source_id, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (act2_id, exp_id, 'hmac_test', 'src', 'DISCOVERED', now_iso))
        conn.commit()

    conn.close()


def test_remediation_migration_aborts_safely_if_duplicates_exist(tmp_path):
    test_db = tmp_path / "dup_test.db"
    # Create tables without unique index manually to simulate legacy duplicates
    conn = sqlite3.connect(str(test_db))
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.executescript("""
        CREATE TABLE remediation_actions (
            id TEXT PRIMARY KEY,
            exposure_id TEXT NOT NULL,
            identity_hmac TEXT NOT NULL,
            source_id TEXT NOT NULL,
            status TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    # Insert two actions for same exposure
    exp_id = "duplicate-exposure-uuid"
    conn.execute("INSERT INTO remediation_actions VALUES ('a1', ?, 'h1', 's', 'DISCOVERED', '2026-10-31');", (exp_id,))
    conn.execute("INSERT INTO remediation_actions VALUES ('a2', ?, 'h1', 's', 'DISCOVERED', '2026-10-31');", (exp_id,))
    conn.commit()
    conn.close()

    # Running init_db must abort migration and raise RuntimeError
    with pytest.raises(RuntimeError) as exc_info:
        init_db(test_db)

    assert "Duplicate exposure_id rows detected" in str(exc_info.value)

    # Ensure both original duplicate records still exist (no silent deletion or merging)
    conn = sqlite3.connect(str(test_db))
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM remediation_actions WHERE exposure_id = ?", (exp_id,))
    rows = cursor.fetchall()
    conn.close()
    assert len(rows) == 2
