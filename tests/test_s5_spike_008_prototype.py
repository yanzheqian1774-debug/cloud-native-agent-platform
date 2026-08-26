"""Expose isolated S5-SPIKE-008 tests to unchanged repository CI discovery."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
PROTOTYPE_ROOT = (
    REPOSITORY / "experiments" / "s5-spike-008-authoring-view-mock-prototype"
).resolve()
SOURCE = (PROTOTYPE_ROOT / "tests" / "test_prototype.py").resolve()

if PROTOTYPE_ROOT.parent != (REPOSITORY / "experiments").resolve():
    raise RuntimeError("S5_SPIKE_008_PROTOTYPE_ROOT_INVALID")
if SOURCE.parent != PROTOTYPE_ROOT / "tests" or not SOURCE.is_file():
    raise RuntimeError("S5_SPIKE_008_TEST_MODULE_UNAVAILABLE")

SPEC = importlib.util.spec_from_file_location("s5_spike_008_tests", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("S5_SPIKE_008_TEST_MODULE_UNLOADABLE")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

for name in dir(MODULE):
    if name.startswith("test_"):
        globals()[name] = getattr(MODULE, name)
