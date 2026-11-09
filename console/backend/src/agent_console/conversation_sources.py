"""Readable published analysis sources, independent of historical business plans."""

import json

from .authority_contracts import AuthorityError
from .plan_suggestion_domain import ExactReference, PlanningError
from .planning_candidates import identities, read_published, require_read
from .resource_automation_validation import validate
from .workbench_business_problem import OwnerPrincipal


def sources(automation, call, root=None):
    from .development_administrator import for_call

    if not for_call(call):
        return []
    app = automation.bound_app(call)
    principal = OwnerPrincipal(
        call.context.principal_id,
        call.context.scope.tenant_id,
        call.context.scope.security_domain,
    )
    scope = app.scope(principal)
    # Work scope never authorizes execution; exact owner checks still apply below.
    work = automation.work(
        call.context,
        root
        or ExactReference(
            resource_id="conversation-source-discovery",
            revision_id="1",
            digest="0" * 64,
        ),
        automation.grants.clock(),
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
            check = validate("knowledge", content, work)
            raw = json.loads(content["documents"][0]["chunks"][0]["content"])
            if raw.get("synthetic") is not True:
                continue
            if check["sourceSchema"] not in {
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
