CREATE SCHEMA IF NOT EXISTS prepared_delivery;
CREATE TABLE prepared_delivery.packages (
 namespace text NOT NULL, security_domain text NOT NULL, preparation_digest text NOT NULL,
 package_digest text NOT NULL, workflow_run_id text NOT NULL, record jsonb NOT NULL,
 PRIMARY KEY(namespace,security_domain,preparation_digest,package_digest)
);
CREATE TABLE prepared_delivery.events (
 namespace text NOT NULL, security_domain text NOT NULL, preparation_digest text NOT NULL,
 event_id text NOT NULL, version bigint NOT NULL CHECK(version>0), package_digest text NOT NULL,
 actor_id text NOT NULL, command_key text NOT NULL, command_digest text NOT NULL,
 action text NOT NULL CHECK(action IN ('ACCEPT_DELIVERY','RETRACT_DELIVERY')),
 predecessor_id text, digest text NOT NULL, record jsonb NOT NULL,
 PRIMARY KEY(namespace,security_domain,event_id),
 UNIQUE(namespace,security_domain,preparation_digest,version),
 UNIQUE(namespace,security_domain,actor_id,command_key),
 FOREIGN KEY(namespace,security_domain,preparation_digest,package_digest)
 REFERENCES prepared_delivery.packages(namespace,security_domain,preparation_digest,package_digest)
);
CREATE TABLE prepared_delivery.heads (
 namespace text NOT NULL, security_domain text NOT NULL, preparation_digest text NOT NULL,
 version bigint NOT NULL CHECK(version>0), event_id text NOT NULL,
 PRIMARY KEY(namespace,security_domain,preparation_digest),
 FOREIGN KEY(namespace,security_domain,event_id) REFERENCES prepared_delivery.events(namespace,security_domain,event_id)
);
CREATE TRIGGER immutable_delivery_package BEFORE UPDATE OR DELETE ON prepared_delivery.packages
FOR EACH ROW EXECUTE FUNCTION execution_authority.preparation_immutable();
CREATE TRIGGER immutable_delivery_event BEFORE UPDATE OR DELETE ON prepared_delivery.events
FOR EACH ROW EXECUTE FUNCTION execution_authority.preparation_immutable();
