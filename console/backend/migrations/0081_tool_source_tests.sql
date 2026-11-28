CREATE TABLE tool_definition.source_test_requests (
 namespace text NOT NULL, security_domain text NOT NULL, subject_id text NOT NULL,
 command_key text NOT NULL, binding_digest text NOT NULL, request_digest text NOT NULL,
 request jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,subject_id,command_key),
 UNIQUE(namespace,security_domain,command_key)
);
CREATE TABLE tool_definition.source_test_facts (
 namespace text NOT NULL, security_domain text NOT NULL, subject_id text NOT NULL,
 command_key text NOT NULL, kind text NOT NULL, fact jsonb NOT NULL,
 fact_digest text NOT NULL, recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,subject_id,command_key,kind),
 FOREIGN KEY(namespace,security_domain,subject_id,command_key)
 REFERENCES tool_definition.source_test_requests(namespace,security_domain,subject_id,command_key),
 CHECK(kind IN ('DISPATCH_CLAIM','RESULT'))
);
CREATE FUNCTION tool_definition.reject_source_test_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'TOOL_SOURCE_TEST_APPEND_ONLY'; END $$;
CREATE TRIGGER source_test_requests_immutable BEFORE UPDATE OR DELETE
ON tool_definition.source_test_requests FOR EACH ROW
EXECUTE FUNCTION tool_definition.reject_source_test_mutation();
CREATE TRIGGER source_test_facts_immutable BEFORE UPDATE OR DELETE
ON tool_definition.source_test_facts FOR EACH ROW
EXECUTE FUNCTION tool_definition.reject_source_test_mutation();
