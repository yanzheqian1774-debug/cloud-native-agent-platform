"""Expose the authorized frontend-local S5-IMPL-011 tests to root pytest."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = (REPOSITORY / "console" / "frontend").resolve()
SOURCE = (FRONTEND_ROOT / "tests" / "test_s5_impl_011_technical_view.py").resolve()

if FRONTEND_ROOT.parent != (REPOSITORY / "console").resolve():
    raise RuntimeError("S5_IMPL_011_FRONTEND_ROOT_INVALID")
if SOURCE.parent != FRONTEND_ROOT / "tests" or not SOURCE.is_file():
    raise RuntimeError("S5_IMPL_011_TEST_MODULE_UNAVAILABLE")

SPEC = importlib.util.spec_from_file_location("s5_impl_011_frontend_tests", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("S5_IMPL_011_TEST_MODULE_UNLOADABLE")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

for name in dir(MODULE):
    if name.startswith("test_"):
        globals()[name] = getattr(MODULE, name)
