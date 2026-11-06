-- Approved S1 private records only; rollback disables routes, never drops history.
CREATE SCHEMA IF NOT EXISTS private_conversation;
CREATE TABLE IF NOT EXISTS private_conversation.conversations (
 tenant_id text NOT NULL, security_domain text NOT NULL, conversation_id text NOT NULL,
 owner_id text NOT NULL, title text NOT NULL, version bigint NOT NULL DEFAULT 0,
 created_at timestamptz NOT NULL DEFAULT now(), archived_at timestamptz,
 request_key text NOT NULL, request_digest text NOT NULL, schema_version integer NOT NULL DEFAULT 1,
 PRIMARY KEY(tenant_id,security_domain,conversation_id),
 UNIQUE(tenant_id,security_domain,owner_id,request_key)
);
CREATE TABLE IF NOT EXISTS private_conversation.messages (
 tenant_id text NOT NULL, security_domain text NOT NULL, conversation_id text NOT NULL,
 message_id text NOT NULL, sequence bigint NOT NULL, author_id text NOT NULL,
 content text NOT NULL, focus_link_id text, disposition text NOT NULL,
 request_key text NOT NULL, request_digest text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), schema_version integer NOT NULL DEFAULT 1,
 PRIMARY KEY(tenant_id,security_domain,conversation_id,message_id),
 UNIQUE(tenant_id,security_domain,conversation_id,sequence),
 UNIQUE(tenant_id,security_domain,conversation_id,request_key),
 FOREIGN KEY(tenant_id,security_domain,conversation_id) REFERENCES private_conversation.conversations
);
CREATE TABLE IF NOT EXISTS private_conversation.links (
 tenant_id text NOT NULL, security_domain text NOT NULL, conversation_id text NOT NULL,
 link_id text NOT NULL, target jsonb NOT NULL, created_by text NOT NULL,
 request_key text NOT NULL, request_digest text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), schema_version integer NOT NULL DEFAULT 1,
 PRIMARY KEY(tenant_id,security_domain,conversation_id,link_id),
 UNIQUE(tenant_id,security_domain,conversation_id,request_key),
 UNIQUE(tenant_id,security_domain,conversation_id,target),
 FOREIGN KEY(tenant_id,security_domain,conversation_id) REFERENCES private_conversation.conversations
);
