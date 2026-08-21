# ED-S5-001 closure attempt

> Experimental evidence. Credential values are intentionally absent.

## Result

**FAIL — ED-S5-001 remains OPEN.**

No attempt satisfied the mandatory requirement for meaningful output from a
real external inference model. Candidate v0 was not contradicted or edited.

## Runtime identity

- Hermes v0.20.4 / `nousresearch/hermes-agent:v2026.8.18`
- RepoDigest: `sha256:22e37bb4ed1b0f50cb6bd991dca7ecacd6c9f29df9b4a20fc989d32bc763ccf6`
- Environment: Docker Engine on macOS arm64, Linux arm64 container
- Platform/Provider baseline: commit
  `d648a83e60e2e5375d3f23ed7da7292a54fcfa07` plus spike-local closure changes

## Credential binding

- Source: existing Kubernetes Secret `agent-workloads/model-credentials`, key
  name `api-key`
- Host mechanism: decoded directly into a process-local environment variable
- Runtime mechanism: inherited environment-variable name; later a disposable
  `/opt/data/.env` created inside the temporary runtime volume
- Value printed: no
- Value written to source/evidence/fixtures: no
- Persistent credential artifact retained: no

## Generic path

The request originated as `RuntimeRequest(input, correlation_id)` with no
Hermes API path, profile, gateway command, or provider configuration. The
Hermes Provider selected `kimi-coding-cn`, configured `kimi-k3`, translated the
request to `/v1/chat/completions`, and normalized response content into
`RuntimeResult(output, correlation_id)`.

## Sanitized observations

1. The original five-second prototype interaction timeout expired before a
   completion. The invocation timeout was separated from health-probe timeout.
2. With process-level model selection only, Hermes used its generated default
   `anthropic/claude-opus-4.6`. It returned HTTP 200, `finish_reason=error`, zero
   tokens, and a model-not-found/permission failure. Provider/runtime latency:
   18.570 s; total provision-to-result: 28.480 s.
3. With non-secret persisted selection `model.provider=kimi-coding-cn` and
   `model.default=kimi-k3`, Hermes returned HTTP 200,
   `finish_reason=error`, runtime request ID
   `chatcmpl-962ea4018ce9496592363829da5b6`, zero tokens, and `HTTP 401: Missing
   Authentication header`. Generic correlation ID:
   `ed-s5-001-1727726d096545bb91207479ac966ae4`. Provider/runtime latency:
   16.515 s; total provision-to-result: 38.682 s.
4. Hermes source inspection showed managed environment reload can remove known
   provider variables absent from the active profile `.env`. A disposable
   runtime `.env` binding was attempted first with mode 0600/root ownership and
   then with `hermes:hermes` ownership. Both runs failed the bounded 180-second
   runtime-availability wait; no invocation or model output occurred.

The recognized marker `ED_S5_001_OK` was never observed. All observed usage was
zero. No inference-provider request ID was exposed.

## Semantic classification

- Transport success was observed for two Hermes API responses: HTTP 200.
- Semantic result for both was FAILURE.
- Real Hermes and real gateway: yes for the two recorded responses.
- Successful real external model execution: no evidence.
- Normalized successful result: not produced.

The evidence reinforces, but does not change, Candidate v0's distinction among
transport, runtime-native, dependency/configuration, and execution outcomes.
HTTP success again disagreed with semantic success.

## Remaining blocker

Hermes did not successfully resolve/use the ephemeral Moonshot credential in a
gateway configuration that remained runtime-available. Closing the debt needs
a human-reviewed, Hermes-supported secret-binding procedure or a preconfigured
ephemeral Hermes profile, followed by one successful generic-boundary request.
No further attempts were made in this checkpoint.

