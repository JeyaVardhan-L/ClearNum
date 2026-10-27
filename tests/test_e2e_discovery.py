"""Deterministic end-to-end discovery pipeline validation.
Tests complete pipeline flows across normalization, multi-provider execution,
deduplication, matching tiers, database persistence, partial/total failure handling,
audit trails, and verification rescans using controlled synthetic data.
"""

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import init_db, purge_all_data, get_db_connection
from backend.app.engines.discovery.normalizer import parse_and_normalize
from backend.app.engines.discovery.providers.base import (
    ProviderResult,
    ProviderStatus,
    ProviderOutcome,
    SearchExecutionResult,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    purge_all_data()
    yield
    purge_all_data()


@pytest.mark.asyncio
async def test_e2e_discovery_pipeline_full_lifecycle():
    """Full lifecycle: normalization -> multi-provider dispatch -> deduplication ->
    database persistence -> remediation transition -> audit trail -> verification rescan.
    """
    synthetic_phone = "+14155552671"

    # Mock provider results:
    # Notice: example.com/leak1 is returned by both DDG and SearXNG with different anchors
    ddg_res = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title("https://example.com/leak1#top", "Leak 1", "Contact: +1 415-555-2671", "duckduckgo"),
            ProviderResult.from_url_and_title("https://fastpeoplesearch.com/person1", "Person 1", "(415) 555-2671", "duckduckgo"),
        ],
        outcome=ProviderOutcome("duckduckgo", ProviderStatus.HEALTHY, 2, 45, False, "Completed successfully"),
    )
    searx_res = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title("https://example.com/leak1#comments", "Leak 1 Dup", "Found: 415.555.2671", "searxng"),
        ],
        outcome=ProviderOutcome("searxng", ProviderStatus.HEALTHY, 1, 60, False, "Completed successfully"),
    )
    wiki_res = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title("https://en.wikipedia.org/wiki/Talk:Test", "Wiki Talk", "Reach +14155552671", "wikimedia"),
        ],
        outcome=ProviderOutcome("wikimedia", ProviderStatus.HEALTHY, 1, 30, False, "Completed successfully"),
    )
    hn_res = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title("https://news.ycombinator.com/item?id=884", "HN Hiring", "+1 415 555 2671 mobile", "hackernews"),
        ],
        outcome=ProviderOutcome("hackernews", ProviderStatus.HEALTHY, 1, 25, False, "Completed successfully"),
    )
    wayback_res = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title("https://web.archive.org/web/20220101/https://pastebin.com/old", "Archived Paste", "Phone: +14155552671", "wayback"),
        ],
        outcome=ProviderOutcome("wayback", ProviderStatus.HEALTHY, 1, 40, False, "Completed successfully"),
    )

    with patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=ddg_res), \
         patch("backend.app.engines.discovery.providers.searxng.SearXNGProvider.search", new_callable=AsyncMock, return_value=searx_res), \
         patch("backend.app.engines.discovery.providers.wikimedia.WikimediaProvider.search", new_callable=AsyncMock, return_value=wiki_res), \
         patch("backend.app.engines.discovery.providers.hackernews.HackerNewsProvider.search", new_callable=AsyncMock, return_value=hn_res), \
         patch("backend.app.engines.discovery.providers.wayback.WaybackProvider.search", new_callable=AsyncMock, return_value=wayback_res):

        payload = {
            "phone_number": synthetic_phone,
            "default_region": "US",
            "providers": ["duckduckgo", "searxng", "wikimedia", "hackernews", "wayback"],
            "target_urls": [],
        }

        resp = client.post("/api/discovery/scan", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        # Deduplication check: 6 raw results with 1 duplicate -> exactly 5 distinct exposures
        assert data["total_found"] == 5
        assert data["scan_status"] == "complete"
        assert len(data["provider_outcomes"]) == 5

        # Verify identity in DB
        identity_hmac = data["identity_hmac"]
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT masked_phone FROM identities WHERE hmac_id = ?", (identity_hmac,))
        ident = c.fetchone()
        assert ident is not None
        assert "•" in ident["masked_phone"]

        # Verify exposures stored in DB
        c.execute("SELECT id, url, domain, match_type FROM exposures WHERE identity_hmac = ?", (identity_hmac,))
        exp_rows = c.fetchall()
        assert len(exp_rows) == 5

        # Verify remediation actions created
        c.execute("SELECT id, exposure_id, status FROM remediation_actions WHERE identity_hmac = ?", (identity_hmac,))
        act_rows = c.fetchall()
        # Select action where broker registry provides ACTION_AVAILABLE status
        target_action = next(a for a in act_rows if a["status"] == "ACTION_AVAILABLE")
        target_exposure_id = target_action["exposure_id"]

        # Step 2: Transition remediation state
        trans_req = {
            "exposure_id": target_exposure_id,
            "identity_hmac": identity_hmac,
            "next_state": "SUBMITTED",
            "submission_ref": "REF-SYNTHETIC-12345",
            "notes": "Submitted official opt-out form.",
        }
        trans_resp = client.post("/api/remediation/transition", json=trans_req)
        assert trans_resp.status_code == 200
        assert trans_resp.json()["new_status"] == "SUBMITTED"

        # Verify audit log entry and remediation action record
        c.execute("SELECT from_state, to_state, evidence_notes FROM action_audit_log WHERE action_id = ?", (target_action["id"],))
        audit = c.fetchone()
        assert audit is not None
        assert audit["to_state"] == "SUBMITTED"
        assert audit["evidence_notes"] == "Submitted official opt-out form."

        c.execute("SELECT submission_ref FROM remediation_actions WHERE id = ?", (target_action["id"],))
        assert c.fetchone()["submission_ref"] == "REF-SYNTHETIC-12345"
        conn.close()

        # Step 3: Verification Rescan
        c_exp = next(e for e in data["exposures"] if e["id"] == target_exposure_id)
        with patch("backend.app.engines.prevention.verifier.safe_fetch_url", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = (404, "Not Found", {})
            verify_payload = {
                "exposure_id": target_exposure_id,
                "url": c_exp["url"],
                "phone_number": synthetic_phone,
                "default_region": "US",
            }
            v_resp = client.post("/api/remediation/verify", json=verify_payload)
            assert v_resp.status_code == 200
            v_data = v_resp.json()
            assert v_data["status"] == "NO_LONGER_VISIBLE_AT_CHECKED_URL"
            assert v_data["http_status_code"] == 404


def test_e2e_discovery_partial_failure():
    """Validates pipeline behavior when some providers rate limit or time out,
    ensuring partial_failure status and healthy findings are retained.
    """
    synthetic_phone = "+14155552671"

    ddg_res = SearchExecutionResult(
        results=[],
        outcome=ProviderOutcome("duckduckgo", ProviderStatus.RATE_LIMITED, 0, 50, True, "Rate limited (HTTP 429)"),
    )
    wiki_res = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title("https://en.wikipedia.org/wiki/Directory", "Directory", "+14155552671", "wikimedia"),
        ],
        outcome=ProviderOutcome("wikimedia", ProviderStatus.HEALTHY, 1, 35, False, "Completed successfully"),
    )

    with patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=ddg_res), \
         patch("backend.app.engines.discovery.providers.wikimedia.WikimediaProvider.search", new_callable=AsyncMock, return_value=wiki_res):

        payload = {
            "phone_number": synthetic_phone,
            "default_region": "US",
            "providers": ["duckduckgo", "wikimedia"],
            "target_urls": [],
        }

        resp = client.post("/api/discovery/scan", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["scan_status"] == "partial_failure"
        assert data["total_found"] == 1
        assert len(data["provider_outcomes"]) == 2

        outcomes_by_id = {p["provider_id"]: p for p in data["provider_outcomes"]}
        assert outcomes_by_id["duckduckgo"]["status"] == "rate_limited"
        assert outcomes_by_id["duckduckgo"]["retryable"] is True
        assert outcomes_by_id["wikimedia"]["status"] == "healthy"


def test_e2e_discovery_all_providers_failed():
    """Validates truthful scan_status='all_failed' when all chosen providers fail."""
    synthetic_phone = "+14155552671"

    ddg_res = SearchExecutionResult(
        results=[],
        outcome=ProviderOutcome("duckduckgo", ProviderStatus.RATE_LIMITED, 0, 20, True, "Rate limited"),
    )
    searx_res = SearchExecutionResult(
        results=[],
        outcome=ProviderOutcome("searxng", ProviderStatus.UNREACHABLE, 0, 80, True, "Connection timeout"),
    )

    with patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=ddg_res), \
         patch("backend.app.engines.discovery.providers.searxng.SearXNGProvider.search", new_callable=AsyncMock, return_value=searx_res):

        payload = {
            "phone_number": synthetic_phone,
            "default_region": "US",
            "providers": ["duckduckgo", "searxng"],
            "target_urls": [],
        }

        resp = client.post("/api/discovery/scan", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["scan_status"] == "all_failed"
        assert data["total_found"] == 0
        assert len(data["provider_outcomes"]) == 2


def test_e2e_discovery_custom_target_ssrf_and_matching():
    """Validates custom target URL processing with SSRF safe fetching and context matching."""
    synthetic_phone = "+14155552671"

    # Mock safe_fetch_url for valid target and invalid target
    async def mock_fetch(url: str, *args, **kwargs):
        if "valid-classifieds" in url:
            return 200, "<html><body>Contact seller at (415) 555-2671 for details.</body></html>", {}
        elif "false-positive" in url:
            return 200, "<html><body>Tracking Number: 2024-05-14-9988-1122</body></html>", {}
        return 500, "Server Error", {}

    with patch("backend.app.api.routes.safe_fetch_url", side_effect=mock_fetch):
        payload = {
            "phone_number": synthetic_phone,
            "default_region": "US",
            "providers": [],
            "target_urls": [
                "https://valid-classifieds.example.org/item/42",
                "https://false-positive.example.org/tracking",
            ],
        }

        resp = client.post("/api/discovery/scan", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        # Only the valid target should produce an exposure, false positive is rejected
        assert data["total_found"] == 1
        assert "valid-classifieds.example.org" in data["exposures"][0]["url"]
        assert data["exposures"][0]["match_type"] in ("EXACT", "PROBABLE")
