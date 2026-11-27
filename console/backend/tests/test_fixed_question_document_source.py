"""Formal service document7 Plan/START source binding, not live publication."""

# ruff: noqa: F401,F811 -- Original random owner fixture imports.
import pytest
from fixed_question_document_support import automation, case, repository, services
from test_fixed_work_bound_composition_postgres import (
    test_bound_original_plan_to_start_composition as chain,
)


@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
def test_service_document7_source_reaches_original_start(
    automation, monkeypatch, tmp_path
):
    chain(automation, monkeypatch, tmp_path, "START_COMMITTED")
