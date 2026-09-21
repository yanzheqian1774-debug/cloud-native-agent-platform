-- Bounded task delegation belongs to the existing authorization owner.
SELECT pg_advisory_xact_lock(3230028);
CREATE TABLE IF NOT EXISTS authorization_admin.task_delegation_migrations (
 version integer PRIMARY KEY, checksum text NOT NULL
);
CREATE TABLE IF NOT EXISTS authorization_admin.task_delegations (
 delegation_id text PRIMARY KEY, task_id text NOT NULL,
 tenant_id text NOT NULL, security_domain text NOT NULL, subject_id text NOT NULL,
 root_context_id text NOT NULL, issuer_id text NOT NULL CHECK(issuer_id<>subject_id),
 generation bigint NOT NULL, recovery_epoch bigint NOT NULL,
 created_at timestamptz NOT NULL, expires_at timestamptz NOT NULL,
 idempotency_key text NOT NULL, digest text NOT NULL, record jsonb NOT NULL,
 UNIQUE(tenant_id,security_domain,task_id),
 UNIQUE(tenant_id,security_domain,subject_id),
 UNIQUE(tenant_id,security_domain,root_context_id),
 UNIQUE(tenant_id,security_domain,issuer_id,idempotency_key),
 CHECK(expires_at>created_at)
);
CREATE TABLE IF NOT EXISTS authorization_admin.task_delegation_control (
 delegation_id text PRIMARY KEY REFERENCES authorization_admin.task_delegations,
 revoked boolean NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS authorization_admin.task_delegation_revocations (
 delegation_id text PRIMARY KEY REFERENCES authorization_admin.task_delegations,
 actor_id text NOT NULL, revoked_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS authorization_admin.task_delegation_decisions (
 decision_id text PRIMARY KEY REFERENCES authorization_admin.grant_decisions,
 delegation_id text NOT NULL REFERENCES authorization_admin.task_delegations,
 request_id text NOT NULL UNIQUE REFERENCES authorization_admin.grant_requests,
 target_digest text NOT NULL
);
CREATE TABLE IF NOT EXISTS authorization_admin.task_delegation_ledgers (
 tenant_id text NOT NULL, security_domain text NOT NULL, ledger_id text NOT NULL,
 delegation_id text NOT NULL REFERENCES authorization_admin.task_delegations,
 purpose text NOT NULL CHECK(purpose IN ('understanding','planning')),
 PRIMARY KEY(tenant_id,security_domain,ledger_id),
 UNIQUE(delegation_id,purpose)
);
CREATE TABLE IF NOT EXISTS authorization_admin.task_delegation_resources (
 tenant_id text NOT NULL, security_domain text NOT NULL,
 owner text NOT NULL, resource_id text NOT NULL,
 delegation_id text NOT NULL REFERENCES authorization_admin.task_delegations,
 PRIMARY KEY(tenant_id,security_domain,owner,resource_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS task_delegation_one_problem
 ON authorization_admin.task_delegation_resources(delegation_id)
 WHERE owner='BUSINESS_PROBLEM';
CREATE OR REPLACE FUNCTION authorization_admin.task_delegation_immutable()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 RAISE EXCEPTION 'TASK_DELEGATION_IMMUTABLE';
END $$;
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['task_delegations','task_delegation_revocations',
 'task_delegation_decisions','task_delegation_ledgers','task_delegation_resources'] LOOP
 IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='immutable_' || tab) THEN
 EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON authorization_admin.%I FOR EACH ROW EXECUTE FUNCTION authorization_admin.task_delegation_immutable()', 'immutable_' || tab, tab);
 END IF;
 END LOOP;
END $$;
