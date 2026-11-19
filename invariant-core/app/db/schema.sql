-- Invariant Core Schema
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,
    api_key_hash    TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_definitions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    name            TEXT NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    description     TEXT,
    steps           JSONB NOT NULL,
    invariants      JSONB NOT NULL DEFAULT '[]',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, name, version)
);

CREATE TABLE IF NOT EXISTS transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    workflow_id     UUID NOT NULL REFERENCES workflow_definitions(id),
    reference_code  TEXT NOT NULL UNIQUE,
    state           TEXT NOT NULL DEFAULT 'INITIATED'
                    CHECK (state IN (
                        'INITIATED', 'IN_PROGRESS', 'COMPLETED',
                        'INCONSISTENT', 'RECOVERING', 'FAILED',
                        'CANCELLED', 'COMPENSATED'
                    )),
    context         JSONB NOT NULL DEFAULT '{}',
    expected_completion_at  TIMESTAMPTZ,
    completed_at            TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version         BIGINT NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_transactions_tenant_state ON transactions(tenant_id, state);
CREATE INDEX IF NOT EXISTS idx_transactions_reference ON transactions(reference_code);
CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions(created_at DESC);

CREATE TABLE IF NOT EXISTS entity_references (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id  UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    system_name     TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    entity_snapshot JSONB,
    confidence      NUMERIC(4,3) NOT NULL DEFAULT 1.000 CHECK (confidence BETWEEN 0 AND 1),
    mapping_method  TEXT NOT NULL CHECK (mapping_method IN ('EXPLICIT_ID', 'RULE_BASED', 'MANUAL')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (system_name, entity_type, external_id)
);

CREATE INDEX IF NOT EXISTS idx_entity_refs_transaction ON entity_references(transaction_id);
CREATE INDEX IF NOT EXISTS idx_entity_refs_lookup ON entity_references(system_name, external_id);

CREATE TABLE IF NOT EXISTS ingested_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    idempotency_key     TEXT NOT NULL UNIQUE,
    source_system       TEXT NOT NULL,
    source_event_id     TEXT NOT NULL,
    event_type          TEXT NOT NULL,
    raw_event_type      TEXT NOT NULL,
    raw_payload         JSONB NOT NULL,
    canonical_payload   JSONB NOT NULL,
    occurred_at         TIMESTAMPTZ NOT NULL,
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    transaction_id      UUID REFERENCES transactions(id),
    correlation_confidence NUMERIC(4,3),
    processing_state    TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (processing_state IN (
                            'PENDING', 'CORRELATED', 'PROCESSED',
                            'UNRESOLVABLE', 'DEAD_LETTERED'
                        )),
    signature_verified  BOOLEAN NOT NULL DEFAULT FALSE,
    signature_header    TEXT,
    pubsub_message_id   TEXT,
    pubsub_subscription TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_transaction ON ingested_events(transaction_id);
CREATE INDEX IF NOT EXISTS idx_events_source_type ON ingested_events(source_system, event_type);
CREATE INDEX IF NOT EXISTS idx_events_ingested_at ON ingested_events(ingested_at DESC);

CREATE TABLE IF NOT EXISTS transaction_steps (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id      UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    step_key            TEXT NOT NULL,
    step_order          INTEGER NOT NULL,
    state               TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (state IN (
                            'PENDING', 'COMPLETED', 'SKIPPED',
                            'FAILED', 'COMPENSATED', 'TIMED_OUT'
                        )),
    triggering_event_id UUID REFERENCES ingested_events(id),
    step_data           JSONB,
    validations         JSONB,
    expected_by         TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (transaction_id, step_key)
);

CREATE INDEX IF NOT EXISTS idx_steps_transaction ON transaction_steps(transaction_id);

CREATE TABLE IF NOT EXISTS incidents (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NOT NULL REFERENCES tenants(id),
    transaction_id          UUID REFERENCES transactions(id),
    incident_type           TEXT NOT NULL
                            CHECK (incident_type IN (
                                'MISSING_STEP', 'DUPLICATE_EVENT', 'DATA_MISMATCH',
                                'ORDERING_VIOLATION', 'SLA_BREACH', 'ORPHAN_RECORD',
                                'SCHEMA_DRIFT', 'SILENT_FAILURE', 'UNRESOLVABLE'
                            )),
    severity                TEXT NOT NULL DEFAULT 'MEDIUM'
                            CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    state                   TEXT NOT NULL DEFAULT 'OPEN'
                            CHECK (state IN (
                                'OPEN', 'INVESTIGATING', 'RECOVERY_PROPOSED',
                                'RECOVERY_APPROVED', 'RECOVERING', 'RESOLVED',
                                'WONT_FIX', 'FALSE_POSITIVE'
                            )),
    investigation           JSONB,
    estimated_impact_amount NUMERIC(18, 4),
    estimated_impact_currency TEXT DEFAULT 'INR',
    detected_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS recovery_plans (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id         UUID NOT NULL REFERENCES incidents(id),
    steps               JSONB NOT NULL,
    requires_approval   BOOLEAN NOT NULL DEFAULT TRUE,
    approved_by         TEXT,
    approved_at         TIMESTAMPTZ,
    execution_state     TEXT NOT NULL DEFAULT 'DRAFT'
                        CHECK (execution_state IN (
                            'DRAFT', 'APPROVED', 'DRY_RUN_IN_PROGRESS',
                            'DRY_RUN_COMPLETE', 'EXECUTING', 'COMPLETED',
                            'FAILED', 'ROLLED_BACK'
                        )),
    dry_run_result      JSONB,
    execution_log       JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

