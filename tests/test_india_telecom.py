"""Tests for ClearNum India Telecom DLT Header Decoding and Remediation Engine."""

import pytest
from backend.app.engines.discovery.india_telecom import (
    decode_dlt_sender,
    generate_trai_1909_complaint,
    generate_chakshu_escalation,
    generate_dpdp_revocation_notice,
    TELECOM_CIRCLES,
    ACCESS_PROVIDERS,
    INDIAN_BRAND_REGISTRY,
)
from backend.app.engines.remediation.india_registry import (
    get_all_indian_sources,
    get_inventory_summary,
    get_sources_by_category,
    get_indian_source_by_id,
)
from backend.app.engines.remediation.templates import generate_dpdp_act_notice
from backend.app.engines.discovery.normalizer import parse_and_normalize


def test_dlt_prefix_decoding_all_major_operators_and_circles():
    # 1. Airtel Delhi (AD)
    op, circ, brand = decode_dlt_sender("AD-HDFCBK")
    assert op == "Bharti Airtel"
    assert "Delhi" in circ
    assert brand is not None
    assert "HDFC" in brand.brand_name

    # 2. Vi Mumbai (VM)
    op, circ, brand = decode_dlt_sender("VM-SBINB")
    assert op == "Vi (Vodafone Idea)"
    assert "Mumbai" in circ
    assert brand is not None
    assert "SBI" in brand.brand_name

    # 3. Jio Kolkata (JK)
    op, circ, brand = decode_dlt_sender("JK-SWIGGY")
    assert op == "Reliance Jio"
    assert "Kolkata" in circ

    # 4. BSNL Andhra Pradesh (BA)
    op, circ, brand = decode_dlt_sender("BA-FLPKRT")
    assert op == "BSNL"
    assert "Andhra Pradesh" in circ
    assert brand is not None
    assert "Flipkart" in brand.brand_name

    # 5. Tata Chennai (TC)
    op, circ, brand = decode_dlt_sender("TC-TATASK")
    assert op == "Tata Teleservices"
    assert "Chennai" in circ


def test_dlt_brand_catalog_coverage():
    # Verify we have over 70 distinct brand groups registered
    assert len(INDIAN_BRAND_REGISTRY) >= 70

    # Test sample brands across sectors
    brands_to_test = [
        ("HDFCBK", "HDFC Bank"),
        ("ICICIB", "ICICI Bank"),
        ("KOTAKB", "Kotak Mahindra Bank"),
        ("AXISBK", "Axis Bank"),
        ("PAYTM", "Paytm (One97 Communications)"),
        ("PHONEPE", "PhonePe"),
        ("ZOMATO", "Zomato"),
        ("SWIGGY", "Swiggy (Bundl Technologies)"),
        ("ZEPTO", "Zepto (KiranaKart Technologies)"),
        ("BLINKIT", "Blinkit (formerly Grofers)"),
        ("AMAZON", "Amazon India"),
        ("FLPKRT", "Flipkart (Walmart Group)"),
        ("MEESHO", "Meesho (Fashnear Technologies)"),
        ("JIOINF", "Reliance Jio"),
        ("AIRTEL", "Bharti Airtel"),
        ("UBERIN", "Uber India"),
        ("OLACAB", "Ola Cabs"),
        ("MAKEMT", "MakeMyTrip"),
        ("BKMYSH", "BookMyShow"),
    ]

    for code, expected_name in brands_to_test:
        assert code in INDIAN_BRAND_REGISTRY
        assert INDIAN_BRAND_REGISTRY[code].brand_name == expected_name


def test_trai_1909_complaint_syntax_and_deadline():
    complaint = generate_trai_1909_complaint(
        sender="VM-HDFCBK",
        message_body="Get personal loan of Rs 5 Lakhs instantly at 10.5%. Call now.",
        received_timestamp_iso="2026-10-29T10:30:00Z",
    )
    assert complaint["recipient_sms_shortcode"] == "1909"
    assert "COMP TEL NO" in complaint["formal_syntax"]
    assert "VM-HDFCBK" in complaint["formal_syntax"]
    assert "72 hours" in complaint["deadline_info"]
    assert "TCCCPR 2018" in complaint["regulatory_basis"]


def test_chakshu_escalation_workflow():
    escalation = generate_chakshu_escalation(
        sender="+919876543210",
        message_body="Dear customer, your electricity power will be disconnected tonight. Call officer 9876543210.",
    )
    assert escalation["portal_url"] == "https://sancharsaathi.gov.in/sfc/"
    assert "Chakshu" in escalation["portal_name"]
    assert len(escalation["instructions"]) >= 3
    assert any("electricity" in step.lower() or "category" in step.lower() for step in escalation["instructions"])


def test_dpdp_revocation_notice():
    brand = INDIAN_BRAND_REGISTRY["HDFCBK"]
    notice = generate_dpdp_revocation_notice(brand, user_phone_masked="+91 ••••• ••178")
    assert "Digital Personal Data Protection Act" in notice
    assert "Section 6(4)" in notice
    assert "Section 12" in notice
    assert brand.brand_name in notice
    assert brand.grievance_email in notice


def test_india_inventory_112_targets_comprehensive():
    sources = get_all_indian_sources()
    assert len(sources) >= 110

    valid_exec_types = {"verified_live", "manual_browser", "user_assisted", "remediation_only", "automated_lookup"}
    valid_statuses = {"accessible_live", "accessible_manual", "blocked_anti_bot", "restricted_auth", "remediation_only", "verified_live"}

    # Check required fields on every single target
    for s in sources:
        assert s.source_id.strip() != ""
        assert s.name.strip() != ""
        assert s.official_url.startswith("http")
        assert s.category.startswith(("A_", "B_", "C_", "D_", "E_", "F_", "G_", "H_", "I_", "J_"))
        assert s.execution_type in valid_exec_types
        assert s.verification_status in valid_statuses
        assert s.lookup_method.strip() != ""
        assert s.evidence_attribution.strip() != ""
        assert s.last_verified_at.strip() != ""
        assert s.implementation_status.strip() != ""
        assert s.known_limitations.strip() != ""

    summary = get_inventory_summary()
    assert summary["total_sources"] >= 110
    assert len(summary["by_category"]) == 10
    for cat, count in summary["by_category"].items():
        assert count >= 10, f"Category {cat} should have at least 10 sources, got {count}"


def test_indian_normalization_and_dorks():
    # Standard 10-digit Indian mobile
    norm = parse_and_normalize("8106833178", "IN")
    assert norm.is_valid is True
    assert norm.e164 == "+918106833178"
    assert norm.country_code == 91
    assert '"81068-33178"' in norm.search_queries
    assert '"08106833178"' in norm.search_queries
    assert any("81068" in q for q in norm.search_queries)

    # 10-digit with leading zero
    norm_zero = parse_and_normalize("08106833178", "IN")
    assert norm_zero.is_valid is True
    assert norm_zero.e164 == "+918106833178"

    # With +91
    norm_intl = parse_and_normalize("+91 81068 33178", "IN")
    assert norm_intl.is_valid is True
    assert norm_intl.e164 == "+918106833178"
