from pydantic import BaseModel, Field

class CapturePaymentRequest(BaseModel):
    transaction_ref: str           # Must match an order's transaction_ref
    amount_paise: int = Field(ge=1)
    currency: str = "INR"
    method: str = "upi"
    idempotency_key: str           # Caller-provided, used for dedup

class RefundRequest(BaseModel):
    amount_paise: int = Field(ge=1)
    reason: str = "Customer request"
    idempotency_key: str

class PaymentResponse(BaseModel):
    id: str
    transaction_ref: str
    amount_paise: int
    amount_display: float
    currency: str
    method: str
    status: str
    captured_at: str | None
    created_at: str
