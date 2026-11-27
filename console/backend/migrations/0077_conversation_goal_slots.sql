-- Private orchestration slots only; no domain/execution authority.
CREATE SCHEMA conversation_goals;
CREATE TABLE conversation_goals.schema_migrations (
 version integer PRIMARY KEY, checksum text NOT NULL, adapter text NOT NULL,
 installed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE conversation_goals.slots (
 tenant_id text NOT NULL, security_domain text NOT NULL, conversation_id text NOT NULL,
 goal_id text NOT NULL, owner_id text NOT NULL, root_message_id text NOT NULL,
 command_key text NOT NULL, request_digest text NOT NULL, record jsonb NOT NULL,
 record_digest text NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,security_domain,conversation_id,goal_id),
 UNIQUE(tenant_id,security_domain,conversation_id,command_key),
 UNIQUE(tenant_id,security_domain,conversation_id,root_message_id),
 FOREIGN KEY(tenant_id,security_domain,conversation_id)
 REFERENCES private_conversation.conversations(tenant_id,security_domain,conversation_id),
 FOREIGN KEY(tenant_id,security_domain,conversation_id,root_message_id)
 REFERENCES private_conversation.messages(tenant_id,security_domain,conversation_id,message_id),
 CHECK(record->>'schemaVersion'='conversation-goal-slot.v1'),
 CHECK(record->>'commandId'=command_key AND record->>'requestDigest'=request_digest),
 CHECK(record->>'goalId'=goal_id AND record->>'ownerId'=owner_id),
 CHECK(record->>'conversationId'=conversation_id AND record->>'tenantId'=tenant_id
 AND record->>'securityDomain'=security_domain AND record->>'rootMessageId'=root_message_id)
);
CREATE TABLE conversation_goals.journals (
 tenant_id text NOT NULL, security_domain text NOT NULL, conversation_id text NOT NULL,
 goal_id text NOT NULL, version bigint NOT NULL CHECK(version>=0), state jsonb,
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,security_domain,conversation_id,goal_id),
 FOREIGN KEY(tenant_id,security_domain,conversation_id,goal_id)
 REFERENCES conversation_goals.slots(tenant_id,security_domain,conversation_id,goal_id)
);
CREATE TABLE conversation_goals.messages (
 tenant_id text NOT NULL, security_domain text NOT NULL, conversation_id text NOT NULL,
 message_id text NOT NULL, goal_id text NOT NULL,
 PRIMARY KEY(tenant_id,security_domain,conversation_id,message_id),
 FOREIGN KEY(tenant_id,security_domain,conversation_id,goal_id)
 REFERENCES conversation_goals.slots(tenant_id,security_domain,conversation_id,goal_id),
 FOREIGN KEY(tenant_id,security_domain,conversation_id,message_id)
 REFERENCES private_conversation.messages(tenant_id,security_domain,conversation_id,message_id)
);
CREATE FUNCTION conversation_goals.reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'conversation goal identities are immutable'; END;
$$;
CREATE TRIGGER immutable_goal_slot BEFORE UPDATE OR DELETE ON conversation_goals.slots
FOR EACH ROW EXECUTE FUNCTION conversation_goals.reject_mutation();
CREATE TRIGGER immutable_goal_message BEFORE UPDATE OR DELETE ON conversation_goals.messages
FOR EACH ROW EXECUTE FUNCTION conversation_goals.reject_mutation();
CREATE TABLE conversation_goals.claimed_messages (
 tenant_id text NOT NULL, security_domain text NOT NULL, conversation_id text NOT NULL,
 message_id text NOT NULL, invocation_id text NOT NULL, goal_id text,
 PRIMARY KEY(tenant_id,security_domain,conversation_id,message_id,invocation_id),
 FOREIGN KEY(tenant_id,security_domain,conversation_id,message_id)
 REFERENCES private_conversation.messages(tenant_id,security_domain,conversation_id,message_id)
);
CREATE TRIGGER immutable_goal_claim BEFORE UPDATE OR DELETE ON conversation_goals.claimed_messages
FOR EACH ROW EXECUTE FUNCTION conversation_goals.reject_mutation();
CREATE TABLE conversation_goals.result_adoptions (
 tenant_id text NOT NULL, security_domain text NOT NULL, conversation_id text NOT NULL,
 invocation_id text NOT NULL, goal_id text NOT NULL, owner_id text NOT NULL,
 message_id text NOT NULL, command_key text NOT NULL, request_digest text NOT NULL,
 record jsonb NOT NULL, record_digest text NOT NULL,
 PRIMARY KEY(tenant_id,security_domain,invocation_id),
 UNIQUE(tenant_id,security_domain,conversation_id,command_key),
 UNIQUE(tenant_id,security_domain,conversation_id,goal_id),
 FOREIGN KEY(tenant_id,security_domain,conversation_id,goal_id)
 REFERENCES conversation_goals.slots(tenant_id,security_domain,conversation_id,goal_id),
 FOREIGN KEY(tenant_id,security_domain,conversation_id,message_id)
 REFERENCES private_conversation.messages(tenant_id,security_domain,conversation_id,message_id)
);
CREATE TRIGGER immutable_goal_adoption BEFORE UPDATE OR DELETE ON conversation_goals.result_adoptions
FOR EACH ROW EXECUTE FUNCTION conversation_goals.reject_mutation();
