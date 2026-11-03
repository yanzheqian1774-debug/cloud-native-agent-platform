-- D8 additive development authority; historical 8/20/21 and USD10 remain intact.
CREATE TABLE authorization_admin.planning_recovery_observations (
 observation_id text PRIMARY KEY,
 tenant_id text NOT NULL, security_domain text NOT NULL,
 subject_id text NOT NULL, root_id text NOT NULL, invocation_id text NOT NULL,
 request_key text NOT NULL, digest text NOT NULL, record jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,security_domain,subject_id,request_key)
);
CREATE TRIGGER immutable_planning_recovery_observation BEFORE UPDATE OR DELETE ON
 authorization_admin.planning_recovery_observations FOR EACH ROW
 EXECUTE FUNCTION authorization_admin.task_delegation_immutable();
CREATE TABLE authorization_admin.development_planning_followups (
 task_request_id text PRIMARY KEY REFERENCES authorization_admin.bounded_task_requests(request_id),
 context_id text NOT NULL UNIQUE REFERENCES authorization_admin.context_call_requests(context_id),
 predecessor_invocation_id text NOT NULL,
 tenant_id text NOT NULL, security_domain text NOT NULL, subject_id text NOT NULL,
 root_id text NOT NULL, ledger_id text NOT NULL,
 cumulative_call_cap integer NOT NULL CHECK(cumulative_call_cap=100),
 total_cost_cap_microusd bigint NOT NULL CHECK(total_cost_cap_microusd=50000000),
 UNIQUE(tenant_id,security_domain,ledger_id,predecessor_invocation_id)
);
CREATE TRIGGER immutable_development_planning_followup BEFORE UPDATE OR DELETE ON
 authorization_admin.development_planning_followups FOR EACH ROW
 EXECUTE FUNCTION authorization_admin.task_delegation_immutable();
