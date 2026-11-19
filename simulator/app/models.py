from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum


class FailureMode(str, Enum):
    NONE                    = "none"
    ERP_SILENT_FAILURE      = "erp_silent_failure"       # ERP returns 200 but persists nothing
    WRONG_AMOUNT            = "wrong_amount"             # Payment amount ≠ order amount (paise/rupee bug)
    SHIPMENT_FAILS          = "shipment_creation_fails"  # Shipping service returns 503
    DUPLICATE_PAYMENT_EVENT = "duplicate_payment_event"  # Same payment event sent twice
    DROP_ERP_WEBHOOK        = "drop_erp_webhook"         # ERP never publishes its event


class SimulateRequest(BaseModel):
    customer_email: str = "test@example.com"
    customer_name: str = "Test Customer"
    sku: str = "LAPTOP-PRO-15"
    product_name: str = 'Professional Laptop 15"'
    qty: int = 1
    unit_price_paise: int = 6_000_000   # ₹60,000 in paise
    failure_mode: FailureMode = FailureMode.NONE
    failure_options: dict = Field(default_factory=dict)


class StepResult(BaseModel):
    step: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


class SimulationResult(BaseModel):
    transaction_ref: str
    failure_mode: str
    steps: list[StepResult]
    final_status: str   # "COMPLETED" | "PARTIAL_FAILURE" | "FAILED"
    summary: str

