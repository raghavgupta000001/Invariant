from pydantic import BaseModel, Field

class LineItem(BaseModel):
    sku: str
    name: str
    qty: int = Field(ge=1)
    unit_price_paise: int = Field(ge=0)

class CreateSalesOrderRequest(BaseModel):
    transaction_ref: str
    customer_id: str
    customer_email: str
    line_items: list[LineItem]
    total_amount_paise: int

class ReserveInventoryRequest(BaseModel):
    transaction_ref: str
    sales_order_id: str
    items: list[LineItem]

class GenerateInvoiceRequest(BaseModel):
    transaction_ref: str
    sales_order_id: str
    amount_paise: int
