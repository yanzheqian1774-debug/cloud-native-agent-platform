"""Private startup gates, no database, model, authority or process effects."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from agent_console.fixed_question_startup import PinnedFile, configure, read_pin


def pin(tmp_path, name, value):
    path = tmp_path / name
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def configuration(tmp_path, *, enabled=True):
    ref = dict(resource_id="work", revision_id="r", digest="a" * 64)
    policy = dict(
        schemaVersion="fixed-question-delegation-policy.v1",
        policyId="test",
        enabled=True,
        generation=1,
        generationDigest="b" * 64,
        recoveryEpoch=1,
        issuerId="human:issuer",
        issuerCredentialId="issuer",
        expiresAt=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        grantTTLSeconds=60,
        scopes=[
            dict(
                tenantId="t",
                securityDomain="d",
                subjectId="human:actor",
                conversationId="chat",
                bindingDigest="c" * 64,
                work=ref,
                executionSubject="service:work",
                serviceCredentialId="service",
            )
        ],
    )
    value = dict(
        schemaVersion="fixed-question-startup.v1",
        enabled=enabled,
        questionPolicy=pin(tmp_path, "question.json", policy),
        policySetConfiguration=pin(tmp_path, "set.json", {"explicit": "controlled"}),
        servicePolicyDigest="d" * 64,
    )
    top = pin(tmp_path, "startup.json", value)
    return {
        "FIXED_QUESTION_DELEGATION_CONFIGURATION": top["path"],
        "FIXED_QUESTION_DELEGATION_CONFIGURATION_SHA256": top["sha256"],
    }, value


def test_absent_and_explicit_off_do_not_construct(tmp_path):
    def fail(*_):
        pytest.fail("disabled startup constructed a leaf")

    assert configure({}, (), factory=fail) is None
    environment, _ = configuration(tmp_path, enabled=False)
    assert configure(environment, (), factory=fail) is None


def test_missing_real_c1_owner_refuses_before_factory(tmp_path):
    environment, _ = configuration(tmp_path)
    with pytest.raises(ValueError, match="TYPED_UNDERSTANDING_REQUIRED"):
        configure(environment, (), factory=lambda *_: pytest.fail("constructed"))


@pytest.mark.parametrize("mode", ["symlink", "permissions", "changed"])
def test_private_exact_pin_refuses_changes(tmp_path, mode):
    item = pin(tmp_path, "private.json", {"x": 1})
    from pathlib import Path

    path = Path(item["path"])
    if mode == "symlink":
        link = tmp_path / "link.json"
        link.symlink_to(path)
        item["path"] = str(link)
    elif mode == "permissions":
        path.chmod(0o644)
    else:
        path.write_text('{"x":2}')
    with pytest.raises((ValueError, OSError)):
        read_pin(PinnedFile(**item))


@pytest.mark.parametrize("runtime_kind", ["typed7", "procurement1", "wrong_subject"])
def test_startup_selects_one_exact_existing_leaf_and_closes_on_failure(
    tmp_path, monkeypatch, runtime_kind
):
    # This isolates startup selection; real registry/runtime owner integration is
    # verified separately by the document service chain, not these controlled ports.
    from types import SimpleNamespace as NS

    import agent_console.fixed_question_startup as module

    environment, config = configuration(tmp_path)
    expected = module.NativeTypedQuestionDocumentSkillExecutor.revision
    runtime = NS(
        subject="service:work" if runtime_kind != "wrong_subject" else "service:other",
        durable_wait=NS(
            typedQuestions=True,
            executorId=expected.executor_id,
            executorRevision=expected.executor_revision,
            executorConfigurationDigest=expected.configuration_digest,
        )
        if runtime_kind != "procurement1"
        else None,
    )
    events = []
    leaf = NS(
        runtime=runtime,
        work=NS(bound_service_execution=NS(registry=object())),
        execution_repository=object(),
    )

    class Assembly:
        def service_leaf(self, scope, **kwargs):
            events.append((scope, kwargs))
            return leaf

        def close(self):
            events.append("closed")

    def factory(path, env):
        assert path == config["policySetConfiguration"]["path"]
        assert env == environment and env is not environment
        events.append("constructed")
        return Assembly()

    monkeypatch.setattr(
        module, "settlement_reader_for_services", lambda *_: lambda *_: None
    )
    monkeypatch.setattr(
        module, "FixedQuestionComposition", lambda *args, **kwargs: (args, kwargs)
    )
    if runtime_kind != "typed7":
        with pytest.raises(ValueError, match="TYPED_DOCUMENT_RUNTIME_REQUIRED"):
            configure(environment, (), factory=factory)
        assert events[-1] == "closed"
    else:
        owner = configure(environment, (), factory=factory)
        assert events == [
            "constructed",
            (("t", "d"), {"credential_id": "service", "policy_digest": "d" * 64}),
        ]
        owner.close()
        owner.close()
        assert events.count("closed") == 1
