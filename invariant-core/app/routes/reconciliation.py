from fastapi import APIRouter
from app.routes.ingest import get_ingestion_service
from app.engine.reconciliation import ReconciliationEngine

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])
_reconciliation_engine = ReconciliationEngine()


@router.post("/sweep")
async def trigger_reconciliation_sweep():
    service = get_ingestion_service()
    active_txns = service.state_machine.list_transactions()
    violations = await _reconciliation_engine.run_sweep_all(active_txns)

    raised = []
    for v in violations:
        service.state_machine.mark_inconsistent(v.transaction_ref, v.description)
        inc = service.incident_service.raise_incident(v)
        raised.append(inc)

    return {
        "status": "SWEEP_COMPLETE",
        "transactions_checked": len(active_txns),
        "violations_found": len(violations),
        "incidents_raised": raised,
    }


@router.post("/evaluate")
async def evaluate_invariants_all():
    service = get_ingestion_service()
    active_txns = service.state_machine.list_transactions()
    violations = service.checker.evaluate_all(active_txns)

    raised = []
    for v in violations:
        service.state_machine.mark_inconsistent(v.transaction_ref, v.description)
        inc = service.incident_service.raise_incident(v)
        raised.append(inc)

    return {
        "transactions_evaluated": len(active_txns),
        "violations_found": len(violations),
        "incidents_raised": raised,
    }

