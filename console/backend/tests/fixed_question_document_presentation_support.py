"""Original BrowserSession, exact READ and independent question grant owners."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

from agent_console.authority_contracts import GrantSource
from agent_console.browser_session_application import (
    BrowserSessionPolicy,
    BrowserSessionService,
    StaticGenerationAuthenticator,
)
from agent_console.fixed_chat_delivery import FixedChatDelivery
from agent_console.fixed_chat_read_access import FixedChatReadAccess, ReadAccess
from agent_console.fixed_chat_read_policy import FixedChatReadPolicy
from agent_console.fixed_question_execution import FixedQuestionExecutionAuthority
from agent_console.fixed_question_policy import FixedQuestionPolicy
from agent_console.fixed_question_presentation import (
    FixedQuestionPresentations,
    PresentQuestion,
)
from agent_console.fixed_question_store import FixedQuestionStore
from agent_console.native_wait_store import NativeWaitStore
from agent_console.private_conversation import PrivateConversations
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
)
from agent_console.workbench_pagination import WorkbenchCursorCodec
from test_workbench_authorization_postgres import FakeController


def present(a, live, native, work):
    # The original controlled activation barrier exposes only the fields its
    # old read tests needed. Bind the additional real generation digest here.
    a.adapter.controller = FakeController(a.gen)
    a.adapter.controller.readiness.generation_digest = a.gen.digest
    sessions = BrowserSessionService(
        a.authority,
        StaticGenerationAuthenticator(a.gen, source=GrantSource.BROWSER_BOOTSTRAP),
        BrowserSessionPolicy(
            timedelta(minutes=5),
            timedelta(minutes=30),
            timedelta(hours=1),
            timedelta(minutes=10),
        ),
        csrf_signing_key=b"q" * 32,
        recovery_epoch=1,
    )
    secret = sessions.create_account_session(
        sessions.issue_login_nonce(), "reviewer324", "isolated-document7-password"
    )
    _, context = sessions.authenticate_session(secret.value)
    records = PrivateConversations(a.authority.pool.conninfo, lambda *args: None)
    with a.authority.connection_scope() as c:
        FixedQuestionStore.migrate(c)
        bound = c.execute(
            "SELECT record,digest FROM fixed_work_sources.bindings "
            "WHERE namespace=%s AND security_domain=%s",
            (context.scope.tenant_id, context.scope.security_domain),
        ).fetchone()
    scope = dict(
        tenantId=context.scope.tenant_id,
        securityDomain=context.scope.security_domain,
        subjectId=context.principal_id,
        conversationId=bound["record"]["conversationId"],
        bindingDigest=bound["digest"],
        work=bound["record"]["work"],
    )
    read_policy = FixedChatReadPolicy.model_validate(
        dict(
            schemaVersion="fixed-chat-read-policy.v1",
            policyId="document7-read",
            enabled=True,
            expiresAt=datetime.now(UTC) + timedelta(hours=1),
            grantTTLSeconds=3600,
            scopes=[scope],
        )
    )
    delivery = FixedChatDelivery(
        read_policy, records, a.automation, WorkbenchCursorCodec(b"q" * 32)
    )

    def call(c):
        return AuthorizedOwnerCall(
            "PREPARE_FIXED_QUESTION",
            context,
            c,
            {},
            {},
            {},
            (),
            AuthorizedOwnerAuthority(a.adapter, context, c, 1, ()),
            1,
            1,
        )

    chat = scope["conversationId"]
    with a.authority.connection_scope() as c:
        result = delivery.read(call(c), chat)
        item = next(i for i in result["items"] if i["phase"] == "EXECUTION")
        access = ReadAccess(
            bindingDigest=result["bindingDigest"],
            workDigest=result["work"]["digest"],
            eventId=item["eventId"],
            receiptDigest=item["receiptDigest"],
            preparationDigest=item["preparationDigest"],
            runId=item["runId"],
            readTargetDigest=item["readTargetDigest"],
            commandId="question-read",
        )
        assert (
            FixedChatReadAccess(delivery).prepare(call(c), chat, access)["state"]
            == "READ_READY"
        )
    issuer = a.automation.authenticate(context)
    service = live.runtime.bound_service_execution.registry._policy()
    policy = FixedQuestionPolicy.model_validate(
        dict(
            schemaVersion="fixed-question-delegation-policy.v1",
            policyId="document7-question",
            enabled=True,
            generation=1,
            generationDigest=a.gen.digest,
            recoveryEpoch=1,
            issuerId=issuer.principal_id,
            issuerCredentialId=issuer.session_id_or_service_credential_id,
            expiresAt=read_policy.expiresAt,
            grantTTLSeconds=3600,
            scopes=[
                {
                    **scope,
                    "executionSubject": service.subjectId,
                    "serviceCredentialId": service.credentialId,
                }
            ],
        )
    )
    owner = FixedQuestionPresentations(
        delivery,
        policy,
        clock=lambda: datetime.now(UTC),
        validate_execution=FixedQuestionExecutionAuthority(live.runtime, native, work),
    )
    waiting = live.sessions[-1].waiting
    with a.authority.connection_scope() as c:
        cp = NativeWaitStore(c, waiting.identity).checkpoint(waiting.checkpoint_digest)
        identity, _ = owner.observe(
            call(c),
            chat,
            item["eventId"],
            item["receiptDigest"],
            cp.identity.skill_invocation_id,
            cp.question_key,
        )
        head = records.owned(c, context, chat, lock=True)
        command = PresentQuestion(
            identity=identity,
            expectedConversationVersion=head["version"],
            commandId="present-document7-question",
        )
        value, replay = owner.prepare(call(c), chat, command)
        assert not replay and value.actorId != identity.executionSubject
    with a.authority.connection_scope() as c:
        repeated, replay = owner.prepare(call(c), chat, command)
        assert replay and repeated == value
    return NS(
        sessions=sessions,
        secret=secret,
        context=context,
        records=records,
        delivery=delivery,
        read_policy=read_policy,
        policy=policy,
        presentations=owner,
        presentation=value,
        call=call,
        item=item,
    )
