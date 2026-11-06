"""Explicit v2 candidate shapes within the existing bounded Skill schema subset."""

from copy import deepcopy

from .resource_use_domain import canonical_digest

DIMENSIONS = ("region", "channel", "product")
METRICS = ("netSales", "cost", "grossProfit")
UNKNOWN_LABELS = ("", "UNKNOWN", "UNSPECIFIED", "N/A", "未知")
LIMITS = {
    "maxRows": 1000,
    "maxInputBytes": 4 * 1024 * 1024,
    "maxOutputBytes": 4 * 1024 * 1024,
    "maxObjectDepth": 24,
    "maxProperties": 200000,
    "timeoutMs": 5000,
}


def obj(properties, required=None, *, extra=False):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties) if required is None else required,
        "additionalProperties": extra,
    }


def array(items):
    return {"type": "array", "items": items}


def string(*values):
    return {"type": "string", **({"enum": list(values)} if values else {})}


REFERENCE = obj(
    {
        "resource_id": string(),
        "revision_id": string(),
        "digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    }
)
RATE = obj(
    {"status": string("DEFINED", "BASELINE_ZERO"), "value": string()}, ["status"]
)
METRIC = obj({**{k: string() for k in ("baseline", "current", "delta")}, "rate": RATE})
ROW_REFS = array(obj({"period": string(), "rowIds": array(string())}))
LABEL = obj(
    {
        "rawValue": string(),
        "sourceValueState": string("PRESENT", "MISSING"),
        "value": string(),
        "valueStatus": string("PROVIDED_UNVERIFIED", "UNRESOLVED"),
    }
)
GROUP = obj(
    {
        "currency": string(),
        "value": string(),
        "valueStatus": string("PROVIDED_UNVERIFIED", "UNRESOLVED"),
        **dict.fromkeys(METRICS, METRIC),
        "sourceRows": ROW_REFS,
    }
)
COMPARISON = obj(
    {"currency": string(), **dict.fromkeys(METRICS, METRIC), "sourceRows": ROW_REFS}
)
ROW_TERM = obj(
    {
        "rowId": string(),
        "sourceLine": {"type": "integer"},
        "period": string(),
        "periodRole": string("BASELINE", "CURRENT"),
        "changeSign": {"type": "integer", "enum": [-1, 1]},
        "currency": string(),
        "kind": string("SALE", "RETURN"),
        **dict.fromkeys(METRICS, string()),
        "deltaContributions": obj(dict.fromkeys(METRICS, string())),
        "dimensions": obj(dict.fromkeys(DIMENSIONS, LABEL)),
    }
)
RECONCILIATION = obj(
    {
        "currency": string(),
        "groupCount": {"type": "integer"},
        **dict.fromkeys(
            METRICS,
            obj(
                {
                    "sumGroupDelta": string(),
                    "currencyDelta": string(),
                    "matches": {"type": "boolean", "enum": [True]},
                }
            ),
        ),
    }
)
EXCLUSION = obj(
    {
        "rowId": string(),
        "sourceLine": {"type": "integer"},
        "reason": string("CANCELLED"),
        "rawValues": obj({}, [], extra=True),
    }
)
ISSUE = obj(
    {
        "rowId": string(),
        "sourceLine": {"type": "integer"},
        "field": string(*DIMENSIONS),
        "reason": string("DIMENSION_UNRESOLVED_INCLUDED"),
        "rawValue": string(),
        "sourceValueState": string("PRESENT", "MISSING"),
    }
)
INPUT_SCHEMA = obj(
    {
        "schemaVersion": string("sales-diagnostic-input.v2"),
        "synthetic": {"type": "boolean", "enum": [True]},
        "sourceSnapshot": REFERENCE,
        "source": obj({}, [], extra=True),
        "dependencies": obj({}, [], extra=True),
    }
)
OUTPUT_SCHEMA = obj(
    {
        "schemaVersion": string("sales-diagnostic-output.v2"),
        "contractDigest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "synthetic": {"type": "boolean", "enum": [True]},
        "metric": string("RECOGNIZED_NET_SALES_EXCLUDING_TAX"),
        "grossProfitDefinition": string("NET_SALES_MINUS_SIGNED_COST"),
        "periods": array(string()),
        "sourceSnapshot": REFERENCE,
        "sourceDigest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "source": obj({}, [], extra=True),
        "currencyComparisons": array(COMPARISON),
        "dimensions": obj({d: array(GROUP) for d in DIMENSIONS}),
        "rowContributions": array(ROW_TERM),
        "excludedRows": array(EXCLUSION),
        "inputIssues": array(ISSUE),
        "reconciliations": obj({d: array(RECONCILIATION) for d in DIMENSIONS}),
        "limitations": array(string()),
        "businessConclusion": string("UNDETERMINED"),
        "operation": string(
            "READ_DATA", "VALIDATE_DATA", "SUMMARIZE", "ANALYZE_DATA", "RENDER_REPORT"
        ),
    }
)
CONTRACT = {
    "schemaVersion": "sales-diagnostic-contract.v2",
    "inputSchema": INPUT_SCHEMA,
    "outputSchema": OUTPUT_SCHEMA,
    "limits": LIMITS,
    "semanticInvariants": [
        "All financial strings have exactly two decimal places; no binary floats.",
        "The integer oracle scales by100 for arithmetic, "
        "not ISO minor-unit certification.",
        "GP equals signed netSales minus signed cost for every posted source row.",
        "Baseline terms subtract; current terms add; returns keep signed amounts.",
        "Cancelled rows are excluded before financial parsing and retain raw rows.",
        "Missing/invalid posted cost and inconsistent SALE/RETURN signs fail closed.",
        "BASELINE_ZERO rate omits value; DEFINED rate has delta/abs(baseline).",
        "Unknown labels map to empty UNRESOLVED groups with exact raw row labels.",
        "Each dimension partitions all posted rows exactly once per currency.",
        "Every dimension/currency/metric sum equals its currency total delta.",
        "Never sum currencies or add the three dimension decompositions together.",
        "Dependencies match exact v2 contract, source commitments and recomputation.",
        "Provided labels/currency codes are not certified ontology/ISO identities.",
    ],
    "unknownDimensionLabels": list(UNKNOWN_LABELS),
    "ratePrecision": 38,
    "rateRounding": "ROUND_HALF_EVEN",
    "status": "LOCAL_CANDIDATE_NOT_ACTIVATED",
}
CONTRACT_DIGEST = canonical_digest(CONTRACT)


def contract_document():
    return deepcopy(CONTRACT)
