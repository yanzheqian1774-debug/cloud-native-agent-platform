-- Additive private message facts; existing messages and0046 remain unchanged.
CREATE TABLE IF NOT EXISTS private_conversation.message_facts (
 tenant_id text NOT NULL, security_domain text NOT NULL, conversation_id text NOT NULL,
 message_id text NOT NULL, kind text NOT NULL CHECK(kind IN ('SOURCE','ACTION_INTENT','OWNER_RECEIPT')),
 facts jsonb NOT NULL,
 PRIMARY KEY(tenant_id,security_domain,conversation_id,message_id),
 FOREIGN KEY(tenant_id,security_domain,conversation_id,message_id)
 REFERENCES private_conversation.messages
);
CREATE TABLE IF NOT EXISTS private_conversation.action_intents (
 tenant_id text NOT NULL, security_domain text NOT NULL, conversation_id text NOT NULL,
 intent_id text NOT NULL, message_id text NOT NULL, confirmed_by text NOT NULL,
 confirmed_at timestamptz NOT NULL DEFAULT now(), action text NOT NULL,
 payload jsonb NOT NULL, payload_digest text NOT NULL, owner_request_key text NOT NULL,
 source jsonb, expected_owner_version bigint NOT NULL,
 request_key text NOT NULL, request_digest text NOT NULL,
 claimed_at timestamptz, owner_ref jsonb,
 PRIMARY KEY(tenant_id,security_domain,conversation_id,intent_id),
 UNIQUE(tenant_id,security_domain,confirmed_by,action,owner_request_key),
 UNIQUE(tenant_id,security_domain,conversation_id,request_key),
 FOREIGN KEY(tenant_id,security_domain,conversation_id,message_id)
 REFERENCES private_conversation.messages
);
