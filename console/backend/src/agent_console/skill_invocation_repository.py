"""Repository port for the PostgreSQL-owned Skill invocation authority."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from .execution_domain import ScopeIdentity
from .skill_invocation_domain import (
    InvocationState,
    SkillInvocationRequest,
    SkillInvocationSnapshot,
)


class SkillInvocationRepository(Protocol):
    def prepare_dispatch(
        self,
        request: SkillInvocationRequest,
        inputs: dict[str, Any],
        *,
        payload_digest: str,
        now: datetime,
    ) -> tuple[SkillInvocationSnapshot, bool]: ...

    def commit_terminal(
        self,
        request: SkillInvocationRequest,
        *,
        state: InvocationState,
        output: dict[str, Any] | None,
        provider_observation_id: str,
        error_code: str | None,
        started_at: datetime,
        observed_at: datetime,
    ) -> SkillInvocationSnapshot: ...

    def get_snapshot(
        self, scope: ScopeIdentity, invocation_id: str
    ) -> SkillInvocationSnapshot | None: ...
