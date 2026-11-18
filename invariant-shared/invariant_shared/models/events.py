from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime, timezone
from enum import Enum
import uuid

class EventType(str, Enum):
    ORDER_CREATED = "order.created"
    ORDER_CANCELLED = "order.cancelled"
    PAYMENT_CAPTURED = "payment.captured"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"
    ERP_ORDER_CREATED = "erp.order_created"
    ERP_ORDER_FAILED = "erp.order_failed"
    ERP_INVENTORY_RESERVED = "erp.inventory_reserved"
    ERP_INVOICE_GENERATED = "erp.invoice_generated"
    SHIPMENT_CREATED = "shipment.created"
    SHIPMENT_FAILED = "shipment.failed"

class CanonicalEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    source_system: str
    transaction_ref: str           # Links events across services e.g. "TXN-1042"
    entity_id: str                 # Source system's own ID
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
