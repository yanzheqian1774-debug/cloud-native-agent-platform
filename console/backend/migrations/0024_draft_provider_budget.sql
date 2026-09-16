CREATE SCHEMA IF NOT EXISTS draft_provider_budget;

CREATE TABLE IF NOT EXISTS draft_provider_budget.schema_migrations (
  version integer PRIMARY KEY,
  checksum text NOT NULL,
  adapter text NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS draft_provider_budget.policies (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  ledger_id text NOT NULL,
  profile_revision_id text NOT NULL,
  profile_digest text NOT NULL CHECK (profile_digest ~ '^[0-9a-f]{64}$'),
  currency text NOT NULL CHECK (currency = 'USD'),
  call_cap bigint NOT NULL CHECK (call_cap > 0),
  total_cost_cap_microusd bigint NOT NULL CHECK (total_cost_cap_microusd > 0),
  input_price_microusd_per_million_tokens bigint NOT NULL CHECK (input_price_microusd_per_million_tokens >= 0),
  output_price_microusd_per_million_tokens bigint NOT NULL CHECK (output_price_microusd_per_million_tokens >= 0),
  record jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace, security_domain, ledger_id)
);

CREATE TABLE IF NOT EXISTS draft_provider_budget.reservations (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  ledger_id text NOT NULL,
  reservation_id text NOT NULL,
  operation_id text NOT NULL,
  invocation_id text NOT NULL,
  input_token_upper_bound bigint NOT NULL CHECK (input_token_upper_bound > 0),
  output_token_ceiling bigint NOT NULL CHECK (output_token_ceiling > 0),
  worst_case_cost_microusd bigint NOT NULL CHECK (worst_case_cost_microusd >= 0),
  payload_digest text NOT NULL CHECK (payload_digest ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace, security_domain, ledger_id, reservation_id),
  UNIQUE (namespace, security_domain, ledger_id, operation_id),
  UNIQUE (namespace, security_domain, ledger_id, invocation_id),
  FOREIGN KEY (namespace, security_domain, ledger_id)
    REFERENCES draft_provider_budget.policies(namespace, security_domain, ledger_id)
);

CREATE TABLE IF NOT EXISTS draft_provider_budget.settlements (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  ledger_id text NOT NULL,
  reservation_id text NOT NULL,
  operation_id text NOT NULL,
  observation_id text NOT NULL,
  input_tokens bigint NOT NULL CHECK (input_tokens > 0),
  output_tokens bigint NOT NULL CHECK (output_tokens >= 0),
  actual_cost_microusd bigint NOT NULL CHECK (actual_cost_microusd >= 0),
  payload_digest text NOT NULL CHECK (payload_digest ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace, security_domain, ledger_id, reservation_id),
  UNIQUE (namespace, security_domain, ledger_id, operation_id),
  FOREIGN KEY (namespace, security_domain, ledger_id, reservation_id)
    REFERENCES draft_provider_budget.reservations(namespace, security_domain, ledger_id, reservation_id)
);

CREATE OR REPLACE FUNCTION draft_provider_budget.reject_immutable_rewrite()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'IMMUTABLE_DRAFT_PROVIDER_BUDGET_HISTORY';
END $$;

DO $$
DECLARE
  relation_name text;
BEGIN
  FOREACH relation_name IN ARRAY ARRAY['policies', 'reservations', 'settlements'] LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_trigger
      WHERE tgname = 'immutable_draft_provider_budget_' || relation_name
        AND tgrelid = ('draft_provider_budget.' || relation_name)::regclass
    ) THEN
      EXECUTE format(
        'CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON draft_provider_budget.%I '
        'FOR EACH ROW EXECUTE FUNCTION draft_provider_budget.reject_immutable_rewrite()',
        'immutable_draft_provider_budget_' || relation_name,
        relation_name
      );
    END IF;
  END LOOP;
END $$;
