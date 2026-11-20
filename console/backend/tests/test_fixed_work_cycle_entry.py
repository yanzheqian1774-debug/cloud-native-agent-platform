"""Standalone entry boundaries; controlled assembly is not real cycle acceptance."""

import hashlib
import json
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from types import SimpleNamespace as N
from unittest.mock import Mock

import pytest
from agent_console import fixed_work_cycle_factory as factory
from agent_console.authority_configuration import (
    CredentialConfiguration,
    StaticAuthorityGeneration,
)
from agent_console.authority_contracts import (
    AuthorityError,
    AuthorityScope,
    GrantSource,
)
from agent_console.fixed_work_bound_composition import compose_bound_cycle_service
from agent_console.fixed_work_bound_policy import BoundServicePlanningPolicy
from agent_console.fixed_work_cycle_configuration import CycleConfiguration, FilePin
from agent_operator.fixed_work_cycle_entry import execute, main
from test_fixed_work_cycle_host import setup_host


def config(tmp_path, enabled=False):
    pin = dict(path=str(tmp_path / "not-read"), sha256="a" * 64)
    return CycleConfiguration.model_validate(
        dict(
            schemaVersion="fixed-work-cycle-process.v1",
            enabled=enabled,
            sourceRoot=str(Path(__file__).parents[3]),
            sourceFiles={"not-read": "a" * 64},
            **{
                k: pin
                for k in (
                    "authorityRuntime",
                    "planningRuntime",
                    "servicePolicy",
                    "resourcePolicy",
                    "readonlyPolicy",
                    "serviceCredential",
                )
            },
        )
    )


def save(tmp_path, document):
    p = tmp_path / "cycle.json"
    p.write_text(document.model_dump_json())
    p.chmod(0o600)
    return p


def test_disabled_cli_never_constructs_or_reads_owner_dependencies(
    tmp_path, monkeypatch
):
    build = Mock(side_effect=AssertionError("must not build"))
    monkeypatch.setattr(factory, "build_cycle_process", build)
    assert execute(save(tmp_path, config(tmp_path))) == {
        "state": "DISABLED",
        "modelCalled": False,
        "executionStarted": False,
    }
    build.assert_not_called()


def test_factory_disabled_does_not_verify_private_files(tmp_path):
    assert factory.build_cycle_process(config(tmp_path)) is None


@pytest.mark.parametrize("run", [False, True])
def test_explicit_run_only_and_all_paths_close(tmp_path, monkeypatch, run):
    process = N(
        check=Mock(return_value={"modelCalled": False}), run=Mock(), close=Mock()
    )
    monkeypatch.setattr(factory, "build_cycle_process", lambda _: process)
    result = execute(
        save(tmp_path, config(tmp_path, True)), run=run, stop=Event(), observe=Mock()
    )
    assert result["state"] == ("STOPPED" if run else "CHECKED_ONLY")
    assert process.run.call_count == int(run)
    process.close.assert_called_once()


def test_check_failure_stops_without_run_retry_or_secret_output(
    tmp_path, monkeypatch, capsys
):
    process = N(
        check=Mock(side_effect=RuntimeError("secret-DSN")), run=Mock(), close=Mock()
    )
    monkeypatch.setattr(factory, "build_cycle_process", lambda _: process)
    assert (
        main(
            [
                "--configuration",
                str(save(tmp_path, config(tmp_path, True))),
                "--check-only",
            ]
        )
        == 1
    )
    output = capsys.readouterr().out
    assert "secret-DSN" not in output and '"automaticRetry": false' in output
    process.run.assert_not_called()
    process.close.assert_called_once()


def test_pins_reject_drift_public_and_symlink(tmp_path):
    p = tmp_path / "pin"
    p.write_text("original")
    p.chmod(0o600)
    pin = FilePin(path=p, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    assert pin.verify() == p
    p.write_text("changed")
    with pytest.raises(ValueError, match="CHANGED"):
        pin.verify()
    p.chmod(0o644)
    with pytest.raises(ValueError, match="PRIVATE"):
        pin.verify()
    q = tmp_path / "link"
    q.symlink_to(p)
    with pytest.raises(ValueError, match="INVALID"):
        pin.model_copy(update={"path": q}).verify()


def test_source_manifest_is_exact_not_subset(tmp_path, monkeypatch):
    from agent_console import fixed_work_cycle_configuration as cfg

    c = config(tmp_path, True)
    monkeypatch.setattr(
        cfg, "source_files", lambda _: {"a.py": "a" * 64, "b.py": "b" * 64}
    )
    c = c.model_copy(update={"sourceFiles": {"a.py": "a" * 64}})
    with pytest.raises(ValueError, match="SOURCE_CHANGED"):
        c.verify()


def test_changed_config_stops_before_next_owner_step():
    config_ = N(verify=Mock(side_effect=[None, ValueError("CHANGED")]))
    original = Mock()
    loop = N(step=original)
    loop.run = lambda stop, observer: loop.step()
    process = factory.CycleProcess(config_, loop, ExitStack())
    process.check = lambda: config_.verify()
    with pytest.raises(ValueError, match="CHANGED"):
        process.run(Event(), Mock())
    original.assert_not_called()
    assert loop.step is original


def test_unknown_on_restart_reads_same_original_invocation_never_begin():
    for _ in range(2):
        host, context = setup_host(
            result={"technical_status": "OUTCOME_UNKNOWN", "kind": None}
        )
        assert host.step(context, "slot")["stage"] == "PLANNING_OBSERVATION"
        host.runtime.begin.assert_not_called()
        assert host.runtime.service.read.call_args.args[1] == "original"
        host.continuation.continue_once.assert_not_called()


@pytest.mark.parametrize(
    "kind,principal",
    [
        (GrantSource.BROWSER_BOOTSTRAP, "human:a"),
        (GrantSource.SERVICE_ONLY, "human:a"),
        (GrantSource.SERVICE_ONLY, "service:other"),
    ],
)
def test_real_service_authentication_rejects_human_or_wrong_service(
    tmp_path, monkeypatch, kind, principal
):
    from agent_console import fixed_work_bound_composition as bound

    now = datetime.now(UTC)
    policy = BoundServicePlanningPolicy.model_construct(
        enabled=True,
        subjectId="service:expected",
        credentialId="cred",
        tenantId="t",
        securityDomain="d",
        expiresAt=now + timedelta(hours=1),
    )
    monkeypatch.setattr(bound.ServicePlanningPolicy, "load", lambda _: policy)
    gen = StaticAuthorityGeneration(
        1,
        "a" * 64,
        "v1",
        "test",
        (
            CredentialConfiguration(
                "cred",
                hashlib.sha256(b"unit-secret").hexdigest(),
                principal,
                AuthorityScope("t", "d"),
                now + timedelta(hours=1),
                kind,
                (),
            ),
        ),
        (),
        frozenset(),
    )

    @contextmanager
    def protected():
        yield gen

    foundation = N(
        generation_controller=N(protected_request=protected),
        repository=Mock(),
        grants=N(authorization=Mock()),
    )
    planning = Mock(side_effect=AssertionError("identity must fail before planning"))
    with pytest.raises(AuthorityError):
        compose_bound_cycle_service(
            foundation=foundation,
            planning_factory=planning,
            readonly_owner=None,
            policy_path=tmp_path / "not-read",
            credential_reader=lambda: "unit-secret",
            enabled=True,
        )
    planning.assert_not_called()


def test_no_untrusted_dynamic_factory_in_configuration(tmp_path):
    from pydantic import ValidationError

    document = config(tmp_path).model_dump(mode="json")
    document["factory"] = "arbitrary.module:make"
    with pytest.raises(ValidationError):
        CycleConfiguration.model_validate(document)


def test_fresh_planning_keeps_existing_exact_admission_rejected():
    runtime = N(
        dependencies=N(exact_admission_factory=object(), admission_factory=None)
    )
    with pytest.raises(AuthorityError, match="DEDICATED_PLANNING_REQUIRED"):
        factory._planning_factory(runtime, None, None, Path("/unused"))
    assert runtime.dependencies.exact_admission_factory is not None


@pytest.mark.parametrize("changed", [False, True])
def test_real_planning_service_source_port_reads_bound_source_not_config_only(
    monkeypatch, changed
):
    from agent_console import fixed_work_service_admission as admission
    from agent_console import fixed_work_service_policy as policy_module
    from agent_console import fixed_work_sources_postgres as sources
    from agent_console.authority_contracts import (
        AuthenticationSource,
        TrustedRequestContext,
    )
    from agent_console.plan_suggestion_domain import ExactReference
    from agent_console.plan_suggestion_service import PlanningSuggestionService
    from agent_console.workbench_business_problem import OwnerPrincipal

    @contextmanager
    def held(value):
        yield value

    c = N(transaction=lambda: held(None))
    repository = N(pool=N(connection=lambda: held(c)))
    ref = ExactReference(
        resource_id="knowledge:source", revision_id="r1", digest="b" * 64
    )
    policy = N(
        target="exact-target",
        resourceSnapshot=ref,
        tenantId="t",
        securityDomain="d",
        work=N(resource_id="work", revision_id="r1"),
    )
    monkeypatch.setattr(policy_module.ServicePlanningPolicy, "load", lambda _: policy)
    checked = Mock()
    monkeypatch.setattr(admission.ServicePlanningRegistry, "_check", checked)
    # _policy retains the normal typed-policy check in production. This focused
    # port test controls policy parsing/current authority; not a real grant test.
    monkeypatch.setattr(admission.ServicePlanningRegistry, "_policy", lambda _: policy)
    selected = ref.model_copy(update={"digest": "c" * 64}) if changed else ref
    read = Mock(
        return_value={
            "record": {"inputSource": {"source": selected.model_dump(mode="json")}}
        }
    )
    monkeypatch.setattr(sources, "read", read)
    context = TrustedRequestContext(
        "service:a",
        AuthorityScope("t", "d"),
        "cred",
        AuthenticationSource.SERVICE_CREDENTIAL,
        "v1",
    )
    dependencies = N(
        exact_admission_factory=None,
        admission_factory=None,
        profile=object(),
        model_resolver=object(),
        budget=object(),
        quote=object(),
        provider=Mock(),
        commitment_key=b"x" * 32,
        identity_factory=Mock(),
        adaptive_limits=None,
    )
    service = factory._planning_factory(
        N(dependencies=dependencies),
        N(repository=repository, problems=object()),
        Mock(),
        Path("/private/policy"),
    )(context)
    assert isinstance(service, PlanningSuggestionService)
    principal = OwnerPrincipal("service:a", "t", "d")
    if changed:
        with pytest.raises(AuthorityError, match="SINGLE_SOURCE_SNAPSHOT_REQUIRED"):
            service.prepare_resources(principal, policy.target)
    else:
        assert service.prepare_resources(principal, policy.target) == ref
    checked.assert_called_once_with(c, context, policy)
    read.assert_called_once()
    dependencies.provider.assert_not_called()
    with pytest.raises(AuthorityError, match="SOURCE_TARGET_CHANGED"):
        service.prepare_resources(
            OwnerPrincipal("human:other", "t", "d"), policy.target
        )


def test_concrete_factory_wires_original_owners_and_closes_all_pools(
    tmp_path, monkeypatch
):
    """Real factory/owner constructors, controlled IO boundaries, no DB claim."""
    import importlib

    from agent_console import (
        authority_foundation,
        readonly_continuation_policy,
        resource_automation_policy,
    )
    from agent_console import fixed_work_existing_planning as existing
    from agent_console.governed_execution_ownership import (
        execution_database_fingerprint,
    )
    from agent_console.plan_suggestion_bootstrap import PlanningInvocationDependencies
    from agent_console.plan_suggestion_domain import ExactReference
    from agent_console.plan_suggestion_service import PlanningSuggestionService
    from agent_console.readonly_continuation import ReadonlyContinuation
    from agent_console.resource_automation import ResourceAutomation

    db = "postgresql://test.invalid/isolated-not-opened"
    fingerprint = execution_database_fingerprint(db)
    migration = (
        Path(factory.__file__).parents[2]
        / "migrations/0018_browser_session_grant_authority.sql"
    )
    authority = tmp_path / "authority.json"
    authority.write_text(
        json.dumps(
            dict(
                schemaVersion="authority-foundation-runtime.v1",
                databaseUrl=db,
                migrationPath=str(migration),
                generationPath=str(tmp_path / "generation"),
                generationDigest="a" * 64,
                csrfSigningKeyPath=str(tmp_path / "csrf"),
                continuationSigningKeyPath=str(tmp_path / "continuation"),
                recoveryControlPath=str(tmp_path / "recovery"),
                databaseFingerprint=fingerprint,
                operatorId="test-only",
            )
        )
    )
    repos = []

    def repository(url, **kwargs):
        assert url == db
        r = N(
            pool=N(conninfo=url, close=Mock()),
            compatibility=Mock(),
            native_dispatch_compatibility=Mock(),
        )
        repos.append(r)
        return r

    for module, name in (
        ("business_problem_postgres", "PostgresBusinessProblemRepository"),
        ("execution_postgres", "PostgresExecutionAuthorityRepository"),
        ("agent_definition_postgres", "PostgresAgentDefinitionRepository"),
        ("skill_mcp_postgres", "PostgresSkillMcpRepository"),
        ("runtime_profile_postgres", "PostgresRuntimeProfileRepository"),
        ("knowledge_postgres", "PostgresKnowledgeRepository"),
    ):
        monkeypatch.setattr(
            importlib.import_module("agent_console." + module), name, repository
        )
    employee = N(compatibility=Mock())
    monkeypatch.setattr(
        importlib.import_module("agent_console.digital_employee_definition_postgres"),
        "PostgresEmployeeDefinitionRepository",
        lambda _: employee,
    )
    ref = ExactReference(resource_id="model:m", revision_id="r", digest="a" * 64)
    profile = N(profile_revision_id="profile", profile_digest="b" * 64, model=ref)
    deps = PlanningInvocationDependencies(
        profile, object(), object(), object(), Mock(), b"x" * 32, Mock()
    )
    runtime = N(dependencies=deps, budget=N(ledger_id="root"), close=Mock())
    monkeypatch.setattr(existing, "build_existing_planning", lambda *args: runtime)
    foundation = N(
        grants=N(authorization=Mock()),
        generation_controller=N(readiness=N(database_fingerprint=fingerprint)),
        close=Mock(),
    )
    foundation_builder = Mock(return_value=foundation)
    monkeypatch.setattr(
        authority_foundation, "build_authority_foundation", foundation_builder
    )
    monkeypatch.setattr(factory, "_schema", Mock())
    monkeypatch.setattr(factory, "_existing_schemas", Mock())
    policy = N(probe_runtime=Mock())
    monkeypatch.setattr(
        resource_automation_policy.AutomationPolicy, "load", lambda _: policy
    )
    monkeypatch.setattr(
        readonly_continuation_policy.ReadonlyContinuationPolicy,
        "load",
        lambda _: policy,
    )
    captured = {}

    def bound(**kwargs):
        captured.update(kwargs)
        assert isinstance(kwargs["readonly_owner"], ReadonlyContinuation)
        assert isinstance(kwargs["readonly_owner"].automation, ResourceAutomation)
        from agent_console.authority_contracts import (
            AuthenticationSource,
            TrustedRequestContext,
        )

        ctx = TrustedRequestContext(
            "service:a",
            AuthorityScope("t", "d"),
            "cred",
            AuthenticationSource.SERVICE_CREDENTIAL,
            "v1",
        )
        service = kwargs["planning_factory"](ctx)
        assert isinstance(service, PlanningSuggestionService)
        assert service.exact_admission is None  # later attached by original registry
        return N(
            host=N(
                runtime=N(
                    registry=N(
                        _policy=lambda: N(
                            profileRevisionId="profile",
                            profileDigest="b" * 64,
                            model=ref,
                            ledgerId="root",
                        )
                    )
                )
            )
        )

    monkeypatch.setattr(factory, "compose_bound_cycle_service", bound)
    monkeypatch.setattr(factory.CycleProcess, "check", Mock(return_value={}))
    cfg = config(tmp_path, True).model_copy(
        update={"authorityRuntime": FilePin(path=authority, sha256="a" * 64)}
    )
    monkeypatch.setattr(CycleConfiguration, "verify", Mock())
    process = factory.build_cycle_process(cfg)
    assert foundation_builder.call_args.kwargs["existing_only"] is True
    assert captured["policy_plan_approval_enabled"] is False
    assert captured["readonly_owner"].automation.owned_business is None
    assert captured["readonly_owner"].coordinator.repository is repos[1]
    process.close()
    assert len(repos) == 6
    for r in repos:
        r.pool.close.assert_called_once()
    runtime.close.assert_called_once()
    foundation.close.assert_called_once()
