"""Finite compatibility checks reject semantic changes, not infer user intent."""

from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.native_typed_document_skill import (
    NativeTypedQuestionDocumentSkillExecutor,
)
from agent_console.ontology_action_correction_policy import (
    verify_actions,
    verify_compatibility,
)
from agent_console.ontology_execution import DocumentSemanticsBinding
from agent_console.plan_suggestion_domain import ExactReference
from test_document_rule_owner import rules


def case():
    old = rules()
    ref = old.actions[0].skill
    revision = NativeTypedQuestionDocumentSkillExecutor.revision
    new = old.model_copy(
        update={
            "actions": tuple(
                a.model_copy(
                    update=dict(
                        executor_id=revision.executor_id,
                        executor_revision=revision.executor_revision,
                        executor_digest=revision.configuration_digest,
                    )
                )
                for a in old.actions
            )
        }
    )
    binding = DocumentSemanticsBinding(
        ontology=ExactReference(resource_id="old", revision_id="r1", digest="a" * 64),
        mapping_code=old.mappings[0].code,
        source=old.mappings[0].source,
        scope=old.scope,
    )
    scope = NS(
        documentRules=binding,
        skills=(ref,),
        operations=tuple(a.operation for a in old.actions),
    )
    return old, new, scope


def test_new_scope_actions_verify_without_grant_or_execution():
    old, new, scope = case()
    verify_actions(new, scope)
    with pytest.raises(AuthorityError, match="ACTION_BINDING_MISMATCH"):
        verify_actions(old, scope)


@pytest.mark.parametrize(
    "field,value",
    [
        ("executor_revision", "6"),
        ("executor_digest", "0" * 64),
        ("operation", "DELETE_DATA"),
        ("side_effect", "WRITE"),
    ],
)
def test_action_declaration_cannot_alias_unsupported_revision(field, value):
    _, new, scope = case()
    actions = (new.actions[0].model_copy(update={field: value}), *new.actions[1:])
    with pytest.raises(AuthorityError, match="ACTION_BINDING_MISMATCH"):
        verify_actions(new.model_copy(update={"actions": actions}), scope)


def test_changed_business_content_is_not_an_action_correction():
    old, new, scope = case()
    changed = new.model_copy(update={"name": "Different business description"})
    p = NS(oldBinding=scope.documentRules, newBinding=scope.documentRules)
    with (
        patch(
            "agent_console.ontology_action_correction_policy.published_content",
            side_effect=[old, changed],
        ),
        pytest.raises(AuthorityError, match="BUSINESS_RULES_CHANGED"),
    ):
        verify_compatibility(None, None, p, NS(scope=scope))


def test_verified_owned_action_binding_keeps_exact_published_skill(monkeypatch):
    old, new, scope = case()
    p = NS(oldBinding=scope.documentRules, newBinding=scope.documentRules)
    revision = NativeTypedQuestionDocumentSkillExecutor.revision
    content = {
        "operations": [
            {
                "name": operation,
                "executorId": revision.executor_id,
                "executorRevision": revision.executor_revision,
                "executorConfigurationDigest": revision.configuration_digest,
            }
            for operation in scope.operations
        ]
    }
    with (
        patch(
            "agent_console.ontology_action_correction_policy.published_content",
            side_effect=[old, new],
        ),
        patch(
            "agent_console.planning_candidates.read_published",
            return_value=(content, "exact retained skill"),
        ) as read,
    ):
        verify_compatibility(None, None, p, NS(scope=scope))
    assert read.call_args.args == (None, None, "SKILL", scope.skills[0])
    assert read.call_args.kwargs == {"_published_binding": True}
