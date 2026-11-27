-- Private question identity and explicit human/service delegation facts only.
CREATE SCHEMA fixed_question;
CREATE TABLE fixed_question.schema_migrations (
 version integer PRIMARY KEY, checksum text NOT NULL, adapter text NOT NULL,
 installed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE fixed_question.questions (
 tenant_id text NOT NULL, security_domain text NOT NULL, conversation_id text NOT NULL,
 identity_digest text NOT NULL, record jsonb NOT NULL,
 PRIMARY KEY(tenant_id,security_domain,identity_digest),
 FOREIGN KEY(tenant_id,security_domain,conversation_id)
 REFERENCES private_conversation.conversations(tenant_id,security_domain,conversation_id),
 CHECK(record->>'tenantId'=tenant_id AND record->>'securityDomain'=security_domain
 AND record->>'conversationId'=conversation_id)
);
CREATE TABLE fixed_question.presentations (
 tenant_id text NOT NULL, security_domain text NOT NULL, conversation_id text NOT NULL,
 presentation_id text NOT NULL, identity_digest text NOT NULL,
 actor_id text NOT NULL, command_id text NOT NULL, request_digest text NOT NULL,
 record jsonb NOT NULL, record_digest text NOT NULL,
 PRIMARY KEY(tenant_id,security_domain,presentation_id),
 UNIQUE(tenant_id,security_domain,conversation_id,actor_id,command_id),
 UNIQUE(tenant_id,security_domain,identity_digest,actor_id),
 FOREIGN KEY(tenant_id,security_domain,identity_digest)
 REFERENCES fixed_question.questions(tenant_id,security_domain,identity_digest),
 CHECK(record->>'schemaVersion'='fixed-question-presentation.v1'),
 CHECK(record->>'presentationId'=presentation_id AND record->>'actorId'=actor_id
 AND record->>'commandId'=command_id AND record->>'requestDigest'=request_digest),
 CHECK(record->'identity'->>'tenantId'=tenant_id
 AND record->'identity'->>'securityDomain'=security_domain
 AND record->'identity'->>'conversationId'=conversation_id)
);
CREATE TABLE fixed_question.answers (
 tenant_id text NOT NULL, security_domain text NOT NULL, conversation_id text NOT NULL,
 presentation_id text NOT NULL, identity_digest text NOT NULL,
 actor_id text NOT NULL, command_id text NOT NULL, request_digest text NOT NULL,
 message_id text NOT NULL, record jsonb NOT NULL, record_digest text NOT NULL,
 PRIMARY KEY(tenant_id,security_domain,presentation_id),
 UNIQUE(tenant_id,security_domain,conversation_id,actor_id,command_id),
 UNIQUE(tenant_id,security_domain,identity_digest),
 FOREIGN KEY(tenant_id,security_domain,presentation_id)
 REFERENCES fixed_question.presentations(tenant_id,security_domain,presentation_id),
 FOREIGN KEY(tenant_id,security_domain,conversation_id,message_id)
 REFERENCES private_conversation.messages(tenant_id,security_domain,conversation_id,message_id),
 CHECK(record->>'schemaVersion'='fixed-question-answer.v1'),
 CHECK(record->>'presentationId'=presentation_id AND record->>'actorId'=actor_id
 AND record->>'commandId'=command_id AND record->>'requestDigest'=request_digest
 AND record->>'inputMessageId'=message_id AND record->>'questionIdentityDigest'=identity_digest)
);
CREATE FUNCTION fixed_question.reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'fixed question facts are immutable'; END;
$$;
CREATE TRIGGER immutable_question BEFORE UPDATE OR DELETE ON fixed_question.questions
FOR EACH ROW EXECUTE FUNCTION fixed_question.reject_mutation();
CREATE TRIGGER immutable_presentation BEFORE UPDATE OR DELETE ON fixed_question.presentations
FOR EACH ROW EXECUTE FUNCTION fixed_question.reject_mutation();
CREATE TRIGGER immutable_answer BEFORE UPDATE OR DELETE ON fixed_question.answers
FOR EACH ROW EXECUTE FUNCTION fixed_question.reject_mutation();
