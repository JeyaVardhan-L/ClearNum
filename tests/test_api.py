"""Integration tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["zero_cost_mode"] is True


def test_phone_parse_endpoint():
    resp = client.post("/api/identity/parse", json={"phone_number": "+14155552671", "default_region": "US"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_possible"] is True
    assert data["e164"] == "+14155552671"
    assert data["country_code"] == 1
    assert len(data["search_queries"]) >= 3


def test_manual_dorks_endpoint():
    resp = client.get("/api/discovery/manual-dorks?phone_number=+14155552671")
    assert resp.status_code == 200
    dorks = resp.json()
    assert len(dorks) >= 10
    assert any("Google" in d["engine_name"] for d in dorks)
    assert any("FastPeopleSearch" in d["engine_name"] for d in dorks)


def test_remediation_sources_endpoint():
    resp = client.get("/api/remediation/sources")
    assert resp.status_code == 200
    sources = resp.json()
    assert len(sources) >= 15
    assert any(s["source_id"] == "fastpeoplesearch" for s in sources)


def test_template_generation_endpoint():
    resp = client.post("/api/remediation/template", json={
        "template_type": "CCPA_DELETE",
        "phone_number": "+14155552671",
        "recipient_name": "Test Broker",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "CCPA" in data["title"]
    assert "Test Broker" in data["body_markdown"]


def test_synthetic_scenario_and_metrics_flow():
    # 1. Load synthetic demo
    resp = client.post("/api/demo/synthetic")
    assert resp.status_code == 200
    demo_data = resp.json()
    hmac_id = demo_data["identity_hmac"]

    # 2. Query exposures
    exp_resp = client.get(f"/api/discovery/exposures?identity_hmac={hmac_id}")
    assert exp_resp.status_code == 200
    exposures = exp_resp.json()
    assert len(exposures) == 5

    # 3. Test transition of an exposure in SUBMITTED state to ACKNOWLEDGED
    target_exp = next((e for e in exposures if e["remediation_status"] == "SUBMITTED"), exposures[0])
    trans_resp = client.post("/api/remediation/transition", json={
        "exposure_id": target_exp["id"],
        "identity_hmac": hmac_id,
        "next_state": "ACKNOWLEDGED",
        "submission_ref": "TEST-REF-999",
        "notes": "Acknowledged by broker in test",
    })
    assert trans_resp.status_code == 200

    # 3b. Verify audit trail recorded in privacy export
    export_resp = client.get(f"/api/privacy/export?identity_hmac={hmac_id}")
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert "audit_trail" in export_data
    assert len(export_data["audit_trail"]) >= 1
    latest_audit = export_data["audit_trail"][-1]
    assert latest_audit["to_state"] == "ACKNOWLEDGED"
    assert latest_audit["evidence_type"] == "CONFIRMATION_RECEIPT"
    assert "TEST-REF-999" in latest_audit["evidence_notes"] or "Acknowledged" in latest_audit["evidence_notes"]

    # 4. Check metrics
    metric_resp = client.get(f"/api/prevention/metrics?identity_hmac={hmac_id}")
    assert metric_resp.status_code == 200
    metrics = metric_resp.json()
    assert metrics["total_exposures"] == 5
    assert metrics["verified_removed"] >= 1



def test_purge_endpoint():
    resp = client.post("/api/privacy/purge")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_scan_endpoint_and_deduplication():
    # Test scan with local fallback
    resp = client.post("/api/discovery/scan", json={
        "phone_number": "+14155552671",
        "default_region": "US",
        "providers": [],
        "target_urls": [],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "identity_hmac" in data
    assert data["total_found"] == 0

    # Rescan same identity without foreign key errors
    resp2 = client.post("/api/discovery/scan", json={
        "phone_number": "+14155552671",
        "default_region": "US",
        "providers": [],
        "target_urls": [],
    })
    assert resp2.status_code == 200


def test_invalid_transition_endpoint_rejection():
    # 1. Load synthetic demo
    resp = client.post("/api/demo/synthetic")
    assert resp.status_code == 200
    demo_data = resp.json()
    hmac_id = demo_data["identity_hmac"]

    # 2. Query exposures and find one in DISCOVERED state
    exp_resp = client.get(f"/api/discovery/exposures?identity_hmac={hmac_id}")
    assert exp_resp.status_code == 200
    exposures = exp_resp.json()
    disc_exp = next(e for e in exposures if e["remediation_status"] == "DISCOVERED")

    # 3. Attempt illegal transition from DISCOVERED directly to VERIFIED_REMOVED (must fail with 400)
    trans_resp = client.post("/api/remediation/transition", json={
        "exposure_id": disc_exp["id"],
        "identity_hmac": hmac_id,
        "next_state": "VERIFIED_REMOVED",
    })
    assert trans_resp.status_code == 400


def test_export_audit_endpoint():
    # Load synthetic scenario
    resp = client.post("/api/demo/synthetic")
    assert resp.status_code == 200
    hmac_id = resp.json()["identity_hmac"]

    # Export report
    exp_resp = client.get(f"/api/privacy/export?identity_hmac={hmac_id}")
    assert exp_resp.status_code == 200
    report = exp_resp.json()
    assert "report_title" in report
    assert "exposures" in report
    assert len(report["exposures"]) == 5



def test_analyze_sms_endpoint_dlt_and_commercial():
    # 1. Test Indian Bank DLT promotional SMS
    resp = client.post("/api/discovery/analyze-sms", json={
        "sender": "VM-HDFCBK",
        "message_body": "Pre-approved personal loan of Rs 5 Lakhs available now. Special low interest rate.",
        "region": "IN",
        "user_phone": "+918106833178",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["sender"] == "VM-HDFCBK"
    assert data["brand_name"] == "HDFCBK"
    assert data["dlt_prefix"] == "VM"
    assert data["category"] == "COMMERCIAL_BANKING"
    assert "COMP TEL NO 918106833178" in data["complaint_sms"]
    assert "HDFCBK" in data["merchant_notice"]

    # 2. Test Shopping App SMS
    resp_shop = client.post("/api/discovery/analyze-sms", json={
        "sender": "AD-SWIGGY",
        "message_body": "50% off on your favourite meals on Swiggy today!",
        "region": "IN",
    })
    assert resp_shop.status_code == 200
    data_shop = resp_shop.json()
    assert data_shop["brand_name"] == "SWIGGY"
    assert data_shop["category"] == "COMMERCIAL_SHOPPING"

    # 3. Test Numeric Shortcode with STOP
    resp_short = client.post("/api/discovery/analyze-sms", json={
        "sender": "223344",
        "message_body": "Flash sale ending tonight! Reply STOP to opt out.",
        "region": "US",
    })
    assert resp_short.status_code == 200
    data_short = resp_short.json()
    assert data_short["is_shortcode"] is True
    assert data_short["has_opt_out_keyword"] is True
    assert data_short["opt_out_command"] == "STOP"
