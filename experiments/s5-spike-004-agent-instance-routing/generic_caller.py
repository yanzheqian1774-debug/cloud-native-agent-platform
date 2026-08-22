"""Logical caller for Checkpoint B."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LogicalAgentRequest:
    execution_id: str
    definition_id: str
    payload: str
    instance_id: str | None = None


@dataclass(frozen=True)
class LogicalAgentOutcome:
    execution_id: str
    instance_id: str
    output: str


class LogicalAgentEndpoint(Protocol):
    def invoke(self, request: LogicalAgentRequest) -> LogicalAgentOutcome: ...


class GenericCaller:
    def __init__(self, endpoint: LogicalAgentEndpoint) -> None:
        self._endpoint = endpoint

    def invoke(self, request: LogicalAgentRequest) -> LogicalAgentOutcome:
        return self._endpoint.invoke(request)
