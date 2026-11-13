# Existing ontology test-resource read coverage

The ordinary account receives AUTHORIZATION_NOT_FOUND from the ontology directory.
The existing test-resource read policy supports other published resources but
cannot describe BUSINESS_ONTOLOGY collection or exact revision reads.

Extend only the existing policy's READ/LIST inventory and exact digest lookup,
using business_ontology.revisions and its existing namespace/security-domain
boundary. No new grant action, endpoint, lifecycle, migration or execution
permission is introduced. Loading this code does not activate or issue grants.
The existing authorizer still checks target identity, current revocations,
denials, generation, issuer, expiry and auditable requests.

Validation covers the exact collection, required revision digest, mismatched
digest, missing revision and rejection of USE/CREATE/REVISE/TEST/PUBLISH. Run
existing policy regression and normal repository commit checks. Real activation
must separately bind actual revision digests within the existing authorized test
scope and then verify ordinary-account reads. This does not solve the observed
60-second preparation wait or authorize maintenance operations.
