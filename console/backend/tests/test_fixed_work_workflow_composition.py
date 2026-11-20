"""Combined route/default-off contracts; real owner behavior lives in PG tests."""

from types import SimpleNamespace

import pytest
import test_workbench_bootstrap as b
from agent_console.workbench_fixed_work_source import source_operations
from agent_console.workbench_workflow import workflow_operations
from agent_console.workbench_workflow_policy import policy_publication_operations

base = b.test_composition_registers_business_and_read_only_workflow_operations


@pytest.mark.parametrize(
    "source,workflow", [(False, False), (True, False), (False, True), (True, True)]
)
def test_combined_route_registrations_keep_human_and_no_collisions(source, workflow):
    service = SimpleNamespace()
    human = workflow_operations(service)
    operations = (
        *human,
        *source_operations(object(), enabled=source),
        *policy_publication_operations(service, {}, enabled=workflow),
    )
    keys = [(op.method, op.path) for op in operations]
    assert len(keys) == len(set(keys))
    assert tuple(operations[: len(human)]) == human
    assert len(operations) == len(human) + (3 if source else 0) + (2 if workflow else 0)


@pytest.mark.parametrize(
    "source,workflow", [(False, False), (True, False), (False, True), (True, True)]
)
def test_bootstrap_optional_owners_do_not_silently_enable_or_degrade(
    tmp_path, monkeypatch, source, workflow
):
    monkeypatch.setenv("FIXED_WORK_SOURCE_ENABLED", str(source).lower())
    monkeypatch.setenv("WORKFLOW_POLICY_PUBLICATION_ENABLED", str(workflow).lower())
    if source:
        # Real bootstrap cannot silently ignore a requested source feature without
        # its authoring/owned-conversation dependencies. No DB or migration is run.
        with pytest.raises(ValueError, match="FIXED_WORK_SOURCE_OWNERS_REQUIRED"):
            base(tmp_path, monkeypatch)
    else:
        # With optional resource services absent, old Human routes stay identical;
        # publication flag alone does not create a permission or a usable writer.
        base(tmp_path, monkeypatch)
