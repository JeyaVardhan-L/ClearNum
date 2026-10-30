"""Tests for Evidence Origin and Verification Transparency (Phase 5D).
Verifies:
1. Search snippet evidence (SEARCH_SNIPPET).
2. Fetched-page evidence (FETCHED_PAGE).
3. Archived snapshot evidence (ARCHIVED_SNAPSHOT).
4. Unknown legacy evidence (UNKNOWN).
5. Provider failures do not erase established evidence.
6. HTTP 200 without phone match does not create an exposure.
7. HTTP 200 with phone match creates a verified FETCHED_PAGE exposure.
8. Historical evidence without current-page confirmation is not misclaimed as live.
9. Database migration compatibility for legacy databases without evidence_origin.
10. API serialization and response schema contracts.
"""

import tempfile
import uuid
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import init_db, get_db_connection, utc_now_iso
from backend.app.engines.discovery.normalizer import parse_and_normalize
from backend.app.engines.discovery.matcher import match_phone_in_text
from backend.app.engines.discovery.providers.base import (
    ProviderResult,
    SearchExecutionResult,
    ProviderOutcome,
    ProviderStatus,
)


# -----------------------------------------------------------------------------
# 1. Search Snippet Evidence (SEARCH_SNIPPET)
# -----------------------------------------------------------------------------
def test_search_snippet_evidence(tmp_path: Path):
    """Search provider snippet match is explicitly categorized as SEARCH_SNIPPET,
    never claimed as a verified live page-body match."""
    db_file = tmp_path / "test_snippet.db"
    key_file = tmp_path / ".test_key"
    key_file.write_bytes(b"test_key_seed_32_bytes_long_1234")
    init_db(db_file)

    synthetic_phone = "+919876543210"
    norm = parse_and_normalize(synthetic_phone)

    res_ddg = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title(
                url="https://example.com/directory?id=5",
                title="Public Business Directory",
                snippet="Inquire for details: +91 98765 43210 available weekdays.",
                provider_id="duckduckgo",
                evidence_origin="SEARCH_SNIPPET",
            )
        ],
        outcome=ProviderOutcome(
            provider_id="duckduckgo",
            status=ProviderStatus.HEALTHY,
            result_count=1,
            duration_ms=30,
            retryable=False,
            diagnostic="Healthy",
        ),
    )

    with patch.object(settings, "db_path", db_file), \
         patch.object(settings, "key_path", key_file), \
         patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=res_ddg):

        client = TestClient(app)
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "providers": ["duckduckgo"],
            "consent": {"granted": True, "confirmed_providers": ["duckduckgo"]},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["exposures"]) == 1
        exp = data["exposures"][0]

        # Invariant: Evidence origin is SEARCH_SNIPPET
        assert exp["evidence_origin"] == "SEARCH_SNIPPET"

        # Check database persistence
        conn = get_db_connection(db_file)
        c = conn.cursor()
        c.execute("SELECT evidence_origin FROM exposures WHERE id = ?", (exp["id"],))
        row = c.fetchone()
        assert row["evidence_origin"] == "SEARCH_SNIPPET"
        conn.close()

        # Query /api/discovery/exposures
        list_resp = client.get(f"/api/discovery/exposures?identity_hmac={norm.hmac_id}")
        assert list_resp.status_code == 200
        list_items = list_resp.json()
        assert list_items[0]["evidence_origin"] == "SEARCH_SNIPPET"


# -----------------------------------------------------------------------------
# 2. Fetched-Page Evidence (FETCHED_PAGE)
# -----------------------------------------------------------------------------
def test_fetched_page_evidence(tmp_path: Path):
    """User-supplied URL whose body is retrieved and verified live has origin FETCHED_PAGE."""
    db_file = tmp_path / "test_fetched.db"
    key_file = tmp_path / ".test_key"
    key_file.write_bytes(b"test_key_seed_32_bytes_long_1234")
    init_db(db_file)

    synthetic_phone = "+919876543210"
    norm = parse_and_normalize(synthetic_phone)
    target_url = "https://verified-site.in/contact"
    html_body = "<html><body><h1>Contact Us</h1><p>Customer Care: +91 98765 43210</p></body></html>"

    with patch.object(settings, "db_path", db_file), \
         patch.object(settings, "key_path", key_file), \
         patch("backend.app.api.routes.safe_fetch_url", new_callable=AsyncMock, return_value=(200, html_body, {})):

        client = TestClient(app)
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "providers": [],
            "target_urls": [target_url],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["exposures"]) == 1
        exp = data["exposures"][0]

        # Invariant: Fetched live page has origin FETCHED_PAGE
        assert exp["evidence_origin"] == "FETCHED_PAGE"
        assert exp["canonical_url"] == "https://verified-site.in/contact"
        assert exp["match_classification"] == "CONFIRMED_MATCH"

        # Check database persistence
        conn = get_db_connection(db_file)
        c = conn.cursor()
        c.execute("SELECT evidence_origin FROM exposures WHERE id = ?", (exp["id"],))
        assert c.fetchone()["evidence_origin"] == "FETCHED_PAGE"
        conn.close()


# -----------------------------------------------------------------------------
# 3. Archived Snapshot Evidence (ARCHIVED_SNAPSHOT)
# -----------------------------------------------------------------------------
def test_archived_snapshot_evidence(tmp_path: Path):
    """Wayback Machine snapshot results are assigned ARCHIVED_SNAPSHOT."""
    db_file = tmp_path / "test_archived.db"
    key_file = tmp_path / ".test_key"
    key_file.write_bytes(b"test_key_seed_32_bytes_long_1234")
    init_db(db_file)

    synthetic_phone = "+919876543210"
    norm = parse_and_normalize(synthetic_phone)

    res_wayback = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title(
                url="https://web.archive.org/web/20220101120000/https://example.com/ad/1",
                title="Archived Snapshot — example.com (Jan 01, 2022)",
                snippet="Historical capture on Jan 01, 2022 indexing telephone digits: +91 98765 43210",
                provider_id="wayback",
                evidence_origin="ARCHIVED_SNAPSHOT",
            )
        ],
        outcome=ProviderOutcome(
            provider_id="wayback",
            status=ProviderStatus.HEALTHY,
            result_count=1,
            duration_ms=60,
            retryable=False,
            diagnostic="Healthy",
        ),
    )

    with patch.object(settings, "db_path", db_file), \
         patch.object(settings, "key_path", key_file), \
         patch("backend.app.engines.discovery.providers.wayback.WaybackProvider.search", new_callable=AsyncMock, return_value=res_wayback):

        client = TestClient(app)
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "providers": ["wayback"],
            "consent": {"granted": True, "confirmed_providers": ["wayback"]},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["exposures"]) == 1
        exp = data["exposures"][0]

        # Invariant: Evidence origin is ARCHIVED_SNAPSHOT
        assert exp["evidence_origin"] == "ARCHIVED_SNAPSHOT"

        # Check database persistence
        conn = get_db_connection(db_file)
        c = conn.cursor()
        c.execute("SELECT evidence_origin FROM exposures WHERE id = ?", (exp["id"],))
        assert c.fetchone()["evidence_origin"] == "ARCHIVED_SNAPSHOT"
        conn.close()


# -----------------------------------------------------------------------------
# 4. Unknown Legacy Evidence (UNKNOWN)
# -----------------------------------------------------------------------------
def test_unknown_legacy_evidence(tmp_path: Path):
    """Historical records without evidence origin default to UNKNOWN and are never silently promoted."""
    db_file = tmp_path / "test_legacy_unknown.db"
    key_file = tmp_path / ".test_key"
    key_file.write_bytes(b"test_key_seed_32_bytes_long_1234")
    init_db(db_file)

    synthetic_phone = "+919876543210"
    norm = parse_and_normalize(synthetic_phone)
    now_iso = utc_now_iso()

    conn = get_db_connection(db_file)
    c = conn.cursor()
    c.execute("""
        INSERT INTO identities (id, hmac_id, masked_phone, country_code, carrier_name, line_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), norm.hmac_id, norm.masked_display, "91", "Carrier", "MOBILE", now_iso))

    legacy_id = str(uuid.uuid4())
    # Explicitly insert with NULL evidence_origin simulating pre-Phase 5D record
    c.execute("""
        INSERT INTO exposures (
            id, identity_hmac, source_id, url, canonical_url, evidence_origin, domain, title, match_type, confidence, snippet, discovered_at, last_checked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (legacy_id, norm.hmac_id, "generic_web", "https://old-record.com", "https://old-record.com", None, "old-record.com", "Old Record", "EXACT", 1.0, "Call +91 98765 43210", now_iso, now_iso))
    conn.commit()
    conn.close()

    with patch.object(settings, "db_path", db_file), \
         patch.object(settings, "key_path", key_file):

        client = TestClient(app)
        resp = client.get(f"/api/discovery/exposures?identity_hmac={norm.hmac_id}")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["evidence_origin"] == "UNKNOWN"


# -----------------------------------------------------------------------------
# 5. Provider Failures Do Not Erase Established Evidence
# -----------------------------------------------------------------------------
def test_provider_failures_preserve_existing_evidence(tmp_path: Path):
    """When external providers fail, previously established exposures and evidence origins are never erased."""
    db_file = tmp_path / "test_failures.db"
    key_file = tmp_path / ".test_key"
    key_file.write_bytes(b"test_key_seed_32_bytes_long_1234")
    init_db(db_file)

    synthetic_phone = "+919876543210"
    norm = parse_and_normalize(synthetic_phone)
    now_iso = utc_now_iso()

    # Seed an existing confirmed exposure
    conn = get_db_connection(db_file)
    c = conn.cursor()
    c.execute("""
        INSERT INTO identities (id, hmac_id, masked_phone, country_code, carrier_name, line_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), norm.hmac_id, norm.masked_display, "91", "Carrier", "MOBILE", now_iso))

    existing_id = str(uuid.uuid4())
    c.execute("""
        INSERT INTO exposures (
            id, identity_hmac, source_id, url, canonical_url, evidence_origin, domain, title, match_type, confidence, snippet, discovered_at, last_checked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (existing_id, norm.hmac_id, "generic_web", "https://important-leak.com/page", "https://important-leak.com/page", "FETCHED_PAGE", "important-leak.com", "Leak Page", "EXACT", 1.0, "+91 98765 43210", now_iso, now_iso))
    conn.commit()
    conn.close()

    # Simulate provider failure (rate limited)
    failed_outcome = ProviderOutcome(
        provider_id="duckduckgo",
        status=ProviderStatus.RATE_LIMITED,
        result_count=0,
        duration_ms=100,
        retryable=True,
        diagnostic="Rate limit HTTP 429",
    )
    res_failed = SearchExecutionResult(results=[], outcome=failed_outcome)

    with patch.object(settings, "db_path", db_file), \
         patch.object(settings, "key_path", key_file), \
         patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=res_failed):

        client = TestClient(app)
        scan_resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "providers": ["duckduckgo"],
            "consent": {"granted": True, "confirmed_providers": ["duckduckgo"]},
        })
        assert scan_resp.status_code == 200

        # Query exposures: existing evidence remains completely intact
        list_resp = client.get(f"/api/discovery/exposures?identity_hmac={norm.hmac_id}")
        assert list_resp.status_code == 200
        items = list_resp.json()
        assert len(items) == 1
        assert items[0]["id"] == existing_id
        assert items[0]["evidence_origin"] == "FETCHED_PAGE"
        assert items[0]["confidence"] == 1.0


# -----------------------------------------------------------------------------
# 6. HTTP 200 Without Phone Match Does Not Create Exposure
# -----------------------------------------------------------------------------
def test_http_200_without_phone_match(tmp_path: Path):
    """Target URL returning HTTP 200 without phone number does NOT create an exposure."""
    db_file = tmp_path / "test_http_200_nomatch.db"
    key_file = tmp_path / ".test_key"
    key_file.write_bytes(b"test_key_seed_32_bytes_long_1234")
    init_db(db_file)

    synthetic_phone = "+919876543210"
    target_url = "https://unrelated-corporate.com/about"
    unrelated_html = "<html><body><h1>Welcome</h1><p>General inquiries: info@corporate.com. No phone numbers listed here.</p></body></html>"

    with patch.object(settings, "db_path", db_file), \
         patch.object(settings, "key_path", key_file), \
         patch("backend.app.api.routes.safe_fetch_url", new_callable=AsyncMock, return_value=(200, unrelated_html, {})):

        client = TestClient(app)
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "providers": [],
            "target_urls": [target_url],
        })
        assert resp.status_code == 200
        data = resp.json()

        # Invariant: HTTP 200 without phone digits produces ZERO exposures
        assert len(data["exposures"]) == 0

        # Check database
        conn = get_db_connection(db_file)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as count FROM exposures")
        assert c.fetchone()["count"] == 0
        conn.close()


# -----------------------------------------------------------------------------
# 7. HTTP 200 With Phone Match Creates Verified FETCHED_PAGE Exposure
# -----------------------------------------------------------------------------
def test_http_200_with_phone_match(tmp_path: Path):
    """Target URL returning HTTP 200 with phone number creates verified FETCHED_PAGE exposure."""
    db_file = tmp_path / "test_http_200_match.db"
    key_file = tmp_path / ".test_key"
    key_file.write_bytes(b"test_key_seed_32_bytes_long_1234")
    init_db(db_file)

    synthetic_phone = "+919876543210"
    target_url = "https://classifieds.in/item/500"
    matching_html = "<html><body><h1>Listing</h1><p>Call seller directly: +91 98765 43210 for purchase.</p></body></html>"

    with patch.object(settings, "db_path", db_file), \
         patch.object(settings, "key_path", key_file), \
         patch("backend.app.api.routes.safe_fetch_url", new_callable=AsyncMock, return_value=(200, matching_html, {})):

        client = TestClient(app)
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "providers": [],
            "target_urls": [target_url],
        })
        assert resp.status_code == 200
        data = resp.json()

        assert len(data["exposures"]) == 1
        exp = data["exposures"][0]
        assert exp["evidence_origin"] == "FETCHED_PAGE"
        assert exp["canonical_url"] == "https://classifieds.in/item/500"
        assert exp["match_classification"] == "CONFIRMED_MATCH"
        assert exp["confidence"] == 1.0


# -----------------------------------------------------------------------------
# 8. Historical Evidence Not Claimed As Live
# -----------------------------------------------------------------------------
def test_historical_evidence_without_current_page_confirmation(tmp_path: Path):
    """Archived snapshot records are clearly categorized as ARCHIVED_SNAPSHOT and not claimed as live exposures."""
    synthetic_phone = "+919876543210"
    norm = parse_and_normalize(synthetic_phone)

    # Unit test matcher with ARCHIVED_SNAPSHOT origin
    match_eval = match_phone_in_text(
        "Historical capture 2021: seller phone was +91 98765 43210",
        norm,
        evidence_origin="ARCHIVED_SNAPSHOT",
    )
    assert match_eval.matched is True
    assert match_eval.evidence_origin == "ARCHIVED_SNAPSHOT"
    assert match_eval.match_classification == "CONFIRMED_MATCH"


# -----------------------------------------------------------------------------
# 9. Database Migration Compatibility
# -----------------------------------------------------------------------------
def test_database_migration_compatibility(tmp_path: Path):
    """Legacy database created without evidence_origin column is safely migrated and backfilled."""
    db_file = tmp_path / "legacy_v1.db"
    key_file = tmp_path / ".test_key"
    key_file.write_bytes(b"test_key_seed_32_bytes_long_1234")

    # Manually create legacy schema without evidence_origin
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE identities (
            id TEXT PRIMARY KEY,
            hmac_id TEXT UNIQUE NOT NULL,
            masked_phone TEXT NOT NULL,
            country_code TEXT,
            carrier_name TEXT,
            line_type TEXT,
            created_at TEXT NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE exposures (
            id TEXT PRIMARY KEY,
            identity_hmac TEXT NOT NULL,
            source_id TEXT NOT NULL,
            url TEXT NOT NULL,
            canonical_url TEXT,
            domain TEXT,
            title TEXT,
            match_type TEXT NOT NULL,
            confidence REAL NOT NULL,
            snippet TEXT,
            discovered_at TEXT NOT NULL,
            last_checked_at TEXT NOT NULL
        );
    """)
    synthetic_phone = "+919876543210"
    norm = parse_and_normalize(synthetic_phone)
    now_iso = utc_now_iso()

    exp_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO exposures (
            id, identity_hmac, source_id, url, canonical_url, domain, title, match_type, confidence, snippet, discovered_at, last_checked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (exp_id, norm.hmac_id, "generic_web", "https://legacy.example.com", "https://legacy.example.com", "legacy.example.com", "Legacy", "EXACT", 1.0, "+91 98765 43210", now_iso, now_iso))
    conn.commit()
    conn.close()

    # Trigger init_db migrations
    init_db(db_file)

    # Check that evidence_origin column was added and backfilled to UNKNOWN
    conn_check = get_db_connection(db_file)
    c_check = conn_check.cursor()
    c_check.execute("SELECT evidence_origin FROM exposures WHERE id = ?", (exp_id,))
    row = c_check.fetchone()
    assert row["evidence_origin"] == "UNKNOWN"
    conn_check.close()


# -----------------------------------------------------------------------------
# 10. API Serialization and Schema Contracts
# -----------------------------------------------------------------------------
def test_api_serialization_and_contracts(tmp_path: Path):
    """Verifies DiscoveredExposureItem schema serialization across all 4 evidence origin tiers."""
    db_file = tmp_path / "test_contracts.db"
    key_file = tmp_path / ".test_key"
    key_file.write_bytes(b"test_key_seed_32_bytes_long_1234")
    init_db(db_file)

    synthetic_phone = "+919876543210"
    norm = parse_and_normalize(synthetic_phone)
    now_iso = utc_now_iso()

    conn = get_db_connection(db_file)
    c = conn.cursor()
    c.execute("""
        INSERT INTO identities (id, hmac_id, masked_phone, country_code, carrier_name, line_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), norm.hmac_id, norm.masked_display, "91", "Carrier", "MOBILE", now_iso))

    # Insert 4 exposures representing each evidence origin
    origins = ["SEARCH_SNIPPET", "FETCHED_PAGE", "ARCHIVED_SNAPSHOT", "UNKNOWN"]
    for i, orig in enumerate(origins):
        c.execute("""
            INSERT INTO exposures (
                id, identity_hmac, source_id, url, canonical_url, evidence_origin, domain, title, match_type, confidence, snippet, discovered_at, last_checked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            norm.hmac_id,
            "generic_web",
            f"https://example{i}.com",
            f"https://example{i}.com",
            orig,
            f"example{i}.com",
            f"Example {i}",
            "EXACT",
            1.0,
            f"Context {i}: +91 98765 43210",
            now_iso,
            now_iso,
        ))
    conn.commit()
    conn.close()

    with patch.object(settings, "db_path", db_file), \
         patch.object(settings, "key_path", key_file):

        client = TestClient(app)
        resp = client.get(f"/api/discovery/exposures?identity_hmac={norm.hmac_id}")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 4
        returned_origins = {it["evidence_origin"] for it in items}
        assert returned_origins == {"SEARCH_SNIPPET", "FETCHED_PAGE", "ARCHIVED_SNAPSHOT", "UNKNOWN"}

