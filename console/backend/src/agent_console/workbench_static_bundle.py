"""Pin local acceptance assets so validation builds cannot alter a running UI."""

import hashlib
import json
import shutil
from pathlib import Path


def pin_frontend(source: Path, destination: Path, *, assistance_required: bool):
    profile = json.loads((source / "workbench-build-profile.json").read_text())
    if profile.get("schemaVersion") != "workbench-build-profile.v1" or (
        assistance_required
        and (
            profile.get("draftAssistance") is not True
            or profile.get("trustedWorkbenchRoutes") is not True
        )
    ):
        raise ValueError("WORKBENCH_FRONTEND_MODE_MISMATCH")
    if not (source / "index.html").is_file():
        raise ValueError("WORKBENCH_FRONTEND_INDEX_MISSING")

    def digest(directory):
        value = hashlib.sha256()
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise ValueError("WORKBENCH_FRONTEND_SYMLINK_FORBIDDEN")
            if path.is_file():
                name = path.relative_to(directory).as_posix().encode()
                data = path.read_bytes()
                value.update(len(name).to_bytes(8) + name)
                value.update(len(data).to_bytes(8) + data)
        return value.hexdigest()

    expected = digest(source)
    pinned = destination / expected
    if not pinned.exists():
        shutil.copytree(source, pinned)
    if digest(pinned) != expected:
        raise ValueError("WORKBENCH_FRONTEND_BUNDLE_MISMATCH")
    return pinned
