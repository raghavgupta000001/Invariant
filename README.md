# Invariant — Business Transaction Integrity & Recovery Platform
> **Target Role:** Forward Deployed Engineer Intern 2027, Google Cloud Consulting  
> An enterprise agentic platform that correlates business events across independent distributed systems, enforces business invariants, detects silent inconsistencies, identifies root causes with evidence grounding, and coordinates safe saga recovery.

---

```
Traditional monitoring asks: "Did the API return 200?"
Invariant asks:              "Is the business in the correct state?"
```

A transaction is not complete simply because five microservices return HTTP 200. It is complete only when five independently operating systems (Shopify, Razorpay, SAP/ERP, Warehouses, Logistics) have reached mutually consistent final states.

`Invariant` addresses the distributed systems reality documented by AWS, Google Cloud, Razorpay, and Shopify: **at-least-once deliveries, duplicate webhooks, clock skews, partial failures, and silent DB rollbacks.**

---

## 🏛️ System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                          INTELLIGENCE LAYER                            │
│           Google ADK · Multi-Agent Orchestrator · Hybrid RAG           │
│   (Evidence Collector → Root Cause Analyst → Recovery Planner)         │
├────────────────────────────────────────────────────────────────────────┤
│                          INTEGRITY LAYER                               │
│       Transaction State Machine · SQL Business Invariant Checker       │
│               Dual-Track Scheduled Reconciliation Engine               │
├────────────────────────────────────────────────────────────────────────┤
│                          INGESTION LAYER                               │
│       Webhook Receivers · Normalizers (ICEF v1) · Deduplication        │
├────────────────────────────────────────────────────────────────────────┤
│                      SIMULATED CONNECTOR LAYER                         │
│   order-service (8001) · payment-service (8002) · erp-service (8003)   │
│                 shipping-service (8004) · simulator (8000)             │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Benchmark Evaluation (50 Scenarios)

Evaluated against the **50-Scenario Reproducible Failure Benchmark Catalog** (`benchmark/BENCHMARK_REPORT.md`):

| Evaluation Metric | Target | Invariant Score | Assessment |
|---|---|---|---|
| **Detection Recall** | ≥ 80% | **100.0%** | ✅ Exceeded (50/50 detected) |
| **Detection Precision** | ≥ 95% | **100.0%** | ✅ Zero False Positives |
| **Root Cause Accuracy** | ≥ 70% | **100.0%** | ✅ Cites Verifiable Evidence |
| **P50 Detection Latency** | < 100 ms | **0.09 ms** | ✅ Real-Time SQL Engine |
| **P95 Detection Latency** | < 500 ms | **0.21 ms** | ✅ Sub-Millisecond Speed |
| **P50 Investigation Latency** | < 1000 ms | **51.5 ms** | ✅ Low Latency Pipeline |
| **Mean Cost Per Investigation** | < $0.05 | **$0.00569** | ✅ Cost Optimized |
| **Duplicate Prevention** | 100% | **100.0%** | ✅ Zero Duplicate Operations |

---

## ⚡ Key Technical Differentiators

1. **Deterministic Before Generative**: Invariant detects anomalies and invariant violations using exact SQL queries and state-machine transitions. The system never relies on an LLM to compare financial amounts (`₹60,000 ≠ ₹600`).
2. **Dual-Track Anomaly Detection**:
   - **Track A (Event-Driven)**: Processes incoming events via webhooks and Pub/Sub in real time.
   - **Track B (Scheduled Reconciliation)**: Periodically polls authoritative source-of-truth APIs to discover **silent failures** (cases where a webhook was dropped or an API returned 200 but rolled back).
3. **Evidence-Grounded AI**: Agents built with Google ADK patterns cannot fabricate diagnoses. Every claim in the Root Cause Analysis cites a concrete event ID, log record, or live API observation.
4. **Safety-First Saga Recovery**: All recovery operations require pre-flight idempotency checks, dry-run simulation mode, and human approval gates for high-risk financial actions.

---

## 📁 Repository Structure

```
Invariant/
├── Makefile                               # Build, test, and benchmark targets
├── docker-compose.yml                     # 10 container services (Microservices + DB + AI)
├── docker/init-db.sql                     # Multi-database initialization script
│
├── invariant-shared/                      # Canonical ICEF event models & asyncpg base
├── order-service/        (Port 8001)      # Commerce / Shopify simulator (orders_db)
├── payment-service/      (Port 8002)      # Gateway / Razorpay simulator with Idempotency Keys (payments_db)
├── erp-service/          (Port 8003)      # Enterprise ERP with Silent Failure injection (erp_db)
├── shipping-service/     (Port 8004)      # Courier / Logistics simulator (shipping_db)
├── simulator/            (Port 8000)      # 6-step business transaction orchestrator
│
├── failure-generator/    (Port 8010)      # 50-Scenario benchmark catalog & injection API
│   └── catalog/scenarios.py               # 50 reproducible failure definitions with ground-truth
│
├── invariant-core/       (Port 8080)      # Core Integrity Platform (invariant_core_db)
│   ├── app/normalizers/                   # Razorpay, Shopify, ERP, Shipping ICEF normalizers
│   ├── app/engine/state_machine.py        # Transaction lifecycle state engine
│   ├── app/engine/correlation.py          # Cross-system entity reference correlator
│   ├── app/engine/invariants.py           # SQL business invariant evaluation engine
│   ├── app/engine/reconciliation.py       # Dual-track scheduled reconciliation sweep
│   └── app/services/incident_service.py   # Incident management & deduplication
│
├── invariant-ai/         (Port 8090)      # Google ADK Multi-Agent Intelligence Layer
│   ├── app/agents/orchestrator.py         # Multi-agent investigation pipeline
│   ├── app/rag/retriever.py               # Hybrid RAG (Dense + BM25 Sparse + RRF)
│   ├── app/telemetry/metrics.py           # LLM native metrics (tokens, cost, latency, cache)
│   └── knowledge_base/runbooks/           # Operational troubleshooting runbooks
│
├── invariant-recovery/   (Port 8095)      # Saga Orchestration & Recovery Engine
│   ├── app/saga/compensation_map.py       # Compensating action registry
│   └── app/engine/executor.py             # Pre-flight checks, dry runs, approval gates
│
└── benchmark/                             # Benchmark evaluation suite
    ├── benchmark_runner.py                # 50-scenario evaluation engine
    └── BENCHMARK_REPORT.md                # Published benchmark report
```

---

## 🚀 Quick Start

### 1. Run Automated Test Suite (30 Tests)
```bash
make test
```

### 2. Run Benchmark Evaluation Suite
```bash
make benchmark
```

### 3. Start Local Microservices & Infrastructure
```bash
make up
```

### 4. Trigger Happy Path Simulation
```bash
make simulate-happy-path
```

---

## 🎯 Google Forward Deployed Engineer Alignment

| Requirement | Invariant Architecture & Implementation | Proof in Codebase |
|---|---|---|
| **Python & Algorithms** | Modern async Python 3.12, FastAPI, asyncpg, typed domain models | All 6 services |
| **Production AI to Launch** | Multi-agent ADK investigation pipeline with structured JSON outputs | `invariant-ai/app/agents/` |
| **Cloud Architecture** | Cloud Run microservices, Cloud SQL, Pub/Sub, Cloud Trace, Secret Manager | `docker-compose.yml`, `invariant-roadmap.md` §10 |
| **Structured Pipelines** | ICEF event normalization, state machine, SQL invariant checks | `invariant-core/app/engine/` |
| **Unstructured Pipelines & RAG**| Hybrid Dense + BM25 Sparse retrieval with Reciprocal Rank Fusion | `invariant-ai/app/rag/` |
| **Multi-Agent Systems** | Orchestrator → Evidence Collector → Root Cause Analyst → Recovery Planner | `invariant-ai/app/agents/orchestrator.py` |
| **LLM Native Metrics** | Token counting, latency tracking, cost-per-request calculation, semantic cache | `invariant-ai/app/telemetry/metrics.py` |
| **State Management** | Saga compensation pattern, transactional outbox, idempotency keys | `invariant-recovery/` |
| **Technical Discovery** | 50 reproducible failure catalog, benchmark methodology, published report | `failure-generator/`, `benchmark/` |

---

*Licensed under Apache 2.0. Built for Google Cloud Consulting.*
