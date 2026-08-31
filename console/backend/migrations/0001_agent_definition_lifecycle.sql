CREATE SCHEMA IF NOT EXISTS agent_definition;

CREATE TABLE IF NOT EXISTS agent_definition.schema_migrations (
    version integer PRIMARY KEY,
    checksum text NOT NULL,
    adapter text NOT NULL CHECK (adapter = 'agent-definition-postgresql-v1'),
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_definition.definitions (
    namespace text NOT NULL,
    security_domain text NOT NULL,
    definition_id text NOT NULL,
    aggregate_version bigint NOT NULL CHECK (aggregate_version > 0),
    record jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (namespace, security_domain, definition_id),
    CHECK (record->>'namespace' = namespace),
    CHECK (record->>'securityDomain' = security_domain),
    CHECK (record->>'definitionId' = definition_id),
    CHECK ((record->>'aggregateVersion')::bigint = aggregate_version)
);

CREATE TABLE IF NOT EXISTS agent_definition.lifecycle_facts (
    namespace text NOT NULL,
    security_domain text NOT NULL,
    definition_id text NOT NULL,
    ordinal bigint NOT NULL,
    fact_id text NOT NULL,
    fact jsonb NOT NULL,
    PRIMARY KEY (namespace, security_domain, definition_id, ordinal),
    UNIQUE (namespace, security_domain, fact_id),
    FOREIGN KEY (namespace, security_domain, definition_id)
        REFERENCES agent_definition.definitions(namespace, security_domain, definition_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_definition.tombstones (
    namespace text NOT NULL,
    security_domain text NOT NULL,
    definition_id text NOT NULL,
    tombstone jsonb NOT NULL,
    PRIMARY KEY (namespace, security_domain, definition_id)
);
