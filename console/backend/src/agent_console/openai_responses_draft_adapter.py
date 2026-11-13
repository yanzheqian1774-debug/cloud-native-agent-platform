"""Bounded OpenAI Responses adapter for governed Draft Assistance.

This module never reads environment variables and never retries or follows a
redirect. Raw request/response content is ephemeral and is not included in
exceptions or object representations.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import math
import os
import re
import ssl
import stat
import time
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urlsplit

from agent_console.draft_assistance import (
    DraftAssistanceError,
    DraftResultKind,
    ObservationState,
    PreparedProviderRequest,
    ProviderBudgetQuote,
    ProviderObservation,
)
from agent_console.draft_assistance_policy import (
    V1_INSTRUCTIONS,
    V1_SCHEMA,
    PolicyValidationError,
    context_references,
    conversation_context_references,
    legacy_content,
    policy_for,
    validate_result,
)

ADAPTER_ID = "openai-responses-draft"
ADAPTER_REVISION = "v1"
PROTOCOL = "OPENAI_RESPONSES_V1"
OUTPUT_SCHEMA_VERSION = "problem-draft-assistance-output.v1"

INSTRUCTIONS = V1_INSTRUCTIONS

OUTPUT_SCHEMA = V1_SCHEMA


@dataclass(frozen=True, slots=True)
class OpenAIResponsesConfiguration:
    execution_class: str
    responses_url: str
    native_model_id: str
    credential_reference: str
    credential_version: str
    credential_resolver_id: str
    credential_resolver_revision: str
    credential_file: Path
    connect_timeout_seconds: int
    read_timeout_seconds: int
    total_timeout_seconds: int
    maximum_input_tokens: int
    maximum_output_tokens: int
    maximum_response_bytes: int
    input_price_microusd_per_million_tokens: int
    output_price_microusd_per_million_tokens: int
    ca_file: Path | None = None
    planning_model_policy: str | None = None

    def __post_init__(self) -> None:
        if self.planning_model_policy is not None and (
            self.planning_model_policy != "gpt61-sol-standard-uncached-low.v1"
            or self.native_model_id != "gpt-6.1-sol"
            or self.input_price_microusd_per_million_tokens != 2_000_000
            or self.output_price_microusd_per_million_tokens != 10_000_000
            or not isinstance(self.maximum_input_tokens, int)
            or self.maximum_input_tokens >= 272_000
        ):
            raise DraftAssistanceError("OPENAI_RESPONSES_PROFILE_INVALID")
        if (
            not isinstance(self.execution_class, str)
            or not isinstance(self.responses_url, str)
            or self.execution_class not in {"REAL_PROVIDER", "LOCAL_HTTPS_MOCK"}
        ):
            raise DraftAssistanceError("OPENAI_RESPONSES_PROFILE_INVALID")
        parsed = urlsplit(self.responses_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path != "/v1/responses"
        ):
            raise DraftAssistanceError("OPENAI_RESPONSES_PROFILE_INVALID")
        text_values = (
            self.native_model_id,
            self.credential_reference,
            self.credential_version,
            self.credential_resolver_id,
            self.credential_resolver_revision,
        )
        if any(
            not isinstance(value, str) or not value or value.strip() != value
            for value in text_values
        ):
            raise DraftAssistanceError("OPENAI_RESPONSES_PROFILE_INVALID")
        if not isinstance(self.credential_file, Path) or (
            self.ca_file is not None and not isinstance(self.ca_file, Path)
        ):
            raise DraftAssistanceError("OPENAI_RESPONSES_PROFILE_INVALID")
        if not self.credential_file.is_absolute() or (
            self.ca_file is not None and not self.ca_file.is_absolute()
        ):
            raise DraftAssistanceError("OPENAI_RESPONSES_PROFILE_INVALID")
        positive = (
            self.connect_timeout_seconds,
            self.read_timeout_seconds,
            self.total_timeout_seconds,
            self.maximum_input_tokens,
            self.maximum_output_tokens,
            self.maximum_response_bytes,
        )
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 1
            for value in positive
        ) or any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in (
                self.input_price_microusd_per_million_tokens,
                self.output_price_microusd_per_million_tokens,
            )
        ):
            raise DraftAssistanceError("OPENAI_RESPONSES_PROFILE_INVALID")
        if self.total_timeout_seconds < max(
            self.connect_timeout_seconds, self.read_timeout_seconds
        ):
            raise DraftAssistanceError("OPENAI_RESPONSES_PROFILE_INVALID")


class ResolvedOpenAICredential:
    """Sealed short-lived value whose repr never exposes the credential."""

    __slots__ = ("_value", "reference", "version")

    def __init__(self, value: str, reference: str, version: str) -> None:
        self._value = value
        self.reference = reference
        self.version = version

    def authorization_value(self) -> str:
        return f"Bearer {self._value}"

    def __repr__(self) -> str:
        return "ResolvedOpenAICredential(<redacted>)"


class ExactFileOpenAICredentialResolver:
    def __init__(
        self,
        configuration: OpenAIResponsesConfiguration,
        *,
        expected_profile_revision_id: str,
        expected_connection_profile_id: str,
        expected_connection_profile_revision_id: str,
    ) -> None:
        self.configuration = configuration
        self.expected_profile_revision_id = expected_profile_revision_id
        self.expected_connection_profile_id = expected_connection_profile_id
        self.expected_connection_profile_revision_id = (
            expected_connection_profile_revision_id
        )
        self.calls = 0

    def resolve(self, profile, invocation_id):
        del invocation_id
        self.calls += 1
        if (
            profile.profile_revision_id != self.expected_profile_revision_id
            or profile.connection_profile_id != self.expected_connection_profile_id
            or profile.connection_profile_revision_id
            != self.expected_connection_profile_revision_id
            or profile.adapter_id != ADAPTER_ID
            or (profile.adapter_revision, profile.output_schema_version)
            not in {
                (ADAPTER_REVISION, OUTPUT_SCHEMA_VERSION),
                (ADAPTER_REVISION, "plan-suggestion-output.v1"),
                ("v2", "problem-draft-assistance-output.v2"),
                ("v2-zh-CN", "problem-draft-assistance-output.v2"),
                ("v3", "conversation-understanding-output.v3"),
                ("v3-execution", "conversation-understanding-output.v3-execution"),
                ("v3-relation", "conversation-understanding-output.v3-relation"),
                (
                    "v3-relation-adoption",
                    "conversation-understanding-output.v3-relation-adoption",
                ),
                (
                    "v3-relation-adoption-source",
                    "conversation-understanding-output.v3-relation-adoption",
                ),
            }
        ):
            raise DraftAssistanceError("CREDENTIAL_RESOLUTION_FAILED")
        descriptor = None
        try:
            descriptor = os.open(
                self.configuration.credential_file,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            )
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) & 0o077
            ):
                raise OSError
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = None
                raw = stream.read(8193)
        except OSError as exc:
            raise DraftAssistanceError("CREDENTIAL_RESOLUTION_FAILED") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
        if len(raw) < 8 or len(raw) > 8192 or b"\x00" in raw:
            raise DraftAssistanceError("CREDENTIAL_RESOLUTION_FAILED")
        try:
            value = raw.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise DraftAssistanceError("CREDENTIAL_RESOLUTION_FAILED") from exc
        if not value or any(char.isspace() for char in value):
            raise DraftAssistanceError("CREDENTIAL_RESOLUTION_FAILED")
        return ResolvedOpenAICredential(
            value,
            self.configuration.credential_reference,
            self.configuration.credential_version,
        )


class OpenAIResponsesDraftTransport:
    def __init__(self, configuration: OpenAIResponsesConfiguration) -> None:
        self.configuration = configuration
        self.synthetic = configuration.execution_class == "LOCAL_HTTPS_MOCK"
        self.dispatch_count = 0
        self.isolation_enabled = True
        self.cleanup_failed = False
        self.last_deadline = None
        self.progress = lambda stage: None

    @staticmethod
    def _cost(tokens: int, price_microusd_per_million: int) -> int:
        return math.ceil(tokens * price_microusd_per_million / 1_000_000)

    def prepare(self, *, invocation_id, content, profile):
        del invocation_id
        if (
            profile.adapter_id != ADAPTER_ID
            or (profile.adapter_revision, profile.output_schema_version)
            not in {
                (ADAPTER_REVISION, OUTPUT_SCHEMA_VERSION),
                ("v2", "problem-draft-assistance-output.v2"),
                ("v2-zh-CN", "problem-draft-assistance-output.v2"),
                ("v3", "conversation-understanding-output.v3"),
                ("v3-execution", "conversation-understanding-output.v3-execution"),
                ("v3-relation", "conversation-understanding-output.v3-relation"),
                (
                    "v3-relation-adoption",
                    "conversation-understanding-output.v3-relation-adoption",
                ),
                (
                    "v3-relation-adoption-source",
                    "conversation-understanding-output.v3-relation-adoption",
                ),
            }
            or profile.maximum_output_tokens != self.configuration.maximum_output_tokens
            or profile.total_timeout_seconds != self.configuration.total_timeout_seconds
        ):
            raise DraftAssistanceError("OPENAI_RESPONSES_PROFILE_MISMATCH")
        try:
            policy = policy_for(profile.adapter_revision, profile.output_schema_version)
            if policy.revision in {
                "v2",
                "v2-zh-CN",
                "v3",
                "v3-execution",
                "v3-relation",
                "v3-relation-adoption",
                "v3-relation-adoption-source",
            }:
                (
                    conversation_context_references
                    if policy.revision
                    in {
                        "v3",
                        "v3-execution",
                        "v3-relation",
                        "v3-relation-adoption",
                        "v3-relation-adoption-source",
                    }
                    else context_references
                )(content)
                if policy.revision in {
                    "v3-relation-adoption",
                    "v3-relation-adoption-source",
                } and any(
                    r.startswith("server-message:")
                    for r in conversation_context_references(content)
                ):
                    raise PolicyValidationError("DRAFT_CONTEXT_INVALID")
            else:
                content = legacy_content(content)
        except PolicyValidationError as exc:
            raise DraftAssistanceError(str(exc)) from None
        document = {
            "model": self.configuration.native_model_id,
            "instructions": policy.instructions,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": content}],
                }
            ],
            "background": False,
            "stream": True,
            "store": False,
            "max_output_tokens": self.configuration.maximum_output_tokens,
            "truncation": "disabled",
            "tools": [],
            "tool_choice": "none",
            "parallel_tool_calls": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "problem_draft_assistance_output",
                    "strict": True,
                    "schema": policy.schema,
                }
            },
        }
        from .conversation_source_input import current_attachment

        attachment = current_attachment()
        if attachment is not None:
            if policy.revision not in {
                "v3",
                "v3-execution",
                "v3-relation",
                "v3-relation-adoption",
                "v3-relation-adoption-source",
            }:
                raise DraftAssistanceError("DRAFT_POLICY_MISMATCH")
            if policy.revision == "v3-relation-adoption-source":
                from .understanding_source_body import provider_attachment

                attachment = provider_attachment(attachment)
            elif policy.revision == "v3-relation-adoption":
                selected = json.loads(attachment)
                attachment = json.dumps(
                    {
                        k: selected[k]
                        for k in (
                            "kind",
                            "source",
                            "sourceContentDigest",
                            "sourceSchema",
                            "name",
                        )
                    },
                    ensure_ascii=False,
                )
            document["input"].append(
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": attachment}],
                }
            )
        if policy.revision in {
            "v3-relation",
            "v3-relation-adoption",
            "v3-relation-adoption-source",
        }:
            from .conversation_relation_context import provider_input

            if attachment is not None and policy.revision == "v3-relation":
                raise DraftAssistanceError("CONVERSATION_ROUTING_SOURCE_CONFLICT")
            document["input"].append(
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": provider_input()}],
                }
            )
        payload = json.dumps(
            document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        # A byte count is deliberately conservative: token count cannot exceed the
        # complete encoded request byte count, and it includes instructions/schema.
        input_upper_bound = len(payload)
        if input_upper_bound > self.configuration.maximum_input_tokens:
            raise DraftAssistanceError("PROVIDER_INPUT_BOUND_EXCEEDED")
        quote = ProviderBudgetQuote(
            input_upper_bound,
            self.configuration.maximum_output_tokens,
            self._cost(
                input_upper_bound,
                self.configuration.input_price_microusd_per_million_tokens,
            )
            + self._cost(
                self.configuration.maximum_output_tokens,
                self.configuration.output_price_microusd_per_million_tokens,
            ),
        )
        return PreparedProviderRequest(payload, quote)

    @staticmethod
    def _observation_id(invocation_id: str, correlation: str, kind: str) -> str:
        digest = hashlib.sha256(
            f"{invocation_id}\0{correlation}\0{kind}".encode()
        ).hexdigest()
        return f"openai-response-observation:{digest}"

    def _failure(
        self,
        invocation_id: str,
        correlation: str,
        reason_code: str,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        latency_ms: int | None = None,
    ) -> ProviderObservation:
        return ProviderObservation(
            self._observation_id(invocation_id, correlation, reason_code),
            ObservationState.FAILED,
            correlation=correlation,
            reason_code=reason_code,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )

    def exchange(self, *, invocation_id, request, credential):
        """Shared one-shot Responses HTTP exchange; no purpose-specific semantics."""
        if (
            not isinstance(request.payload, bytes)
            or not isinstance(credential, ResolvedOpenAICredential)
            or credential.reference != self.configuration.credential_reference
            or credential.version != self.configuration.credential_version
        ):
            raise DraftAssistanceError("OPENAI_RESPONSES_REQUEST_INVALID")
        parsed = urlsplit(self.configuration.responses_url)
        ssl_context = ssl.create_default_context(
            cafile=(
                str(self.configuration.ca_file)
                if self.configuration.ca_file is not None
                else None
            )
        )
        connection = http.client.HTTPSConnection(
            parsed.hostname,
            parsed.port or 443,
            timeout=self.configuration.connect_timeout_seconds,
            context=ssl_context,
        )
        started = time.monotonic()
        self.dispatch_count += 1
        response = None
        try:
            self.progress("CONNECT")
            connection.connect()
            elapsed = time.monotonic() - started
            remaining = self.configuration.total_timeout_seconds - elapsed
            if remaining <= 0:
                raise TimeoutError
            if connection.sock is None:
                raise OSError
            connection.sock.settimeout(
                min(self.configuration.read_timeout_seconds, remaining)
            )
            self.progress("SEND_REQUEST")
            connection.request(
                "POST",
                parsed.path,
                body=request.payload,
                headers={
                    "Authorization": credential.authorization_value(),
                    "X-Client-Request-Id": invocation_id,
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                    "Connection": "close",
                },
            )
            self.progress("WAIT_HEADERS")
            response = connection.getresponse()
            raw_correlation = response.getheader("x-request-id")
            correlation = (
                raw_correlation
                if raw_correlation is not None
                and re.fullmatch(r"[A-Za-z0-9._:-]{1,200}", raw_correlation)
                else f"http-{response.status}-{invocation_id}"
            )
            self.progress("READ_BODY")
            from .response_stream import read_response

            body = read_response(response, self.configuration, self.progress)
        except (OSError, TimeoutError, ValueError, http.client.HTTPException) as exc:
            raise DraftAssistanceError("TRANSPORT_AMBIGUOUS") from exc
        finally:
            self.progress("CLOSE")
            # Connection: close transfers ownership of the stream to the response.
            # A short/oversized/failed read must not rely on garbage collection.
            try:
                if response is not None:
                    response.close()
            finally:
                connection.close()
        latency_ms = max(0, int((time.monotonic() - started) * 1000))
        self.progress("VALIDATE_RESPONSE")
        return response.status, body, correlation, latency_ms

    def dispatch(self, *, invocation_id, request, credential, profile):
        if self.isolation_enabled:
            from .responses_deadline import ResponsesBoundaryError, supervise
            from .responses_jobs import DraftResponsesJob

            if self.cleanup_failed:
                raise DraftAssistanceError("TRANSPORT_AMBIGUOUS")
            self.dispatch_count += 1
            try:
                value, diagnostic = supervise(
                    DraftResponsesJob(
                        self.configuration, invocation_id, request, credential, profile
                    ),
                    self.configuration,
                )
            except ResponsesBoundaryError as exc:
                self.last_deadline = exc.diagnostic
                self.cleanup_failed = (
                    self.cleanup_failed or exc.diagnostic["reason"] == "CLEANUP_FAILURE"
                )
                raise
            self.last_deadline = diagnostic
            value["state"] = ObservationState(value["state"])
            if value.get("result_kind"):
                value["result_kind"] = DraftResultKind(value["result_kind"])
            return replace(ProviderObservation(**value), local_cleanup=diagnostic)
        self._measurement = None
        result = self._dispatch_observation(
            invocation_id=invocation_id,
            request=request,
            credential=credential,
            profile=profile,
        )
        m = self._measurement
        return replace(
            result,
            measurement=m,
            input_tokens=m["usage"]["input_tokens"] if m and m["settleable"] else None,
            output_tokens=m["usage"]["output_tokens"]
            if m and m["settleable"]
            else None,
        )

    def _dispatch_observation(self, *, invocation_id, request, credential, profile):
        policy = policy_for(profile.adapter_revision, profile.output_schema_version)
        status_code, body, correlation, latency_ms = self.exchange(
            invocation_id=invocation_id, request=request, credential=credential
        )
        from .planning_measurement import measurement

        try:
            metered_response = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            metered_response = {}
        self._measurement = measurement(
            metered_response, correlation, invocation_id, latency_ms, self.configuration
        )
        if len(body) > self.configuration.maximum_response_bytes:
            return self._failure(
                invocation_id,
                correlation,
                "PROVIDER_RESPONSE_TOO_LARGE",
                latency_ms=latency_ms,
            )
        if not 200 <= status_code < 300:
            if status_code == 429:
                reason = "PROVIDER_RATE_LIMITED"
            elif status_code >= 500:
                reason = "PROVIDER_UNAVAILABLE"
            else:
                reason = "PROVIDER_HTTP_REJECTED"
            return self._failure(
                invocation_id, correlation, reason, latency_ms=latency_ms
            )
        try:
            document = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._failure(
                invocation_id,
                correlation,
                "PROVIDER_RESPONSE_INVALID",
                latency_ms=latency_ms,
            )
        if not isinstance(document, dict):
            return self._failure(
                invocation_id,
                correlation,
                "PROVIDER_RESPONSE_INVALID",
                latency_ms=latency_ms,
            )
        usage = document.get("usage")
        input_tokens = output_tokens = None
        if isinstance(usage, dict):
            measured_input = usage.get("input_tokens")
            measured_output = usage.get("output_tokens")
            if (
                isinstance(measured_input, int)
                and not isinstance(measured_input, bool)
                and measured_input > 0
            ):
                input_tokens = measured_input
            if (
                isinstance(measured_output, int)
                and not isinstance(measured_output, bool)
                and measured_output >= 0
            ):
                output_tokens = measured_output
        status = document.get("status")
        if document.get("model") != self.configuration.native_model_id:
            return self._failure(
                invocation_id,
                correlation,
                "MODEL_BINDING_MISMATCH",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )
        if status == "incomplete":
            details = document.get("incomplete_details")
            reason = (
                "PROVIDER_OUTPUT_TRUNCATED"
                if isinstance(details, dict)
                and details.get("reason") == "max_output_tokens"
                else "PROVIDER_RESPONSE_INCOMPLETE"
            )
            return self._failure(
                invocation_id,
                correlation,
                reason,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )
        if status in {"queued", "in_progress"}:
            return ProviderObservation(
                self._observation_id(invocation_id, correlation, str(status)),
                ObservationState.UNKNOWN,
                correlation=correlation,
                reason_code="PROVIDER_FOREGROUND_NONTERMINAL",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )
        if status != "completed":
            return self._failure(
                invocation_id,
                correlation,
                "PROVIDER_RESPONSE_FAILED",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )
        output = document.get("output")
        if not isinstance(output, list):
            return self._failure(
                invocation_id,
                correlation,
                "PROVIDER_RESPONSE_INVALID",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )
        texts: list[str] = []
        refused = False
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "refusal":
                    refused = True
                elif part.get("type") == "output_text" and isinstance(
                    part.get("text"), str
                ):
                    texts.append(part["text"])
        if refused:
            return self._failure(
                invocation_id,
                correlation,
                "PROVIDER_REFUSAL",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )
        if len(texts) != 1:
            return self._failure(
                invocation_id,
                correlation,
                "PROVIDER_RESPONSE_INVALID",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )
        try:
            result = json.loads(texts[0])
        except json.JSONDecodeError:
            from .output_validation_diagnostic import record_failure

            record_failure(self._measurement, "JSON_PARSE")
            return self._failure(
                invocation_id,
                correlation,
                "OUTPUT_SCHEMA_INVALID",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )
        validation_stage = "REQUEST_REFERENCES"
        try:
            refs = frozenset()
            if policy.revision in {
                "v2",
                "v2-zh-CN",
                "v3",
                "v3-execution",
                "v3-relation",
                "v3-relation-adoption",
                "v3-relation-adoption-source",
            }:
                sent = json.loads(request.payload)
                refs = (
                    conversation_context_references
                    if policy.revision
                    in {
                        "v3",
                        "v3-execution",
                        "v3-relation",
                        "v3-relation-adoption",
                        "v3-relation-adoption-source",
                    }
                    else context_references
                )(sent["input"][0]["content"][0]["text"])
            if policy.revision in {
                "v3-relation-adoption",
                "v3-relation-adoption-source",
            }:
                from .understanding_adoption_policy import server_references

                refs |= server_references(request.payload)
            validation_stage = "LOCAL_RESULT"
            understanding = validate_result(result, policy, refs)
            validation_stage = "ROUTE_BINDING"
            route = None
            if policy.revision == "v3-relation":
                from .conversation_relation_context import validated_route

                route = validated_route(result, request.payload)
            elif policy.revision in {
                "v3-relation-adoption",
                "v3-relation-adoption-source",
            }:
                from .understanding_adoption_policy import route as adoption_route

                route = adoption_route(result, request.payload)
        except (PolicyValidationError, ValueError, KeyError, TypeError) as exc:
            from .output_validation_diagnostic import record_failure

            record_failure(self._measurement, validation_stage, exc)
            return self._failure(
                invocation_id,
                correlation,
                "OUTPUT_SCHEMA_INVALID",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )
        kind = result["kind"]
        question = result["clarificationQuestion"]
        title = result["title"]
        description = result["description"]
        if kind == "CURRENT_QUESTION_ANSWER" and policy.revision in {
            "v3-relation",
            "v3-relation-adoption",
            "v3-relation-adoption-source",
        }:
            return ProviderObservation(
                self._observation_id(invocation_id, correlation, kind),
                ObservationState.SUCCEEDED,
                correlation=correlation,
                result_kind=DraftResultKind.CURRENT_QUESTION_ANSWER,
                conversation_route=route,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        if kind in {"DIRECT_ANSWER", "NEEDS_DATA"} and policy.revision in {
            "v3",
            "v3-execution",
            "v3-relation",
            "v3-relation-adoption",
            "v3-relation-adoption-source",
        }:
            return ProviderObservation(
                self._observation_id(invocation_id, correlation, kind),
                ObservationState.SUCCEEDED,
                correlation=correlation,
                result_kind=DraftResultKind(kind),
                conversation_route=route,
                answer=result["answer"],
                data_needs=result["dataNeeds"],
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        if kind == "NEEDS_CLARIFICATION":
            if (
                not isinstance(question, str)
                or not question.strip()
                or any(value is not None for value in (title, description))
            ):
                reason = "OUTPUT_SCHEMA_INVALID"
            else:
                return ProviderObservation(
                    self._observation_id(invocation_id, correlation, kind),
                    ObservationState.SUCCEEDED,
                    correlation=correlation,
                    conversation_route=route,
                    understanding=understanding,
                    result_kind=DraftResultKind.NEEDS_CLARIFICATION,
                    clarification_question=question,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
        elif kind == "DRAFT_READY":
            if (
                question is not None
                or not isinstance(title, str)
                or not title.strip()
                or not isinstance(description, str)
                or not description.strip()
            ):
                reason = "OUTPUT_SCHEMA_INVALID"
            else:
                return ProviderObservation(
                    self._observation_id(invocation_id, correlation, kind),
                    ObservationState.SUCCEEDED,
                    correlation=correlation,
                    conversation_route=route,
                    understanding=understanding,
                    result_kind=DraftResultKind.DRAFT_READY,
                    title=title,
                    description=description,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
        else:
            reason = "OUTPUT_SCHEMA_INVALID"
        from .output_validation_diagnostic import record_failure

        record_failure(self._measurement, "FINAL_RESULT")
        return self._failure(
            invocation_id,
            correlation,
            reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )

    def observe(self, correlation: str) -> ProviderObservation:
        return ProviderObservation(
            self._observation_id("foreground", correlation, "observe-unsupported"),
            ObservationState.UNKNOWN,
            correlation=correlation,
            reason_code="PROVIDER_OBSERVATION_UNSUPPORTED_FOREGROUND",
        )

    def cancel(self, correlation: str) -> ProviderObservation:
        return ProviderObservation(
            self._observation_id("foreground", correlation, "cancel-unsupported"),
            ObservationState.UNKNOWN,
            correlation=correlation,
            reason_code="PROVIDER_CANCELLATION_UNSUPPORTED_FOREGROUND",
        )
