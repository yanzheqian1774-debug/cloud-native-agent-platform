-- D324-6: immutable exact planning preparation and one bounded count revision.
CREATE TABLE authorization_admin.planning_call_preparations (
 tenant_id text NOT NULL, security_domain text NOT NULL, subject_id text NOT NULL,
 request_key text NOT NULL, context_id text NOT NULL UNIQUE
 REFERENCES authorization_admin.context_call_requests(context_id),
 input_commitment text NOT NULL, record jsonb NOT NULL,
 PRIMARY KEY(tenant_id,security_domain,subject_id,request_key)
);
CREATE TABLE authorization_admin.planning_call_allowances (
 tenant_id text NOT NULL, security_domain text NOT NULL, ledger_id text NOT NULL,
 context_id text NOT NULL UNIQUE REFERENCES authorization_admin.context_call_requests(context_id),
 original_call_cap integer NOT NULL CHECK(original_call_cap=8),
 cumulative_call_cap integer NOT NULL CHECK(cumulative_call_cap=20),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,security_domain,ledger_id)
);
CREATE TRIGGER immutable_planning_preparation BEFORE UPDATE OR DELETE ON
 authorization_admin.planning_call_preparations FOR EACH ROW
 EXECUTE FUNCTION authorization_admin.task_delegation_immutable();
CREATE TRIGGER immutable_planning_allowance BEFORE UPDATE OR DELETE ON
 authorization_admin.planning_call_allowances FOR EACH ROW
 EXECUTE FUNCTION authorization_admin.task_delegation_immutable();
