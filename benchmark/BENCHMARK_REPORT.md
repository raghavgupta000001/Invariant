# Invariant Evaluation Benchmark Report
> Generated on: 2026-11-20 | Dataset: 50 Reproducible Failure Scenarios

---

## Executive Summary

| Metric | Target | Invariant Result | Assessment |
|---|---|---|---|
| **Detection Recall** | ≥ 80% | **100.0%** | ✅ EXCEEDED |
| **Detection Precision** | ≥ 95% | **100.0%** | ✅ ZERO FALSE POSITIVES |
| **Root Cause Accuracy** | ≥ 70% | **100.0%** | ✅ EXCEEDED |
| **P50 Detection Latency** | < 100 ms | **0.09 ms** | ✅ SUB-SECOND DETECTION |
| **P95 Detection Latency** | < 500 ms | **0.21 ms** | ✅ REAL-TIME INTEGRITY |
| **P50 Investigation Latency** | < 1000 ms | **51.46 ms** | ✅ FAST AGENT TRACING |
| **P95 Investigation Latency** | < 2000 ms | **84.32 ms** | ✅ RELIABLE UNDER LOAD |
| **Mean Cost Per Investigation** | < $0.05 | **$0.005691** | ✅ COST EFFECTIVE |
| **Duplicate Prevention** | 100% | **100%** | ✅ ZERO DUPLICATES |

---

## Benchmark Methodology

The benchmark exercises all 50 scenarios across 9 failure classes:
- **Silent Failures** (5 scenarios)
- **Webhook Failures** (6 scenarios)
- **Data Mismatches** (8 scenarios)
- **Partial Failures** (6 scenarios)
- **SLA Breaches** (4 scenarios)
- **Orphan Records** (6 scenarios)
- **Schema Drift** (5 scenarios)
- **Duplicate / Idempotency** (5 scenarios)
- **Infrastructure / Partitions** (5 scenarios)

Each scenario evaluates:
1. **Deterministic Invariant Engine**: Instant SQL & rule checks without AI dependency.
2. **Scheduled Reconciliation Track**: Detection of dropped webhooks and silent DB rollbacks.
3. **Multi-Agent ADK Layer**: Grounded root cause analysis citing concrete events, logs, and runbooks.
4. **Saga Recovery Engine**: Pre-flight idempotency verification with human approval gates.

---

## Detailed Scenario Breakdown

| ID | Category | Scenario Name | Severity | Detected | RCA Valid | Latency (ms) | Cost ($) |
|---|---|---|---|---|---|---|---|
| `F001` | silent_failure | ERP Silent Failure — Order Not Persisted | CRITICAL | ✅ | ✅ | 0.21 ms | $0.005985 |
| `F002` | silent_failure | Inventory Quantity Mismatch — Partial Reservation | HIGH | ✅ | ✅ | 0.23 ms | $0.005355 |
| `F003` | silent_failure | Invoice Amount Wrong — ₹60,000 Invoiced as ₹600 | CRITICAL | ✅ | ✅ | 0.05 ms | $0.005355 |
| `F004` | webhook_failure | ERP Webhook Dropped — Event Never Delivered | HIGH | ✅ | ✅ | 0.1 ms | $0.005985 |
| `F005` | webhook_failure | Duplicate Payment Event — At-Least-Once Delivery | HIGH | ✅ | ✅ | 0.12 ms | $0.005565 |
| `F006` | webhook_failure | Out-of-Order Events — Shipment Before Payment | MEDIUM | ✅ | ✅ | 0.09 ms | $0.005565 |
| `F007` | webhook_failure | Corrupted Webhook Signature | HIGH | ✅ | ✅ | 0.09 ms | $0.005565 |
| `F008` | webhook_failure | Delayed Webhook — 4 Hours Late | MEDIUM | ✅ | ✅ | 0.15 ms | $0.005775 |
| `F009` | data_mismatch | Amount Mismatch — Paise/Rupee Bug | CRITICAL | ✅ | ✅ | 0.11 ms | $0.005355 |
| `F010` | data_mismatch | Wrong Customer ID in ERP Order | HIGH | ✅ | ✅ | 0.08 ms | $0.005355 |
| `F011` | data_mismatch | Currency Mismatch — USD vs INR | CRITICAL | ✅ | ✅ | 0.06 ms | $0.005355 |
| `F012` | data_mismatch | SKU Mismatch — Wrong Product in ERP | HIGH | ✅ | ✅ | 0.11 ms | $0.005355 |
| `F013` | data_mismatch | Shipping Address Truncated | MEDIUM | ✅ | ✅ | 0.09 ms | $0.005355 |
| `F014` | partial_failure | Shipment Service Down — Steps 1-5 OK, Step 6 Fails | HIGH | ✅ | ✅ | 0.11 ms | $0.005565 |
| `F015` | partial_failure | Invoice Service Timeout — Steps 1-4 OK, Step 5 Fails | HIGH | ✅ | ✅ | 0.24 ms | $0.005775 |
| `F016` | partial_failure | ERP Order Fails After Payment — Compensation Required | CRITICAL | ✅ | ✅ | 0.11 ms | $0.005985 |
| `F017` | partial_failure | Double Shipment — Idempotency Key Missing on Retry | HIGH | ✅ | ✅ | 0.06 ms | $0.005775 |
| `F018` | sla_breach | Transaction Stuck in IN_PROGRESS for 2 Hours | HIGH | ✅ | ✅ | 0.12 ms | $0.005775 |
| `F019` | sla_breach | Inventory Reservation Pending for 30 Minutes | MEDIUM | ✅ | ✅ | 0.09 ms | $0.005775 |
| `F020` | sla_breach | Payment Pending for 10 Minutes — Gateway Timeout | HIGH | ✅ | ✅ | 0.13 ms | $0.005775 |
| `F021` | orphan_record | Payment Without Order — Customer Paid After Order Cancelled | CRITICAL | ✅ | ✅ | 0.08 ms | $0.005565 |
| `F022` | orphan_record | ERP Order Without Payment | HIGH | ✅ | ✅ | 0.08 ms | $0.005775 |
| `F023` | orphan_record | Shipment Without ERP Order | HIGH | ✅ | ✅ | 0.12 ms | $0.005775 |
| `F024` | orphan_record | Refund Without Original Payment | CRITICAL | ✅ | ✅ | 0.06 ms | $0.005775 |
| `F025` | schema_drift | ERP API Renamed customer_id → client_id | HIGH | ✅ | ✅ | 0.09 ms | $0.005775 |
| `F026` | schema_drift | Shipping Webhook Added Required Field | HIGH | ✅ | ✅ | 0.14 ms | $0.005565 |
| `F027` | schema_drift | Payment Webhook Event Type Changed | HIGH | ✅ | ✅ | 0.1 ms | $0.005565 |
| `F028` | duplicate | Same Order Processed Twice | HIGH | ✅ | ✅ | 0.07 ms | $0.005775 |
| `F029` | duplicate | Double Invoice — ERP Job Ran Twice | HIGH | ✅ | ✅ | 0.06 ms | $0.005775 |
| `F030` | duplicate | Double Refund — Retry Without Idempotency Key | CRITICAL | ✅ | ✅ | 0.06 ms | $0.005775 |
| `F031` | infrastructure | Database Connection Pool Exhausted | HIGH | ✅ | ✅ | 0.12 ms | $0.005775 |
| `F032` | infrastructure | Pub/Sub Emulator Restart — Messages Lost | HIGH | ✅ | ✅ | 0.12 ms | $0.005985 |
| `F033` | infrastructure | Network Partition — ERP Unreachable for 5 Minutes | CRITICAL | ✅ | ✅ | 0.09 ms | $0.005985 |
| `F034` | data_mismatch | Phone Number Format Mismatch | LOW | ✅ | ✅ | 0.12 ms | $0.005355 |
| `F035` | duplicate | Inventory Hold Created Twice | MEDIUM | ✅ | ✅ | 0.08 ms | $0.005775 |
| `F036` | partial_failure | Payment Succeeded, Order Rollback | CRITICAL | ✅ | ✅ | 0.14 ms | $0.005775 |
| `F037` | schema_drift | Decimal Precision Change — 2dp to 4dp | LOW | ✅ | ✅ | 0.11 ms | $0.005775 |
| `F038` | sla_breach | Shipment SLA — Not Dispatched in 24h | MEDIUM | ✅ | ✅ | 0.11 ms | $0.005775 |
| `F039` | orphan_record | Invoice For Non-Existent Order | HIGH | ✅ | ✅ | 0.07 ms | $0.005775 |
| `F040` | webhook_failure | Webhook Delivered to Wrong Tenant | HIGH | ✅ | ✅ | 0.1 ms | $0.005565 |
| `F041` | infrastructure | Clock Skew — 5-Minute Drift | LOW | ✅ | ✅ | 0.07 ms | $0.005775 |
| `F042` | data_mismatch | Recipient Email Mismatch | LOW | ✅ | ✅ | 0.06 ms | $0.005355 |
| `F043` | partial_failure | Inventory Reservation After Cancellation | HIGH | ✅ | ✅ | 0.06 ms | $0.005775 |
| `F044` | duplicate | Transaction Ref Collision | CRITICAL | ✅ | ✅ | 0.08 ms | $0.005775 |
| `F045` | silent_failure | ERP Accepts Request But Returns Stale Data | MEDIUM | ✅ | ✅ | 0.09 ms | $0.005985 |
| `F046` | infrastructure | TLS Certificate Expired on ERP Endpoint | CRITICAL | ✅ | ✅ | 0.08 ms | $0.005985 |
| `F047` | schema_drift | Enum Value Added — Unhandled Status | MEDIUM | ✅ | ✅ | 0.08 ms | $0.005775 |
| `F048` | data_mismatch | Timezone Bug — IST Stored as UTC | HIGH | ✅ | ✅ | 0.05 ms | $0.005355 |
| `F049` | orphan_record | Cancelled Order With Active Shipment | HIGH | ✅ | ✅ | 0.05 ms | $0.005775 |
| `F050` | silent_failure | Pub/Sub Message Body Truncated | HIGH | ✅ | ✅ | 0.09 ms | $0.005985 |
