-- D324 accepted: preserve source Plan/Approval owners; references are not copies.
SELECT pg_advisory_xact_lock(3240034);
CREATE TABLE execution_authority.plan_references (
 namespace text NOT NULL, security_domain text NOT NULL,
 plan_id text NOT NULL, plan_version bigint NOT NULL,
 source_owner text NOT NULL CHECK(source_owner IN ('EXECUTION','PLANNING')),
 legacy_id text, legacy_version bigint, planning_id text, planning_version integer,
 PRIMARY KEY(namespace,security_domain,plan_id,plan_version),
 CHECK ((source_owner='EXECUTION' AND legacy_id=plan_id AND legacy_version=plan_version
         AND legacy_id IS NOT NULL AND legacy_version IS NOT NULL
         AND planning_id IS NULL AND planning_version IS NULL)
     OR (source_owner='PLANNING' AND planning_id=plan_id AND planning_version=plan_version
         AND planning_id IS NOT NULL AND planning_version IS NOT NULL
         AND legacy_id IS NULL AND legacy_version IS NULL)),
 FOREIGN KEY(namespace,security_domain,legacy_id,legacy_version)
 REFERENCES execution_authority.plans(namespace,security_domain,plan_id,plan_version),
 FOREIGN KEY(namespace,security_domain,planning_id,planning_version)
 REFERENCES workflow_planning.plans(namespace,security_domain,plan_id,version)
);
INSERT INTO execution_authority.plan_references
 SELECT namespace,security_domain,plan_id,plan_version,'EXECUTION',plan_id,plan_version,NULL,NULL
 FROM execution_authority.plans;
INSERT INTO execution_authority.plan_references
 SELECT namespace,security_domain,plan_id,version,'PLANNING',NULL,NULL,plan_id,version
 FROM workflow_planning.plans;
CREATE FUNCTION execution_authority.register_plan_reference() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
 IF TG_TABLE_SCHEMA='workflow_planning' THEN
 INSERT INTO execution_authority.plan_references VALUES
 (NEW.namespace,NEW.security_domain,NEW.plan_id,NEW.version,'PLANNING',NULL,NULL,NEW.plan_id,NEW.version);
 ELSE
 INSERT INTO execution_authority.plan_references VALUES
 (NEW.namespace,NEW.security_domain,NEW.plan_id,NEW.plan_version,'EXECUTION',NEW.plan_id,NEW.plan_version,NULL,NULL);
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER register_execution_plan AFTER INSERT ON execution_authority.plans
 FOR EACH ROW EXECUTE FUNCTION execution_authority.register_plan_reference();
CREATE TRIGGER register_planning_plan AFTER INSERT ON workflow_planning.plans
 FOR EACH ROW EXECUTE FUNCTION execution_authority.register_plan_reference();
-- Replace only the two consuming FKs; source owners retain their own constraints.
DO $$ DECLARE item record; BEGIN
 FOR item IN SELECT conname,conrelid::regclass AS target FROM pg_constraint
 WHERE contype='f' AND confrelid='execution_authority.plans'::regclass
 AND conrelid IN ('execution_authority.workflow_runs'::regclass,'resource_use.uses'::regclass)
 LOOP
 EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I',item.target,item.conname);
 EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I FOREIGN KEY(namespace,security_domain,plan_id,plan_version) REFERENCES execution_authority.plan_references(namespace,security_domain,plan_id,plan_version)',item.target,item.conname);
 END LOOP;
END $$;
ALTER TABLE execution_authority.task_runs ADD CONSTRAINT task_run_prepared_lineage_unique
 UNIQUE(namespace,security_domain,task_run_id,workflow_run_id);
CREATE TABLE execution_authority.prepared_task_bindings (
 namespace text NOT NULL,security_domain text NOT NULL,task_run_id text NOT NULL,
 workflow_run_id text NOT NULL,task_id text NOT NULL,assignment_id text NOT NULL,
 participant jsonb NOT NULL,
 CHECK(participant->>'task_id'=task_id AND participant->>'assignment_id'=assignment_id),
 PRIMARY KEY(namespace,security_domain,task_run_id),
 UNIQUE(namespace,security_domain,workflow_run_id,task_id),
 FOREIGN KEY(namespace,security_domain,task_run_id,workflow_run_id)
 REFERENCES execution_authority.task_runs(namespace,security_domain,task_run_id,workflow_run_id),
 FOREIGN KEY(namespace,security_domain,workflow_run_id) REFERENCES execution_authority.run_preparations,
 FOREIGN KEY(namespace,security_domain,assignment_id) REFERENCES execution_authority.assignments
);
CREATE TABLE execution_authority.prepared_start_commands (
 namespace text NOT NULL,security_domain text NOT NULL,actor_id text NOT NULL,
 command_key text NOT NULL,payload_digest text NOT NULL,workflow_run_id text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,actor_id,command_key),
 FOREIGN KEY(namespace,security_domain,workflow_run_id) REFERENCES execution_authority.run_preparations
);
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['plan_references','prepared_task_bindings','prepared_start_commands'] LOOP
 EXECUTE format('CREATE TRIGGER immutable_prepared_binding BEFORE UPDATE OR DELETE ON execution_authority.%I FOR EACH ROW EXECUTE FUNCTION execution_authority.preparation_immutable()',tab);
 END LOOP;
END $$;

CREATE FUNCTION execution_authority.validate_prepared_task_binding() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
 IF NOT EXISTS (
 SELECT 1 FROM execution_authority.run_preparations p,
 jsonb_array_elements(p.record->'participants') participant
 WHERE p.namespace=NEW.namespace AND p.security_domain=NEW.security_domain
 AND p.workflow_run_id=NEW.workflow_run_id AND participant=NEW.participant
 ) THEN RAISE EXCEPTION 'PREPARED_TASK_BINDING_MISMATCH'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER validate_prepared_task_binding BEFORE INSERT ON execution_authority.prepared_task_bindings
 FOR EACH ROW EXECUTE FUNCTION execution_authority.validate_prepared_task_binding();
CREATE TABLE execution_authority.prepared_candidates (
 namespace text NOT NULL, security_domain text NOT NULL, digest text NOT NULL,
 plan_id text NOT NULL, plan_version bigint NOT NULL, record jsonb NOT NULL,
 prepared_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,digest),
 FOREIGN KEY(namespace,security_domain,plan_id,plan_version)
 REFERENCES execution_authority.plan_references(namespace,security_domain,plan_id,plan_version)
);
CREATE TRIGGER immutable_prepared_candidate BEFORE UPDATE OR DELETE ON execution_authority.prepared_candidates
 FOR EACH ROW EXECUTE FUNCTION execution_authority.preparation_immutable();

-- Native owner stop receipts prove that cancellation won before effect permission.
CREATE TABLE execution_authority.prepared_stop_receipts (
 namespace text NOT NULL, security_domain text NOT NULL, receipt_id text NOT NULL,
 command_id text NOT NULL, attempt_id text NOT NULL, request_id text NOT NULL, digest text NOT NULL,
 record jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,receipt_id),
 UNIQUE(namespace,security_domain,command_id),
 FOREIGN KEY(namespace,security_domain,attempt_id) REFERENCES execution_authority.attempts
);
CREATE TRIGGER prepared_stop_receipt_immutable BEFORE UPDATE OR DELETE
ON execution_authority.prepared_stop_receipts FOR EACH ROW
EXECUTE FUNCTION execution_authority.preparation_immutable();

CREATE TABLE execution_authority.prepared_control_commands (
 namespace text NOT NULL, security_domain text NOT NULL, actor_id text NOT NULL,
 command_key text NOT NULL, workflow_run_id text NOT NULL, digest text NOT NULL,
 action text NOT NULL, authority_basis text NOT NULL, result jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,actor_id,command_key),
 FOREIGN KEY(namespace,security_domain,workflow_run_id) REFERENCES execution_authority.run_preparations
);
CREATE TRIGGER prepared_control_command_immutable BEFORE UPDATE OR DELETE
ON execution_authority.prepared_control_commands FOR EACH ROW
EXECUTE FUNCTION execution_authority.preparation_immutable();

CREATE TABLE execution_authority.prepared_resource_commands (
 namespace text NOT NULL, security_domain text NOT NULL, actor_id text NOT NULL,
 command_key text NOT NULL, digest text NOT NULL, result jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,actor_id,command_key)
);
CREATE TRIGGER prepared_resource_command_immutable BEFORE UPDATE OR DELETE
ON execution_authority.prepared_resource_commands FOR EACH ROW
EXECUTE FUNCTION execution_authority.preparation_immutable();
