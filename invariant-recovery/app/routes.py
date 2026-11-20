import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.models.recovery import (
    RecoveryPlan,
    RecoveryStepDefinition,
    ExecutionState,
    RiskLevel,
)
from app.engine.executor import RecoveryExecutor

router = APIRouter(prefix="/recovery", tags=["recovery"])
executor = RecoveryExecutor()

_plans: dict[str, RecoveryPlan] = {}


@router.post("/plans/generate")
async def generate_plan(incident: dict):
    """
    Generates a formal RecoveryPlan with safety gates, risk levels, and idempotency checks.
    """
    plan_id = f"PLAN-{uuid.uuid4().hex[:6].upper()}"
    incident_id = incident.get("id", "INC-GEN")
    txn_ref = incident.get("transaction_ref", "TXN-GEN")
    incident_type = incident.get("incident_type", "UNKNOWN")

    steps: list[RecoveryStepDefinition] = []
    if incident_type == "DATA_MISMATCH":
        steps = [
            RecoveryStepDefinition(
                step_number=1,
                action="verify_payment_gateway_status",
                target_system="payment-service",
                parameters={"transaction_ref": txn_ref},
                idempotency_check="query payment gateway current status",
                expected_outcome="Verify recorded amount in gateway",
                risk_level=RiskLevel.LOW,
                requires_human_approval=False,
            ),
            RecoveryStepDefinition(
                step_number=2,
                action="initiate_refund",
                target_system="payment-service",
                parameters={"transaction_ref": txn_ref},
                idempotency_check="check no existing refund for this payment",
                expected_outcome="Refund issued without duplicating operations",
                rollback_action="re-authorize charge",
                risk_level=RiskLevel.HIGH,
                requires_human_approval=True,
            ),
        ]
    else:
        steps = [
            RecoveryStepDefinition(
                step_number=1,
                action="check_erp_for_existing_order",
                target_system="erp-service",
                parameters={"transaction_ref": txn_ref},
                idempotency_check="GET /erp/orders/{transaction_ref}",
                expected_outcome="Confirm no order exists in ERP",
                risk_level=RiskLevel.LOW,
                requires_human_approval=False,
            ),
            RecoveryStepDefinition(
                step_number=2,
                action="retry_order_creation",
                target_system="erp-service",
                parameters={"transaction_ref": txn_ref, "idempotency_key": f"recov-{plan_id}"},
                idempotency_check="ensure idempotency key uniqueness before sending",
                expected_outcome="ERP sales order created successfully",
                risk_level=RiskLevel.MEDIUM,
                requires_human_approval=True,
            ),
            RecoveryStepDefinition(
                step_number=3,
                action="reconcile_state",
                target_system="invariant-core",
                parameters={"transaction_ref": txn_ref},
                idempotency_check="confirm state is COMPLETED",
                expected_outcome="Transaction marked consistent",
                risk_level=RiskLevel.LOW,
                requires_human_approval=False,
            ),
        ]

    plan = RecoveryPlan(
        id=plan_id,
        incident_id=incident_id,
        transaction_ref=txn_ref,
        steps=steps,
        execution_state=ExecutionState.DRAFT,
        requires_approval=any(s.requires_human_approval for s in steps),
    )
    _plans[plan_id] = plan
    return plan.model_dump()


@router.post("/plans/{plan_id}/dry-run")
async def run_dry_run(plan_id: str):
    plan = _plans.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Recovery plan not found")
    result = await executor.simulate_dry_run(plan)
    return {"plan_id": plan_id, "execution_state": plan.execution_state.value, "dry_run_result": result}


@router.post("/plans/{plan_id}/approve")
async def approve_plan(plan_id: str, approver: str = Query("ops-admin")):
    plan = _plans.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Recovery plan not found")
    plan.execution_state = ExecutionState.APPROVED
    plan.approved_by = approver
    plan.approved_at = datetime.now(timezone.utc)
    return {"plan_id": plan_id, "execution_state": plan.execution_state.value, "approved_by": approver}


@router.post("/plans/{plan_id}/execute")
async def execute_plan_endpoint(plan_id: str):
    plan = _plans.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Recovery plan not found")
    try:
        updated_plan = await executor.execute_plan(plan)
        return updated_plan.model_dump()
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: str):
    plan = _plans.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Recovery plan not found")
    return plan.model_dump()

