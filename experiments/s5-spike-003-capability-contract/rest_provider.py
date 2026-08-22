"""REST-specific translation behind the experimental provider boundary."""

from collections.abc import Callable
from uuid import uuid4

import httpx
from capability_contract import (
    CapabilityRequest,
    CapabilityResult,
    InvocationHandle,
    ResultStatus,
)


class RestTodoProvider:
    provider_ref = "provider/rest/jsonplaceholder-todo"

    def __init__(self, get: Callable[..., httpx.Response] = httpx.get) -> None:
        self._get = get
        self._results: dict[str, CapabilityResult] = {}
        self.start_count = 0

    def start(self, request: CapabilityRequest) -> InvocationHandle:
        self.start_count += 1
        native_id = str(uuid4())
        try:
            response = self._get(
                f"https://jsonplaceholder.typicode.com/todos/{request.input['todo_id']}",
                timeout=10.0,
            )
            response.raise_for_status()
            native = response.json()
            result = CapabilityResult(
                status=ResultStatus.SUCCEEDED,
                correlation_id=request.correlation_id,
                output={
                    "item_id": native["id"],
                    "summary": native["title"],
                    "completed": native["completed"],
                },
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            result = CapabilityResult(
                status=ResultStatus.FAILED,
                correlation_id=request.correlation_id,
                error_code="provider_failure",
                message=type(exc).__name__,
            )
        self._results[native_id] = result
        return InvocationHandle(self.provider_ref, native_id)

    def result(self, handle: InvocationHandle) -> CapabilityResult:
        return self._results.pop(handle.native_id)
