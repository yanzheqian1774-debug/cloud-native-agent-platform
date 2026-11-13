# G1: recognize the exact problem create collection

The conversation work before-hook submits BUSINESS_PROBLEM CREATE on the exact
collection. Its validator currently routes only object READ/REVISE/TRANSITION,
and the canonical problem owner lacks CREATE discovery. Grant submission therefore
fails before owner creation. Existing work authorization tests stub this validator.

Add exact CREATE collection recognition in the canonical problem owner and dispatch
that action through the existing Workbench validator. Require the owner and existing
connection; reject wildcard, suffixed, unrelated targets and unsupported actions.
Target existence is not permission. No changes to requestability, current grants,
policy, account, budget, approval or owner execution authorization. No skip of the
existing bounded grant-request/decision flow. Add tests using the real owner method,
including rejected targets and proof that discovery performs no database writes.

Planning after-hook remains independently bound to the configured planning model;
understanding revision changes must not overwrite planning or its historic record.
Verify the configured planning target is an exact registered planning binding and
requestable under WORKBENCH_PLANNING after CREATE has a receipt. Do not repeat the
model call or blindly repeat a potentially committed create request.
