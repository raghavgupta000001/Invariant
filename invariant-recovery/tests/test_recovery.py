import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.recovery import ExecutionState, RiskLevel


def test_recovery_plan_lifecycle_with_dry_run_and_approval():
    with TestClient(app) as client:
        # 1. Generate plan for an incident
        incident = {
            "id": "INC-TEST-REC-01",
            "transaction_ref": "TXN-TEST-REC",
            "incident_type": "DATA_MISMATCH",
            "description": "Payment amount mismatch detected",
        }
        res_gen = client.post("/recovery/plans/generate", json=incident)
        assert res_gen.status_code == 200
        plan = res_gen.json()
        plan_id = plan["id"]
        assert plan["execution_state"] == ExecutionState.DRAFT.value
        assert plan["requires_approval"] is True

        # 2. Dry run simulation
        res_dry = client.post(f"/recovery/plans/{plan_id}/dry-run")
        assert res_dry.status_code == 200
        dry_data = res_dry.json()
        assert dry_data["execution_state"] == ExecutionState.DRY_RUN_COMPLETE.value
        assert dry_data["dry_run_result"]["all_steps_valid"] is True

        # 3. Unapproved execution attempt must be REJECTED (HTTP 403)
        res_unapproved = client.post(f"/recovery/plans/{plan_id}/execute")
        assert res_unapproved.status_code == 403

        # 4. Human Approval
        res_app = client.post(f"/recovery/plans/{plan_id}/approve?approver=lead-fde")
        assert res_app.status_code == 200
        assert res_app.json()["execution_state"] == ExecutionState.APPROVED.value
        assert res_app.json()["approved_by"] == "lead-fde"

        # 5. Live Execution with Audit Log
        res_exec = client.post(f"/recovery/plans/{plan_id}/execute")
        assert res_exec.status_code == 200
        exec_data = res_exec.json()
        assert exec_data["execution_state"] == ExecutionState.COMPLETED.value
        assert len(exec_data["execution_log"]) >= 2

        # 6. Verify audit log integrity
        for entry in exec_data["execution_log"]:
            assert "step" in entry
            assert "action" in entry
            assert "status" in entry

