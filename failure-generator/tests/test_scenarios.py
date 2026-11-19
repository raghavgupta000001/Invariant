import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app
from catalog.scenarios import SCENARIOS, get_scenario, get_by_category


def test_scenario_catalog_integrity():
    """Verify that all 50 scenarios are uniquely identified and valid."""
    assert len(SCENARIOS) == 50
    ids = [s.id for s in SCENARIOS]
    assert len(set(ids)) == 50, "Scenario IDs must be unique"

    for s in SCENARIOS:
        assert s.id.startswith("F")
        assert s.name
        assert s.description
        assert s.category
        assert s.severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
        assert s.ground_truth.incident_type
        assert s.ground_truth.invariant_violated
        assert s.ground_truth.root_cause
        assert s.ground_truth.expected_recovery


def test_list_scenarios_endpoint():
    with TestClient(app) as client:
        res = client.get("/failures/scenarios")
        assert res.status_code == 200
        data = res.json()
        assert data["count"] == 50
        assert "categories" in data
        assert "severities" in data


def test_filter_scenarios_by_category():
    with TestClient(app) as client:
        res = client.get("/failures/scenarios?category=silent_failure")
        assert res.status_code == 200
        data = res.json()
        assert data["count"] == 5
        for s in data["scenarios"]:
            assert s["category"] == "silent_failure"


def test_get_scenario_detail():
    with TestClient(app) as client:
        res = client.get("/failures/scenarios/F001")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == "F001"
        assert data["ground_truth"]["invariant_violated"] == "payment_without_erp_order"


def test_get_scenario_not_found():
    with TestClient(app) as client:
        res = client.get("/failures/scenarios/F999")
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_inject_scenario_mocked():
    from app.injector import FailureInjector

    with patch.object(
        FailureInjector,
        "execute_scenario",
        new=AsyncMock(return_value={
            "scenario_id": "F001",
            "scenario_name": "ERP Silent Failure",
            "status": "PARTIAL_FAILURE",
            "transaction_ref": "TXN-TEST-1234",
            "ground_truth": {"incident_type": "MISSING_STEP"},
        })
    ):
        with TestClient(app) as client:
            res = client.post("/failures/inject/F001")
            assert res.status_code == 200
            data = res.json()
            assert data["scenario_id"] == "F001"
            assert data["status"] == "PARTIAL_FAILURE"

