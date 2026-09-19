-- Additive receipt; existing budget owner remains the only settlement authority.
CREATE TABLE IF NOT EXISTS workflow_planning.provider_receipts (
 namespace text NOT NULL, security_domain text NOT NULL,
 invocation_id text NOT NULL, record jsonb NOT NULL,
 PRIMARY KEY(namespace,security_domain,invocation_id),
 FOREIGN KEY(namespace,security_domain,invocation_id)
 REFERENCES workflow_planning.invocations(namespace,security_domain,invocation_id)
);
CREATE TRIGGER planning_immutable_provider_receipts
 BEFORE UPDATE OR DELETE ON workflow_planning.provider_receipts
 FOR EACH ROW EXECUTE FUNCTION workflow_planning.immutable_record();
