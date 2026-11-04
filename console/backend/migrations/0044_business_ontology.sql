-- ONTOLOGY-SALES-01: independent definition owner in the existing database.
CREATE SCHEMA IF NOT EXISTS business_ontology;
CREATE TABLE business_ontology.schema_migrations (
 version integer PRIMARY KEY, checksum text NOT NULL
);
CREATE TABLE business_ontology.definitions (
 namespace text NOT NULL, security_domain text NOT NULL, ontology_id text NOT NULL,
 version integer NOT NULL, head_revision text NOT NULL,
 PRIMARY KEY(namespace,security_domain,ontology_id)
);
CREATE TABLE business_ontology.revisions (
 namespace text NOT NULL, security_domain text NOT NULL, ontology_id text NOT NULL,
 revision_id text NOT NULL, digest text NOT NULL, author text NOT NULL,
 predecessor text, content jsonb NOT NULL,
 PRIMARY KEY(namespace,security_domain,ontology_id,revision_id),
 FOREIGN KEY(namespace,security_domain,ontology_id)
 REFERENCES business_ontology.definitions(namespace,security_domain,ontology_id)
);
CREATE TABLE business_ontology.lifecycle_facts (
 ordinal bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 namespace text NOT NULL, security_domain text NOT NULL, ontology_id text NOT NULL,
 revision_id text NOT NULL, digest text NOT NULL, action text NOT NULL,
 actor text NOT NULL, request_key text NOT NULL, command_digest text NOT NULL,
 result jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(namespace,security_domain,actor,request_key),
 FOREIGN KEY(namespace,security_domain,ontology_id,revision_id)
 REFERENCES business_ontology.revisions(namespace,security_domain,ontology_id,revision_id)
);
CREATE TABLE business_ontology.dependency_refs (
 namespace text NOT NULL, security_domain text NOT NULL, ontology_id text NOT NULL,
 revision_id text NOT NULL, kind text NOT NULL, reference jsonb NOT NULL,
 FOREIGN KEY(namespace,security_domain,ontology_id,revision_id)
 REFERENCES business_ontology.revisions(namespace,security_domain,ontology_id,revision_id)
);
CREATE FUNCTION business_ontology.immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'ONTOLOGY_IMMUTABLE'; END $$;
CREATE TRIGGER immutable_revision BEFORE UPDATE OR DELETE ON business_ontology.revisions
 FOR EACH ROW EXECUTE FUNCTION business_ontology.immutable();
CREATE TRIGGER immutable_fact BEFORE UPDATE OR DELETE ON business_ontology.lifecycle_facts
 FOR EACH ROW EXECUTE FUNCTION business_ontology.immutable();
CREATE TRIGGER immutable_dependency BEFORE UPDATE OR DELETE ON business_ontology.dependency_refs
 FOR EACH ROW EXECUTE FUNCTION business_ontology.immutable();
