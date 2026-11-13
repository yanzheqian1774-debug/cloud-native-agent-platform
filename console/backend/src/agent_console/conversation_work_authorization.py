"""Exact owner permissions for the already authorized synthetic conversation.

Normal grant requests/decisions are durable; business owner checks stay in place.
No execution, resource management, external write or administrator authority.
"""

from datetime import timedelta
from uuid import uuid4

from .authority_contracts import (
    AuthorityError,
    ExactGrant,
    GrantDecision,
    GrantId,
    GrantRequestStatus,
)
from .business_problem_authorization import (
    criteria_resource,
    criterion_resource,
    criterion_revision_resource,
    problem_resource,
)
from .context_call_admission import active, request_row
from .conversation_planning_admission import require_resolved_source
from .grant_administration_application import GrantRequestCommand
from .task_delegation import digest


class ConversationWorkAuthorization:
    def __init__(self, planning):
        self.planning = planning
        self.adapter = planning.conversation_experience
        self.understanding = self.adapter.understanding
        self.experience = self.adapter.experience
        self.repository = planning.repository
        self.grants = planning.delegation.grants

    def _draft(self, c, context, invocation_id):
        account, now, expires = self.experience._require(self.understanding, c, context)
        invocation = c.execute(
            "SELECT record FROM draft_assistance.invocation_versions"
            " WHERE namespace=%s "
            "AND security_domain=%s AND invocation_id=%s ORDER BY ag"
            "gregate_version DESC LIMIT 1",
            (context.scope.tenant_id, context.scope.security_domain, invocation_id),
        ).fetchone()
        value = invocation["record"] if invocation else {}
        row = request_row(c, value.get("contextId", ""))
        if (
            not row
            or value.get("state") != "SUCCEEDED"
            or value.get("resultKind") != "DRAFT_READY"
            or value.get("initiatingPrincipalId") != context.principal_id
            or row["subject_id"] != context.principal_id
            or row["record"].get("experience_policy_digest")
            != self.experience.policy_digest
            or row["record"].get("conversation_id")
            not in self.experience.document.conversations
        ):
            raise AuthorityError("CONTEXT_ADMISSION_DRAFT_INVALID")
        decision = active(c, row, self.understanding.configuration)
        require_resolved_source(c, row)
        return row, account, now, min(expires, decision["expires_at"])

    def _scope(self, c, context, operation, payload, path):
        if operation == "CREATE_PROBLEM":
            if payload.get("ownerId") != context.principal_id:
                raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")
            source = self._draft(c, context, payload.get("draftInvocationId", ""))
            return source, {
                ExactGrant("BUSINESS_PROBLEM", "CREATE", problem_resource())
            }
        problem = path.get("problem_id") or payload.get("problemId")
        source = self.adapter.require_source(self.planning, c, context, problem)
        row = source[0]
        expected = {ExactGrant("BUSINESS_PROBLEM", "READ", problem_resource(problem))}
        if operation == "WRITE_CRITERION":
            if payload.get("predecessorRevisionId") or payload.get(
                "successCriterionId"
            ):
                raise AuthorityError("CONTEXT_ADMISSION_EXACT_TARGET_DENIED")
            expected |= {
                ExactGrant("SUCCESS_CRITERION", a, criterion_resource())
                for a in ("CREATE", "READ")
            }
        elif operation == "WRITE_CRITERIA_SET":
            if payload.get("predecessorSetRevisionId"):
                raise AuthorityError("CONTEXT_ADMISSION_EXACT_TARGET_DENIED")
            expected |= {
                ExactGrant("SUCCESS_CRITERIA_SET", a, criteria_resource(problem))
                for a in ("CREATE", "READ")
            }
            for revision in payload.get("orderedCriterionRevisionIds", []):
                owned = c.execute(
                    "SELECT 1 FROM authorization_admin.context_call_objects "
                    "WHERE context_id=%s "
                    "AND owner='SUCCESS_CRITERION' AND resource_id=%s",
                    (row["context_id"], revision),
                ).fetchone()
                if not owned:
                    raise AuthorityError("CONTEXT_ADMISSION_CRITERION_TARGET_DENIED")
                expected.add(
                    ExactGrant(
                        "SUCCESS_CRITERION",
                        "READ",
                        criterion_revision_resource(revision),
                    )
                )
        elif operation == "TRANSITION_PROBLEM":
            if payload.get("toState") != "ACTIVE":
                raise AuthorityError("CONTEXT_ADMISSION_EXACT_TARGET_DENIED")
            expected.add(
                ExactGrant("BUSINESS_PROBLEM", "TRANSITION", problem_resource(problem))
            )
        return source, expected

    def before(self, context, operation, payload, path, grants):
        if not self.experience.matches(context) or operation not in {
            "CREATE_PROBLEM",
            "WRITE_CRITERION",
            "WRITE_CRITERIA_SET",
            "TRANSITION_PROBLEM",
        }:
            return
        # Existing unrelated manual operations retain their previous authority path.
        if operation == "CREATE_PROBLEM" and not payload.get("draftInvocationId"):
            return

        def resolve(c):
            source, expected = self._scope(c, context, operation, payload, path)
            if set(grants) != expected:
                raise AuthorityError("CONTEXT_ADMISSION_EXACT_TARGET_DENIED")
            return source, expected

        self._issue(context, resolve)

    def after(self, context, operation, payload, result):
        if (
            not self.experience.matches(context)
            or operation != "CREATE_PROBLEM"
            or not payload.get("draftInvocationId")
        ):
            return
        problem = result["revision"]["business_problem_id"]

        def resolve(c):
            source = self.adapter.require_source(self.planning, c, context, problem)
            original = self._draft(c, context, payload["draftInvocationId"])[0]
            if source[0]["context_id"] != original["context_id"]:
                raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")
            return source, {
                ExactGrant("BUSINESS_PROBLEM", "READ", problem_resource(problem)),
                ExactGrant("PLAN", "PREPARE", "plan:prepare:" + problem),
                ExactGrant("PLAN", "READ", "plan:prepared:" + problem),
                ExactGrant(
                    "MODEL_GOVERNANCE",
                    "INVOKE_MODEL",
                    self.planning.configuration["model_target"],
                ),
            }

        self._issue(context, resolve)

    @staticmethod
    def _purpose(member):
        if member.owner == "BUSINESS_PROBLEM":
            return (
                "F3_SYNTHETIC_EXPERIENCE_READ"
                if member.action == "READ"
                else "WORKBENCH_PROBLEM"
            )
        if member.owner in {"SUCCESS_CRITERION", "SUCCESS_CRITERIA_SET"}:
            return "WORKBENCH_SUCCESS_CRITERIA"
        return "WORKBENCH_PLANNING"

    def _issue(self, context, resolve):
        with self.repository.connection_scope() as c:
            source, expected = resolve(c)
            identity = source[0]["context_id"]
        requests = {}
        for member in sorted(
            expected, key=lambda g: (g.owner, g.action, g.exact_resource)
        ):
            purpose = self._purpose(member)
            key = "f3-work:" + digest(
                [
                    identity,
                    purpose,
                    [member.owner, member.action, member.exact_resource],
                ]
            )
            request = self.grants.submit_request(
                context, GrantRequestCommand(purpose, (member,), key)
            )
            requests[request.request_id] = (purpose, member)
        with self.repository.connection_scope() as c:
            # Lock the current account before source validation takes share locks.
            # Concurrent tabs must not deadlock while upgrading the same account.
            now = c.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            credential = self.repository._current_credential_id(
                c,
                context,
                now=now,
                recovery_epoch=self.grants.recovery_epoch,
                lock_session=True,
            )
            if credential != self.experience.document.accountId:
                raise AuthorityError("CONTEXT_ADMISSION_ACCOUNT_INACTIVE")
            source, current_expected = resolve(c)
            row, _, now, expires = source
            if row["context_id"] != identity or current_expected != expected:
                raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")
            expires = min(expires, now + timedelta(hours=8))
            for request_id in requests:
                c.execute(
                    "SELECT request_id FROM authorization_admin.grant_reques"
                    "ts WHERE request_id=%s FOR UPDATE",
                    (request_id,),
                )
                request = self.repository._request(c, request_id)
                if (
                    request.subject_principal_id != context.principal_id
                    or request.scope != context.scope
                    or (request.purpose, *request.members) != requests[request_id]
                    or any(
                        not self.grants.target_validator.is_known_exact_target(
                            context, g, connection=c
                        )
                        for g in request.members
                    )
                ):
                    raise AuthorityError("CONTEXT_ADMISSION_EXACT_TARGET_DENIED")
                if request.status is not GrantRequestStatus.PENDING:
                    # Original owner checks still reject expired/revoked grants.
                    continue
                decision = GrantDecision(
                    "grant-decision-" + uuid4().hex,
                    request_id,
                    "policy:f3-conversation-experience",
                    identity,
                    True,
                    "BOUNDED_SYNTHETIC_WORK",
                    "POLICY",
                    self.experience.policy_digest,
                    self.grants.generation.policy_version,
                    "f3-work:" + identity,
                    now,
                )
                c.execute(
                    "INSERT INTO authorization_admin.grant_decisions "
                    "(decision_id,request_id,issuer_principal_id,issuer_meta"
                    "_decision_id,approved,"
                    "reason_category,basis_type,basis_reference_digest,polic"
                    "y_version,audit_source,created_at) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        decision.decision_id,
                        request_id,
                        decision.issuer_principal_id,
                        identity,
                        True,
                        decision.reason_category,
                        "POLICY",
                        self.experience.policy_digest,
                        decision.policy_version,
                        decision.audit_source,
                        now,
                    ),
                )
                for member in request.members:
                    self.repository._insert_grant(
                        c,
                        GrantId("grant-" + uuid4().hex),
                        request,
                        decision,
                        member,
                        now,
                        expires,
                        self.grants.recovery_epoch,
                    )
                c.execute(
                    "UPDATE authorization_admin.grant_requests SET state='APPROVED',"
                    "aggregate_version=aggregate_version+1,decided_at=%s WHE"
                    "RE request_id=%s",
                    (now, request_id),
                )
                self.repository._audit(
                    c,
                    event_type="CONTEXT_EXPERIENCE_WORK_GRANTED",
                    actor_id=decision.issuer_principal_id,
                    outcome="APPROVED",
                    reason=decision.reason_category,
                    occurred_at=now,
                    scope=context.scope,
                    subject_id=request_id,
                    generation=self.grants.generation.generation,
                    recovery_epoch=self.grants.recovery_epoch,
                )
