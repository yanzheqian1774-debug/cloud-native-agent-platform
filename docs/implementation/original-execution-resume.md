# Original conversation execution recovery

G1: bounded frontend adapter on existing readonly-continuation GET/POST owners.
GET requires exact Plan READ; an existing receipt additionally requires exact
EXECUTION READ. Missing or denied access is not evidence of absence. The owner
returns READONLY_CONTINUATION_NOT_FOUND only after reading the original Plan,
source/work authorization and exact digest-derived command key. Preparation,
Run start and command receipt share one transaction; Native effects occur after
commit. No backend permission/lifecycle or public contract change is required.

Original EXECUTE/pending state gets an explicit read-only status action. A valid
receipt matching Plan id/version/digest and subject reconnects the existing
execution through normal journal CAS. Only exact 404
READONLY_CONTINUATION_NOT_FOUND enables a separate explicit continue button.
Continue reads again, then uses the same Plan POST if still absent; a concurrent
committed receipt is attached without POST. Other errors and mismatches fail
closed. Refresh never retries. Preserve old pending/error until a verified
result is attached; do not clear pending to trigger automatic retry.

Test: existing/missing/mismatched/unauthorized receipts, reread races, one
explicit dispatch, refresh zero dispatch, normal journal save and no models.
Frontend lint/build and fixture browser tests are required; deployment and real
acceptance remain parent-owned. No SSO, migration or resource policy change.

## Source audit of the existing authorization chain

A. Necessary boundaries retained:
- resource_automation: exact Plan/root/source read, configured work/expiry,
  policy credential, exact resource grants and genuine skill tests; no model.
- automatic_document_inputs: exact published ontology READ and source/scope
  binding before passing rule inputs; no empty-schema workaround.
- readonly_continuation + readonly_instance_assembly: policy work/source check,
  exact published employee/resource mapping, deterministic instance/assignment
  identities from original Plan digest, resource reads and ontology READ/USE.
  for_transaction(connection) keeps assembly writes in the owner transaction.
- workbench_prepared_execution PREPARE: validates Plan, target, participants and
  current resources before inserting the exact prepared candidate. Only then
  execution_grants enumerates Run/participant/skill-ordinal/evaluation/output
  targets. PreparedExecutionGrantTargets validates against that candidate;
  no pre-created fake Run/output is required to request a future exact target.
- prepared_execution_application + prepared_native_coordinator: exact Run and
  participant admission, ontology USE, expected skill attempt ordinal, then
  transactional queue. Repeat same Plan key reads committed receipt.
- prepared_native_composition: worker reconstitutes the original subject/scope,
  command generation and authorization resource; checks current authority,
  pinned ontology and separately configured Native/model admission and budget.
- readonly_continuation_worker: filters by exact execution-policy digest,
  subject/root/source/agent/expiry and committed receipt; terminal evaluation
  uses original command authority. It does not invent a new caller.
- prepared_result_review + prepared execution read: exact execution/evaluation/
  evidence/resource-use permissions; human business confirmation remains a
  separate action, not silently supplied by automatic evaluation.

B. Repeated checks, not proved redundant:
- Plan/root/resource checks recur at resource preparation, execution preparation,
  dispatch and read. These cross different transaction/time/effect boundaries;
  removing them would lose stale/revocation protection.
- Repeated permission checks within assembly/preparation currently share a
  transaction but also protect independently callable owners. No safe removal
  established in this bounded audit; no new model calls are involved.

C. Verified enumeration/transfer/lifecycle defects and limits:
- Missing v4 ontology/semantics test inputs: fixed by prior a7c54c1 adapter.
- Missing ontology READ/USE with READONLY_WORK_EXECUTION purpose: parent verified
  generation configuration gap, not missing recovery invocation ownership.
- Original conversation EXECUTE pending could not read/reattach original receipt
  and its legacy configuration button cleared pending before authoritative
  readback: addressed by this package.
- Generation and policy digest changes/expiry intentionally invalidate worker
  admission; deployment must preserve/check the exact active policies and
  grants. Do not assume a prior successful preparation authorizes later effects.
- Initial automatic scope grants skill attempt 1 only. Retry ordinals require
  existing explicit retry authorization, not broad automatic retries.
- This is source review plus controlled tests, not proof that real runtime,
  Kubernetes placement, model budget, worker identity and returned evidence all
  pass. Parent owns full installed end-to-end verification and current policy
  inventory; no claim of full-chain completion is made here.
