CREATE SCHEMA IF NOT EXISTS browser_identity;
CREATE SCHEMA IF NOT EXISTS authorization_admin;

CREATE TABLE IF NOT EXISTS browser_identity.schema_migrations (
    version integer PRIMARY KEY,
    checksum text NOT NULL,
    adapter text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS browser_identity.login_nonces (
    nonce_digest text PRIMARY KEY CHECK (length(nonce_digest) = 64),
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS browser_identity.sessions (
    session_id text PRIMARY KEY,
    secret_digest text NOT NULL UNIQUE CHECK (length(secret_digest) = 64),
    principal_id text NOT NULL,
    tenant_id text NOT NULL,
    security_domain text NOT NULL,
    credential_id text NOT NULL,
    credential_expires_at timestamptz NOT NULL,
    authentication_policy_version text NOT NULL,
    issued_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    idle_expires_at timestamptz NOT NULL,
    absolute_expires_at timestamptz NOT NULL,
    recovery_epoch bigint NOT NULL CHECK (recovery_epoch > 0),
    authority_generation bigint NOT NULL CHECK (authority_generation > 0),
    rotated_to_session_id text REFERENCES browser_identity.sessions(session_id),
    CHECK (issued_at <= last_seen_at),
    CHECK (last_seen_at <= idle_expires_at),
    CHECK (idle_expires_at <= absolute_expires_at),
    CHECK (absolute_expires_at <= credential_expires_at)
);

CREATE INDEX IF NOT EXISTS sessions_credential_idx
    ON browser_identity.sessions (credential_id);

CREATE TABLE IF NOT EXISTS browser_identity.session_revocation_facts (
    revocation_id text PRIMARY KEY,
    session_id text NOT NULL UNIQUE REFERENCES browser_identity.sessions(session_id),
    reason_category text NOT NULL,
    actor_id text NOT NULL,
    revoked_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS authorization_admin.schema_migrations (
    version integer PRIMARY KEY,
    checksum text NOT NULL,
    adapter text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS authorization_admin.active_generation (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    generation bigint NOT NULL CHECK (generation > 0),
    generation_digest text NOT NULL CHECK (length(generation_digest) = 64),
    recovery_epoch bigint NOT NULL CHECK (recovery_epoch > 0),
    activated_by text NOT NULL,
    activated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS authorization_admin.grant_requests (
    request_id text PRIMARY KEY,
    subject_principal_id text NOT NULL,
    tenant_id text NOT NULL,
    security_domain text NOT NULL,
    purpose text NOT NULL,
    state text NOT NULL CHECK (state IN ('PENDING', 'APPROVED', 'REJECTED')),
    aggregate_version bigint NOT NULL DEFAULT 1 CHECK (aggregate_version > 0),
    created_at timestamptz NOT NULL,
    decided_at timestamptz
);

CREATE TABLE IF NOT EXISTS authorization_admin.grant_request_members (
    request_id text NOT NULL REFERENCES authorization_admin.grant_requests(request_id),
    ordinal integer NOT NULL CHECK (ordinal > 0),
    owner text NOT NULL,
    action text NOT NULL,
    exact_resource text NOT NULL CHECK (position('*' in exact_resource) = 0),
    PRIMARY KEY (request_id, ordinal),
    UNIQUE (request_id, owner, action, exact_resource)
);

CREATE TABLE IF NOT EXISTS authorization_admin.grant_decisions (
    decision_id text PRIMARY KEY,
    request_id text NOT NULL UNIQUE REFERENCES authorization_admin.grant_requests(request_id),
    issuer_principal_id text NOT NULL,
    issuer_meta_decision_id text NOT NULL,
    approved boolean NOT NULL,
    reason_category text NOT NULL,
    basis_type text NOT NULL,
    basis_reference_digest text NOT NULL CHECK (length(basis_reference_digest) = 64),
    policy_version text NOT NULL,
    audit_source text NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS authorization_admin.grants (
    grant_id text PRIMARY KEY,
    decision_id text NOT NULL REFERENCES authorization_admin.grant_decisions(decision_id),
    request_id text NOT NULL REFERENCES authorization_admin.grant_requests(request_id),
    subject_principal_id text NOT NULL,
    tenant_id text NOT NULL,
    security_domain text NOT NULL,
    owner text NOT NULL,
    action text NOT NULL,
    exact_resource text NOT NULL CHECK (position('*' in exact_resource) = 0),
    basis_type text NOT NULL,
    basis_reference_digest text NOT NULL CHECK (length(basis_reference_digest) = 64),
    issuer_principal_id text NOT NULL,
    issuer_meta_decision_id text NOT NULL,
    policy_version text NOT NULL,
    audit_source text NOT NULL,
    not_before timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL,
    recovery_epoch bigint NOT NULL CHECK (recovery_epoch > 0),
    CHECK (not_before < expires_at),
    UNIQUE (decision_id, owner, action, exact_resource)
);

CREATE TABLE IF NOT EXISTS authorization_admin.effective_grants (
    grant_id text PRIMARY KEY REFERENCES authorization_admin.grants(grant_id),
    subject_principal_id text NOT NULL,
    tenant_id text NOT NULL,
    security_domain text NOT NULL,
    owner text NOT NULL,
    action text NOT NULL,
    exact_resource text NOT NULL,
    not_before timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    recovery_epoch bigint NOT NULL
);

CREATE INDEX IF NOT EXISTS effective_grant_lookup_idx
    ON authorization_admin.effective_grants
    (subject_principal_id, tenant_id, security_domain, owner, action, exact_resource);

CREATE TABLE IF NOT EXISTS authorization_admin.continuation_offers (
    offer_id text PRIMARY KEY,
    continuation_digest text NOT NULL UNIQUE CHECK (length(continuation_digest) = 64),
    subject_principal_id text NOT NULL,
    tenant_id text NOT NULL,
    security_domain text NOT NULL,
    purpose text NOT NULL,
    owner text NOT NULL,
    canonical_resource_reference text NOT NULL,
    owner_revision text NOT NULL,
    policy_generation bigint NOT NULL CHECK (policy_generation > 0),
    mint_key text NOT NULL,
    mint_payload_digest text NOT NULL CHECK (length(mint_payload_digest) = 64),
    issued_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    recovery_epoch bigint NOT NULL CHECK (recovery_epoch > 0),
    UNIQUE (owner, canonical_resource_reference, subject_principal_id, purpose, mint_key),
    CHECK (issued_at < expires_at)
);

CREATE TABLE IF NOT EXISTS authorization_admin.continuation_offer_members (
    offer_id text NOT NULL REFERENCES authorization_admin.continuation_offers(offer_id),
    ordinal integer NOT NULL CHECK (ordinal > 0),
    owner text NOT NULL,
    action text NOT NULL,
    exact_resource text NOT NULL CHECK (position('*' in exact_resource) = 0),
    PRIMARY KEY (offer_id, ordinal),
    UNIQUE (offer_id, owner, action, exact_resource)
);

CREATE TABLE IF NOT EXISTS authorization_admin.continuation_consumptions (
    continuation_digest text PRIMARY KEY,
    request_id text NOT NULL UNIQUE REFERENCES authorization_admin.grant_requests(request_id),
    subject_principal_id text NOT NULL,
    purpose text NOT NULL,
    idempotency_key text NOT NULL,
    payload_digest text NOT NULL CHECK (length(payload_digest) = 64),
    consumed_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS authorization_admin.grant_revocation_facts (
    revocation_id text PRIMARY KEY,
    grant_id text NOT NULL UNIQUE REFERENCES authorization_admin.grants(grant_id),
    actor_id text NOT NULL,
    reason_category text NOT NULL,
    payload_digest text NOT NULL CHECK (length(payload_digest) = 64),
    revoked_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS authorization_admin.idempotency_claims (
    tenant_id text NOT NULL,
    security_domain text NOT NULL,
    actor_id text NOT NULL,
    command_type text NOT NULL,
    idempotency_key text NOT NULL,
    payload_digest text NOT NULL CHECK (length(payload_digest) = 64),
    result_kind text NOT NULL,
    result_id text NOT NULL,
    result_record jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY
      (tenant_id, security_domain, actor_id, command_type, idempotency_key)
);

CREATE TABLE IF NOT EXISTS authorization_admin.recovery_records (
    recovery_epoch bigint PRIMARY KEY CHECK (recovery_epoch > 0),
    database_fingerprint text NOT NULL,
    generation bigint NOT NULL CHECK (generation > 0),
    generation_digest text NOT NULL CHECK (length(generation_digest) = 64),
    migration_version integer NOT NULL,
    state text NOT NULL CHECK (state IN ('RECOVERY_CLOSED', 'ACTIVE')),
    operator_id text NOT NULL,
    audit_continuity_digest text NOT NULL CHECK (length(audit_continuity_digest) = 64),
    recorded_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS authorization_admin.audit_events (
    event_id text PRIMARY KEY,
    event_type text NOT NULL,
    actor_id text NOT NULL,
    tenant_id text,
    security_domain text,
    subject_id text,
    generation bigint,
    recovery_epoch bigint,
    outcome text NOT NULL,
    reason_category text NOT NULL,
    event_digest text NOT NULL CHECK (length(event_digest) = 64),
    occurred_at timestamptz NOT NULL
);
