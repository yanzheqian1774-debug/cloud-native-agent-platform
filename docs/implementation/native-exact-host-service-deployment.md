# Exact-host service: coordinator-only deployment and stop procedure

Candidate only. No command below has been run against the actual platform.
No model call, schema change, grant, allowance, expiry or data-scope change is
required or authorized by this document. Use the existing credential loader;
never print/export secrets into status evidence. Do not reuse a manifest for an
older source (907c296 is the implementation base, not the eventual installed SHA).

## Prepare once, independently of future preparations

1. Install the reviewed package **default off** with the normal single-writer
   installer and full old-table/budget/state protection. Generate the installation
   manifest containing all new modules and their actual source hashes.
2. In the approved worker environment, load the existing authority/continuation/
   owned-business/Native-loop policy paths and credential from the existing loader.
   Keep their current generation, exact scopes, allowance and deadline unchanged.
   The configuration generator derives subject/domain from that same current owned
   policy and refuses expired policy. It cannot sign or renew anything.
3. Prepare a new private config, without database access or process startup:

```sh
python -m agent_operator.native_host_service_prepare \
  --manifest /absolute/next-install/manifest.json \
  --state-directory /absolute/private/native-host-service-state \
  --output /absolute/private/native-host-service-config/service.json \
  --max-hosts 2
```

The output defaults to disabled. For the separately reviewed actual activation,
prepare a distinct immutable config with `--enabled`; never overwrite the old
config or an in-use startup record. This is deployment activation only, not a
per-preparation action. No future prep list is accepted.

4. Launch the single service once using the existing loaded environment:

```sh
export NATIVE_EXACT_HOST_SERVICE_CONFIGURATION=/absolute/private/native-host-service-config/active.json
export NATIVE_DISPATCH_WORKER_ID=native-exact-discovery
export NATIVE_DISPATCH_PREPARED_SKILL=registered-readonly-v1
python -m agent_operator.native_host_service
```

Do not set `NATIVE_HOST_STARTUP_CONFIGURATION` or `NATIVE_HOST_SERVICE_*_FD` on the
manager. Existing required database, authority, migration and policy environment
values remain unchanged. The discovery assembly is never polled; child worker IDs
are generated from exact database/scope/subject/preparation identity.

5. Set `NATIVE_EXACT_HOST_SERVICE_STATUS_DIRECTORY` on the API to the same private
   state directory, enabling only the existing-authorized native-progress optional
   observation. Verify default-off absence and exact ordinary READ behavior.
6. Record actual manager PID/birth, manifest/policy hashes, machine database lock,
   service status and child registry. Confirm no preexisting UNKNOWN task was
   selected. **Only now** create two new authorized ordinary-user works through the
   UI. Their prep IDs must not occur in pre-start config. Observe automatic exact
   child startup, current grants/allowance checks, clarification, and original-chat
   result. No per-prep script/start command is allowed during this acceptance.

## Stop and next installation

- Single writer reads private `service-status.json` and all `exact-host-*.json`
  process records (exclude boot/startup immutable records by schema).
- Validate schema, worker/manifest binding and PID **plus processBirth** using the
  same `ps -p PID -o lstart=` observation. Never signal a numeric PID whose birth
  does not match. A mismatch is blocked/needs inspection, not permission to kill.
- Send SIGTERM only to the verified manager process. It closes each parent pipe,
  preventing additional worker polls after the in-flight owner operation finishes.
  It does not manufacture an execution cancellation or kill a provider to claim
  success. Wait the configured shutdown interval.
- Require the manager's actual exit. `DRAINED` means its children were observed
  exited; it does not itself prove the manager is already gone. For every child,
  require actual process exit plus release of inherited exact-worker lock. The
  machine-local DB-fingerprint lock is inherited by every child and must also be
  acquirable/released as a final zero-live-writer check. Inspect from the same OS
  account; do not delete lock files to bypass contention.
- `EXIT_UNCONFIRMED`, live matching PID, unreadable state, held lock or missing
  startup chain blocks source/config replacement. Wait/inspect through existing
  runtime recovery; never launch a fresh worker ID to evade a retained claim.
- Preserve all boot/startup files. A subsequent deployment uses the same private
  state directory and stable workers; each restart pins the new current source
  and verifies the prior exact startup digest. Existing predecessor scope must be
  identical. Missing records or the bounded chain limit fail closed.
- A new manifest/policy hash requires a new config and verified physical restart,
  not editing files underneath current children. No automatic generation switch,
  scope growth, authority renewal or UNKNOWN successor is performed here.

Failure evidence must distinguish configuration/discovery/child-start/observation
failure from Native execution failure. Local host readiness never certifies work
completion; durable Native and outcome owners remain authoritative.

The machine lock directory is the canonical system `/tmp` directory plus
`native-exact-host-service-<OS uid>`, with the database fingerprint as lock filename.
It is independent of TMPDIR and stateDirectory. macOS `/tmp` symlink resolution is
performed only for this internally derived path; user-configured paths remain
strictly canonical. Supervision is for the same deployment OS account, not a
cross-account/cross-machine ownership service.
