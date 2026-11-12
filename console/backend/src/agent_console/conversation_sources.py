"""Readable published analysis sources, independent of historical business plans."""

import json
from dataclasses import dataclass

from .authority_contracts import AuthorityError
from .plan_suggestion_domain import ExactReference, PlanningError
from .planning_candidates import identities, read_published, require_read
from .resource_automation_policy import source_digest
from .resource_automation_validation import validate
from .workbench_business_problem import OwnerPrincipal


@dataclass(frozen=True)
class ReadableSourceValidation:
    """Content validation only; never an execution or policy authorization."""

    sourceContentDigests: tuple[str, ...]


def sources(automation, call, root=None):
    app = automation.bound_app(call)
    principal = OwnerPrincipal(
        call.context.principal_id,
        call.context.scope.tenant_id,
        call.context.scope.security_domain,
    )
    scope = app.scope(principal)
    # A named task still checks its existing work policy. Browsing sources only
    # needs current exact read grants; it must not require an execution window.
    task_work = (
        automation.work(call.context, root, automation.grants.clock())
        if root is not None
        else None
    )
    result = []
    seen = set()
    for item in identities(call.connection, scope, "KNOWLEDGE"):
        try:
            ref = ExactReference(
                resource_id=item["identity"],
                revision_id=item["revision"],
                digest=item["digest"].removeprefix("sha256:"),
            )
            require_read(call.authority, principal, "KNOWLEDGE", ref)
            content, name = read_published(call.connection, scope, "KNOWLEDGE", ref)
            work = task_work or ReadableSourceValidation((source_digest(content),))
            check = validate("knowledge", content, work)
            raw = json.loads(content["documents"][0]["chunks"][0]["content"])
            if raw.get("synthetic") is not True:
                continue
            if check["sourceSchema"] not in {
                "document-review-source.v1",
                "tabular-diagnostic-source.v1",
                "sales-diagnostic-source.v1",
                "synthetic-delivery-source.v1",
            }:
                continue
            if check["sourceContentDigest"] in seen:
                continue
            seen.add(check["sourceContentDigest"])
            from .conversation_capability import describe
            from .question_member_capabilities import observe

            offer = describe(
                raw, observe(automation, call, ref, check["sourceSchema"], work)
            )
            result.append(
                {
                    **offer,
                    "source": ref.model_dump(mode="json"),
                    "name": name,
                    "sourceSchema": check["sourceSchema"],
                    "sourceContentDigest": check["sourceContentDigest"],
                    "periods": raw.get("periods", []),
                    "synthetic": True,
                }
            )
        except (AuthorityError, PlanningError, ValueError, KeyError, TypeError):
            continue
    return result


class ConversationSources:
    def __init__(self, automation):
        self.automation = automation

    def __call__(self, call):
        return {"items": sources(self.automation, call), "executionStarted": False}
