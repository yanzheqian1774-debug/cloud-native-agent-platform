# ED-S5-001 controlled retry #2

> Experimental evidence. Credential values are intentionally absent.

## Result

**FAIL — RUNTIME_AVAILABILITY_FAILURE. ED-S5-001 remains OPEN.**

The one authorized attempt used a fresh disposable `/opt/data`, the pinned
Hermes image, the standalone gateway command, `kimi-coding-cn`, `kimi-k3`, and
a mode-0600 profile `.env`. The gateway did not become available within the
bounded 180-second startup window. The runner stopped before its sanitized
runtime-resolution preflight and sent no inference request.

## Runtime identity

- Hermes: v0.20.4
- Image: `nousresearch/hermes-agent:v2026.8.18`
- RepoDigest:
  `sha256:22e37bb4ed1b0f50cb6bd991dca7ecacd6c9f29df9b4a20fc989d32bc763ccf6`
- Active home requested: `/opt/data`
- Mode requested: standalone gateway
- Environment: Docker Engine on macOS arm64, Linux arm64 container

## Preflight gate

| Check | Result | Sanitized evidence |
| --- | --- | --- |
| P01 active home | NOT REACHED | Runtime resolver was gated behind gateway availability. Provisioning fixed `HERMES_HOME=/opt/data` in the pinned image. |
| P02 standalone mode | NOT REACHED | Runner requested one `gateway run`; runtime resolution was not reached. |
| P03 config exists | PASS | Both non-secret `hermes config set` commands completed before provision. |
| P04 resolved provider | NOT REACHED | No runtime-resolution output was collected. |
| P05 resolved model | NOT REACHED | No runtime-resolution output was collected. |
| P06 `.env` exists | PASS | Ephemeral binding command completed successfully. |
| P07 credential key name | PASS | Binding mechanism wrote only the configured `KIMI_CN_API_KEY` assignment. |
| P08 assignment non-empty | PASS | Runner rejected an absent/empty source before provisioning; value was not printed. |
| P09 value not printed | PASS | No credential value appeared in command output or evidence. |
| P10 ownership/mode | PASS | Binding used mode 0600 and `hermes:hermes`; the command completed successfully. |
| P11 gateway process available | FAIL | No READY health result within 180 seconds. |
| P12 API interaction surface | FAIL | Hermes health interaction never became available. |

Because P11 and P12 failed, the attempt stopped. P04 and P05 are deliberately
not inferred from configured values.

## Invocation and semantic evidence

- Generic `RuntimeRequest` constructed: yes, in memory only
- Request sent to Hermes: **no**
- Request sent to Kimi: **no**
- Transport result: none
- Semantic result: not executed
- Normalized `RuntimeResult`: none
- Marker observed: no
- Usage: none
- Runtime-native ID: none
- Inference-provider ID: none
- Correlation ID emitted: none

## Interpretation

This result is specifically `RUNTIME_AVAILABILITY_FAILURE`, not model
authentication, authorization, model-not-found, transport, or semantic
failure. The attempt produced no evidence about Kimi because inference was
correctly blocked by the failed preflight.

The result does not contradict Runtime Contract Candidate v0. It reinforces
the distinction between configured model binding, runtime availability,
dependency resolution, and execution success. AP-S5-004 remains SUPPORTED.

## Security and cleanup

- Credential source referenced only by Secret name, key name, and environment
  variable name.
- Credential value printed: no.
- Credential value committed or written to evidence: no.
- Temporary `.env` and disposable `/opt/data`: removed by temporary-directory
  cleanup.
- Temporary container: removed by provider cleanup.
- Source Kubernetes Secret: read-only and unchanged.
- Automatic configuration change/retry after failure: none.
