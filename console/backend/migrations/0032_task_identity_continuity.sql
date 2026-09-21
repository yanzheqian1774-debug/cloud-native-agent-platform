-- Accepted ARCH-323 continuity: same authority, immutable transition and signature facts.
SELECT pg_advisory_xact_lock(3230028);
CREATE TABLE authorization_admin.task_identity_transitions (
 transition_id text PRIMARY KEY, old_generation bigint NOT NULL,
 generation bigint NOT NULL UNIQUE, recovery_epoch bigint NOT NULL,
 old_digest text NOT NULL, generation_digest text NOT NULL,
 operator_id text NOT NULL, database_fingerprint text NOT NULL,
 record jsonb NOT NULL, digest text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 CHECK(generation>old_generation)
);
CREATE TABLE authorization_admin.task_identity_continuities (
 continuity_id text PRIMARY KEY,
 delegation_id text NOT NULL REFERENCES authorization_admin.task_delegations,
 predecessor_id text REFERENCES authorization_admin.task_identity_continuities,
 ordinal integer NOT NULL CHECK(ordinal>0),
 transition_id text NOT NULL REFERENCES authorization_admin.task_identity_transitions,
 generation bigint NOT NULL, recovery_epoch bigint NOT NULL,
 issuer_id text NOT NULL, subject_id text NOT NULL CHECK(issuer_id<>subject_id),
 subject_credential_id text NOT NULL, issuer_credential_id text NOT NULL,
 idempotency_key text NOT NULL, payload_digest text NOT NULL,
 record jsonb NOT NULL, digest text NOT NULL,
 created_at timestamptz NOT NULL, expires_at timestamptz NOT NULL,
 UNIQUE(delegation_id,ordinal),
 UNIQUE(delegation_id,generation,idempotency_key),
 CHECK(expires_at>created_at AND expires_at<=created_at+interval '8 hours')
);
CREATE TABLE authorization_admin.task_identity_continuity_revocations (
 continuity_id text PRIMARY KEY REFERENCES authorization_admin.task_identity_continuities,
 actor_id text NOT NULL, revoked_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['task_identity_transitions','task_identity_continuities','task_identity_continuity_revocations'] LOOP
 EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON authorization_admin.%I FOR EACH ROW EXECUTE FUNCTION authorization_admin.task_delegation_immutable()', 'immutable_' || tab, tab);
 END LOOP;
END $$;
