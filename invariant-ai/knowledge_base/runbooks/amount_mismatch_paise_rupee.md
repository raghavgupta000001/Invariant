# Runbook: Amount Mismatch (Paise to Rupee Conversion Bug)
ID: RB-002
Severity: CRITICAL
System: Payment / Commerce Connector

## Symptoms
- Transaction order total and captured payment amount differ by factor of 100.
- Example: Order placed for ₹60,000 (6,000,000 paise), payment recorded as ₹600 (60,000 paise).
- Reconciliation invariant `amount_consistency` flagged CRITICAL violation.

## Potential Root Causes
1. **Unit Conversion Error**: Connector code divides `amount_paise` by 100 before passing to a gateway API that expects amounts in paise.
2. **Schema Drift**: Gateway changed payload specification from decimal rupees to integer paise.
3. **Discount / Coupon Application Glitch**: Promo code applied during checkout not synchronized with order total calculation.

## Diagnostic Steps
1. Retrieve order line items and verify original gross total.
2. Inspect payment gateway captured event payload for `amount` vs `amount_paise`.
3. Check currency field for consistency (e.g. INR vs USD).

## Safe Recovery Procedure
1. Notify customer support and operations immediately.
2. Do NOT blindly capture additional amount without customer authorization.
3. If order cannot be fulfilled at captured price: cancel order and issue full refund.
4. If merchant honors price: generate invoice for actual captured amount and update order total.

