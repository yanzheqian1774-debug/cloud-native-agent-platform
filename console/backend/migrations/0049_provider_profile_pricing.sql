-- Explicit operator preparation only; original ledger policy/history remain immutable.
CREATE TABLE IF NOT EXISTS draft_provider_budget.profile_pricing_revisions (
 namespace text NOT NULL, security_domain text NOT NULL, ledger_id text NOT NULL,
 profile_revision_id text NOT NULL, profile_digest text NOT NULL,
 revision_digest text NOT NULL CHECK(revision_digest ~ '^[a-f0-9]{64}$'),
 record jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(namespace,security_domain,ledger_id,profile_revision_id),
 UNIQUE(namespace,security_domain,ledger_id,revision_digest),
 FOREIGN KEY(namespace,security_domain,ledger_id)
 REFERENCES draft_provider_budget.policies(namespace,security_domain,ledger_id)
);
CREATE TABLE IF NOT EXISTS draft_provider_budget.reservation_pricing (
 namespace text NOT NULL, security_domain text NOT NULL, ledger_id text NOT NULL,
 reservation_id text NOT NULL, revision_digest text NOT NULL,
 PRIMARY KEY(namespace,security_domain,ledger_id,reservation_id),
 FOREIGN KEY(namespace,security_domain,ledger_id,reservation_id)
 REFERENCES draft_provider_budget.reservations(namespace,security_domain,ledger_id,reservation_id),
 FOREIGN KEY(namespace,security_domain,ledger_id,revision_digest)
 REFERENCES draft_provider_budget.profile_pricing_revisions(namespace,security_domain,ledger_id,revision_digest)
);
DO $$ DECLARE relation_name text; BEGIN
 FOREACH relation_name IN ARRAY ARRAY['profile_pricing_revisions','reservation_pricing'] LOOP
  IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='immutable_draft_provider_budget_'||relation_name
   AND tgrelid=('draft_provider_budget.'||relation_name)::regclass) THEN
   EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON draft_provider_budget.%I FOR EACH ROW EXECUTE FUNCTION draft_provider_budget.reject_immutable_rewrite()', 'immutable_draft_provider_budget_'||relation_name,relation_name);
  END IF;
 END LOOP;
END $$;
CREATE OR REPLACE FUNCTION draft_provider_budget.check_settlement_price()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE input_price bigint; output_price bigint; BEGIN
 SELECT (v.record->>'inputPriceMicrousdPerMillionTokens')::bigint,
        (v.record->>'outputPriceMicrousdPerMillionTokens')::bigint
 INTO input_price,output_price FROM draft_provider_budget.reservation_pricing b
 JOIN draft_provider_budget.profile_pricing_revisions v
 USING(namespace,security_domain,ledger_id,revision_digest)
 WHERE b.namespace=NEW.namespace AND b.security_domain=NEW.security_domain
 AND b.ledger_id=NEW.ledger_id AND b.reservation_id=NEW.reservation_id;
 IF NOT FOUND THEN
  RETURN NEW; -- Legacy reservations keep their unchanged legacy settlement path.
 END IF;
 IF NEW.actual_cost_microusd <> ceil(NEW.input_tokens::numeric*input_price/1000000)
   +ceil(NEW.output_tokens::numeric*output_price/1000000) THEN
  RAISE EXCEPTION 'PROVIDER_BUDGET_RESERVATION_PRICE_MISMATCH';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS provider_budget_settlement_price ON draft_provider_budget.settlements;
CREATE TRIGGER provider_budget_settlement_price BEFORE INSERT ON draft_provider_budget.settlements
 FOR EACH ROW EXECUTE FUNCTION draft_provider_budget.check_settlement_price();
