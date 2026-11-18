from pydantic import BaseModel, Field, EmailStr
from typing import Optional
import uuid

class OrderItem(BaseModel):
    sku: str
    name: str
    qty: int = Field(ge=1)
    unit_price_paise: int = Field(ge=0)  # price in paise (1 INR = 100 paise)

class CreateOrderRequest(BaseModel):
    customer_email: str
    customer_name: str
    items: list[OrderItem]
    notes: dict = Field(default_factory=dict)
    
    @property
    def total_amount_paise(self) -> int:
        return sum(item.qty * item.unit_price_paise for item in self.items)

class OrderResponse(BaseModel):
    id: str
    transaction_ref: str
    customer_email: str
    customer_name: str
    items: list[dict]
    total_amount_paise: int
    total_amount_display: float
    currency: str
    status: str
    created_at: str

class CancelOrderRequest(BaseModel):
    reason: str = "Customer request"
