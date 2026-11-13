-- F3 adapter of independently signed, one-call recovery; old UNKNOWN is immutable.
CREATE TABLE IF NOT EXISTS authorization_admin.conversation_planning_recoveries (
 recovery_id text PRIMARY KEY,
 tenant_id text NOT NULL, security_domain text NOT NULL, subject_id text NOT NULL,
 conversation_id text NOT NULL, predecessor_invocation_id text NOT NULL,
 request_key text NOT NULL, new_request_key text NOT NULL,
 record jsonb NOT NULL, digest text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,security_domain,subject_id,request_key),
 UNIQUE(tenant_id,security_domain,subject_id,predecessor_invocation_id),
 UNIQUE(tenant_id,security_domain,subject_id,new_request_key)
);
CREATE TABLE IF NOT EXISTS authorization_admin.conversation_planning_recovery_bindings (
 recovery_id text PRIMARY KEY REFERENCES authorization_admin.conversation_planning_recoveries(recovery_id),
 context_id text NOT NULL UNIQUE REFERENCES authorization_admin.context_call_requests(context_id),
 invocation_id text NOT NULL UNIQUE,
 record jsonb NOT NULL, digest text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER immutable_conversation_planning_recovery BEFORE UPDATE OR DELETE ON
 authorization_admin.conversation_planning_recoveries FOR EACH ROW
 EXECUTE FUNCTION authorization_admin.task_delegation_immutable();
CREATE TRIGGER immutable_conversation_planning_recovery_binding BEFORE UPDATE OR DELETE ON
 authorization_admin.conversation_planning_recovery_bindings FOR EACH ROW
 EXECUTE FUNCTION authorization_admin.task_delegation_immutable();
