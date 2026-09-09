# S5-V023-IMPL-305 Trusted Workbench BFF

Status: independent implementation in progress; shared startup wiring not complete.

Base: `9c28fa5b28c0cab6a39dc05f5367e93c8bcc8913`

This increment implements the independent ARCH-300 I2 boundary: strict Workbench
schemas, a closed typed route registry, browser session/CSRF/Origin/Host checks,
and a current exact-grant adapter that keeps the I1 generation barrier and the
owner call inside one caller-owned PostgreSQL transaction.

Routes are registered only when composition supplies an explicit transactional
owner handler. A handler receives the trusted context, authorization decisions,
and the same PostgreSQL connection used for the current-grant check. Existing
header-based or separately-transactional owner ports are not silently wrapped.

The shared `app.py`, bootstrap, persistence/schema compatibility, owner
PostgreSQL adapters, browser harness, and supervisor wiring remain untouched
while IMPL-295 owns those paths. Consequently the public BFF is not enabled and
this checkpoint does not claim a production browser-to-owner link.

Workflow and Employee lifecycle actions beyond the I1 registered CREATE/LIST/READ
vocabulary, Assignment start/retry, standalone Resource Use, and Evidence content
remain unregistered. They require an accepted exact action plus a formal owner
transaction port; the adapter does not infer authority or create a second writer.
