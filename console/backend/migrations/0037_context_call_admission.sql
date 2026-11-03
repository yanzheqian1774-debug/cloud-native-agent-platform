-- D324-5: bounded synthetic contexts; no grants, credentials or budget reset.
SELECT pg_advisory_xact_lock(3230028);
CREATE TABLE authorization_admin.context_call_requests (
 context_id text PRIMARY KEY,
 tenant_id text NOT NULL, security_domain text NOT NULL,
 subject_id text NOT NULL, account_id text NOT NULL,
 account_revision bigint NOT NULL,
 first_invocation_id text NOT NULL UNIQUE,
 record jsonb NOT NULL, digest text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE authorization_admin.context_call_decisions (
 admission_id text PRIMARY KEY,
 context_id text NOT NULL REFERENCES authorization_admin.context_call_requests,
 ordinal integer NOT NULL CHECK(ordinal>0),
 issuer_id text NOT NULL, subject_id text NOT NULL CHECK(issuer_id<>subject_id),
 generation bigint NOT NULL, recovery_epoch bigint NOT NULL,
 idempotency_key text NOT NULL, payload_digest text NOT NULL,
 record jsonb NOT NULL, created_at timestamptz NOT NULL,
 expires_at timestamptz NOT NULL,
 UNIQUE(context_id,ordinal), UNIQUE(issuer_id,idempotency_key),
 CHECK(expires_at>created_at AND expires_at<=created_at+interval '8 hours')
);
CREATE TABLE authorization_admin.context_call_revocations (
 admission_id text PRIMARY KEY REFERENCES authorization_admin.context_call_decisions,
 actor_id text NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE authorization_admin.context_call_objects (
 tenant_id text NOT NULL, security_domain text NOT NULL,
 owner text NOT NULL, resource_id text NOT NULL,
 context_id text NOT NULL REFERENCES authorization_admin.context_call_requests,
 invocation_id text NOT NULL,
 PRIMARY KEY(tenant_id,security_domain,owner,resource_id)
);
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['context_call_requests','context_call_decisions','context_call_revocations','context_call_objects'] LOOP
 EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON authorization_admin.%I FOR EACH ROW EXECUTE FUNCTION authorization_admin.task_delegation_immutable()', 'immutable_' || tab, tab);
 END LOOP;
END $$;
