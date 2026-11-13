# F3 team test read support

The installed team route exists, but ordinary test users have no TEAM requestability rules or test-read inventory support. A 404 is not evidence of an empty team directory.

Extend the existing bounded test-read owner with TEAM LIST and exact revision READ. A collection may be listed only when explicitly configured; each detail requires the canonical revision digest and matching tenant/security domain. Existing service authentication, requestability, revocation, expiry, grant decisions and audit remain authoritative. CREATE and REVISE remain forbidden in this policy.

Validation: parser rejects writes and incomplete targets; an isolated PostgreSQL team snapshot verifies correct revision, digest and scope. Real activation requires a separately prepared exact inventory and requestability generation. No runtime configuration or grants are changed by this code commit. Actual ordinary-account team access and prototype acceptance remain pending.
