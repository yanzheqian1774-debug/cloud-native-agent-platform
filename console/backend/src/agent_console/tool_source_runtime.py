"""Trusted registered read-only protocol adapter, never a host ZIP loader."""

import base64
import hashlib
import time

import httpx

from .execution_domain import record_digest
from .skill_executor import HttpReadOnlySkillExecutor
from .tool_import import preview_plugin_zip


def source_request(repository, call, current, binding, inputs):
    from .execution_domain import ScopeIdentity

    scope = ScopeIdentity(binding.namespace, binding.securityDomain)
    kind, payload = repository.source(call.connection, scope, binding.sourceDigest)
    if (
        kind != "PLUGIN_ZIP"
        or hashlib.sha256(payload).hexdigest() != binding.sourceDigest
    ):
        raise ValueError("TOOL_SOURCE_EXACT_ZIP_REQUIRED")
    preview = preview_plugin_zip(payload)
    manifest = preview["sourceDocument"]
    operation = current["record"]["operation"]
    matched = [o for o in preview["operations"] if o["name"] == operation["name"]]
    files = {f["path"]: f["digest"] for f in preview["files"]}
    if (
        manifest["runtime"] != binding.runtime
        or manifest["entrypoint"] != binding.entrypoint
        or files.get(binding.entrypoint) != binding.entrypointDigest
        or len(matched) != 1
        or matched[0]["source"] != operation["source"]
        or operation["sideEffect"] != "read-only"
        or manifest.get("permissions", [])
    ):
        raise ValueError("TOOL_SOURCE_RUNTIME_OR_ENTRYPOINT_MISMATCH")
    return {
        "toolId": current["toolId"],
        "revisionId": current["revisionId"],
        "revisionDigest": current["digest"],
        "sourceDigest": binding.sourceDigest,
        "entrypoint": binding.entrypoint,
        "entrypointDigest": binding.entrypointDigest,
        "runtime": binding.runtime,
        "runtimeRevision": binding.runtimeRevision,
        "operation": operation["name"],
        "inputDigest": record_digest(inputs),
        "sourceBase64": base64.b64encode(payload).decode(),
        "arguments": inputs,
        "syntheticReadOnly": True,
    }


class BoundedStream(httpx.SyncByteStream):
    def __init__(self, stream, limit, deadline):
        self.stream, self.limit, self.deadline = stream, limit, deadline

    def __iter__(self):
        size = 0
        for chunk in self.stream:
            size += len(chunk)
            if size > self.limit or time.monotonic() > self.deadline:
                raise ValueError("TOOL_SOURCE_RESPONSE_LIMIT")
            yield chunk

    def close(self):
        self.stream.close()


class RegisteredLocalTransport(httpx.HTTPTransport):
    def __init__(self, binding):
        super().__init__(retries=0)
        self.binding = binding
        self.deadline = time.monotonic() + binding.timeoutMs / 1000

    def handle_request(self, request):
        if str(request.url) != self.binding.endpoint + "/v1/read-only/invoke":
            raise ValueError("TOOL_SOURCE_REGISTERED_ENDPOINT_REQUIRED")
        response = super().handle_request(request)
        response.stream = BoundedStream(
            response.stream, self.binding.maximumOutputBytes + 8192, self.deadline
        )
        return response


def invoke(binding, invocation_id, request):
    executor = HttpReadOnlySkillExecutor(
        executor_id=binding.runtime,
        executor_revision=binding.runtimeRevision,
        endpoint=binding.endpoint,
        transport=RegisteredLocalTransport(binding),
    )
    response = executor.invoke(
        invocation_id, "tool-source-test.v1", request, binding.timeoutMs
    )
    envelope = response.output
    proof = envelope.get("execution", {})
    expected = {
        key: request[key]
        for key in (
            "toolId",
            "revisionId",
            "revisionDigest",
            "sourceDigest",
            "entrypoint",
            "entrypointDigest",
            "runtime",
            "runtimeRevision",
            "operation",
            "inputDigest",
        )
    }
    actual = envelope.get("actual")
    if (
        proof != expected
        or not isinstance(actual, dict)
        or envelope.get("actualDigest") != record_digest(actual)
        or envelope.get("sourceExecuted") is not True
    ):
        raise ValueError("TOOL_SOURCE_EXECUTION_PROOF_INVALID")
    return actual, {
        **proof,
        "actualDigest": record_digest(actual),
        "observationId": response.provider_observation_id,
        "executorConfigurationDigest": executor.revision.configuration_digest,
    }
