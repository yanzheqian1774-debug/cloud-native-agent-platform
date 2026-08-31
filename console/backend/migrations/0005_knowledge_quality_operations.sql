-- S5-IMPL-050. Migration 0004 is intentionally owned by S5-IMPL-049.
-- Final chain validation is blocked until 0004 is durably integrated.
CREATE SCHEMA IF NOT EXISTS knowledge_quality;

CREATE TABLE IF NOT EXISTS knowledge_quality.schema_migrations (
    version integer PRIMARY KEY,
    checksum text NOT NULL,
    adapter text NOT NULL CHECK (adapter = 'knowledge-quality-postgresql-v1'),
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_quality.entities (
    namespace text NOT NULL,
    security_domain text NOT NULL,
    entity_type text NOT NULL CHECK (entity_type IN (
      'IMPORT_JOB', 'EVALUATION_DATASET', 'EVALUATION_RUN',
      'RETRIEVAL_CONFIGURATION', 'METRIC_FACT', 'SUMMARY',
      'DUPLICATE_CANDIDATE', 'DUPLICATE_DECISION'
    )),
    entity_id text NOT NULL,
    entity_digest text NOT NULL CHECK (entity_digest ~ '^[0-9a-f]{64}$'),
    record jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (namespace, security_domain, entity_type, entity_id),
    CHECK (record->>'namespace' = namespace),
    CHECK (record->>'securityDomain' = security_domain),
    CHECK (record->>'entityType' = entity_type),
    CHECK (record->>'entityId' = entity_id),
    CHECK (record->>'digest' = entity_digest)
);

CREATE INDEX IF NOT EXISTS knowledge_quality_entities_scope_type
  ON knowledge_quality.entities(namespace, security_domain, entity_type, created_at, entity_id);
