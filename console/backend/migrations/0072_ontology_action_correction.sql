-- Internal append-only compatibility receipt. No execution state or old admission rewrite.
CREATE TABLE authorization_admin.ontology_action_corrections (
 admission_id text PRIMARY KEY REFERENCES authorization_admin.owned_business_admissions,
 namespace text NOT NULL, security_domain text NOT NULL, subject_id text NOT NULL,
 plan_id text NOT NULL, plan_version integer NOT NULL, plan_digest text NOT NULL,
 request_key text NOT NULL, record_digest text NOT NULL, record jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(namespace,security_domain,subject_id,request_key)
);
CREATE TRIGGER immutable_ontology_action_corrections BEFORE UPDATE OR DELETE ON
 authorization_admin.ontology_action_corrections FOR EACH ROW
 EXECUTE FUNCTION authorization_admin.task_delegation_immutable();
