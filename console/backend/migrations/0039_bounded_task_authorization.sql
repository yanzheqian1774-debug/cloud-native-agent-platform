-- D324-7 A: immutable task/root/scope authorization; no historical grants changed.
CREATE TABLE authorization_admin.bounded_task_requests (
 request_id text PRIMARY KEY, task_id text NOT NULL CHECK(task_id='S5-V023-IMPL-324'),
 tenant_id text NOT NULL, security_domain text NOT NULL, root_id text NOT NULL,
 subject_id text NOT NULL, account_id text NOT NULL, account_revision bigint NOT NULL,
 request_key text NOT NULL, digest text NOT NULL, record jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,security_domain,subject_id,request_key)
);
CREATE TABLE authorization_admin.bounded_task_decisions (
 decision_id text PRIMARY KEY, request_id text NOT NULL REFERENCES authorization_admin.bounded_task_requests,
 predecessor_id text REFERENCES authorization_admin.bounded_task_decisions,
 issuer_id text NOT NULL, idempotency_key text NOT NULL, payload_digest text NOT NULL,
 not_before timestamptz NOT NULL, expires_at timestamptz NOT NULL,
 generation bigint NOT NULL, recovery_epoch bigint NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK(expires_at>not_before AND expires_at<=not_before+interval '8 hours'),
 UNIQUE(issuer_id,idempotency_key)
);
CREATE TABLE authorization_admin.bounded_task_revocations (
 decision_id text PRIMARY KEY REFERENCES authorization_admin.bounded_task_decisions,
 actor_id text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE authorization_admin.bounded_task_objects (
 request_id text NOT NULL REFERENCES authorization_admin.bounded_task_requests,
 owner text NOT NULL, resource_id text NOT NULL, revision_id text NOT NULL,
 digest text NOT NULL, parent_owner text, parent_id text, parent_revision_id text, origin text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(request_id,owner,resource_id,revision_id),
 FOREIGN KEY(request_id,parent_owner,parent_id,parent_revision_id)
 REFERENCES authorization_admin.bounded_task_objects(request_id,owner,resource_id,revision_id)
);
CREATE TABLE authorization_admin.bounded_task_effects (
 decision_id text NOT NULL REFERENCES authorization_admin.bounded_task_decisions,
 owner text NOT NULL, action text NOT NULL, resource_id text NOT NULL,
 session_id text NOT NULL, checked_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(decision_id,owner,action,resource_id,session_id)
);
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['bounded_task_requests','bounded_task_decisions',
 'bounded_task_revocations','bounded_task_objects','bounded_task_effects'] LOOP
 EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON authorization_admin.%I FOR EACH ROW EXECUTE FUNCTION authorization_admin.task_delegation_immutable()', 'immutable_'||tab, tab);
 END LOOP;
END $$;
