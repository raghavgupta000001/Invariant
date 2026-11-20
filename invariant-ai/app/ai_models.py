from pydantic import BaseModel, Field
from typing import Literal, Optional, Any


class EvidenceItem(BaseModel):
    source: str
    observation: str
    relevance: str
    confidence: Literal["CONFIRMED", "INFERRED", "HYPOTHETICAL"]


class RootCauseHypothesis(BaseModel):
    hypothesis: str
    evidence: list[EvidenceItem]
    confidence_level: Literal["HIGH", "MEDIUM", "LOW", "INCONCLUSIVE"]
    confidence_rationale: str
    similar_incidents: list[str] = Field(default_factory=list)


class RecoveryStep(BaseModel):
    step_number: int
    action: str
    target_system: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_check: str
    expected_outcome: str
    rollback_action: Optional[str] = None
    requires_human_approval: bool = True
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"


class InvestigationResult(BaseModel):
    investigation_id: str
    incident_id: str
    transaction_ref: str
    status: Literal["COMPLETE", "INCONCLUSIVE", "BLOCKED"]
    expected_workflow_state: str
    actual_state_summary: str
    first_divergence: str
    root_cause: RootCauseHypothesis
    all_evidence: list[EvidenceItem]
    recovery_plan: list[RecoveryStep]
    recovery_confidence: Literal["HIGH", "MEDIUM", "LOW"]
    open_questions: list[str] = Field(default_factory=list)
    knowledge_sources_used: list[str] = Field(default_factory=list)
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    investigation_duration_ms: int = 0
