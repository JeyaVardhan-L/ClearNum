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
