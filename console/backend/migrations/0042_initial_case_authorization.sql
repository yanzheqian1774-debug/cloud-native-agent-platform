-- D9 initial exact-case calls; does not replace D7/D8 history or budget policies.
CREATE TABLE authorization_admin.initial_case_planning_calls (
 task_request_id text PRIMARY KEY REFERENCES authorization_admin.bounded_task_requests(request_id),
 context_id text NOT NULL UNIQUE REFERENCES authorization_admin.context_call_requests(context_id),
 tenant_id text NOT NULL, security_domain text NOT NULL, subject_id text NOT NULL,
 root_id text NOT NULL, ledger_id text NOT NULL,
 cumulative_call_cap integer NOT NULL CHECK(cumulative_call_cap=100),
 total_cost_cap_microusd bigint NOT NULL CHECK(total_cost_cap_microusd=50000000)
);
CREATE TRIGGER immutable_initial_case_planning_call BEFORE UPDATE OR DELETE ON
 authorization_admin.initial_case_planning_calls FOR EACH ROW
 EXECUTE FUNCTION authorization_admin.task_delegation_immutable();
