from pydantic import BaseModel, Field
from typing import Optional, Any, Literal
from datetime import datetime, timezone
from enum import Enum


class TransactionState(str, Enum):
    INITIATED = "INITIATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    INCONSISTENT = "INCONSISTENT"
    RECOVERING = "RECOVERING"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    COMPENSATED = "COMPENSATED"


class StepState(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    COMPENSATED = "COMPENSATED"
    TIMED_OUT = "TIMED_OUT"


class IncidentType(str, Enum):
    MISSING_STEP = "MISSING_STEP"
    DUPLICATE_EVENT = "DUPLICATE_EVENT"
    DATA_MISMATCH = "DATA_MISMATCH"
    ORDERING_VIOLATION = "ORDERING_VIOLATION"
    SLA_BREACH = "SLA_BREACH"
    ORPHAN_RECORD = "ORPHAN_RECORD"
    SCHEMA_DRIFT = "SCHEMA_DRIFT"
    SILENT_FAILURE = "SILENT_FAILURE"
    UNRESOLVABLE = "UNRESOLVABLE"


class IncidentSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class InvariantViolation(BaseModel):
    invariant_name: str
    severity: IncidentSeverity
    transaction_ref: str
    incident_type: IncidentType
    description: str
    evidence: dict[str, Any]
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
