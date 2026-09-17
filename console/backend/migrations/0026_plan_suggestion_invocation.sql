-- D2 additive contextual target; legacy draft rows and contracts remain intact.
CREATE TABLE IF NOT EXISTS workflow_planning.invocations (
 namespace text NOT NULL, security_domain text NOT NULL,
 invocation_id text NOT NULL, actor_id text NOT NULL, request_key text NOT NULL,
 payload_digest text NOT NULL, record jsonb NOT NULL,
 PRIMARY KEY(namespace,security_domain,invocation_id),
 UNIQUE(namespace,security_domain,actor_id,request_key)
);
CREATE TABLE IF NOT EXISTS workflow_planning.invocation_results (
 namespace text NOT NULL, security_domain text NOT NULL,
 invocation_id text NOT NULL, record jsonb NOT NULL,
 PRIMARY KEY(namespace,security_domain,invocation_id),
 FOREIGN KEY(namespace,security_domain,invocation_id)
 REFERENCES workflow_planning.invocations(namespace,security_domain,invocation_id)
);
ALTER TABLE contextual_resource_use.uses DROP CONSTRAINT IF EXISTS uses_context_kind_check;
ALTER TABLE contextual_resource_use.uses ADD CONSTRAINT uses_context_kind_check
 CHECK (context_kind IN ('DRAFT_ASSISTANCE_INVOCATION','PLAN_SUGGESTION_INVOCATION'));
ALTER TABLE model_evidence.records DROP CONSTRAINT IF EXISTS records_schema_version_check;
ALTER TABLE model_evidence.records ADD CONSTRAINT records_schema_version_check
 CHECK (schema_version IN ('model-draft-assistance-invocation-evidence.v1',
                          'model-plan-suggestion-invocation-evidence.v1'));
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['invocations','invocation_results'] LOOP
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'planning_immutable_' || tab) THEN
   EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON workflow_planning.%I FOR EACH ROW EXECUTE FUNCTION workflow_planning.immutable_record()', 'planning_immutable_' || tab, tab);
  END IF;
 END LOOP;
END $$;
