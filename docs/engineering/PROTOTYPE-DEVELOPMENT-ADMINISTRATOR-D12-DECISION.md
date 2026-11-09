# D12 — Local development superadministrator

Status: ACCEPTED. The user explicitly replied “同意” to the concrete development
administrator proposal on 2026-11-09. Implementation: in progress, not installed.

This decision supersedes the D11 prohibition on blanket browser permissions ONLY
for an explicitly enabled devadmin local account in s5-323-demo / isolated-real-demo.
Ordinary accounts and deployments without this optional immutable-generation
configuration retain the D11 rules. No new authentication method or database.

The independent principal human:development-admin can read/use current and future
resources, access/continue all conversations in this development scope, and publish
technically valid resources without individual resource grants or human review.
The role persists until disabled; session expiry, account disable/revocation, CSRF,
active generation/recovery epoch, scope isolation and technical validation remain.
Cross-conversation operations retain original ownership and record the real actor.
Resource publication records identify DEVELOPMENT_ADMINISTRATOR and current
authority generation, never a fictitious service approval or another human.
Historical commands and UNKNOWN effects are not automatically retried.

Implementation plan: optional generation configuration + local account binding;
current authorization reader checks after session/account validation; scoped
conversation access extension; management ownership extension and role-checked
internal publication proof; role display; positive/negative isolated tests; controlled
single-writer deployment with private backup; real account/browser verification.

Acceptance includes default-off and revocation denial, scope/session isolation,
new resource visibility, cross-owner continuation with real actor, publication
without resource-grant requests, failed validation staying unpublished, historical
results/budgets unchanged. General execution capacity is tested separately.
