-- Versioned execution bindings owned by Execution, not the ontology publisher.
CREATE TABLE execution_authority.ontology_bindings (
 namespace text NOT NULL, security_domain text NOT NULL,
 workflow_run_id text NOT NULL, digest text NOT NULL, record jsonb NOT NULL,
 PRIMARY KEY(namespace,security_domain,workflow_run_id),
 FOREIGN KEY(namespace,security_domain,workflow_run_id)
 REFERENCES execution_authority.workflow_runs(namespace,security_domain,workflow_run_id)
);
CREATE TRIGGER immutable_ontology_binding BEFORE UPDATE OR DELETE
 ON execution_authority.ontology_bindings
 FOR EACH ROW EXECUTE FUNCTION execution_authority.preparation_immutable();
