-- Internal, opt-in bounded business authorization. No old context/budget rewrite.
CREATE TABLE authorization_admin.owned_business_admissions (
 admission_id text PRIMARY KEY,
 tenant_id text NOT NULL,
 security_domain text NOT NULL,
 subject_id text NOT NULL,
 conversation_id text NOT NULL,
 invocation_id text NOT NULL,
 context_id text NOT NULL REFERENCES authorization_admin.context_call_requests,
 policy_digest text NOT NULL,
 record_digest text NOT NULL,
 record jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,security_domain,subject_id,invocation_id)
);
CREATE TABLE authorization_admin.owned_business_revocations (
 admission_id text PRIMARY KEY REFERENCES authorization_admin.owned_business_admissions,
 actor_id text NOT NULL,
 reason_code text NOT NULL CHECK(reason_code IN ('POLICY_REVOKED','USER_REQUESTED')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER immutable_owned_business_admissions BEFORE UPDATE OR DELETE ON
 authorization_admin.owned_business_admissions FOR EACH ROW
 EXECUTE FUNCTION authorization_admin.task_delegation_immutable();
CREATE TRIGGER immutable_owned_business_revocations BEFORE UPDATE OR DELETE ON
 authorization_admin.owned_business_revocations FOR EACH ROW
 EXECUTE FUNCTION authorization_admin.task_delegation_immutable();
