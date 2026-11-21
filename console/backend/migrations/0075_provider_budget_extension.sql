-- Explicit cumulative successor on the original ledger. No rewritten allowance.
CREATE TABLE draft_provider_budget.extensions (
 namespace text NOT NULL, security_domain text NOT NULL, ledger_id text NOT NULL,
 extension_id text NOT NULL, allowance_id text NOT NULL,
 record jsonb NOT NULL, digest text NOT NULL CHECK (digest ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(namespace,security_domain,ledger_id,extension_id),
 FOREIGN KEY(namespace,security_domain,ledger_id,allowance_id)
 REFERENCES draft_provider_budget.allowances(namespace,security_domain,ledger_id,allowance_id)
);
CREATE TABLE draft_provider_budget.extension_activations (
 namespace text NOT NULL, security_domain text NOT NULL, ledger_id text NOT NULL,
 allowance_id text NOT NULL, extension_id text NOT NULL, command_id text NOT NULL,
 record jsonb NOT NULL, digest text NOT NULL CHECK (digest ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(namespace,security_domain,ledger_id,allowance_id),
 UNIQUE(namespace,security_domain,ledger_id,command_id),
 FOREIGN KEY(namespace,security_domain,ledger_id,extension_id)
 REFERENCES draft_provider_budget.extensions(namespace,security_domain,ledger_id,extension_id)
);
CREATE TABLE draft_provider_budget.extension_deactivations (
 namespace text NOT NULL, security_domain text NOT NULL, ledger_id text NOT NULL,
 extension_id text NOT NULL, record jsonb NOT NULL, digest text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(namespace,security_domain,ledger_id,extension_id),
 FOREIGN KEY(namespace,security_domain,ledger_id,extension_id)
 REFERENCES draft_provider_budget.extensions(namespace,security_domain,ledger_id,extension_id)
);
CREATE TABLE draft_provider_budget.reservation_extension_basis (
 namespace text NOT NULL, security_domain text NOT NULL, ledger_id text NOT NULL,
 reservation_id text NOT NULL, extension_id text NOT NULL,
 record jsonb NOT NULL, digest text NOT NULL CHECK (digest ~ '^[a-f0-9]{64}$'),
 PRIMARY KEY(namespace,security_domain,ledger_id,reservation_id),
 FOREIGN KEY(namespace,security_domain,ledger_id,reservation_id)
 REFERENCES draft_provider_budget.reservations(namespace,security_domain,ledger_id,reservation_id),
 FOREIGN KEY(namespace,security_domain,ledger_id,extension_id)
 REFERENCES draft_provider_budget.extensions(namespace,security_domain,ledger_id,extension_id)
);
CREATE FUNCTION draft_provider_budget.reject_extension_rewrite()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 RAISE EXCEPTION 'IMMUTABLE_PROVIDER_BUDGET_EXTENSION'; END; $$;
CREATE TRIGGER immutable_extension BEFORE UPDATE OR DELETE ON draft_provider_budget.extensions
 FOR EACH ROW EXECUTE FUNCTION draft_provider_budget.reject_extension_rewrite();
CREATE TRIGGER immutable_extension_activation BEFORE UPDATE OR DELETE ON draft_provider_budget.extension_activations
 FOR EACH ROW EXECUTE FUNCTION draft_provider_budget.reject_extension_rewrite();
CREATE TRIGGER immutable_extension_deactivation BEFORE UPDATE OR DELETE ON draft_provider_budget.extension_deactivations
 FOR EACH ROW EXECUTE FUNCTION draft_provider_budget.reject_extension_rewrite();
CREATE TRIGGER immutable_reservation_extension_basis BEFORE UPDATE OR DELETE ON draft_provider_budget.reservation_extension_basis
 FOR EACH ROW EXECUTE FUNCTION draft_provider_budget.reject_extension_rewrite();
