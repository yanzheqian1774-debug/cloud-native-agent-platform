CREATE TABLE authorization_admin.mcp_tool_test_requests (
 namespace text NOT NULL, security_domain text NOT NULL, subject_id text NOT NULL,
 command_key text NOT NULL, binding_digest text NOT NULL, request_digest text NOT NULL,
 request jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,subject_id,command_key)
);
CREATE TABLE authorization_admin.mcp_tool_test_facts (
 namespace text NOT NULL, security_domain text NOT NULL, subject_id text NOT NULL,
 command_key text NOT NULL, ordinal integer NOT NULL, kind text NOT NULL,
 fact jsonb NOT NULL, fact_digest text NOT NULL, recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,subject_id,command_key,ordinal),
 UNIQUE(namespace,security_domain,subject_id,command_key,kind),
 FOREIGN KEY(namespace,security_domain,subject_id,command_key) REFERENCES authorization_admin.mcp_tool_test_requests(namespace,security_domain,subject_id,command_key),
 CHECK(kind IN ('DISPATCH_CLAIM','RESULT'))
);

CREATE FUNCTION authorization_admin.reject_mcp_tool_test_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'MCP_TOOL_TEST_APPEND_ONLY'; END $$;
CREATE TRIGGER mcp_tool_test_requests_immutable BEFORE UPDATE OR DELETE
ON authorization_admin.mcp_tool_test_requests FOR EACH ROW
EXECUTE FUNCTION authorization_admin.reject_mcp_tool_test_mutation();
CREATE TRIGGER mcp_tool_test_facts_immutable BEFORE UPDATE OR DELETE
ON authorization_admin.mcp_tool_test_facts FOR EACH ROW
EXECUTE FUNCTION authorization_admin.reject_mcp_tool_test_mutation();
ALTER TABLE authorization_admin.mcp_tool_test_facts ADD CHECK
 ((ordinal=1 AND kind='DISPATCH_CLAIM') OR (ordinal=2 AND kind='RESULT'));
