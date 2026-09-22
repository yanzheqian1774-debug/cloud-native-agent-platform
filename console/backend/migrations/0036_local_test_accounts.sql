-- D324-4: same Browser Session Authority, no business grants or history rewrites.
CREATE TABLE browser_identity.local_accounts (
    account_id text PRIMARY KEY,
    username text NOT NULL UNIQUE,
    principal_id text NOT NULL,
    tenant_id text NOT NULL,
    security_domain text NOT NULL,
    status text NOT NULL CHECK (status IN ('ENABLED','DISABLED','REVOKED')),
    revision bigint NOT NULL CHECK (revision > 0),
    created_at timestamptz NOT NULL
);
CREATE TABLE browser_identity.local_account_passwords (
    account_id text NOT NULL REFERENCES browser_identity.local_accounts,
    revision bigint NOT NULL,
    password_hash text NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY(account_id,revision)
);
CREATE TABLE browser_identity.local_account_sessions (
    session_id text PRIMARY KEY REFERENCES browser_identity.sessions,
    account_id text NOT NULL REFERENCES browser_identity.local_accounts,
    account_revision bigint NOT NULL
);
CREATE TABLE browser_identity.local_account_commands (
    command_id text PRIMARY KEY,
    account_id text NOT NULL REFERENCES browser_identity.local_accounts,
    action text NOT NULL,
    revision bigint NOT NULL,
    operator_id text NOT NULL,
    recorded_at timestamptz NOT NULL
);
CREATE TABLE browser_identity.local_login_limits (
    bucket text PRIMARY KEY,
    started_at timestamptz NOT NULL,
    attempts integer NOT NULL CHECK (attempts >= 0)
);
