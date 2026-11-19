from pydantic import BaseModel, Field
from typing import Any, Optional, Literal
from datetime import datetime, timezone
import uuid


class ICEFMeta(BaseModel):
    icef_version: str = "1.0"
    event_id: str = Field(default_factory=lambda: f"evt_inv_{uuid.uuid4().hex}")
    idempotency_key: str
    source_system: str
    source_event_id: str
    raw_event_type: str
    canonical_event_type: str
    occurred_at: datetime
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    signature_verified: bool = False


class ICEFEntity(BaseModel):
    type: str  # e.g., "order", "payment", "sales_order", "shipment"
    id: str    # ID in originating system
    correlation_hints: dict[str, Any] = Field(default_factory=dict)


class ICEFCorrelation(BaseModel):
    transaction_ref: Optional[str] = None
    transaction_id: Optional[str] = None
    confidence: float = 1.0
    method: Literal["EXPLICIT_ID", "RULE_BASED", "HEURISTIC"] = "EXPLICIT_ID"


class CanonicalEvent(BaseModel):
    meta: ICEFMeta
    entity: ICEFEntity
    data: dict[str, Any] = Field(default_factory=dict)
    transaction_correlation: ICEFCorrelation = Field(default_factory=ICEFCorrelation)

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")

