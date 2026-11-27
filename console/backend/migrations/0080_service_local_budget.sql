-- Optional exact Service sub-budget; original ledger and historical facts survive.
CREATE TABLE draft_provider_budget.service_scopes (
 namespace text NOT NULL, security_domain text NOT NULL, ledger_id text NOT NULL,
 scope_id text NOT NULL, record jsonb NOT NULL, digest text NOT NULL,
 PRIMARY KEY(namespace,security_domain,ledger_id,scope_id),
 FOREIGN KEY(namespace,security_domain,ledger_id)
 REFERENCES draft_provider_budget.policies(namespace,security_domain,ledger_id)
);
CREATE TABLE draft_provider_budget.service_reservations (
 namespace text NOT NULL, security_domain text NOT NULL, ledger_id text NOT NULL,
 reservation_id text NOT NULL, scope_id text NOT NULL,
 provenance jsonb NOT NULL, digest text NOT NULL,
 PRIMARY KEY(namespace,security_domain,ledger_id,reservation_id),
 FOREIGN KEY(namespace,security_domain,ledger_id,reservation_id)
 REFERENCES draft_provider_budget.reservations(namespace,security_domain,ledger_id,reservation_id),
 FOREIGN KEY(namespace,security_domain,ledger_id,scope_id)
 REFERENCES draft_provider_budget.service_scopes(namespace,security_domain,ledger_id,scope_id)
);
CREATE FUNCTION draft_provider_budget.reject_service_budget_rewrite()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 RAISE EXCEPTION 'IMMUTABLE_SERVICE_LOCAL_BUDGET'; END; $$;
CREATE TRIGGER immutable_service_scope BEFORE UPDATE OR DELETE ON draft_provider_budget.service_scopes
 FOR EACH ROW EXECUTE FUNCTION draft_provider_budget.reject_service_budget_rewrite();
CREATE TRIGGER immutable_service_reservation BEFORE UPDATE OR DELETE ON draft_provider_budget.service_reservations
 FOR EACH ROW EXECUTE FUNCTION draft_provider_budget.reject_service_budget_rewrite();
