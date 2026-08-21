# Evidence debt

## ED-S5-001 — Real Model Completion Evidence

- Status: OPEN
- Checkpoint B impact: non-blocking
- Closure deadline: before S5-SPIKE-001 final

Checkpoint A reached the real Hermes gateway through the experimental generic
boundary, but no valid inference-provider credential was safely available.
Hermes returned HTTP 200 containing a provider-authentication failure and zero
token usage. Checkpoint B does not require model completion and will not persist
or expose credentials to close this debt.

## Closure attempt

Status remains OPEN after the authorized closure attempt on 2026-08-22. A safe
credential source was found and never exposed, but no request produced nonzero
usage or meaningful model output. See `ed-s5-001-closure.md`.

## Controlled retry #2

Status remains OPEN after the one authorized retry on 2026-08-22. The
remediation-approved profile `.env` binding completed, but the standalone
gateway did not become available within 180 seconds. The mandatory preflight
stopped before runtime provider/model resolution and before any inference
request. See `ed-s5-001-controlled-retry-2.md`.
