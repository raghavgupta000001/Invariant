# Runbook: Silent Failure Detection & Reconciliation
ID: RB-003
Severity: HIGH
System: Core Reconciliation Engine / ERP / Shipping

## Symptoms
- Webhook or API response indicated success (HTTP 200 OK), but the target system state does not reflect the change.
- Technical monitoring reports 100% healthy uptime, while operational audits discover missing inventory or lost orders.

## Potential Root Causes
1. **Asynchronous Worker Crash**: Webhook receiver queued a background task which died before committing.
2. **Read Replica Lag**: Query to secondary DB node read stale snapshot before replication caught up.
3. **Database Transaction Rollback After HTTP Response Sent**: Response sent before explicit commit.

## Safe Recovery Procedure
1. Perform active source-of-truth polling directly against primary database or authoritative API.
2. Cross-reference idempotency keys.
3. Execute compensating action or re-enqueue idempotent mutation.

