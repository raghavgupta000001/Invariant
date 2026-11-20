from pydantic import BaseModel, Field
from typing import Optional, Literal, Any
from datetime import datetime, timezone
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExecutionState(str, Enum):
    DRAFT = "DRAFT"
    DRY_RUN_IN_PROGRESS = "DRY_RUN_IN_PROGRESS"
    DRY_RUN_COMPLETE = "DRY_RUN_COMPLETE"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class CompensatingAction(BaseModel):
    name: str
    description: str
    connector: str
    operation: str
    idempotency_check: str
    risk: RiskLevel
    requires_approval: bool = True
    pre_check: Optional[str] = None


class RecoveryStepDefinition(BaseModel):
    step_number: int
    action: str
    target_system: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_check: str
    expected_outcome: str
    rollback_action: Optional[str] = None
    requires_human_approval: bool = True
    risk_level: RiskLevel = RiskLevel.MEDIUM


class ExecutionLogEntry(BaseModel):
    step: int
    action: str
    status: str
    result: Optional[str] = None
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RecoveryPlan(BaseModel):
    id: str
    incident_id: str
    transaction_ref: str
    steps: list[RecoveryStepDefinition]
    execution_state: ExecutionState = ExecutionState.DRAFT
    requires_approval: bool = True
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    dry_run_result: Optional[dict[str, Any]] = None
    execution_log: list[ExecutionLogEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

