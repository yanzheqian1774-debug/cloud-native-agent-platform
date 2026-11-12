"""Editable business-facing draft fields; executable source identity is fixed."""

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolDraftContent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(min_length=1, max_length=160, strict=True)
    purpose: str = Field(default="", max_length=4000, strict=True)
    inputSchema: dict | None = None
    outputSchema: dict | None = None
    sideEffect: Literal[
        "UNCONFIRMED", "read-only", "creates-file", "external-write"
    ] = "UNCONFIRMED"

    @model_validator(mode="after")
    def bounded_content(self):
        if not self.name.strip():
            raise ValueError("TOOL_NAME_REQUIRED")
        try:
            encoded = json.dumps(
                self.model_dump(), ensure_ascii=False, allow_nan=False
            ).encode()
        except (ValueError, RecursionError) as exc:
            raise ValueError("TOOL_CONTENT_INVALID") from exc
        if len(encoded) > 100000:
            raise ValueError("TOOL_CONTENT_SIZE_LIMIT")
        return self
