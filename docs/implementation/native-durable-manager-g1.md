# G1 — exact host observation for the approved durable human wait slice

Base c3d6029. Root owns actual installation, policy, worker and model operations.
This isolated increment owns only native_host_service.py, native_host_service_discovery.py and dedicated tests. NativeWaitCommandAccess and wait owner/state/schema remain with the durable-wait implementation. Default absent adapter preserves legacy behavior.

## Interface and responsibilities

Discovery captures optional assembly/caller.wait_access. After original receipt, exact owned-work/current authority and progress/command checks, inspect(connection,candidate) returns None for no positive checkpoint or completed wait; otherwise state/checkpointDigest/questionKey/resumable/activeWorkerId/startupRecordDigest. Reader failure raises; never interpret it as no wait.

Launch eligibility: QUIESCING, WAITING_FOR_USER, CONTINUATION_CLAIMED and ADVANCING cannot start a new host. ANSWER_SAVED is eligible only with resumable=true (owner has exact STOP_CONFIRMED). Existing UNKNOWN exclusion remains. COMPLETED uses original outcome after_tick behavior.

Maintenance is separate from launch: Discovery.maintain(candidate,process_record) may retain an already live ADVANCING child only when its exact worker/startup record match the authoritative reader. It cannot make a new host launch eligible. QUIESCING closes the existing control pipe and waits for actual process exit; an answer arriving first cannot start another host.

After Popen.poll confirms this exact child exited, manager persists one fixed exitReceipt in existing local process state, bound to original namespace/domain/subject/prep/run, worker, pid, processBirth, startup digest, boot, returnCode and first observation time. Existing startup record digest/observation are rechecked. No new nonce or service identity is invented. PID disappearance alone is not proof.

Discovery.stopped(connection via original pool,candidate,process_record,startup_record,exit_receipt,verify_exit) calls only the existing wait adapter. verify_exit is the manager closure over the actual child/poll and fixed record, never a browser boolean. Backend constructs the existing typed StopObservation and invokes owner.confirm_stopped. No wait SQL in manager.

If owner confirmation fails after physical exit and successful proof persistence, release the dead OS process slot/FD while preserving identical proof and UNKNOWN; retry observation only. The same preparation remains blocked unless its authoritative wait owner confirms readiness. If physical exit or durable proof remains unconfirmed, retain slot/lock. Other independently authorized preparations must not starve behind a dead process. Do not mint a receipt timestamp, claim another job or redispatch INPUT/model. Existing post-G cleanup and missing-record fail-closed rules remain.

## Validation and limits

Controlled local tests: waiting no restart, answered-before-stop no restart, exact advancing live child preserved, wrong worker/startup rejected, completed after_tick retained, callback failure preserves the same receipt and releases only confirmed-dead durable capacity, missing/corrupt startup and PID reuse cannot produce stop proof, legacy no-adapter behavior unchanged. Backend owner PG and runtime composition remain separately required; local test success is not actual durable waiting acceptance.

No public Task/Skill/command terminal semantics, CRD, permission, table or new infrastructure changes in this increment. Same original job and slot. If restart needs a new invocation or UNKNOWN recovery, stop and report rather than silently implement.

## Trusted local observation redelivery

An actual poll-confirmed exit creates one immutable exitProof envelope (processRecord + exitReceipt + canonical digest) in the existing owner-only local process file. Startup path must be the exact configured directory/worker/boot filename; existing owned_file enforces same UID, mode0600 and no symlink. On restart, only an already saved EXIT_CONFIRMED proof can be redelivered; absent PID or legacy EXIT_CONFIRMED without proof cannot create one. Original process/startup fields, preparation/run/subject and both digests are rechecked. The backend still checks the current checkpoint and original startup/current authority. The local record is evidence of one old process exit, not execution outcome or execution permission.

Discovery page may redeliver such proof for positive wait records before its launch filter, then rereads the original wait owner. No launch occurs while missing/unknown/failed observation. Normal current() before GO and maintain() never recurse into observation. Graceful service shutdown also saves actual exit proof and lists pendingWaitObservations if owner delivery failed; DRAINED still describes OS children only.

Targeted validation: see final logs; initial24 local tests passed with existing host service regression; separate missing-PID/no-proof negative passed. Controlled children, no actual service, DB, model or permission writes. Backend adapter remains a sibling candidate requiring joint integration/owner verification.
