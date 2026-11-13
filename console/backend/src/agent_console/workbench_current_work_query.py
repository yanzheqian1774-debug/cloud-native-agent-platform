"""Bounded query and principal-bound cursors for the F3 task directory.

This module conveys no read authority. The owner adapter must authorize every
page and construct both counts and rows from the same authorized snapshot.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import TrustedRequestContext
from .resource_use_domain import canonical_digest
from .workbench_pagination import WorkbenchCursorCodec


class CurrentWorkQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scopeFilter: Literal["visible", "initiated"] | None = None
    query: str = Field(default="", max_length=200)
    state: Literal["all", "waiting", "completed", "answered"] = "all"
    sourceFilter: Literal["all", "conversation"] = "all"
    pageSize: int = Field(default=25, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)

    def resolved(self, *, verified_development_administrator: bool):
        if self.scopeFilter is not None:
            return self
        return self.model_copy(
            update={
                "scopeFilter": "visible"
                if verified_development_administrator
                else "initiated"
            }
        )

    def cursor_route(
        self,
        context: TrustedRequestContext,
        *,
        generation: int,
        recovery_epoch: int,
    ) -> str:
        if self.scopeFilter is None:
            raise ValueError("CURRENT_WORK_SCOPE_UNRESOLVED")
        return "current-work:attribution-v2:" + canonical_digest(
            [
                context.principal_id,
                generation,
                recovery_epoch,
                self.scopeFilter,
                self.query,
                self.state,
                *([self.sourceFilter] if self.sourceFilter != "all" else []),
            ]
        )

    def after(
        self,
        codec: WorkbenchCursorCodec,
        context: TrustedRequestContext,
        *,
        generation: int,
        recovery_epoch: int,
    ) -> tuple[str, ...] | None:
        route = self.cursor_route(
            context, generation=generation, recovery_epoch=recovery_epoch
        )
        if self.cursor is None:
            return None
        return codec.resolve(
            self.cursor,
            route=route,
            context=context,
            page_size=self.pageSize,
            key_size=2,
        )

    def next_cursor(
        self,
        codec: WorkbenchCursorCodec,
        context: TrustedRequestContext,
        *,
        generation: int,
        recovery_epoch: int,
        created_at: str,
        workflow_run_id: str,
    ) -> str:
        return codec.mint(
            route=self.cursor_route(
                context, generation=generation, recovery_epoch=recovery_epoch
            ),
            context=context,
            page_size=self.pageSize,
            last_key=(created_at, workflow_run_id),
        )
