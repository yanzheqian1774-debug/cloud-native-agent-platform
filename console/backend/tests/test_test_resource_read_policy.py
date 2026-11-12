from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityError,
    AuthorityScope,
    TrustedRequestContext,
)
from agent_console.test_resource_read_policy import TestReadPolicy, TestReadTarget
from pydantic import ValidationError


def policy(**changes):
    return TestReadPolicy.model_validate(
        dict(
            schemaVersion="test-resource-read-policy.v1",
            policyId="test-read",
            policyVersion="1",
            tenant="test",
            securityDomain="isolated",
            subjects=["human:tester"],
            issuer="service:read-policy",
            credentialPath="/not-read-by-configuration",
            expiresAt=datetime.now(UTC) + timedelta(hours=2),
            targets=[
                dict(
                    owner="EMPLOYEE",
                    action="READ",
                    resource="employee:definition:revision",
                    digest="a" * 64,
                    purpose="READ_RESOURCE",
                )
            ],
        )
        | changes
    )


@pytest.mark.parametrize(
    "owner,action,resource",
    [
        ("EXECUTION", "START", "governed-execution:prepared:task"),
        ("MODEL_GOVERNANCE", "INVOKE_MODEL", "model:revision:model:r"),
        ("EMPLOYEE", "PUBLISH", "employee:definition:revision"),
        ("TOOL", "REVISE", "tool:test:aggregate"),
        ("GRANT_ADMIN", "DECIDE", "grant-scope:test:isolated"),
    ],
)
def test_write_and_administration_cannot_enter_read_inventory(owner, action, resource):
    with pytest.raises((ValidationError, AuthorityError)):
        TestReadTarget(
            owner=owner,
            action=action,
            resource=resource,
            digest="a" * 64,
            purpose="READ_RESOURCE",
        )


def test_exact_revision_requires_digest_and_collection_does_not():
    target = policy().targets[0].model_dump()
    with pytest.raises(ValidationError):
        TestReadTarget.model_validate(target | {"digest": None})
    collection = target | {
        "action": "LIST",
        "resource": "employee:collection",
        "digest": None,
    }
    TestReadTarget.model_validate(collection)
    with pytest.raises(ValidationError):
        TestReadTarget.model_validate(collection | {"digest": "b" * 64})


@pytest.mark.parametrize(
    "changes",
    [
        {"grantTTLSeconds": 28801},
        {"credentialPath": "relative"},
        {"subjects": ["human:tester", "human:tester"]},
        {"subjects": ["service:read-policy"]},
        {"expiresAt": datetime(2026, 1, 1)},
        {"schemaVersion": "test-resource-read-policy.v2"},
    ],
)
def test_invalid_scope_lifetime_and_configuration_rejected(changes):
    with pytest.raises(ValidationError):
        policy(**changes)


def test_duplicate_target_even_with_different_purpose_rejected():
    target = policy().targets[0].model_dump()
    with pytest.raises(ValidationError):
        policy(targets=[target, target | {"purpose": "OTHER_READ"}])


def test_disabled_and_foreign_subject_rejected_before_credential_read():
    grants = SimpleNamespace(clock=lambda: datetime.now(UTC))
    context = TrustedRequestContext(
        "human:tester",
        AuthorityScope("test", "isolated"),
        "session",
        AuthenticationSource.BROWSER_SESSION,
        "1",
    )
    with pytest.raises(AuthorityError, match="TEST_READ_POLICY_DISABLED"):
        policy().authenticate(grants, context)
    with pytest.raises(AuthorityError, match="TEST_READ_POLICY_SCOPE_DENIED"):
        policy(enabled=True, tenant="foreign").authenticate(grants, context)
    with pytest.raises(AuthorityError, match="TEST_READ_POLICY_SCOPE_DENIED"):
        policy(
            enabled=True, expiresAt=datetime.now(UTC) - timedelta(seconds=1)
        ).authenticate(grants, context)


def test_existing_catalog_list_targets_are_requestable_without_revision_lookup():
    from agent_console.agent_definition_postgres import (
        PostgresAgentDefinitionRepository,
    )
    from agent_console.workbench_workflow_authoring import WorkflowAuthoringTargets

    assert PostgresAgentDefinitionRepository.is_known_grant_target_for_workbench(
        None, None, "LIST", "agent:collection"
    )
    assert not PostgresAgentDefinitionRepository.is_known_grant_target_for_workbench(
        None, None, "LIST", "agent:foreign"
    )
    context = SimpleNamespace(scope=AuthorityScope("test", "isolated"))
    from agent_console.authority_contracts import ExactGrant

    assert WorkflowAuthoringTargets().is_known_exact_target(
        context,
        ExactGrant("WORKFLOW", "LIST", "workflow:collection"),
        connection=object(),
    )
    assert not WorkflowAuthoringTargets().is_known_exact_target(
        context, ExactGrant("WORKFLOW", "LIST", "workflow:foreign"), connection=object()
    )
