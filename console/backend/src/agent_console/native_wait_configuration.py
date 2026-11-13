"""Explicit immutable successor configuration; no old executor/runtime upgrade."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .native_document_skill import NativeDurableDocumentSkillExecutor


class DurableWaitConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    schemaVersion: Literal["native-durable-wait.v1"]
    enabled: Literal[True]
    executorId: str
    executorRevision: str
    executorConfigurationDigest: str
    nativeRuntimePolicyDigest: str = Field(pattern="^[0-9a-f]{64}$")
    maximumHumanWaitSeconds: int = Field(ge=181, le=86400)

    @model_validator(mode="after")
    def exact_successor(self):
        expected = NativeDurableDocumentSkillExecutor.revision
        if (
            self.executorId,
            self.executorRevision,
            self.executorConfigurationDigest,
        ) != (
            expected.executor_id,
            expected.executor_revision,
            expected.configuration_digest,
        ):
            raise ValueError("NATIVE_WAIT_EXECUTOR_BINDING_REQUIRED")
        return self

    @classmethod
    def load(cls, path, runtime_policy_digest):
        document = json.loads(Path(path).read_text())
        model = (
            TypedQuestionWaitConfiguration
            if cls is DurableWaitConfiguration
            and document.get("schemaVersion") == "native-durable-wait.v2"
            else cls
        )
        value = model.model_validate(document)
        if value.nativeRuntimePolicyDigest != runtime_policy_digest:
            raise ValueError("NATIVE_WAIT_RUNTIME_BINDING_CHANGED")
        return value


class TypedQuestionWaitConfiguration(DurableWaitConfiguration):
    """Explicit v7-only successor; v1 fields and executor binding stay frozen."""

    schemaVersion: Literal["native-durable-wait.v2"]
    typedQuestions: Literal[True]

    @model_validator(mode="after")
    def exact_successor(self):
        from .native_typed_document_skill import (
            NativeTypedQuestionDocumentSkillExecutor,
        )

        expected = NativeTypedQuestionDocumentSkillExecutor.revision
        if (
            self.executorId,
            self.executorRevision,
            self.executorConfigurationDigest,
        ) != (
            expected.executor_id,
            expected.executor_revision,
            expected.configuration_digest,
        ):
            raise ValueError("NATIVE_TYPED_QUESTION_EXECUTOR_BINDING_REQUIRED")
        return self
