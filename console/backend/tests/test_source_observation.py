"""Read-only scope projection is not an execution binding or missing-tool oracle."""

import json
from types import SimpleNamespace as NS

import pytest
from agent_console import conversation_sources as source_module
from agent_console import question_member_capabilities as members
from agent_console.authority_contracts import AuthorityError
from agent_console.conversation_capability import describe
from agent_console.owned_business_policy import OwnedBusinessPolicy
from agent_console.owned_business_resource_adapter import OwnedResourceWork
from test_owned_business_policy import document


@pytest.fixture
def observation(monkeypatch):
    scope = OwnedBusinessPolicy.model_validate(document()).scopes[0]
    refs = {
        "EMPLOYEE": scope.employees[0],
        "AGENT": scope.agents[0],
        "SKILL": scope.skills[0],
        "RUNTIME": scope.runtimes[0],
        "KNOWLEDGE": scope.source,
    }
    contents = {kind: {} for kind in refs}
    contents["EMPLOYEE"] = {
        "members": [
            {"kind": "RUNTIME_PROFILE" if k == "RUNTIME" else k, **r.model_dump()}
            for k, r in refs.items()
            if k != "EMPLOYEE"
        ]
    }
    contents["SKILL"] = {
        "operations": [
            {"name": n} for n in ["READ_DATA", "ANALYZE_DATA", "RENDER_REPORT"]
        ]
    }
    # Exact scope grants these operations, but does not prove USE/START.
    scope = scope.model_copy(
        update={"operations": ("READ_DATA", "ANALYZE_DATA", "RENDER_REPORT")}
    )
    calls = []
    monkeypatch.setattr(
        members,
        "identities",
        lambda *a, **k: pytest.fail("must not scan latest employee directory"),
    )

    def read(c, s, kind, ref):
        assert ref == refs[kind]
        calls.append(kind)
        return contents[kind], "published"

    monkeypatch.setattr(members, "read_published", read)
    monkeypatch.setattr(members, "require_read", lambda *args: None)
    monkeypatch.setattr(members, "validate", lambda *args, **kwargs: None)
    call = NS(
        connection=object(),
        context=NS(
            scope=NS(tenant_id="t", security_domain="d"), principal_id="human:ordinary"
        ),
        authority=object(),
    )
    automation = NS(services=True, sales_v2_candidate=False)
    work = source_module.ReadableSourceValidation((scope.sourceContentDigest,))
    return NS(
        scope=scope,
        refs=refs,
        contents=contents,
        calls=calls,
        call=call,
        automation=automation,
        work=work,
    )


def read(e):
    assert not isinstance(e.work, OwnedResourceWork)
    return members.observe(
        e.automation,
        e.call,
        e.scope.source,
        "document-review-source.v1",
        e.work,
        observation_scope=e.scope,
    )


def test_exact_scope_observes_only_pinned_members_without_execution_authority(
    observation,
):
    result = read(observation)
    assert result["state"] == "AUTHORIZED_MEMBER_DECLARATIONS_OBSERVED"
    assert len(result["operations"]) == 3
    assert result["executionReady"] is False
    assert set(observation.calls) == set(observation.refs)


@pytest.mark.parametrize("kind", ["EMPLOYEE", "SKILL", "AGENT"])
def test_read_failure_is_not_confirmed_missing_tools(observation, monkeypatch, kind):
    def denied(authority, principal, actual, ref):
        if actual == kind:
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    monkeypatch.setattr(members, "require_read", denied)
    result = read(observation)
    assert result["state"] == "READ_UNAVAILABLE"
    assessment = describe({"schemaVersion": "document-review-source.v1"}, result)[
        "assessment"
    ]
    assert assessment["state"] == "READ_UNAVAILABLE"
    assert assessment["missingOperations"] == []
    assert observation.refs[kind].resource_id not in str(assessment)


def test_invalid_metadata_is_unverified_but_readable_absent_operation_is_missing(
    observation, monkeypatch
):
    from agent_console.native_document_resource_bundle import resource_content
    from agent_console.resource_automation_validation import validate
    from test_native_document_tools import SOURCE

    monkeypatch.setattr(
        members,
        "validate",
        lambda *a, **kw: (_ for _ in ()).throw(ValueError("invalid")),
    )
    assert read(observation)["state"] == "UNVERIFIED"

    def validate_skill(kind, content, work, **kwargs):
        if kind == "skill":
            return validate(kind, content, work, **kwargs)

    monkeypatch.setattr(members, "validate", validate_skill)
    skill = resource_content(SOURCE)["skill"]
    skill["operations"] = [
        op for op in skill["operations"] if op["name"] == "READ_DATA"
    ]
    observation.contents["SKILL"] = skill
    result = read(observation)
    assert result["state"] == "AUTHORIZED_MEMBER_DECLARATIONS_OBSERVED"
    assert [op["operation"] for op in result["operations"]] == ["READ_DATA"]
    assert (
        describe({"schemaVersion": "document-review-source.v1"}, result)["assessment"][
            "state"
        ]
        == "MISSING_TOOLS"
    )


def test_real_contract_error_is_not_a_read_denial(observation, monkeypatch):
    from agent_console.resource_automation_validation import validate

    reasons = []

    def validate_runtime(kind, content, work, **kwargs):
        if kind == "runtime":
            try:
                return validate(kind, content, work, **kwargs)
            except AuthorityError as exc:
                reasons.append(exc.reason_code)
                raise

    monkeypatch.setattr(members, "validate", validate_runtime)
    observation.contents["RUNTIME"] = {"provider": "UNSUPPORTED"}
    result = read(observation)
    assert reasons == ["RESOURCE_RUNTIME_PROVIDER_UNSUPPORTED"]
    assert result["state"] == "UNVERIFIED"
    assert set(observation.calls) == set(observation.refs)
    assessment = describe({"schemaVersion": "document-review-source.v1"}, result)[
        "assessment"
    ]
    assert assessment["state"] == "UNVERIFIED"
    assert assessment["missingOperations"] == []


@pytest.mark.parametrize("complete", [False, True])
@pytest.mark.parametrize("failure", ["read", "contract"])
def test_legacy_partial_observation_remains_uncertain(
    observation, monkeypatch, complete, failure
):
    e = observation
    employee = e.refs["EMPLOYEE"]
    hidden = employee.model_copy(update={"resource_id": "hidden-employee"})
    monkeypatch.setattr(
        members,
        "identities",
        lambda *a, **kw: [
            {"identity": r.resource_id, "revision": r.revision_id, "digest": r.digest}
            for r in (employee, hidden)
        ],
    )
    original_read = members.read_published

    def require(authority, principal, kind, ref):
        if failure == "read" and ref == hidden:
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    def published(c, scope, kind, ref):
        if failure == "contract" and ref == hidden:
            raise ValueError("invalid published metadata")
        return original_read(c, scope, kind, ref)

    monkeypatch.setattr(members, "require_read", require)
    monkeypatch.setattr(members, "read_published", published)
    if not complete:
        e.contents["SKILL"]["operations"] = [{"name": "READ_DATA"}]
    result = members.observe(
        e.automation, e.call, e.scope.source, "document-review-source.v1", e.work
    )
    assessment = describe({"schemaVersion": "document-review-source.v1"}, result)[
        "assessment"
    ]
    expected = (
        "BOUNDED_ANALYSIS_AVAILABLE"
        if complete
        else "READ_UNAVAILABLE"
        if failure == "read"
        else "UNVERIFIED"
    )
    assert assessment["state"] == expected
    assert assessment["missingOperations"] == []
    assert "hidden-employee" not in str(result)


def test_catalogue_passes_current_matched_scope_to_real_observer(
    observation, monkeypatch
):
    e = observation
    raw = {"schemaVersion": "document-review-source.v1", "synthetic": True}
    content = {"documents": [{"chunks": [{"content": json.dumps(raw)}]}]}
    monkeypatch.setattr(
        source_module, "source_digest", lambda body: e.scope.sourceContentDigest
    )
    e.call.operation = "READ_OWNED_CONVERSATION_SOURCES"
    e.automation.bound_app = lambda call: NS(scope=lambda p: object())
    checked = []
    e.automation.owned_business = NS(
        _policy=lambda c, context: checked.append(context),
        policy=NS(validate_source=lambda metadata, body: e.scope),
    )
    monkeypatch.setattr(
        source_module,
        "identities",
        lambda *args: [
            {
                "identity": e.scope.source.resource_id,
                "revision": e.scope.source.revision_id,
                "digest": e.scope.source.digest,
            }
        ],
    )
    monkeypatch.setattr(source_module, "require_read", lambda *args: None)
    monkeypatch.setattr(
        source_module,
        "read_published",
        lambda *args: (content, "Exact production source"),
    )
    monkeypatch.setattr(
        source_module,
        "validate",
        lambda *args: {
            "sourceSchema": raw["schemaVersion"],
            "sourceContentDigest": e.scope.sourceContentDigest,
        },
    )
    result = source_module.sources(e.automation, e.call)
    assert len(checked) == 1
    assert result[0]["assessment"]["state"] == "BOUNDED_ANALYSIS_AVAILABLE"
    assert result[0]["businessEligibility"] == {
        "state": "SOURCE_SCOPE_MATCHED",
        "executionReady": False,
    }
    assert set(e.calls) == set(e.refs)
