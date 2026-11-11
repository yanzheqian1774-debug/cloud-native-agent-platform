# F3 exact resource read feedback (G1)

Baseline: d5d9e217. Frozen product baseline remains V6.9-F3.

Inspection found that ExactResourceDetail's session/detail/session sequence had
no deadline. A pending request could leave the page at its loading status
indefinitely. A controlled stalled-detail browser case failed against the
baseline: no failure state appeared. This is distinct from model execution
timeouts and does not authorize retrying any model or business command.

Bound the whole detail read attempt to 30 seconds. On timeout invalidate the
attempt, clear its content, abort its requests and show explicit read feedback.
Provide an explicit read-only retry for the same route and fixed revision. Each
attempt retains both session checks, exact scope, identity and digest validation.
Unmount or session expiry cancels the timer; late responses cannot replace newer
state. No automatic retry, grant change, API/schema change or execution is added.

Validation: controlled stalled read, successful exact retry, denied retry without
content, existing directory routing/filter/current-history checks; frontend lint
and full-feature build. Real candidate browser verification uses existing
ordinary-role fixed grants and data, holds only the first detail GET, waits the
actual 30 seconds, then removes interception for explicit retry and verifies
refresh/return with no business writes. Distinguish that candidate frontend overlay
from installed main acceptance; submit the error/recovery presentation to the
prototype reviewer before closing this bounded stage.

Remaining scope: this patch does not bound every directory/client read, eliminate
server-side latency, prove model execution recovery, renew Native budgets, or
complete the overall task/resource/digital-employee delivery.

Reviewer follow-up: error states also render the existing independently verified
EmployeeResourceReturn. Do not make escape depend on successful detail retry.
Use "重新读取此版本" and state that the original reference is unchanged; historical
revisions must not imply a switch to the latest publication. Add historical retry,
verified employee-return target and ignored late-response coverage. A pre-existing
UI01 heading assertion still expected an obsolete "usage records" heading; align
that assertion with the already implemented "关联任务中的保存引用" semantics, without
changing the product back to a misleading actual-invocation claim.
