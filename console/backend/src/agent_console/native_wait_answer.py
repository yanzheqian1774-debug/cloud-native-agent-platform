"""Original answer owner bridge; no continuation is claimed by a user answer."""

import json
import os
from datetime import datetime
from pathlib import Path

from agent_runtime.native_loop import digest

from .authority_contracts import AuthorityError
from .native_wait_configuration import DurableWaitConfiguration
from .native_wait_owner import NativeWaitOwner
from .native_wait_store import NativeWaitStore
from .native_wait_types import WaitIdentity
from .owned_business_work_reader import OwnedBusinessWorkReader


def accept_if_waiting(call, app, preparation, value):
    c = call.connection
    if not c.execute(
        "SELECT to_regclass('skill_invocation.native_wait_heads') AS t"
    ).fetchone()["t"]:
        return None
    row = c.execute(
        "SELECT h.checkpoint_digest,cp.record "
        "FROM skill_invocation.native_wait_heads h "
        "JOIN skill_invocation.native_wait_checkpoints cp "
        "USING(namespace,security_domain,skill_invocation_id,checkpoint_digest) "
        "WHERE h.namespace=%s AND h.security_domain=%s AND h.skill_invocation_id=%s",
        (
            preparation.namespace,
            preparation.security_domain,
            call.payload["invocationId"],
        ),
    ).fetchone()
    if not row:
        return None
    paths = [
        os.environ.get(name)
        for name in (
            "NATIVE_DURABLE_WAIT_CONFIGURATION",
            "NATIVE_LOOP_RUNTIME_FILE",
            "OWNED_BUSINESS_ADMISSION_POLICY",
        )
    ]
    if not all(paths):
        raise AuthorityError("NATIVE_WAIT_NOT_ENABLED")
    runtime = json.loads(Path(paths[1]).read_text())
    config = DurableWaitConfiguration.load(paths[0], digest(runtime))
    adapter = call.authority.adapter
    reader = OwnedBusinessWorkReader(
        paths[2],
        adapter.authorization,
        call.authority.generation,
        adapter.controller.readiness.recovery_epoch,
    )
    identity = WaitIdentity.model_validate(row["record"]["identity"])
    cp = NativeWaitStore(c, identity).checkpoint(row["checkpoint_digest"])

    def authorize(connection, checkpoint, operation):
        if operation != "ANSWER" or checkpoint != cp:
            raise AuthorityError("NATIVE_WAIT_ANSWER_OPERATION_REQUIRED")
        app.validate(preparation)
        binding = reader.work(
            connection,
            call.context,
            preparation.semantics.target.problem,
        )
        if (
            binding.scope.source != preparation.source_snapshot
            or cp.identity.principal_id != call.context.principal_id
            or cp.identity.conversation_id != value["conversationId"]
            or cp.identity.preparation_digest != preparation.digest
            or cp.identity.workflow_run_id != preparation.run_id
            or cp.question_key != call.payload["questionKey"]
            or cp.question_digest != value["questionDigest"]
            or (cp.executor_id, cp.executor_revision, cp.executor_configuration_digest)
            != (
                config.executorId,
                config.executorRevision,
                config.executorConfigurationDigest,
            )
            or cp.model_profile_digest != runtime["modelRuntimeDigest"]
            or cp.maximum_decisions != runtime["maximumDecisions"]
            or cp.source_digest != preparation.source_snapshot.digest
            or cp.authority_expires_at
            > min(binding.expires_at, datetime.fromisoformat(runtime["expiresAt"]))
        ):
            raise AuthorityError("NATIVE_WAIT_ANSWER_BINDING_CHANGED")
        # Runtime rechecks original scope evidence before its next effect;
        # this answer does not change that immutable execution context.

    return NativeWaitOwner(authorize, None).accept_answer(c, cp, value)
