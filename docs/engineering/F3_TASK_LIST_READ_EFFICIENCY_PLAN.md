# F3 task directory read efficiency (G1)

Real continuous navigation exposed slow batch loading; visual acceptance did not
close performance. Retain scope/session checks, per-owner GET authorization,
exact execution/problem revision identity and verified original conversation.

Measure current candidate before changing requests: elapsed first useful row and
complete read, GET count by endpoint, stable visible rows, no business writes or
model calls. Then share only in-flight promises within one directory read (never
across sessions/refreshes), overlap the journey read with one already-linked exact execution per bounded
conversation worker, and omit terminal-run question history only for task/result lists.
The attention/history view must still load completed questions for its answered
section. Keep unavailable reads limited rather than claiming an empty complete set.

Validate duplicate aliases resolving to one exact run, verified origin precedence,
stale/denied versions, current questions and completed answer history, abort and
identity changes. Compare the same real data and exact rows before/after; do not
infer a performance guarantee from one sample. No production install in this slice.

## Measured adjustment

The first candidate overlapped journey and exact execution reads, raising per-worker
fanout. A single live sample reduced total requests (138 -> 116) but took longer
(81.9 -> 100.5 s); the historical baseline also omitted one record, so this is not
an equal-result speedup. Concurrent test load is a confound, not proof of cause.
Withdraw the speculative prefetch, retain the four-worker limit and read-scoped
promise deduplication; terminal history omission remains restricted to views which
do not display handled questions. Repeat live readback without concurrent tests.
No performance acceptance is implied by reduced request count alone.
