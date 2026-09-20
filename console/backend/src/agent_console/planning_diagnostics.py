"""323-only fixed provider probes under the signed development admission.

Diagnostic success is never business planning success. No caller supplied prompt,
provider configuration, schema or resource is accepted by these probes.
"""

import json
from copy import deepcopy

from .authority_contracts import AuthorityError

LAYERS = frozenset({"MINIMAL", "STRUCTURED", "ADAPTER"})


def require_diagnostic(connection, budget, principal, request):
    from .task_delegation import active
    from .task_development import revision

    row = connection.execute(
        "SELECT d.delegation_id FROM authorization_admin.task_delegations d "
        "JOIN authorization_admin.task_delegation_ledgers l USING(delegation_id) "
        "WHERE d.subject_id=%s AND d.tenant_id=%s AND d.security_domain=%s "
        "AND d.task_id='S5-V023-ARCH-323' AND l.ledger_id=%s AND l.purpose='planning'",
        (
            principal.principal_id,
            principal.tenant_id,
            principal.security_domain,
            budget.ledger_id,
        ),
    ).fetchone()
    if not row:
        raise AuthorityError("PLANNING_DIAGNOSTIC_NOT_AUTHORIZED")
    row, _ = active(connection, row["delegation_id"], lock=True)
    if not revision(connection, row["delegation_id"]):
        raise AuthorityError("PLANNING_DIAGNOSTIC_NOT_AUTHORIZED")
    if getattr(budget, "delegation_configuration", None) != row["record"]["planning"]:
        raise AuthorityError("TASK_DELEGATION_CONFIGURATION_MISMATCH")
    admission = connection.execute(
        "SELECT record FROM authorization_admin.task_diagnostic_admissions "
        "WHERE delegation_id=%s AND request_key=%s",
        (row["delegation_id"], request.idempotency_key),
    ).fetchone()
    if not admission or admission["record"]["target"] != request.target.model_dump(
        mode="json"
    ):
        raise AuthorityError("PLANNING_DIAGNOSTIC_NOT_AUTHORIZED")


def diagnostic_document(original, layer):
    if layer not in LAYERS:
        raise ValueError("PLANNING_DIAGNOSTIC_LAYER_INVALID")
    document = deepcopy(original)
    document["instructions"] = "Connectivity diagnostic only. Return exactly OK."
    text = "Return OK."
    if layer == "MINIMAL":
        document.pop("text", None)
    elif layer == "STRUCTURED":
        document["instructions"] = 'Diagnostic only. Return {"ok":true}.'
        text = 'Return {"ok":true}.'
        document["text"]["format"] = {
            "type": "json_schema",
            "name": "s5_323_diagnostic",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
                "additionalProperties": False,
            },
        }
    else:
        document["instructions"] = (
            'Adapter diagnostic only. Return exactly {"kind":"UNSUPPORTED",'
            '"questions":[],"semantics":null}. This is not a business judgment.'
        )
        text = "Return the fixed diagnostic object."
    document["input"] = [
        {"role": "user", "content": [{"type": "input_text", "text": text}]}
    ]
    return document


def validate_diagnostic(layer, text):
    if layer == "MINIMAL":
        return text.strip() == "OK"
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return False
    if layer == "STRUCTURED":
        return value == {"ok": True} and type(value.get("ok")) is bool
    if layer == "ADAPTER":
        from .plan_suggestion_invocation import PlanningProviderResult

        try:
            parsed = PlanningProviderResult.model_validate_json(text)
        except ValueError:
            return False
        return parsed.kind == "UNSUPPORTED"
    return False


def policy_digest(layer):
    from .business_problem_domain import canonical_digest
    from .plan_suggestion_policy import output_schema

    return canonical_digest(
        {
            "version": "planning-diagnostic.v1",
            "layer": layer,
            "document": diagnostic_document(
                {
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "plan_suggestion_output",
                            "strict": True,
                            "schema": output_schema(),
                        }
                    }
                },
                layer,
            ),
        }
    )
