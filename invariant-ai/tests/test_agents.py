import pytest
from app.agents.orchestrator import InvestigationOrchestrator
from app.tools.evidence_tools import EvidenceCollectorTools


@pytest.mark.asyncio
async def test_investigation_orchestrator_flow():
    tools = EvidenceCollectorTools()
    orchestrator = InvestigationOrchestrator(tools=tools)

    incident = {
        "id": "INC-TEST-001",
        "transaction_ref": "TXN-TEST-1042",
        "incident_type": "DATA_MISMATCH",
        "severity": "CRITICAL",
        "description": "Payment amount differs from order amount by ₹59,400.",
    }

    result = await orchestrator.investigate_incident(incident)

    assert result.status == "COMPLETE"
    assert result.incident_id == "INC-TEST-001"
    assert result.first_divergence == "payment_captured"
    assert result.root_cause.confidence_level in ("HIGH", "MEDIUM")
    assert len(result.recovery_plan) >= 2
    assert result.total_tokens_used > 0
    assert result.total_cost_usd > 0
    assert result.investigation_duration_ms >= 0

    # Ensure idempotency checks are present on all recovery steps
    for step in result.recovery_plan:
        assert step.idempotency_check, f"Step {step.step_number} must have an idempotency check"

