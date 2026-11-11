"""Runtime owner digests retain exact content checks across owner serialization."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from agent_console.business_capability import (
    BindingKind,
    BusinessCapabilityError,
    CapabilityBinding,
    FixedReference,
)
from agent_console.workbench_business_capability import CapabilityReferences
from agent_console.workbench_owner_authorization import AuthorizedOwnerCall
from test_business_capability import capability


@pytest.mark.parametrize(
    "actual,valid",
    [
        ("a" * 64, True),
        ("sha256:" + "a" * 64, True),
        ("sha256:" + "b" * 64, False),
        ("sha512:" + "a" * 64, False),
    ],
)
def test_runtime_owner_digest_is_checked_without_changing_fixed_reference(
    actual, valid
):
    original = capability()
    revision = replace(
        original,
        bindings=(
            original.bindings[0],
            CapabilityBinding(
                BindingKind.RUNTIME_PROFILE,
                FixedReference("runtime:fixed", "runtime-revision:old", "a" * 64),
                "执行隔离",
            ),
        ),
    )
    employees = Mock()
    employees.read_revision_for_workbench.return_value = {
        "revision": {"role": "核对助手"},
        "digest": "a" * 64,
    }
    reader = CapabilityReferences(employees, {"runtime": object()})
    reader.resources = Mock(
        return_value={
            "name": "固定环境",
            "revision": {"digest": actual, "state": "PUBLISHED"},
        }
    )
    authority = Mock()
    context = SimpleNamespace(
        principal_id="human:tester",
        scope=SimpleNamespace(
            tenant_id=revision.scope.namespace,
            security_domain=revision.scope.security_domain,
        ),
    )
    call = AuthorizedOwnerCall(
        "READ_CAPABILITY_REVISION", context, None, {}, {}, {}, (), authority
    )
    if valid:
        members = reader.validate(call, revision)
        assert members[-1]["digest"] == "a" * 64
        assert members[-1]["revisionId"] == "runtime-revision:old"
    else:
        with pytest.raises(
            BusinessCapabilityError, match="CAPABILITY_MEMBER_VERSION_MISMATCH"
        ):
            reader.validate(call, revision)
    assert authority.require.call_args.args[1:] == (
        "RUNTIME_PROFILE",
        "READ_RESOURCE",
        "runtime-profile:prepared-resource:runtime:fixed:runtime-revision:old",
    )
    assert reader.resources.call_args.args[0].path == {
        "kind": "runtime",
        "identity": "runtime:fixed",
        "revision": "runtime-revision:old",
    }
