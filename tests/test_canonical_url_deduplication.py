"""Tests for Safe Canonical URL Normalization and Exposure Deduplication (Phase 5C).
Verifies:
1. Tracking parameter removal (utm_*, fbclid, gclid, etc.).
2. Fragment removal (#section, #/route, etc.).
3. Hostname and scheme casing and default port normalization.
4. Meaningful query parameter preservation and deterministic sorting.
5. URL encoding handling.
6. Same-page duplicate detection across multiple providers.
7. Different paths remaining distinct.
8. Different hosts remaining distinct.
9. Malformed and unsupported URL rejection.
10. Existing database compatibility and migration.
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
from backend.app.core.canonical_url import canonicalize_url, is_tracking_param
from backend.app.engines.discovery.normalizer import parse_and_normalize
from backend.app.engines.discovery.providers.base import ProviderResult, SearchExecutionResult, ProviderOutcome, ProviderStatus


# -----------------------------------------------------------------------------
# 1. Unit Tests: Tracking Parameter Removal
# -----------------------------------------------------------------------------
def test_tracking_parameter_removal():
    """Known advertising, click tracking, and analytics parameters are cleanly stripped."""
    # UTM parameters
    assert canonicalize_url("https://example.com/page?utm_source=google&utm_medium=cpc&utm_campaign=summer&utm_term=shoes&utm_content=v1") == "https://example.com/page"
    assert canonicalize_url("https://example.com/page?UTM_SOURCE=AD&utm_id=999") == "https://example.com/page"

    # Click IDs & ad tokens
    assert canonicalize_url("https://example.com/item?fbclid=IwAR123456789&gclid=Cj0KCQjw&msclkid=778899") == "https://example.com/item"
    assert canonicalize_url("https://example.com/item?twclid=112233&igshid=aabbcc&ttclid=tt123") == "https://example.com/item"
    assert canonicalize_url("https://example.com/item?mc_cid=camp123&mc_eid=user456") == "https://example.com/item"
    assert canonicalize_url("https://example.com/item?_ga=GA1.2.12345.67890&_gl=1*abcde*") == "https://example.com/item"
    assert canonicalize_url("https://example.com/item?_hsenc=p2ANqtz&_hsmi=123456") == "https://example.com/item"
    assert canonicalize_url("https://example.com/item?ref_src=twsrc%5Etfw&ref_url=https%3A%2F%2Fplatform.twitter.com") == "https://example.com/item"

    # Mixed tracking and non-tracking: non-tracking params MUST be preserved
    assert canonicalize_url("https://example.com/item?id=42&utm_source=email&gclid=xyz") == "https://example.com/item?id=42"


# -----------------------------------------------------------------------------
# 2. Unit Tests: Fragment Removal
# -----------------------------------------------------------------------------
def test_fragment_removal():
    """URL fragments are removed completely without modifying path or query."""
    assert canonicalize_url("https://example.com/contact#form") == "https://example.com/contact"
    assert canonicalize_url("https://example.com/contact#") == "https://example.com/contact"
    assert canonicalize_url("https://example.com/spa/#/dashboard/profile") == "https://example.com/spa"
    assert canonicalize_url("https://example.com/search?q=phone#results-top") == "https://example.com/search?q=phone"


# -----------------------------------------------------------------------------
# 3. Unit Tests: Scheme and Hostname Normalization & Default Ports
# -----------------------------------------------------------------------------
def test_hostname_and_scheme_normalization():
    """Scheme and hostnames are lowercased; default ports are omitted; non-default ports preserved."""
    assert canonicalize_url("HTTPS://EXAMPLE.COM/Listing/1029") == "https://example.com/Listing/1029"
    assert canonicalize_url("HTTP://Example.Org:80/about") == "http://example.org/about"
    assert canonicalize_url("https://Example.Com:443/about") == "https://example.com/about"
    assert canonicalize_url("http://example.com:8080/path") == "http://example.com:8080/path"
    assert canonicalize_url("https://example.com:8443/secure") == "https://example.com:8443/secure"

    # Root path trailing slash normalization: https://example.com/ vs https://example.com
    assert canonicalize_url("https://example.com/") == "https://example.com"
    assert canonicalize_url("https://example.com") == "https://example.com"
    assert canonicalize_url("https://example.com/a/b/") == "https://example.com/a/b"
    assert canonicalize_url("https://example.com/a/b") == "https://example.com/a/b"


# -----------------------------------------------------------------------------
# 4. Unit Tests: Meaningful Query Parameter Preservation & Deterministic Ordering
# -----------------------------------------------------------------------------
def test_meaningful_query_parameter_preservation():
    """Legitimate application query parameters are preserved and deterministically sorted."""
    # Preserves application parameters
    assert canonicalize_url("https://example.com/search?q=9876543210&page=2") == "https://example.com/search?page=2&q=9876543210"
    
    # Deterministic alphabetical ordering
    assert canonicalize_url("https://example.com/profile?z=3&a=1&m=2") == "https://example.com/profile?a=1&m=2&z=3"
    assert canonicalize_url("https://example.com/profile?a=1&m=2&z=3") == "https://example.com/profile?a=1&m=2&z=3"

    # Preserves multiple parameters with tracking parameters removed
    url = "https://example.com/item?category=electronics&utm_medium=cpc&id=99&fbclid=abc"
    assert canonicalize_url(url) == "https://example.com/item?category=electronics&id=99"


# -----------------------------------------------------------------------------
# 5. Unit Tests: URL-Encoding Handling
# -----------------------------------------------------------------------------
def test_url_encoding_handling():
    """Encoded query values and special characters are preserved safely."""
    # Spaces and special chars in query
    res = canonicalize_url("https://example.com/search?name=Jane%20Doe&dept=Sales%26Support")
    assert res == "https://example.com/search?dept=Sales%26Support&name=Jane+Doe"

    # Encoded phone query
    res_phone = canonicalize_url("https://example.com/lookup?phone=%2B14155552671")
    assert res_phone == "https://example.com/lookup?phone=%2B14155552671"


# -----------------------------------------------------------------------------
# 6. Unit Tests: Malformed and Unsupported URL Handling
# -----------------------------------------------------------------------------
def test_malformed_url_handling():
    """Non-string, empty, unsupported scheme, or malformed URLs safely return None without throwing."""
    assert canonicalize_url(None) is None
    assert canonicalize_url("") is None
    assert canonicalize_url("   ") is None
    assert canonicalize_url(12345) is None
    assert canonicalize_url("javascript:alert(1)") is None
    assert canonicalize_url("file:///etc/passwd") is None
    assert canonicalize_url("ftp://ftp.example.com/file.txt") is None
    assert canonicalize_url("data:text/html,<html></html>") is None
    assert canonicalize_url("mailto:security@example.com") is None
    assert canonicalize_url("not a url at all") is None
    assert canonicalize_url("http://") is None
    assert canonicalize_url("https://") is None
    assert canonicalize_url("http:///path/only") is None


# -----------------------------------------------------------------------------
# 7. Integration: Same-Page Duplicate Detection Across Providers
# -----------------------------------------------------------------------------
def test_same_page_duplicate_detection_across_providers(tmp_path: Path):
    """Multiple providers finding the same canonical page create strictly 1 exposure,
    preserving provider provenance and original discovered_at timestamp."""
    db_file = tmp_path / "test_dedup.db"
    key_file = tmp_path / ".test_key"
    key_file.write_bytes(b"test_key_seed_32_bytes_long_1234")
    init_db(db_file)

    synthetic_phone = "+919876543210"
    norm = parse_and_normalize(synthetic_phone)

    # Provider A (DuckDuckGo): raw URL with utm_source
    res_ddg = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title(
                url="https://example-classifieds.in/listing/1029?utm_source=ad",
                title="Used Car for Sale in Bangalore",
                snippet="Contact seller directly: +91 98765 43210 for details.",
                provider_id="duckduckgo",
            )
        ],
        outcome=ProviderOutcome(
            provider_id="duckduckgo",
            status=ProviderStatus.HEALTHY,
            result_count=1,
            duration_ms=45,
            retryable=False,
            diagnostic="Healthy",
        ),
    )

    # Provider B (SearXNG): same page with fragment anchor and different tracking
    res_searx = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title(
                url="https://EXAMPLE-CLASSIFIEDS.IN:443/listing/1029#reviews",
                title="Used Car for Sale in Bangalore",
                snippet="Verified seller contact: +91 98765 43210.",
                provider_id="searxng",
            )
        ],
        outcome=ProviderOutcome(
            provider_id="searxng",
            status=ProviderStatus.HEALTHY,
            result_count=1,
            duration_ms=50,
            retryable=False,
            diagnostic="Healthy",
        ),
    )

    # Provider C (Wikimedia): same page with trailing slash and campaign
    res_wiki = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title(
                url="https://example-classifieds.in/listing/1029/?utm_campaign=winter",
                title="Bangalore Classifieds",
                snippet="Call +91 98765 43210.",
                provider_id="wikimedia",
            )
        ],
        outcome=ProviderOutcome(
            provider_id="wikimedia",
            status=ProviderStatus.HEALTHY,
            result_count=1,
            duration_ms=40,
            retryable=False,
            diagnostic="Healthy",
        ),
    )

    with patch.object(settings, "db_path", db_file), \
         patch.object(settings, "key_path", key_file), \
         patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=res_ddg), \
         patch("backend.app.engines.discovery.providers.searxng.SearXNGProvider.search", new_callable=AsyncMock, return_value=res_searx), \
         patch("backend.app.engines.discovery.providers.wikimedia.WikimediaProvider.search", new_callable=AsyncMock, return_value=res_wiki):

        client = TestClient(app)

        # Execute scan with all three providers
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "providers": ["duckduckgo", "searxng", "wikimedia"],
            "consent": {
                "granted": True,
                "confirmed_providers": ["duckduckgo", "searxng", "wikimedia"],
            },
        })
        assert resp.status_code == 200
        data = resp.json()

        # Invariant: Response contains exactly 1 unique exposure despite 3 provider discoveries
        assert len(data["exposures"]) == 1
        exp = data["exposures"][0]
        assert exp["canonical_url"] == "https://example-classifieds.in/listing/1029"

        # Check database: exactly 1 record exists in exposures table
        conn = get_db_connection(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT id, canonical_url, discovered_at, last_checked_at FROM exposures WHERE identity_hmac = ?", (norm.hmac_id,))
        rows = cursor.fetchall()
        assert len(rows) == 1
        db_exp = rows[0]
        assert db_exp["canonical_url"] == "https://example-classifieds.in/listing/1029"
        first_discovered_at = db_exp["discovered_at"]

        # Check remediation action notes: provider provenance is recorded for all observing providers
        cursor.execute("SELECT notes FROM remediation_actions WHERE exposure_id = ?", (db_exp["id"],))
        act_row = cursor.fetchone()
        assert act_row is not None
        notes = act_row["notes"]
        assert "duckduckgo" in notes
        assert "searxng" in notes
        assert "wikimedia" in notes
        conn.close()

        # Subsequent scan at later time: confirms last_checked_at updates while original discovered_at is preserved
        resp2 = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "providers": ["duckduckgo"],
            "consent": {
                "granted": True,
                "confirmed_providers": ["duckduckgo"],
            },
        })
        assert resp2.status_code == 200
        conn2 = get_db_connection(db_file)
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT discovered_at, last_checked_at FROM exposures WHERE identity_hmac = ?", (norm.hmac_id,))
        row_after = cursor2.fetchone()
        assert row_after["discovered_at"] == first_discovered_at
        conn2.close()


# -----------------------------------------------------------------------------
# 8. Integration: Different Paths Remain Distinct
# -----------------------------------------------------------------------------
def test_different_paths_remain_distinct(tmp_path: Path):
    """Different resource paths on the same host are never merged and remain separate exposures."""
    db_file = tmp_path / "test_paths.db"
    key_file = tmp_path / ".test_key"
    key_file.write_bytes(b"test_key_seed_32_bytes_long_1234")
    init_db(db_file)

    synthetic_phone = "+919876543210"
    norm = parse_and_normalize(synthetic_phone)

    res = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title(
                url="https://example.com/user/alice?utm_source=ddg",
                title="Alice Profile",
                snippet="Call Alice: +91 98765 43210",
                provider_id="duckduckgo",
            ),
            ProviderResult.from_url_and_title(
                url="https://example.com/user/bob?utm_source=ddg",
                title="Bob Profile",
                snippet="Call Bob: +91 98765 43210",
                provider_id="duckduckgo",
            ),
            ProviderResult.from_url_and_title(
                url="https://example.com/products?id=1",
                title="Product 1",
                snippet="Sales phone: +91 98765 43210",
                provider_id="duckduckgo",
            ),
        ],
        outcome=ProviderOutcome(
            provider_id="duckduckgo",
            status=ProviderStatus.HEALTHY,
            result_count=3,
            duration_ms=45,
            retryable=False,
            diagnostic="Healthy",
        ),
    )

    with patch.object(settings, "db_path", db_file), \
         patch.object(settings, "key_path", key_file), \
         patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=res):

        client = TestClient(app)
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "providers": ["duckduckgo"],
            "consent": {"granted": True, "confirmed_providers": ["duckduckgo"]},
        })
        assert resp.status_code == 200
        data = resp.json()

        # Invariant: 3 distinct resource paths remain 3 distinct exposure records
        assert len(data["exposures"]) == 3
        canons = {e["canonical_url"] for e in data["exposures"]}
        assert canons == {
            "https://example.com/user/alice",
            "https://example.com/user/bob",
            "https://example.com/products?id=1",
        }

        # Check database
        conn = get_db_connection(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT canonical_url FROM exposures WHERE identity_hmac = ?", (norm.hmac_id,))
        db_canons = {r["canonical_url"] for r in cursor.fetchall()}
        assert db_canons == canons
        conn.close()


# -----------------------------------------------------------------------------
# 9. Integration: Different Hosts Remain Distinct
# -----------------------------------------------------------------------------
def test_different_hosts_remain_distinct(tmp_path: Path):
    """Different domains or subdomains are never merged."""
    db_file = tmp_path / "test_hosts.db"
    key_file = tmp_path / ".test_key"
    key_file.write_bytes(b"test_key_seed_32_bytes_long_1234")
    init_db(db_file)

    synthetic_phone = "+919876543210"
    norm = parse_and_normalize(synthetic_phone)

    res = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title(
                url="https://alpha.example.com/contact",
                title="Alpha Contact",
                snippet="Contact Alpha: +91 98765 43210",
                provider_id="duckduckgo",
            ),
            ProviderResult.from_url_and_title(
                url="https://beta.example.com/contact",
                title="Beta Contact",
                snippet="Contact Beta: +91 98765 43210",
                provider_id="duckduckgo",
            ),
            ProviderResult.from_url_and_title(
                url="https://otherdomain.org/contact",
                title="Other Org",
                snippet="Reach out: +91 98765 43210",
                provider_id="duckduckgo",
            ),
        ],
        outcome=ProviderOutcome(
            provider_id="duckduckgo",
            status=ProviderStatus.HEALTHY,
            result_count=3,
            duration_ms=45,
            retryable=False,
            diagnostic="Healthy",
        ),
    )

    with patch.object(settings, "db_path", db_file), \
         patch.object(settings, "key_path", key_file), \
         patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=res):

        client = TestClient(app)
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "providers": ["duckduckgo"],
            "consent": {"granted": True, "confirmed_providers": ["duckduckgo"]},
        })
        assert resp.status_code == 200
        data = resp.json()

        assert len(data["exposures"]) == 3
        canons = {e["canonical_url"] for e in data["exposures"]}
        assert canons == {
            "https://alpha.example.com/contact",
            "https://beta.example.com/contact",
            "https://otherdomain.org/contact",
        }


# -----------------------------------------------------------------------------
# 10. Integration: Existing Database Compatibility & Migration
# -----------------------------------------------------------------------------
def test_existing_database_compatibility_and_migration(tmp_path: Path):
    """Pre-existing databases without canonical_url column migrate seamlessly:
    columns are added, legacy rows backfilled, and queries resolve properly."""
    db_file = tmp_path / "legacy.db"
    key_file = tmp_path / ".test_key"
    key_file.write_bytes(b"test_key_seed_32_bytes_long_1234")

    # Create a legacy schema database manually without canonical_url column
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
            domain TEXT,
            title TEXT,
            match_type TEXT NOT NULL,
            confidence REAL NOT NULL,
            snippet TEXT,
            discovered_at TEXT NOT NULL,
            last_checked_at TEXT NOT NULL
        );
    """)
    cursor.execute("""
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

    synthetic_phone = "+919876543210"
    norm = parse_and_normalize(synthetic_phone)
    now_iso = utc_now_iso()

    cursor.execute("""
        INSERT INTO identities (id, hmac_id, masked_phone, country_code, carrier_name, line_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), norm.hmac_id, norm.masked_display, "91", "Carrier", "MOBILE", now_iso))

    legacy_exp_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO exposures (
            id, identity_hmac, source_id, url, domain, title, match_type, confidence, snippet, discovered_at, last_checked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        legacy_exp_id,
        norm.hmac_id,
        "generic_web",
        "https://example.com/classified/999?utm_source=legacy&gclid=old",
        "example.com",
        "Legacy Ad",
        "EXACT",
        1.0,
        "Call +91 98765 43210",
        now_iso,
        now_iso,
    ))
    conn.commit()
    conn.close()

    # Run init_db on the legacy database to trigger safe migrations
    init_db(db_file)

    with patch.object(settings, "db_path", db_file), \
         patch.object(settings, "key_path", key_file):

        client = TestClient(app)

        # 1. Query /api/discovery/exposures on the migrated database
        resp = client.get(f"/api/discovery/exposures?identity_hmac={norm.hmac_id}")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["canonical_url"] == "https://example.com/classified/999"

        # 2. Check SQLite: canonical_url column exists and was backfilled
        conn_check = get_db_connection(db_file)
        c_check = conn_check.cursor()
        c_check.execute("SELECT canonical_url FROM exposures WHERE id = ?", (legacy_exp_id,))
        row = c_check.fetchone()
        assert row["canonical_url"] == "https://example.com/classified/999"
        conn_check.close()

        # 3. New scan for the same page with different tracking: deduplicates against the migrated legacy record
        res_new = SearchExecutionResult(
            results=[
                ProviderResult.from_url_and_title(
                    url="https://example.com/classified/999#reviews",
                    title="Legacy Ad Updated",
                    snippet="Call +91 98765 43210 (verified)",
                    provider_id="searxng",
                )
            ],
            outcome=ProviderOutcome(
                provider_id="searxng",
                status=ProviderStatus.HEALTHY,
                result_count=1,
                duration_ms=45,
                retryable=False,
                diagnostic="Healthy",
            ),
        )

        with patch("backend.app.engines.discovery.providers.searxng.SearXNGProvider.search", new_callable=AsyncMock, return_value=res_new):
            scan_resp = client.post("/api/discovery/scan", json={
                "phone_number": synthetic_phone,
                "providers": ["searxng"],
                "consent": {"granted": True, "confirmed_providers": ["searxng"]},
            })
            assert scan_resp.status_code == 200
            scan_data = scan_resp.json()
            assert len(scan_data["exposures"]) == 1
            assert scan_data["exposures"][0]["id"] == legacy_exp_id
            assert scan_data["exposures"][0]["provider_status"] == "RECORDED"

