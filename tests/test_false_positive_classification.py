"""Regression tests for Phase 5B: Critical False-Positive Classification Fix.

Verifies:
1. Invoice numbers (e.g. INV-9876543210) cannot become probable exposures.
2. Transaction identifiers (e.g. TXN..., ORDER...) cannot become probable exposures.
3. Date-like numeric sequences cannot become probable exposures.
4. Valid phone-number matches retain correct classification and confidence.
5. Possible matches retain their actual confidence.
6. Inconclusive results are not promoted to probable or confirmed exposures.
7. Rejected candidates do not appear in normal exposure listing.
8. Existing database records and API response contracts remain compatible.
"""

import uuid
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import get_db_connection, utc_now_iso
from backend.app.engines.discovery.normalizer import parse_and_normalize
from backend.app.engines.discovery.providers.base import (
    ProviderResult,
    ProviderStatus,
    ProviderOutcome,
    SearchExecutionResult,
)

client = TestClient(app)


def test_invoice_number_cannot_become_probable_exposure():
    """Requirement 1: An invoice number such as INV-9876543210 cannot become a probable exposure."""
    synthetic_phone = "+919876543210"

    invoice_res = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title(
                "https://billing-portal.example.com/inv/9876543210",
                "Customer Invoice Portal",
                "Please find attached billing statement for Invoice INV-9876543210. Due date in 15 days.",
                "duckduckgo",
            )
        ],
        outcome=ProviderOutcome("duckduckgo", ProviderStatus.HEALTHY, 1, 35, False, "Success"),
    )

    with patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=invoice_res):
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "default_region": "IN",
            "providers": ["duckduckgo"],
            "consent": {"granted": True, "confirmed_providers": ["duckduckgo"]},
        })
        assert resp.status_code == 200
        data = resp.json()

        # Invariant: Invoice false positive was rejected and did NOT become an exposure
        assert data["total_found"] == 0
        assert len(data["exposures"]) == 0

        # Verify database isolation: zero exposures inserted
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM exposures WHERE identity_hmac = ?", (data["identity_hmac"],))
        rows = cursor.fetchall()
        conn.close()
        assert len(rows) == 0

        # Verify exposures endpoint returns 0
        exp_resp = client.get(f"/api/discovery/exposures?identity_hmac={data['identity_hmac']}")
        assert exp_resp.status_code == 200
        assert len(exp_resp.json()) == 0


def test_transaction_identifier_cannot_become_probable_exposure():
    """Requirement 2: A transaction identifier cannot become a probable exposure."""
    synthetic_phone = "+919876543210"

    txn_res = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title(
                "https://payment-gateway.example.com/tx/1001",
                "UPI Payment Confirmation",
                "Transaction reference TXN9876543210 of INR 450.00 processed successfully.",
                "duckduckgo",
            ),
            ProviderResult.from_url_and_title(
                "https://store.example.com/orders/track",
                "Order Tracking System",
                "Order ORDER-9876543210 dispatched via Express Logistics.",
                "searxng",
            ),
        ],
        outcome=ProviderOutcome("duckduckgo", ProviderStatus.HEALTHY, 2, 40, False, "Success"),
    )

    with patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=txn_res):
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "default_region": "IN",
            "providers": ["duckduckgo"],
            "consent": {"granted": True, "confirmed_providers": ["duckduckgo"]},
        })
        assert resp.status_code == 200
        data = resp.json()

        # Invariant: Transaction and Order codes are rejected
        assert data["total_found"] == 0
        assert len(data["exposures"]) == 0

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM exposures WHERE identity_hmac = ?", (data["identity_hmac"],))
        assert len(cursor.fetchall()) == 0
        conn.close()


def test_date_like_sequence_cannot_become_probable_exposure():
    """Requirement 3: A date-like numeric sequence cannot become a probable exposure."""
    synthetic_phone = "+14155552671"

    date_res = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title(
                "https://engineering.example.org/release-schedule",
                "Release Engineering Calendar",
                "Maintenance scheduled on 2024-05-18 with follow-up deployment on 2024-05-19 by release-bot.",
                "duckduckgo",
            )
        ],
        outcome=ProviderOutcome("duckduckgo", ProviderStatus.HEALTHY, 1, 20, False, "Success"),
    )

    with patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=date_res):
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "default_region": "US",
            "providers": ["duckduckgo"],
            "consent": {"granted": True, "confirmed_providers": ["duckduckgo"]},
        })
        assert resp.status_code == 200
        data = resp.json()

        # Invariant: Date sequence rejected
        assert data["total_found"] == 0
        assert len(data["exposures"]) == 0


def test_valid_phone_match_retains_correct_classification_and_confidence():
    """Requirement 4: A valid phone-number match retains its correct classification and confidence."""
    synthetic_phone = "+919876543210"

    valid_res = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title(
                "https://corporate.example.in/contact-us",
                "Corporate Directory",
                "Official Toll-Free Support: +91 98765 43210 (Mon-Fri 9am-6pm IST).",
                "duckduckgo",
            )
        ],
        outcome=ProviderOutcome("duckduckgo", ProviderStatus.HEALTHY, 1, 30, False, "Success"),
    )

    with patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=valid_res):
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "default_region": "IN",
            "providers": ["duckduckgo"],
            "consent": {"granted": True, "confirmed_providers": ["duckduckgo"]},
        })
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_found"] == 1
        exp = data["exposures"][0]

        # Valid exact match retains exact classification and confidence
        assert exp["match_type"] == "EXACT"
        assert exp["confidence"] == 1.0
        assert exp["match_classification"] == "CONFIRMED_MATCH"
        assert exp["is_example_or_test"] is False
        assert "+91 98765 43210" in exp["matched_representation"]

        # Verify stored record in DB and list endpoint
        exp_resp = client.get(f"/api/discovery/exposures?identity_hmac={data['identity_hmac']}")
        assert exp_resp.status_code == 200
        stored_items = exp_resp.json()
        assert len(stored_items) == 1
        assert stored_items[0]["match_type"] == "EXACT"
        assert stored_items[0]["confidence"] == 1.0
        assert stored_items[0]["match_classification"] == "CONFIRMED_MATCH"


def test_possible_match_retains_actual_confidence():
    """Requirement 5: A possible match retains its actual confidence (not forced to default 0.75)."""
    synthetic_phone = "+919876543210"

    # Spaced national format: matcher yields confidence=0.85
    possible_res = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title(
                "https://marketplace.example.in/item/5512",
                "Used Car Listing",
                "Vehicle for inspection in Bengaluru. Please call 98765 43210 to arrange viewing.",
                "duckduckgo",
            )
        ],
        outcome=ProviderOutcome("duckduckgo", ProviderStatus.HEALTHY, 1, 30, False, "Success"),
    )

    with patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=possible_res):
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "default_region": "IN",
            "providers": ["duckduckgo"],
            "consent": {"granted": True, "confirmed_providers": ["duckduckgo"]},
        })
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_found"] == 1
        exp = data["exposures"][0]

        # Retains matcher's actual confidence for spaced format (0.85, NOT defaulted 0.75)
        assert exp["match_type"] == "PROBABLE"
        assert exp["confidence"] == 0.85
        assert exp["match_classification"] == "POSSIBLE_MATCH"

        # Verify stored exposure retains actual confidence
        exp_resp = client.get(f"/api/discovery/exposures?identity_hmac={data['identity_hmac']}")
        stored_items = exp_resp.json()
        assert len(stored_items) == 1
        assert stored_items[0]["match_type"] == "PROBABLE"
        assert stored_items[0]["confidence"] == 0.85
        assert stored_items[0]["match_classification"] == "POSSIBLE_MATCH"


def test_inconclusive_result_is_not_promoted():
    """Requirement 6: Inconclusive results are never promoted to probable or confirmed exposures."""
    synthetic_phone = "+919876543210"

    # 1. Candidate where search engine returned a page, but snippet has no matching phone number
    unmatched_res = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title(
                "https://community.example.com/topic/general",
                "Community Guidelines",
                "Welcome to the general discussions on technology, open source, and privacy protocols.",
                "duckduckgo",
            )
        ],
        outcome=ProviderOutcome("duckduckgo", ProviderStatus.HEALTHY, 1, 25, False, "Success"),
    )

    with patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=unmatched_res):
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "default_region": "IN",
            "providers": ["duckduckgo"],
            "consent": {"granted": True, "confirmed_providers": ["duckduckgo"]},
        })
        assert resp.status_code == 200
        data = resp.json()

        # Invariant: Unmatched result is NOT promoted to a probable exposure
        assert data["total_found"] == 0
        assert len(data["exposures"]) == 0

    # 2. Candidate with weak ambiguous local digits lacking area code / country code
    # Target is US number +14155552671. Text only has 7-digit local number "5552671" without area code
    weak_res = SearchExecutionResult(
        results=[
            ProviderResult.from_url_and_title(
                "https://forum.example.org/p/88",
                "Internal Extension List",
                "Dial ext 5552671 on local branch PBX switchboard.",
                "duckduckgo",
            )
        ],
        outcome=ProviderOutcome("duckduckgo", ProviderStatus.HEALTHY, 1, 25, False, "Success"),
    )

    with patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=weak_res):
        resp2 = client.post("/api/discovery/scan", json={
            "phone_number": "+14155552671",
            "default_region": "US",
            "providers": ["duckduckgo"],
            "consent": {"granted": True, "confirmed_providers": ["duckduckgo"]},
        })
        assert resp2.status_code == 200
        data2 = resp2.json()

        # If weak local fragments cannot form a valid 10-digit number, they are not promoted
        assert data2["total_found"] == 0


def test_rejected_candidates_do_not_appear_in_exposure_listing():
    """Requirement 7: Rejected candidates do not appear in the normal exposure listing."""
    synthetic_phone = "+919876543210"

    mixed_res = SearchExecutionResult(
        results=[
            # Candidate 1: Real confirmed phone exposure
            ProviderResult.from_url_and_title(
                "https://public-roster.example.in/members",
                "Public Member Roster",
                "Secretary: +91 98765 43210 (Direct Mobile).",
                "duckduckgo",
            ),
            # Candidate 2: Invoice false positive
            ProviderResult.from_url_and_title(
                "https://erp.example.in/invoices/9876543210",
                "Vendor ERP",
                "Invoice INV-9876543210 generated for customer.",
                "duckduckgo",
            ),
            # Candidate 3: Transaction false positive
            ProviderResult.from_url_and_title(
                "https://bank.example.in/receipt/9876543210",
                "NEFT Transfer Receipt",
                "Ref TXN9876543210 settled via clearing house.",
                "duckduckgo",
            ),
            # Candidate 4: Unrelated snippet
            ProviderResult.from_url_and_title(
                "https://blog.example.in/welcome",
                "Tech Blog",
                "Discussion regarding telecommunications regulatory policies.",
                "duckduckgo",
            ),
        ],
        outcome=ProviderOutcome("duckduckgo", ProviderStatus.HEALTHY, 4, 60, False, "Success"),
    )

    with patch("backend.app.engines.discovery.providers.duckduckgo.DuckDuckGoProvider.search", new_callable=AsyncMock, return_value=mixed_res):
        resp = client.post("/api/discovery/scan", json={
            "phone_number": synthetic_phone,
            "default_region": "IN",
            "providers": ["duckduckgo"],
            "consent": {"granted": True, "confirmed_providers": ["duckduckgo"]},
        })
        assert resp.status_code == 200
        data = resp.json()

        # Exactly 1 exposure found (the legitimate phone number)
        assert data["total_found"] == 1
        assert len(data["exposures"]) == 1
        assert "public-roster.example.in" in data["exposures"][0]["url"]

        # Verify listing endpoint only returns the 1 valid exposure
        exp_resp = client.get(f"/api/discovery/exposures?identity_hmac={data['identity_hmac']}")
        assert exp_resp.status_code == 200
        exposures = exp_resp.json()
        assert len(exposures) == 1
        assert "public-roster.example.in" in exposures[0]["url"]

        # Verify rejected URLs never exist in exposures listing
        urls = [e["url"] for e in exposures]
        assert "https://erp.example.in/invoices/9876543210" not in urls
        assert "https://bank.example.in/receipt/9876543210" not in urls
        assert "https://blog.example.in/welcome" not in urls


def test_existing_database_records_and_api_contracts_compatible():
    """Requirement 8: Existing database records and API response contracts remain compatible."""
    synthetic_phone = "+14155552671"
    norm = parse_and_normalize(synthetic_phone, "US")

    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = utc_now_iso()

    # Create identity
    cursor.execute("""
        INSERT INTO identities (id, hmac_id, masked_phone, country_code, carrier_name, line_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(hmac_id) DO NOTHING
    """, (str(uuid.uuid4()), norm.hmac_id, norm.masked_display, "1", "Carrier", "MOBILE", now_iso))

    # Insert 4 historical/existing records representing all valid database match_type tiers
    records = [
        (str(uuid.uuid4()), "https://example.com/exact", "example.com", "Exact Match Record", "EXACT", 1.0, "...+1 415-555-2671..."),
        (str(uuid.uuid4()), "https://example.com/probable", "example.com", "Spaced Match Record", "PROBABLE", 0.85, "...415 555 2671..."),
        (str(uuid.uuid4()), "https://example.com/incidental", "example.com", "Incidental Match Record", "PROBABLE", 0.75, "...4155552671..."),
        (str(uuid.uuid4()), "https://example.com/weak", "example.com", "Weak Match Record", "WEAK", 0.45, "...5552671..."),
    ]

    for exp_id, url, domain, title, m_type, conf, snip in records:
        cursor.execute("""
            INSERT INTO exposures (
                id, identity_hmac, source_id, url, domain, title, match_type, confidence, snippet, discovered_at, last_checked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (exp_id, norm.hmac_id, "generic_web", url, domain, title, m_type, conf, snip, now_iso, now_iso))

    conn.commit()
    conn.close()

    # Query /api/discovery/exposures
    exp_resp = client.get(f"/api/discovery/exposures?identity_hmac={norm.hmac_id}")
    assert exp_resp.status_code == 200
    items = exp_resp.json()
    assert len(items) == 4

    items_by_url = {it["url"]: it for it in items}

    # Record 1: EXACT -> CONFIRMED_MATCH
    rec_exact = items_by_url["https://example.com/exact"]
    assert rec_exact["match_type"] == "EXACT"
    assert rec_exact["confidence"] == 1.0
    assert rec_exact["match_classification"] == "CONFIRMED_MATCH"

    # Record 2: PROBABLE (conf=0.85) -> POSSIBLE_MATCH
    rec_prob = items_by_url["https://example.com/probable"]
    assert rec_prob["match_type"] == "PROBABLE"
    assert rec_prob["confidence"] == 0.85
    assert rec_prob["match_classification"] == "POSSIBLE_MATCH"

    # Record 3: PROBABLE (conf=0.75) -> INCIDENTAL_MENTION
    rec_inc = items_by_url["https://example.com/incidental"]
    assert rec_inc["match_type"] == "PROBABLE"
    assert rec_inc["confidence"] == 0.75
    assert rec_inc["match_classification"] == "INCIDENTAL_MENTION"

    # Record 4: WEAK -> INCONCLUSIVE
    rec_weak = items_by_url["https://example.com/weak"]
    assert rec_weak["match_type"] == "WEAK"
    assert rec_weak["confidence"] == 0.45
    assert rec_weak["match_classification"] == "INCONCLUSIVE"
