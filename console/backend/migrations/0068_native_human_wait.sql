-- Internal safe checkpoints of one accepted Skill job. Opt-in migration only.
-- No new Attempt, Native command, public lifecycle or execution authority.
CREATE TABLE skill_invocation.native_wait_checkpoints (
 namespace text NOT NULL, security_domain text NOT NULL,
 skill_invocation_id text NOT NULL,
 checkpoint_digest text NOT NULL CHECK(checkpoint_digest ~ '^[0-9a-f]{64}$'),
 ordinal integer NOT NULL CHECK(ordinal BETWEEN 0 AND 31),
 command_id text NOT NULL,
 record jsonb NOT NULL,
 created_at timestamptz NOT NULL,
 human_expires_at timestamptz NOT NULL,
 PRIMARY KEY(namespace,security_domain,skill_invocation_id,checkpoint_digest),
 UNIQUE(namespace,security_domain,skill_invocation_id,ordinal),
 FOREIGN KEY(namespace,security_domain,skill_invocation_id)
  REFERENCES skill_invocation.invocations(namespace,security_domain,skill_invocation_id),
 FOREIGN KEY(namespace,security_domain,command_id)
  REFERENCES execution_authority.native_dispatch_commands(namespace,security_domain,command_id),
 CHECK(human_expires_at > created_at)
);
CREATE TABLE skill_invocation.native_wait_heads (
 namespace text NOT NULL, security_domain text NOT NULL,
 skill_invocation_id text NOT NULL, checkpoint_digest text NOT NULL,
 version bigint NOT NULL CHECK(version > 0),
 state text NOT NULL CHECK(state IN ('QUIESCING','WAITING_FOR_USER','ANSWER_SAVED',
  'CONTINUATION_CLAIMED','ADVANCING','COMPLETED','EXPIRED','BLOCKED')),
 PRIMARY KEY(namespace,security_domain,skill_invocation_id),
 FOREIGN KEY(namespace,security_domain,skill_invocation_id,checkpoint_digest)
  REFERENCES skill_invocation.native_wait_checkpoints
);
CREATE TABLE skill_invocation.native_wait_observations (
 namespace text NOT NULL, security_domain text NOT NULL,
 skill_invocation_id text NOT NULL, version bigint NOT NULL CHECK(version > 0),
 checkpoint_digest text NOT NULL,
 kind text NOT NULL CHECK(kind IN ('REGISTERED','STOP_CONFIRMED','ANSWER_SAVED',
  'CONTINUATION_CLAIMED','ADVANCING','COMPLETED','EXPIRED','BLOCKED')),
 record_digest text NOT NULL CHECK(record_digest ~ '^[0-9a-f]{64}$'),
 record jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,skill_invocation_id,version),
 FOREIGN KEY(namespace,security_domain,skill_invocation_id,checkpoint_digest)
  REFERENCES skill_invocation.native_wait_checkpoints
);
CREATE TABLE skill_invocation.native_wait_continuations (
 namespace text NOT NULL, security_domain text NOT NULL,
 skill_invocation_id text NOT NULL, checkpoint_digest text NOT NULL,
 claim_digest text NOT NULL CHECK(claim_digest ~ '^[0-9a-f]{64}$'),
 record jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(namespace,security_domain,skill_invocation_id,checkpoint_digest),
 FOREIGN KEY(namespace,security_domain,skill_invocation_id,checkpoint_digest)
  REFERENCES skill_invocation.native_wait_checkpoints
);
DO $$ DECLARE name text; BEGIN
 FOREACH name IN ARRAY ARRAY['native_wait_checkpoints','native_wait_observations',
                            'native_wait_continuations'] LOOP
  EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON skill_invocation.%I '
                 'FOR EACH ROW EXECUTE FUNCTION skill_invocation.reject_rewrite()',
                 'immutable_'||name, name);
 END LOOP;
END $$;
