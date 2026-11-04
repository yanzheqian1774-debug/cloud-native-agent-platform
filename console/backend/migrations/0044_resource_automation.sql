-- D11: immutable policy preparation receipts in the existing Execution owner.
CREATE TABLE IF NOT EXISTS execution_authority.resource_automation (
 namespace text NOT NULL, security_domain text NOT NULL,
 subject_id text NOT NULL, request_key text NOT NULL,
 plan_id text NOT NULL, plan_version bigint NOT NULL,
 payload_digest text NOT NULL, record jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,subject_id,request_key),
 FOREIGN KEY(namespace,security_domain,plan_id,plan_version)
 REFERENCES execution_authority.plan_references(namespace,security_domain,plan_id,plan_version)
);
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='immutable_resource_automation') THEN
  CREATE TRIGGER immutable_resource_automation BEFORE UPDATE OR DELETE
  ON execution_authority.resource_automation FOR EACH ROW
  EXECUTE FUNCTION execution_authority.preparation_immutable();
 END IF;
END $$;
CREATE TABLE IF NOT EXISTS execution_authority.resource_policy_plan_commands (
 namespace text NOT NULL, security_domain text NOT NULL,
 subject_id text NOT NULL, request_key text NOT NULL,
 payload_digest text NOT NULL, record jsonb NOT NULL,
 PRIMARY KEY(namespace,security_domain,subject_id,request_key)
);
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='immutable_resource_policy_plan_commands') THEN
  CREATE TRIGGER immutable_resource_policy_plan_commands BEFORE UPDATE OR DELETE
  ON execution_authority.resource_policy_plan_commands FOR EACH ROW
  EXECUTE FUNCTION execution_authority.preparation_immutable();
 END IF;
END $$;
