"""Tests for Privacy-First Search Consent, Transparency Disclosures, and Data Protection Invariants."""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.redactor import redact_text, PhoneRedactingFilter
from backend.app.engines.discovery.providers.base import (
    ProviderResult,
    ProviderStatus,
    ProviderOutcome,
    SearchExecutionResult,
)

client = TestClient(app)


def test_consent_disclosure_endpoint():
    """Verifies the disclosure endpoint exposes each provider, the exact query sent,
    masked preview, purpose, and privacy risk before any search is run."""
    resp = client.get("/api/discovery/disclosure?phone_number=+919876543210&default_region=IN")
    assert resp.status_code == 200
    data = resp.json()

    assert data["default_mode"] == "ASSISTED_MANUAL_SEARCH"
    assert "Privacy Notice" in data["notice"]
    assert "•" in data["masked_phone"]

    providers = {p["provider_id"]: p for p in data["providers"]}
    assert len(providers) == 5

    # Check DuckDuckGo disclosure
    ddg = providers["duckduckgo"]
    assert ddg["provider_name"] == "DuckDuckGo HTML"
    assert "https://html.duckduckgo.com/html/" in ddg["endpoint"]
    assert "web access logs" in ddg["privacy_risk"].lower()
    assert "•" in ddg["masked_query_preview"]

    # Check Wayback CDX disclosure
    wayback = providers["wayback"]
    assert "https://web.archive.org/cdx/search/cdx" in wayback["endpoint"]
    assert "Wildcard" in wayback["data_transmitted"]


def test_backend_enforces_consent_default_denied():
    """CRITICAL SECURITY INVARIANT: Backend must NEVER transmit phone numbers to external
    search engines when consent is missing or denied. Must default to Assisted Manual Search."""
    synthetic_phone = "+919876543210"

    with patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock) as mock_ddg, \
         patch("backend.app.engines.discovery.providers.searxng.SearXNGProvider.search", new_callable=AsyncMock) as mock_searx, \
         patch("backend.app.engines.discovery.providers.wayback.WaybackProvider.search", new_callable=AsyncMock) as mock_wb:

        # 1. Calling scan with NO consent field provided
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "default_region": "IN",
            "providers": ["duckduckgo", "searxng", "wayback"],
        })
        assert resp.status_code == 200
        data = resp.json()

        # Invariant: External providers were NOT called
        mock_ddg.assert_not_called()
        mock_searx.assert_not_called()
        mock_wb.assert_not_called()

        assert data["consent_granted"] is False
        assert data["external_search_conducted"] is False
        assert data["total_found"] == 0
        assert data["manual_dorks_count"] > 0
        assert "Privacy-first default" in data["privacy_notice"]

        # 2. Calling scan with explicit consent=False
        resp2 = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "default_region": "IN",
            "providers": ["duckduckgo"],
            "consent": {"granted": False, "confirmed_providers": []},
            "external_search_consent": False,
        })
        assert resp2.status_code == 200
        data2 = resp2.json()
        mock_ddg.assert_not_called()
        assert data2["consent_granted"] is False


def test_backend_executes_only_authorized_providers_when_consent_granted():
    """Verifies that when explicit consent is provided, only the specifically confirmed
    providers are queried, and rich evidence is returned."""
    synthetic_phone = "+919876543210"

    ddg_res = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title(
                "https://example-classifieds.in/listing/1029?utm_source=ad#top",
                "Vendor Listing",
                "Direct contact: +91 98765 43210 for wholesale quotes.",
                "duckduckgo",
            )
        ],
        outcome=ProviderOutcome("duckduckgo", ProviderStatus.HEALTHY, 1, 45, False, "Success"),
    )

    with patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=ddg_res) as mock_ddg, \
         patch("backend.app.engines.discovery.providers.searxng.SearXNGProvider.search", new_callable=AsyncMock) as mock_searx:

        # Authorize ONLY duckduckgo
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "default_region": "IN",
            "providers": ["duckduckgo", "searxng"],
            "consent": {
                "granted": True,
                "confirmed_providers": ["duckduckgo"],
            },
        })
        assert resp.status_code == 200
        data = resp.json()

        # Invariant: duckduckgo was called; unconfirmed searxng was NOT called
        mock_ddg.assert_called_once()
        mock_searx.assert_not_called()

        assert data["consent_granted"] is True
        assert data["external_search_conducted"] is True
        assert data["total_found"] == 1

        exp = data["exposures"][0]
        # Canonical URL strips tracking query parameters and hash fragments
        assert exp["canonical_url"] == "https://example-classifieds.in/listing/1029"
        assert exp["url"] == "https://example-classifieds.in/listing/1029?utm_source=ad"
        assert exp["match_classification"] in ("CONFIRMED_MATCH", "POSSIBLE_MATCH")
        assert "+91 98765 43210" in exp["matched_representation"]
        assert len(exp["confidence_explanation"]) > 0


def test_cancellation_flow_leaves_no_traces():
    """Simulates a user reviewing the disclosure, opting to cancel, and choosing local manual dorks.
    Zero external queries are made and identity is protected."""
    synthetic_phone = "+919876543210"

    with patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock) as mock_ddg:
        # User reviews disclosure
        disc_resp = client.get(f"/api/discovery/disclosure?phone_number={synthetic_phone}&default_region=IN")
        assert disc_resp.status_code == 200

        # User cancels / selects local manual dorks only
        dorks_resp = client.get(f"/api/discovery/manual-dorks?phone_number={synthetic_phone}&default_region=IN")
        assert dorks_resp.status_code == 200
        dorks = dorks_resp.json()
        assert len(dorks) > 0

        # Zero network calls to search providers
        mock_ddg.assert_not_called()


def test_log_redactor_scrubs_phone_numbers():
    """Verifies that logging redactor actively removes raw phone numbers from messages."""
    raw_log = "Processing query for phone number +91 98765 43210 on duckduckgo"
    redacted = redact_text(raw_log)
    assert "+91 98765 43210" not in redacted
    assert "••" in redacted
