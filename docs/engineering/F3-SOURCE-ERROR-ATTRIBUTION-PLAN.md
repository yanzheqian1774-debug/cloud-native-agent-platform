# G1: distinguish input access failures from stale source evidence

Keep collection LIST and exact resource READ in place, including no-source requests.
Translate denied access into a generic 403 without resource identifiers; translate
authority/storage unavailability into 503. Preserve exact-version/content mismatch
as 409 after authorization. Keep errors before provider dispatch, retain original
message and existing explicit recovery flow. Add friendly original-conversation
copy without automatic retry changes. No model policy/config/digest changes.

Check no-source denied access, real selected digest mismatch, storage failure,
source attachment clearing, and existing source-read regressions. Frontend build
checks the error rendering change. Do not touch the live platform or database.
