-- Append-only references to actual model results; no invocation/receipt copying.
CREATE TABLE draft_assistance.result_adoptions (
 namespace text NOT NULL,
 security_domain text NOT NULL,
 original_invocation_id text NOT NULL,
 result_invocation_id text NOT NULL,
 subject_id text NOT NULL,
 conversation_id text NOT NULL,
 message_id text NOT NULL,
 request_key text NOT NULL,
 record_digest text NOT NULL CHECK(record_digest ~ '^[0-9a-f]{64}$'),
 record jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,original_invocation_id),
 UNIQUE(namespace,security_domain,result_invocation_id),
 UNIQUE(namespace,security_domain,subject_id,request_key),
 FOREIGN KEY(namespace,security_domain,original_invocation_id)
  REFERENCES draft_assistance.invocations(namespace,security_domain,invocation_id),
 FOREIGN KEY(namespace,security_domain,result_invocation_id)
  REFERENCES draft_assistance.invocations(namespace,security_domain,invocation_id),
 CHECK(original_invocation_id <> result_invocation_id)
);
CREATE FUNCTION draft_assistance.immutable_result_adoption() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'IMMUTABLE_UNDERSTANDING_ADOPTION'; END $$;
CREATE TRIGGER immutable_result_adoption BEFORE UPDATE OR DELETE ON
 draft_assistance.result_adoptions FOR EACH ROW
 EXECUTE FUNCTION draft_assistance.immutable_result_adoption();
