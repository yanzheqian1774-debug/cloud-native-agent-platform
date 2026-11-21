# ruff: noqa: F401,F811,E501 -- Real isolated owner fixture imports and exact queries.
"""Real service event/continuation and browser read; controlled provider/Kubernetes.

Human BOUND provenance is immutable fixture setup, not a real product acceptance.
No test creates Human model admission for the reader.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import test_fixed_work_cycle_host_postgres as host
from agent_console import fixed_work_sources_postgres as sources
from agent_console.authority_configuration import (
    OWNER_RESOURCE_PREFIXES,
    RequestabilityRule,
)
from agent_console.authority_contracts import GrantSource
from agent_console.browser_session_application import (
    BrowserSessionPolicy,
    BrowserSessionService,
    StaticGenerationAuthenticator,
)
from agent_console.fixed_chat_delivery import FixedChatDelivery
from agent_console.fixed_chat_read_access import FixedChatReadAccess, ReadAccess
from agent_console.fixed_chat_read_policy import FixedChatReadPolicy
from agent_console.private_conversation import PrivateConversations
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
)
from agent_console.workbench_pagination import WorkbenchCursorCodec
from psycopg.rows import dict_row
from test_fixed_work_activity_read_postgres import (
    automation as original_automation,
)
from test_fixed_work_activity_read_postgres import (
    case,
    repository,
    services,
)
from test_fixed_work_bound_composition_postgres import (
    test_bound_original_plan_to_start_composition as original_chain,
)


@pytest.fixture
def automation(repository, case, services, tmp_path, request, monkeypatch):
    original = host.resources.StaticAuthorityGeneration

    def generation(*args, **kwargs):
        g = original(*args, **kwargs)
        return replace(
            g,
            requestability=(
                *g.requestability,
                *(
                    RequestabilityRule(
                        owner,
                        action,
                        OWNER_RESOURCE_PREFIXES[owner],
                        "RESOURCE_PREPARATION",
                    )
                    for owner, action in (
                        ("EVALUATION", "READ"),
                        ("RESOURCE_USE", "READ"),
                        ("BUSINESS_ONTOLOGY", "READ"),
                    )
                ),
            ),
        )

    monkeypatch.setattr(host.resources, "StaticAuthorityGeneration", generation)
    fixture = original_automation.__wrapped__(
        repository, case, services, tmp_path, request, monkeypatch
    )
    yield next(fixture)
    next(fixture, None)


@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
def test_bound_committed_event_is_read_in_original_chat_without_human_model_lease(
    automation, monkeypatch, tmp_path
):
    a = automation
    sessions = BrowserSessionService(
        a.authority,
        StaticGenerationAuthenticator(a.gen, source=GrantSource.BROWSER_BOOTSTRAP),
        BrowserSessionPolicy(
            timedelta(minutes=5),
            timedelta(minutes=30),
            timedelta(hours=1),
            timedelta(minutes=10),
        ),
        csrf_signing_key=b"v" * 32,
        recovery_epoch=1,
    )
    secret = sessions.create_session(sessions.issue_login_nonce(), "viewer-secret")
    _, ctx = sessions.authenticate_session(secret.value)
    with a.authority.connection_scope() as c:
        c.execute(
            (
                Path(__file__).parents[1] / "migrations/0046_private_conversation.sql"
            ).read_text()
        )
    records = PrivateConversations(a.authority.pool.conninfo, lambda *args: None)
    conversation = records.create(
        ctx, dict(title="Original fixed work", idempotencyKey="original")
    )["conversation_id"]
    append = sources.append

    def setup_source(c, scope, table, value):
        value = {
            **value,
            "subjectId": ctx.principal_id,
            "conversationId": conversation,
            "schemaVersion": "fixed-work-conversation.v1"
            if table == "handoffs"
            else "fixed-work-confirmed-source.v1",
        }
        if table == "bindings":
            from agent_console import owned_business_postgres
            from agent_console.digital_employee_definition import digest
            from psycopg.types.json import Jsonb

            # Complete retained identity fixture; no active Human model lease.
            # Its creation/BIND authority is not claimed as exercised by this test.
            migrations = Path(__file__).parents[1] / "migrations"
            if (
                c.execute(
                    "SELECT to_regclass('authorization_admin.context_call_requests') t"
                ).fetchone()["t"]
                is None
            ):
                c.execute((migrations / "0028_task_delegation.sql").read_text())
                c.execute((migrations / "0037_context_call_admission.sql").read_text())
            if (
                c.execute(
                    "SELECT to_regclass('authorization_admin.owned_business_admissions') t"
                ).fetchone()["t"]
                is None
            ):
                c.execute(
                    (migrations / "0066_owned_business_admission.sql").read_text()
                )
            context_record = dict(
                configuration={"fixture": "retained-source"},
                conversation_id=conversation,
            )
            c.execute(
                "INSERT INTO authorization_admin.context_call_requests(context_id,tenant_id,security_domain,subject_id,account_id,account_revision,first_invocation_id,record,digest) VALUES(%s,%s,%s,%s,%s,1,%s,%s,%s)",
                (
                    "retained-context",
                    *scope,
                    ctx.principal_id,
                    "retained-account",
                    "retained-understanding",
                    Jsonb(context_record),
                    digest(context_record),
                ),
            )
            record = dict(
                schemaVersion="owned-business-admission.v1",
                policyDigest="f" * 64,
                subject=ctx.principal_id,
                tenantId=scope[0],
                securityDomain=scope[1],
                conversationId=conversation,
                contextId="retained-context",
                invocationId="retained-understanding",
                inputSource=value["inputSource"],
                understandingBindings=[
                    dict(
                        contextId="retained-context",
                        configuration=context_record["configuration"],
                        understandingPolicyDigest=None,
                        questionOnly=False,
                    )
                ],
            )
            admission = owned_business_postgres.append(c, ctx, record)
            value.update(
                admission=dict(
                    id=admission["admission_id"], digest=admission["record_digest"]
                ),
                understanding=dict(
                    contextId="retained-context", invocationId="retained-understanding"
                ),
                originalContextId="retained-context",
            )
        return append(c, scope, table, value)

    monkeypatch.setattr(sources, "append", setup_source)
    from agent_console.fixed_work_service_continuation import ServiceCycleContinuation

    original_continue = ServiceCycleContinuation.continue_once
    pending_seen = []

    def inspect_before_start(continuation, service_call, event):
        if not pending_seen:
            with a.authority.connection_scope() as c:
                b = c.execute(
                    "SELECT record,digest FROM fixed_work_sources.bindings"
                ).fetchone()
                pending_policy = FixedChatReadPolicy.model_validate(
                    dict(
                        schemaVersion="fixed-chat-read-policy.v1",
                        policyId="test",
                        enabled=True,
                        expiresAt=datetime.now(UTC) + timedelta(hours=26),
                        grantTTLSeconds=3600,
                        scopes=[
                            dict(
                                tenantId=ctx.scope.tenant_id,
                                securityDomain=ctx.scope.security_domain,
                                subjectId=ctx.principal_id,
                                conversationId=conversation,
                                bindingDigest=b["digest"],
                                work=b["record"]["work"],
                            )
                        ],
                    )
                )
                pending_owner = FixedChatDelivery(
                    pending_policy,
                    records,
                    a.automation,
                    WorkbenchCursorCodec(b"c" * 32),
                )
                read_call = AuthorizedOwnerCall(
                    "READ_FIXED_CHAT_ACTIVITY",
                    ctx,
                    c,
                    {},
                    {},
                    {},
                    (),
                    AuthorizedOwnerAuthority(a.adapter, ctx, c, 1, ()),
                    1,
                    1,
                )
                pending = pending_owner.read(read_call, conversation)
                assert len(pending["items"]) == 1
                item = pending["items"][0]
                assert (
                    item["eventId"] == event
                    and item["phase"] == "PLANNING"
                    and item["planningState"] == "PREPARED"
                )
                assert (
                    item["runId"] is None
                    and item["preparationDigest"] is None
                    and item["receiptDigest"] is None
                )
                pending_seen.append(item)
        return original_continue(continuation, service_call, event)

    monkeypatch.setattr(ServiceCycleContinuation, "continue_once", inspect_before_start)
    original_chain(a, monkeypatch, tmp_path, "SUCCEEDED")
    assert pending_seen
    with a.authority.connection_scope() as c:
        bound = c.execute(
            "SELECT record,digest FROM fixed_work_sources.bindings"
        ).fetchone()
        before = c.execute(
            "SELECT count(*) n FROM fixed_work_triggers.receipts"
        ).fetchone()["n"]
    policy = FixedChatReadPolicy.model_validate(
        dict(
            schemaVersion="fixed-chat-read-policy.v1",
            policyId="test",
            enabled=True,
            expiresAt=datetime.now(UTC) + timedelta(hours=26),
            grantTTLSeconds=3600,
            scopes=[
                dict(
                    tenantId=ctx.scope.tenant_id,
                    securityDomain=ctx.scope.security_domain,
                    subjectId=ctx.principal_id,
                    conversationId=conversation,
                    bindingDigest=bound["digest"],
                    work=bound["record"]["work"],
                )
            ],
        )
    )
    owner = FixedChatDelivery(
        policy, records, a.automation, WorkbenchCursorCodec(b"c" * 32)
    )
    with a.authority.connection_scope() as c:
        call = AuthorizedOwnerCall(
            "READ_FIXED_CHAT_ACTIVITY",
            ctx,
            c,
            {},
            {},
            {},
            (),
            AuthorizedOwnerAuthority(a.adapter, ctx, c, 1, ()),
            1,
            1,
        )
        result = owner.read(call, conversation)
        assert result["conversationId"] == conversation and result["state"] == "BOUND"
        assert result["problem"] == bound["record"]["target"]["problem"]
        assert result["answerDelegation"] == "UNAVAILABLE"
        assert len(result["items"]) == before >= 1
        assert all(
            item["readState"] == "READ_REQUIRED" and item["execution"] is None
            for item in result["items"]
        )
        assert all(
            item["scheduledAt"] and len(item["readTargetDigest"]) == 64
            for item in result["items"]
        )
        assert owner.read(call, conversation) == result
        assert (
            c.execute("SELECT count(*) n FROM fixed_work_triggers.receipts").fetchone()[
                "n"
            ]
            == before
        )

    # Same original independent grant owner; no new model admission or invocation.
    access = FixedChatReadAccess(owner)
    item = result["items"][0]
    assert (
        item["eventId"] == pending_seen[0]["eventId"] and item["phase"] == "EXECUTION"
    )
    command = ReadAccess(
        bindingDigest=result["bindingDigest"],
        workDigest=result["work"]["digest"],
        eventId=item["eventId"],
        receiptDigest=item["receiptDigest"],
        preparationDigest=item["preparationDigest"],
        runId=item["runId"],
        readTargetDigest=item["readTargetDigest"],
        commandId="first-read",
    )

    def invoke():
        with a.authority.connection_scope() as c:
            call = AuthorizedOwnerCall(
                "PREPARE_FIXED_CHAT_READ",
                ctx,
                c,
                {},
                {},
                {},
                (),
                AuthorizedOwnerAuthority(a.adapter, ctx, c, 1, ()),
                1,
                1,
            )
            return access.prepare(call, conversation, command)

    first = invoke()
    assert first["state"] == "READ_READY" and first["readTargetRelation"] == "SAME"
    assert invoke() == first
    with a.authority.connection_scope() as c:
        reads = c.execute(
            "SELECT owner,action FROM authorization_admin.grants WHERE subject_principal_id=%s",
            (ctx.principal_id,),
        ).fetchall()
        assert reads and all(
            r["action"] in {"READ", "READ_RESOURCE", "READ_REFERENCE"} for r in reads
        )
        assert (
            c.execute("SELECT count(*) n FROM fixed_work_triggers.receipts").fetchone()[
                "n"
            ]
            == before
        )
    # Current exact owner read succeeds; it is not a human acceptance or Solved fact.
    from agent_console.workbench_prepared_execution import PreparedExecutionOwner

    with a.authority.connection_scope() as c:
        auth = AuthorizedOwnerAuthority(a.adapter, ctx, c, 1, ())
        view = PreparedExecutionOwner()(
            AuthorizedOwnerCall(
                "READ_PREPARED_EXECUTION",
                ctx,
                c,
                {},
                {"digest": item["preparationDigest"]},
                {},
                (),
                auth,
                1,
                1,
            )
        )
        assert view["progress"]["state"] == "SUCCEEDED"
        assert (
            owner.read(
                AuthorizedOwnerCall(
                    "READ_FIXED_CHAT_ACTIVITY", ctx, c, {}, {}, {}, (), auth, 1, 1
                ),
                conversation,
            )["items"][0]["execution"]["state"]
            == "SUCCEEDED"
        )
    # Original grant surrender, not an injected boolean, prevents key replacement.
    from agent_console.grant_administration_application import GrantRevocationCommand
    from agent_console.workbench_owner_authorization import WorkbenchOwnerError

    with a.authority.connection_scope() as c:
        grant = c.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE subject_principal_id=%s AND owner='EXECUTION' AND action='READ'",
            (ctx.principal_id,),
        ).fetchone()
        prior_count = c.execute(
            "SELECT count(*) n FROM authorization_admin.grant_requests"
        ).fetchone()["n"]
    a.automation.grants.revoke_grant(
        ctx,
        GrantRevocationCommand(
            grant["grant_id"], "TEST_WITHDRAWAL", "withdraw-event-read", surrender=True
        ),
    )
    assert invoke()["state"] == "UNKNOWN"
    replacement = command.model_copy(
        update={"commandId": "cannot-evade", "previousCommandId": "first-read"}
    )
    with pytest.raises(WorkbenchOwnerError), a.authority.connection_scope() as c:
        auth = AuthorizedOwnerAuthority(a.adapter, ctx, c, 1, ())
        access.prepare(
            AuthorizedOwnerCall(
                "PREPARE_FIXED_CHAT_READ", ctx, c, {}, {}, {}, (), auth, 1, 1
            ),
            conversation,
            replacement,
        )
    with a.authority.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_requests"
            ).fetchone()["n"]
            == prior_count
        )
