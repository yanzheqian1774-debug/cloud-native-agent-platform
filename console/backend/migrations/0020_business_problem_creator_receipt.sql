CREATE TABLE business_problem_authority.creator_receipts (
  namespace text NOT NULL,
  security_domain text NOT NULL,
  creator_principal_id text NOT NULL,
  originating_command_type text NOT NULL
    CHECK (originating_command_type = 'CREATE_BUSINESS_PROBLEM'),
  originating_command_idempotency_key text NOT NULL,
  originating_command_payload_digest text NOT NULL
    CHECK (length(originating_command_payload_digest) = 64),
  business_problem_id text NOT NULL,
  revision_id text NOT NULL,
  revision bigint NOT NULL CHECK (revision = 1),
  aggregate_version bigint NOT NULL CHECK (aggregate_version = 1),
  revision_digest text NOT NULL CHECK (length(revision_digest) = 64),
  canonical_resource_reference text NOT NULL,
  committed_owner_revision text NOT NULL
    CHECK (committed_owner_revision ~ '^problem-owner-revision\.v1\.sha256\.[a-f0-9]{64}$'),
  policy_generation bigint NOT NULL CHECK (policy_generation > 0),
  recovery_epoch bigint NOT NULL CHECK (recovery_epoch > 0),
  receipt_started_at timestamptz NOT NULL,
  expires_at timestamptz NOT NULL,
  PRIMARY KEY (
    namespace,
    security_domain,
    creator_principal_id,
    originating_command_type,
    originating_command_idempotency_key
  ),
  UNIQUE (namespace, security_domain, business_problem_id),
  FOREIGN KEY (namespace, security_domain, business_problem_id)
    REFERENCES business_problem_authority.problems(
      namespace, security_domain, business_problem_id
    ),
  FOREIGN KEY (namespace, security_domain, revision_id)
    REFERENCES business_problem_authority.problem_revisions(
      namespace, security_domain, revision_id
    ),
  CHECK (canonical_resource_reference = 'business-problem:' || business_problem_id),
  CHECK (expires_at = receipt_started_at + interval '10 minutes')
);
