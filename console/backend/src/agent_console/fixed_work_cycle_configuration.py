"""Private, pinned configuration for a separate bounded cycle process."""

import hashlib
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FilePin(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: Path
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    def verify(self):
        p = self.path
        if not p.is_absolute() or p.is_symlink() or not p.is_file():
            raise ValueError("FIXED_CYCLE_FILE_INVALID")
        if p.stat().st_uid != os.getuid() or p.stat().st_mode & 0o077:
            raise ValueError("FIXED_CYCLE_PRIVATE_FILE_REQUIRED")
        if hashlib.sha256(p.read_bytes()).hexdigest() != self.sha256:
            raise ValueError("FIXED_CYCLE_FILE_CHANGED")
        return p


def source_files(root):
    result = {}
    for folder in (
        "core/src",
        "runtime/src",
        "operator/src",
        "console/backend/src",
        "console/backend/migrations",
    ):
        for p in (root / folder).rglob("*"):
            if p.suffix in {".py", ".sql"}:
                if p.is_symlink():
                    raise ValueError("FIXED_CYCLE_SOURCE_SYMLINK")
                result[p.relative_to(root).as_posix()] = hashlib.sha256(
                    p.read_bytes()
                ).hexdigest()
    return result


class CycleConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["fixed-work-cycle-process.v1"]
    enabled: bool = Field(default=False, strict=True)
    sourceRoot: Path
    sourceFiles: dict[str, str]
    authorityRuntime: FilePin
    planningRuntime: FilePin
    servicePolicy: FilePin
    resourcePolicy: FilePin
    readonlyPolicy: FilePin
    serviceCredential: FilePin
    budgetExtension: FilePin | None = None
    serviceBudget: FilePin | None = None
    pollSeconds: int = Field(default=30, strict=True, ge=5, le=300)
    policyPlanApprovalEnabled: bool = Field(default=False, strict=True)

    @classmethod
    def load(cls, path):
        p = Path(path)
        if not p.is_absolute() or p.is_symlink() or p.stat().st_mode & 0o077:
            raise ValueError("FIXED_CYCLE_PRIVATE_FILE_REQUIRED")
        if p.stat().st_uid != os.getuid():
            raise ValueError("FIXED_CYCLE_PRIVATE_FILE_REQUIRED")
        return cls.model_validate_json(p.read_text())

    def verify(self):
        actual = Path(__file__).resolve().parents[4]
        if (
            self.sourceRoot != actual
            or not self.sourceFiles
            or source_files(actual) != self.sourceFiles
        ):
            raise ValueError("FIXED_CYCLE_SOURCE_CHANGED")
        for name in (
            "authorityRuntime",
            "planningRuntime",
            "servicePolicy",
            "resourcePolicy",
            "readonlyPolicy",
            "serviceCredential",
        ):
            getattr(self, name).verify()
        if self.serviceBudget is not None:
            self.serviceBudget.verify()
        ambient = os.environ.get("PROVIDER_BUDGET_EXTENSION_POLICY")
        if ambient and (
            self.budgetExtension is None or Path(ambient) != self.budgetExtension.path
        ):
            raise ValueError("FIXED_CYCLE_BUDGET_EXTENSION_UNPINNED")
        if self.budgetExtension is not None:
            self.budgetExtension.verify()
