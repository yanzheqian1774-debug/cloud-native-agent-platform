"""REST-specific translation behind the experimental provider boundary."""

from collections.abc import Callable
from uuid import uuid4

import httpx
from capability_contract import (
    CapabilityRequest,
    CapabilityResult,
    CapabilitySubmission,
    ErrorClass,
    InvocationHandle,
    ResultStatus,
)


class RestTodoProvider:
    provider_ref = "provider/rest/jsonplaceholder-todo"

    def __init__(self, get: Callable[..., httpx.Response] = httpx.get) -> None:
        self._get = get
        self._results: dict[str, CapabilityResult] = {}
        self.native_evidence: dict[str, str] = {}
        self.start_count = 0

    def _failure(
        self, request: CapabilityRequest, native_id: str, error: ErrorClass
    ) -> CapabilityResult:
        diagnostic_ref = f"native-evidence://{self.provider_ref}/{native_id}"
        return CapabilityResult(
            status=ResultStatus.FAILED,
            invocation_id=request.execution.invocation_id,
            correlation_id=request.execution.correlation_id,
            error_class=error,
            message="capability provider failed",
            diagnostic_ref=diagnostic_ref,
        )

    def submit(self, request: CapabilityRequest) -> CapabilitySubmission:
        self.start_count += 1
        native_id = str(uuid4())
        handle = InvocationHandle(self.provider_ref, native_id)
        try:
            response = self._get(
                f"https://jsonplaceholder.typicode.com/todos/{request.input['todo_id']}",
                timeout=10.0,
            )
            if response.status_code >= 500:
                self.native_evidence[native_id] = (
                    f"remote-status:{response.status_code}"
                )
                result = self._failure(
                    request, native_id, ErrorClass.PROVIDER_UNAVAILABLE
                )
            elif response.status_code >= 400:
                self.native_evidence[native_id] = (
                    f"remote-status:{response.status_code}"
                )
                result = self._failure(
                    request, native_id, ErrorClass.REMOTE_EXECUTION_FAILURE
                )
            else:
                native = response.json()
                result = CapabilityResult(
                    status=ResultStatus.SUCCEEDED,
                    invocation_id=request.execution.invocation_id,
                    correlation_id=request.execution.correlation_id,
                    output={
                        "item_id": native["id"],
                        "summary": native["title"],
                        "completed": native["completed"],
                    },
                )
        except KeyError:
            self.native_evidence[native_id] = "missing-required-provider-input"
            result = self._failure(request, native_id, ErrorClass.INPUT_INVALID)
        except httpx.TimeoutException as exc:
            self.native_evidence[native_id] = type(exc).__name__
            result = self._failure(request, native_id, ErrorClass.TIMEOUT)
        except httpx.TransportError as exc:
            self.native_evidence[native_id] = type(exc).__name__
            result = self._failure(request, native_id, ErrorClass.PROVIDER_UNAVAILABLE)
        except (TypeError, ValueError) as exc:
            self.native_evidence[native_id] = type(exc).__name__
            result = self._failure(request, native_id, ErrorClass.UNKNOWN)
        self._results[native_id] = result
        return CapabilitySubmission(request.execution, handle, result)

    def observe(self, handle: InvocationHandle) -> CapabilityResult:
        return self._results.pop(handle.native_id)
