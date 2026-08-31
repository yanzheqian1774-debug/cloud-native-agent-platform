CREATE SCHEMA IF NOT EXISTS knowledge_operation;

CREATE TABLE IF NOT EXISTS knowledge_operation.schema_migrations (
    version integer PRIMARY KEY,
    checksum text NOT NULL,
    adapter text NOT NULL CHECK (adapter = 'knowledge-postgresql-v1'),
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_operation.knowledge (
    namespace text NOT NULL,
    security_domain text NOT NULL,
    knowledge_id text NOT NULL,
    aggregate_version bigint NOT NULL CHECK (aggregate_version > 0),
    record jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (namespace, security_domain, knowledge_id),
    CHECK (record->>'namespace' = namespace),
    CHECK (record->>'securityDomain' = security_domain),
    CHECK (record->>'knowledgeId' = knowledge_id),
    CHECK ((record->>'aggregateVersion')::bigint = aggregate_version)
);

CREATE TABLE IF NOT EXISTS knowledge_operation.lifecycle_facts (
    namespace text NOT NULL,
    security_domain text NOT NULL,
    knowledge_id text NOT NULL,
    ordinal bigint NOT NULL,
    fact_id text NOT NULL,
    fact jsonb NOT NULL,
    PRIMARY KEY (namespace, security_domain, knowledge_id, ordinal),
    UNIQUE (namespace, security_domain, fact_id),
    FOREIGN KEY (namespace, security_domain, knowledge_id)
      REFERENCES knowledge_operation.knowledge(namespace, security_domain, knowledge_id)
);

CREATE TABLE IF NOT EXISTS knowledge_operation.purge_tombstones (
    namespace text NOT NULL,
    security_domain text NOT NULL,
    knowledge_id text NOT NULL,
    tombstone jsonb NOT NULL,
    PRIMARY KEY (namespace, security_domain, knowledge_id)
);
