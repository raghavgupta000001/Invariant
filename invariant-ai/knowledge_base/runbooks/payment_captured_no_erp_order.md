# Runbook: Payment Captured Without ERP Sales Order
ID: RB-001
Severity: CRITICAL
System: ERP / Razorpay / Shopify

## Symptoms
- Payment status is CAPTURED in Razorpay.
- Money has been deducted from customer account.
- No corresponding sales order row exists in ERP database (`erp_db.sales_orders`).
- Customer does not receive order confirmation or tracking updates.

## Potential Root Causes
1. **Webhook Delivery Failure**: Razorpay webhook failed delivery due to network partition or timeout.
2. **ERP Internal Rollback (Silent Failure)**: ERP API returned HTTP 200 but failed during internal DB commit, rolling back without alerting callers.
3. **Field Mapping Error**: Customer identifier or order line items missing in payload causing unhandled exception in ERP connector.

## Diagnostic Steps
1. Query ERP API for sales order by `transaction_ref`.
2. Check Razorpay payment gateway current status for payment ID.
3. Inspect ERP connector logs for HTTP 500 or validation errors.
4. Verify if payment idempotency key was reused.

## Safe Recovery Procedure
1. Verify ERP has not partially recorded the order under an alternate reference.
2. If no record exists, trigger idempotent order creation with `transaction_ref`.
3. If order creation fails repeatedly, initiate customer refund via Razorpay refund API.
4. Confirm state consistency and mark incident resolved.

