from pydantic import BaseModel, Field
from typing import Optional


class DeliveryAddress(BaseModel):
    line1: str
    line2: str = ""
    city: str
    state: str
    pincode: str
    country: str = "IN"


class CreateShipmentRequest(BaseModel):
    transaction_ref: str
    sales_order_id: str
    recipient_name: str
    recipient_email: str
    delivery_address: DeliveryAddress
    carrier: str = "BLUEDART"


class ShipmentResponse(BaseModel):
    id: str
    transaction_ref: str
    tracking_number: str
    carrier: str
    status: str
    recipient_name: str
    estimated_delivery: Optional[str]
    created_at: str
