-- Internal records of one existing governed Skill invocation, not a new lifecycle.
CREATE TABLE IF NOT EXISTS skill_invocation.native_loop_records (
 namespace text NOT NULL, security_domain text NOT NULL,
 skill_invocation_id text NOT NULL, record_key text NOT NULL,
 request_digest text NOT NULL CHECK(length(request_digest)=64),
 result jsonb, created_at timestamptz NOT NULL DEFAULT now(),
 completed_at timestamptz,
 PRIMARY KEY(namespace,security_domain,skill_invocation_id,record_key),
 FOREIGN KEY(namespace,security_domain,skill_invocation_id)
 REFERENCES skill_invocation.invocations(namespace,security_domain,skill_invocation_id)
);
