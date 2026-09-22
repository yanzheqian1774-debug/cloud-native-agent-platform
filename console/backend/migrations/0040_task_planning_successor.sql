-- D324-7 B: one exact successor, not an additive 8+20+21 pool.
CREATE TABLE authorization_admin.task_planning_successors (
 task_request_id text PRIMARY KEY REFERENCES authorization_admin.bounded_task_requests(request_id),
 context_id text NOT NULL UNIQUE REFERENCES authorization_admin.context_call_requests(context_id),
 predecessor_invocation_id text NOT NULL,
 tenant_id text NOT NULL, security_domain text NOT NULL, ledger_id text NOT NULL,
 original_call_cap integer NOT NULL CHECK(original_call_cap=8),
 previous_cumulative_cap integer NOT NULL CHECK(previous_cumulative_cap=20),
 cumulative_call_cap integer NOT NULL CHECK(cumulative_call_cap=21),
 UNIQUE(tenant_id,security_domain,ledger_id)
);
CREATE TRIGGER immutable_task_planning_successor BEFORE UPDATE OR DELETE ON
 authorization_admin.task_planning_successors FOR EACH ROW
 EXECUTE FUNCTION authorization_admin.task_delegation_immutable();
