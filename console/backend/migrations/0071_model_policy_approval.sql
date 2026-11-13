-- Same Model owner; truthful standing-policy successor, no Human fact rewriting.
ALTER TABLE model_governance.lifecycle_facts DROP CONSTRAINT lifecycle_facts_action_check;
ALTER TABLE model_governance.lifecycle_facts ADD CONSTRAINT lifecycle_facts_action_check
CHECK (action IN ('VALIDATED','HUMAN_REVIEWED','POLICY_APPROVED','PUBLISHED',
'ENABLED','DISABLED','DEPRECATED','REVOKED','SUCCESSOR_CREATED'));
CREATE TABLE model_governance.policy_approval_decisions (
 namespace text NOT NULL,
 security_domain text NOT NULL,
 decision_id text NOT NULL,
 actor_id text NOT NULL,
 command_key text NOT NULL,
 model_id text NOT NULL,
 revision_id text NOT NULL,
 model_digest text NOT NULL,
 record jsonb NOT NULL,
 digest text NOT NULL CHECK(digest ~ '^[0-9a-f]{64}$'),
 PRIMARY KEY(namespace,security_domain,decision_id),
 UNIQUE(namespace,security_domain,actor_id,command_key),
 UNIQUE(namespace,security_domain,model_id,revision_id),
 FOREIGN KEY(namespace,security_domain,model_id,revision_id,model_digest)
 REFERENCES model_governance.model_revisions(namespace,security_domain,model_id,revision_id,digest)
);
CREATE TRIGGER model_policy_decision_immutable BEFORE UPDATE OR DELETE
ON model_governance.policy_approval_decisions FOR EACH ROW
EXECUTE FUNCTION model_governance.reject_immutable_rewrite();
