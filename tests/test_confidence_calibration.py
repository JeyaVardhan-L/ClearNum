"""Tests for Phase 5E: Confidence Calibration and Honest Result Interpretation.

Verifies:
1. Exact valid phone matches receive CONFIRMED_MATCH and 1.0 confidence in contact context.
2. Formatted spaced matches receive POSSIBLE_MATCH and calibrated 0.85 confidence.
3. Unformatted continuous digits with telephone keywords receive POSSIBLE_MATCH and 0.80 confidence.
4. Incidental mentions without telephone keywords or in documentation/test fixtures receive INCIDENTAL_MENTION.
5. Partial / ambiguous digit sequences receive INCONCLUSIVE and 0.45 confidence.
6. False-positive sequences (dates, UUIDs, ISBNs, invoice/transaction IDs) are rejected with FALSE_POSITIVE and 0.0 confidence.
7. Search snippet vs. fetched page evidence calibration keeps snippet matches distinct from inspected page bodies.
8. Archived snapshot vs. live page evidence calibration ensures historical records are not conflated with active live exposures.
9. Legacy database record deserialization and honest explanation construction for historical rows.
10. API serialization and frontend contract validation for all newly added calibration metadata.
"""

import uuid
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import get_db_connection, utc_now_iso
from backend.app.engines.discovery.normalizer import parse_and_normalize
from backend.app.engines.discovery.matcher import (
    match_phone_in_text,
    format_evidence_requirement,
    build_calibrated_explanation,
)
from backend.app.engines.discovery.providers.base import (
    ProviderResult,
    ProviderStatus,
    ProviderOutcome,
    SearchExecutionResult,
)

client = TestClient(app)


def test_exact_valid_phone_matches_confidence_calibration():
    """Requirement 1: Exact target telephone representation in a plausible contact context."""
    norm = parse_and_normalize("+919876543210", "IN")
    text = "For customer queries, contact our Mumbai office directly at +91 98765 43210 during business hours."

    res = match_phone_in_text(text, norm, evidence_origin="FETCHED_PAGE")

    assert res.matched is True
    assert res.match_type == "EXACT"
    assert res.confidence == 1.0
    assert res.match_classification == "CONFIRMED_MATCH"
    assert res.matched_tier == "EXACT_CANONICAL"
    assert res.is_example_or_test is False
    assert "+91 98765 43210" in res.matched_text
    assert "Exact canonical telephone representation matched in plausible contact context" in res.confidence_explanation
    assert "Direct live page fetch inspected" in res.verification_requirement


def test_formatted_spaced_matches_confidence_calibration():
    """Requirement 2: Formatted national match without international prefix receives POSSIBLE_MATCH and 0.85 confidence."""
    norm = parse_and_normalize("+919876543210", "IN")
    text = "Please reach our help desk at 98765 43210 to reschedule your appointment."

    res = match_phone_in_text(text, norm, evidence_origin="SEARCH_SNIPPET")

    assert res.matched is True
    assert res.match_type == "PROBABLE"
    assert res.confidence == 0.85
    assert res.match_classification == "POSSIBLE_MATCH"
    assert res.matched_tier == "SPACED_NATIONAL"
    assert "Spaced national format matching telephone numbering plan" in res.confidence_explanation
    assert "Match observed in search snippet only" in res.verification_requirement


def test_unformatted_continuous_digits_with_contact_context():
    """Requirement 3: Continuous 10-digit sequence appearing alongside explicit contact keywords receives POSSIBLE_MATCH and 0.80 confidence."""
    norm = parse_and_normalize("+919876543210", "IN")
    text = "Need immediate assistance? Call 9876543210 to speak with a representative."

    res = match_phone_in_text(text, norm, evidence_origin="FETCHED_PAGE")

    assert res.matched is True
    assert res.match_type == "PROBABLE"
    assert res.confidence == 0.80
    assert res.match_classification == "POSSIBLE_MATCH"
    assert res.matched_tier == "UNFORMATTED_DIGITS"
    assert "alongside explicit telephone/contact keywords" in res.confidence_explanation


def test_incidental_mentions_without_contact_context():
    """Requirement 4: Continuous digits without contact keywords or in sample/doc fixtures receive INCIDENTAL_MENTION."""
    norm = parse_and_normalize("+919876543210", "IN")

    # Case A: Continuous digit sequence without contact label in log/data context
    text_log = "Processing batch queue index 9876543210 completed in 42ms."
    res_log = match_phone_in_text(text_log, norm, evidence_origin="SEARCH_SNIPPET")

    assert res_log.matched is True
    assert res_log.match_type == "PROBABLE"
    assert res_log.confidence == 0.75
    assert res_log.match_classification == "INCIDENTAL_MENTION"
    assert res_log.matched_tier == "UNFORMATTED_DIGITS"
    assert "Continuous digit sequence matching telephone length without explicit contact label" in res_log.confidence_explanation

    # Case B: Number in documentation or dummy sample context
    text_doc = "Developer integration guide: send mock webhook using example dummy phone +91 98765 43210."
    res_doc = match_phone_in_text(text_doc, norm, evidence_origin="FETCHED_PAGE")

    assert res_doc.matched is True
    assert res_doc.match_classification == "INCIDENTAL_MENTION"
    assert res_doc.is_example_or_test is True
    assert res_doc.confidence <= 0.70
    assert "documentation, test fixtures, or sample context" in res_doc.confidence_explanation


def test_partial_ambiguous_digit_sequences():
    """Requirement 5: Ambiguous local digit sequence lacking area code receives INCONCLUSIVE and 0.45 confidence."""
    norm = parse_and_normalize("+14155552671", "US")
    # National number only without area code
    text = "Room extension code: 5552671."

    res = match_phone_in_text(text, norm, evidence_origin="SEARCH_SNIPPET")

    # If detected as weak local fragment
    if res.matched:
        assert res.match_type == "WEAK"
        assert res.confidence == 0.45
        assert res.match_classification == "INCONCLUSIVE"
        assert res.matched_tier == "LOCAL_FRAGMENT"
        assert "Ambiguous local digit sequence" in res.confidence_explanation
    else:
        assert res.match_classification == "INCONCLUSIVE"


def test_false_positive_sequences_rejection():
    """Requirement 6: Dates, UUIDs, ISBNs, and invoice/transaction identifiers are strictly rejected."""
    norm = parse_and_normalize("+919876543210", "IN")

    # Invoice / Transaction ID
    res_inv = match_phone_in_text("Billing notification for INV-9876543210 generated.", norm)
    assert res_inv.matched is False
    assert res_inv.match_type == "FALSE_POSITIVE"
    assert res_inv.confidence == 0.0
    assert res_inv.match_classification == "FALSE_POSITIVE"
    assert any(term in res_inv.confidence_explanation.lower() for term in ("invoice", "transaction", "order"))

    # Date-like false positive
    norm_us = parse_and_normalize("+14155552671", "US")
    res_date = match_phone_in_text("Release timestamp 2024-05-18 confirmed.", norm_us)
    assert res_date.matched is False or res_date.match_type in ("NONE", "FALSE_POSITIVE")
    assert res_date.confidence == 0.0

    # UUID false positive
    res_uuid = match_phone_in_text("Tracing request UUID 14155552-6710-4000-8000-000000000000.", norm_us)
    assert res_uuid.matched is False or res_uuid.match_type in ("NONE", "FALSE_POSITIVE")
    assert res_uuid.confidence == 0.0


def test_search_snippet_vs_fetched_page_evidence_calibration():
    """Requirement 7: Evidence origin is kept separate from match classification; snippet matches are not conflated with fetched page bodies."""
    norm = parse_and_normalize("+919876543210", "IN")
    content = "Direct contact helpline: +91 98765 43210."

    res_snippet = match_phone_in_text(content, norm, evidence_origin="SEARCH_SNIPPET")
    res_fetched = match_phone_in_text(content, norm, evidence_origin="FETCHED_PAGE")

    # Both recognize exact phone number
    assert res_snippet.match_classification == "CONFIRMED_MATCH"
    assert res_fetched.match_classification == "CONFIRMED_MATCH"
    assert res_snippet.confidence == 1.0
    assert res_fetched.confidence == 1.0

    # Evidence origin remains distinct and explicit
    assert res_snippet.evidence_origin == "SEARCH_SNIPPET"
    assert res_fetched.evidence_origin == "FETCHED_PAGE"

    # Limitations are honestly communicated
    assert "Match observed in search snippet only" in res_snippet.verification_requirement
    assert "Direct live page fetch inspected" in res_fetched.verification_requirement
    assert "live web page body has not been inspected" in res_snippet.confidence_explanation
    assert "Confirms matching text is present in current web page body" in res_fetched.confidence_explanation


def test_archived_snapshot_vs_live_page_evidence_calibration():
    """Requirement 8: Archived snapshots are explicitly flagged as historical and not conflated with active live exposures."""
    norm = parse_and_normalize("+919876543210", "IN")
    content = "Executive office phone: +91 98765 43210."

    res_archived = match_phone_in_text(content, norm, evidence_origin="ARCHIVED_SNAPSHOT")
    res_live = match_phone_in_text(content, norm, evidence_origin="FETCHED_PAGE")

    assert res_archived.evidence_origin == "ARCHIVED_SNAPSHOT"
    assert res_live.evidence_origin == "FETCHED_PAGE"

    assert "Historical archive snapshot (Wayback Machine)" in res_archived.verification_requirement
    assert "Live page re-verification is required to confirm whether exposure persists today" in res_archived.verification_requirement
    assert "Direct live page fetch inspected" in res_live.verification_requirement


def test_legacy_database_record_deserialization_and_honest_explanations():
    """Requirement 9: Historical database records deserialize with calibrated match classifications and honest origin explanations."""
    norm = parse_and_normalize("+919876543210", "IN")
    now_iso = utc_now_iso()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Pre-populate identities table
    cursor.execute("""
        INSERT OR REPLACE INTO identities (id, hmac_id, masked_phone, country_code, carrier_name, line_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), norm.hmac_id, norm.masked_display, "91", "Telecom", "MOBILE", now_iso))

    records = [
        (str(uuid.uuid4()), "https://example.com/canonical-exact", "https://example.com/canonical-exact", "example.com", "Exact Match", "EXACT", 1.0, "FETCHED_PAGE", "+91 98765 43210"),
        (str(uuid.uuid4()), "https://example.com/canonical-spaced", "https://example.com/canonical-spaced", "example.com", "Spaced Match", "PROBABLE", 0.85, "SEARCH_SNIPPET", "98765 43210"),
        (str(uuid.uuid4()), "https://example.com/canonical-context", "https://example.com/canonical-context", "example.com", "Context Match", "PROBABLE", 0.80, "FETCHED_PAGE", "Call 9876543210"),
        (str(uuid.uuid4()), "https://example.com/canonical-incidental", "https://example.com/canonical-incidental", "example.com", "Incidental Match", "PROBABLE", 0.75, "SEARCH_SNIPPET", "Record 9876543210 in queue"),
        (str(uuid.uuid4()), "https://example.com/canonical-weak", "https://example.com/canonical-weak", "example.com", "Weak Match", "WEAK", 0.45, "UNKNOWN", "43210"),
        (str(uuid.uuid4()), "https://archive.org/web/historical", "https://archive.org/web/historical", "archive.org", "Archive Match", "EXACT", 1.0, "ARCHIVED_SNAPSHOT", "+91 98765 43210"),
    ]

    for exp_id, url, canon_url, domain, title, m_type, conf, ev_orig, snip in records:
        cursor.execute("""
            INSERT INTO exposures (
                id, identity_hmac, source_id, url, canonical_url, evidence_origin, domain, title, match_type, confidence, snippet, discovered_at, last_checked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (exp_id, norm.hmac_id, "generic_web", url, canon_url, ev_orig, domain, title, m_type, conf, snip, now_iso, now_iso))

    conn.commit()
    conn.close()

    resp = client.get(f"/api/discovery/exposures?identity_hmac={norm.hmac_id}")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 6

    items_by_url = {it["url"]: it for it in items}

    # Record 1: Exact + Fetched
    rec_exact = items_by_url["https://example.com/canonical-exact"]
    assert rec_exact["match_classification"] == "CONFIRMED_MATCH"
    assert rec_exact["matched_tier"] == "EXACT_CANONICAL"
    assert rec_exact["confidence"] == 1.0
    assert "Direct live page fetch inspected" in rec_exact["verification_requirement"]

    # Record 2: Spaced + Snippet
    rec_spaced = items_by_url["https://example.com/canonical-spaced"]
    assert rec_spaced["match_classification"] == "POSSIBLE_MATCH"
    assert rec_spaced["matched_tier"] == "SPACED_NATIONAL"
    assert rec_spaced["confidence"] == 0.85
    assert "Match observed in search snippet only" in rec_spaced["verification_requirement"]

    # Record 3: Contextual 0.80
    rec_ctx = items_by_url["https://example.com/canonical-context"]
    assert rec_ctx["match_classification"] == "POSSIBLE_MATCH"
    assert rec_ctx["matched_tier"] == "UNFORMATTED_DIGITS"
    assert rec_ctx["confidence"] == 0.80

    # Record 4: Incidental 0.75
    rec_inc = items_by_url["https://example.com/canonical-incidental"]
    assert rec_inc["match_classification"] == "INCIDENTAL_MENTION"
    assert rec_inc["matched_tier"] == "UNFORMATTED_DIGITS"
    assert rec_inc["confidence"] == 0.75

    # Record 5: Weak 0.45
    rec_weak = items_by_url["https://example.com/canonical-weak"]
    assert rec_weak["match_classification"] == "INCONCLUSIVE"
    assert rec_weak["matched_tier"] == "LOCAL_FRAGMENT"
    assert rec_weak["confidence"] == 0.45

    # Record 6: Archived 1.0
    rec_arch = items_by_url["https://archive.org/web/historical"]
    assert rec_arch["match_classification"] == "CONFIRMED_MATCH"
    assert rec_arch["evidence_origin"] == "ARCHIVED_SNAPSHOT"
    assert "Historical archive snapshot" in rec_arch["verification_requirement"]


def test_api_serialization_and_frontend_contract_validation():
    """Requirement 10: API serialization enforces complete calibrated metadata contract."""
    synthetic_phone = "+919876543210"

    mock_search_res = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title(
                "https://directory.example.com/contact-profile",
                "Verified Professional Directory",
                "Contact executive direct line: +91 98765 43210 for inquiries.",
                "duckduckgo",
                evidence_origin="SEARCH_SNIPPET",
            ),
        ],
        outcome=ProviderOutcome("duckduckgo", ProviderStatus.HEALTHY, 1, 45, False, "Success"),
    )

    with patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=mock_search_res):
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "default_region": "IN",
            "providers": ["duckduckgo"],
            "consent": {"granted": True, "confirmed_providers": ["duckduckgo"]},
        })
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_found"] == 1
        exposure = data["exposures"][0]

        # Verify full API contract for Phase 5E
        assert exposure["match_classification"] == "CONFIRMED_MATCH"
        assert exposure["confidence"] == 1.0
        assert exposure["matched_tier"] == "EXACT_CANONICAL"
        assert exposure["evidence_origin"] == "SEARCH_SNIPPET"
        assert len(exposure["confidence_explanation"]) > 0
        assert len(exposure["verification_requirement"]) > 0
        assert "Match observed in search snippet only" in exposure["verification_requirement"]
        assert "+91 98765 43210" in exposure["matched_representation"]
