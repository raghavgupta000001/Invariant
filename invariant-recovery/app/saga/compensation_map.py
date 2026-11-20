from app.models.recovery import CompensatingAction, RiskLevel

ECOMMERCE_SAGA_COMPENSATIONS: dict[str, CompensatingAction] = {
    "order_created": CompensatingAction(
        name="cancel_order",
        description="Cancel the order in the commerce platform",
        connector="order-service",
        operation="cancel_order",
        idempotency_check="order status is not already CANCELLED",
        risk=RiskLevel.MEDIUM,
        requires_approval=True,
    ),
    "payment_captured": CompensatingAction(
        name="initiate_refund",
        description="Initiate a refund for the captured payment",
        connector="payment-service",
        operation="refund_payment",
        idempotency_check="verify no existing refund for this payment",
        risk=RiskLevel.HIGH,
        requires_approval=True,
        pre_check="SELECT COUNT(*) FROM refunds WHERE payment_id = :payment_id",
    ),
    "inventory_reserved": CompensatingAction(
        name="release_inventory",
        description="Release the reserved inventory back to available stock",
        connector="erp-service",
        operation="release_inventory",
        idempotency_check="hold still exists and has not been released",
        risk=RiskLevel.LOW,
        requires_approval=False,
    ),
    "invoice_generated": CompensatingAction(
        name="void_invoice",
        description="Void the generated invoice",
        connector="erp-service",
        operation="void_invoice",
        idempotency_check="invoice exists and is not already voided",
        risk=RiskLevel.LOW,
        requires_approval=True,
    ),
}

