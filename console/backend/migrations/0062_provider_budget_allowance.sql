-- Additive, explicitly selected allowance; original ledger history is immutable.
CREATE TABLE IF NOT EXISTS draft_provider_budget.allowances (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  ledger_id text NOT NULL,
  allowance_id text NOT NULL,
  record jsonb NOT NULL,
  digest text NOT NULL CHECK (digest ~ '^[a-f0-9]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace,security_domain,ledger_id,allowance_id),
  FOREIGN KEY(namespace,security_domain,ledger_id)
    REFERENCES draft_provider_budget.policies(namespace,security_domain,ledger_id)
);
CREATE OR REPLACE FUNCTION draft_provider_budget.reject_allowance_rewrite()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'IMMUTABLE_PROVIDER_BUDGET_ALLOWANCE';
END;
$$;
DROP TRIGGER IF EXISTS immutable_allowance ON draft_provider_budget.allowances;
CREATE TRIGGER immutable_allowance BEFORE UPDATE OR DELETE
  ON draft_provider_budget.allowances FOR EACH ROW
  EXECUTE FUNCTION draft_provider_budget.reject_allowance_rewrite();
