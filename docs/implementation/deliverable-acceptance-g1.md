# F3 independent deliverable acceptance — G1 / 0074

Root engineering review approved this bounded successor on 2026-11-20. This is not a HUMAN_REVIEWED fact. Product scope: optional acceptance of the entire currently readable saved delivery and its limitations, independent of business resolution, execution completion, approval to deploy, or the existing HumanConfirmation.

## Owner and compatibility

The existing PreparedResult service and PostgreSQL transaction own three attached tables: immutable packages, immutable acceptance/retraction events, and a CAS head. No Outcome/HumanConfirmation/CRD record is changed. The optional `PREPARED_DELIVERY_ACCEPTANCE_ENABLED=true` switch installs migration 0074 and registers two endpoints; omitted/false leaves the old API response and route set unchanged. No grants, model calls, execution, or budget changes are created by enablement.

The exact authority resource remains `governed-execution:prepared:<digest>`. Separate EXECUTION actions ACCEPT_DELIVERY and RETRACT_DELIVERY are registered. READ never implies either. Both require current authenticated human authority and all source/problem/criterion/output/Evaluation reads. Retraction requires the original accepting actor, current explicit RETRACT_DELIVERY, exact event, nonempty reason, current package and head version. Another authorized reader may see the original decision without being its actor. No administrator bypass is added.

## Serialization and lock order

`PreparedExecutionStore.append_artifact` locks the existing exact `prepared_run_progress` row before writing an artifact. `PreparedResultReview.snapshot` locks that same row and checks the exact preparation, terminal progress, criterion/source snapshots and complete committed artifact set. Delivery commands enter through the original WorkbenchOwnerAuthorization current identity/grant transaction, take a per-subject command advisory lock, then the shared progress row, then their own head. No original writer is changed. Native commands are observed without taking their row locks. No pending/UNKNOWN/RECOVERY_REQUIRED command may qualify a delivery for acceptance.

A package pins scope, preparation/run, original source and full original terminal snapshot, complete artifacts, current outcome/evaluation identity and listed limitations. No timestamp or viewer is included. A changed package does not inherit an old acceptance. Read failures produce UNAVAILABLE, never NOT_RECORDED. Failed/cancelled execution may have a readable partial delivery; the package and UI explicitly retain that terminal state and limitations.

## Commands, recovery and UI

POST `.../prepared-executions/{digest}/delivery-acceptance` accepts the exact action, package digest, expected version, original target event for retract, reason and idempotency key. The original CSRF/authenticated BFF remains in force. A same key with another payload conflicts. Authorization is checked before replay. An original command receipt is read through GET `.../delivery-acceptance/commands/{command_key}`, with current exact READ and complete source/output reads; it does not renew write permission.

The existing result/detail region shows the optional action and explanation: “接受这份交付内容及已列明限制，不代表业务问题已解决或批准上线”. Retraction uses an inline reason, not a new page/modal/approval. Pending request identity is stored before POST. A refresh or unknown transport outcome only reads the original receipt; it never generates another command. Current identity/epoch checks discard late responses. The accepted group uses the existing exact READ directory pagination and exact package/event projection; partial or unavailable records are not counted as unaccepted. Stage/history remains after retract.

## Validation and limits

All tests use isolated disposable databases and controlled browser API responses. No actual environment or model is invoked. Formal current identity/authorization tests and controlled authority-port tests are identified separately in the handoff. A test fixture's configured permissions do not constitute actual grants. Root alone performs later installation, explicit exact action grants and real UI acceptance/retraction. No claim that the business problem is solved or the entire F3 product is accepted follows from this package.
