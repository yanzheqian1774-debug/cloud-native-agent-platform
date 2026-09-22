"""Read-only delivery Native preparation; never creates grants, approvals or Runs."""

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from agent_console.delivery_resource_bundle import resource_content, source_document
from agent_console.prepared_delivery_contract import validate_delivery_mapping
from psycopg.rows import dict_row


def specification():
    # Deliberately not a ConfirmedPlanRevision. Human/owner records do not exist
    # until the normal formal path creates and confirms them.
    return {
        "schemaVersion": "delivery-native-validation-spec.v1",
        "classification": "ISOLATED_CAPABILITY_VALIDATION_NOT_AI_PLAN",
        "synthetic": True,
        "approval": None,
        "scope": {
            "namespace": "s5-324-native-capability",
            "securityDomain": "isolated-native-validation",
        },
        "tasks": [
            {
                "task_id": "read-fixed-orders",
                "operation": "READ_DATA",
                "depends_on": [],
                "inputs": ["published fixed synthetic delivery snapshot"],
                "outputs": ["synthetic-delivery-output.v1"],
            },
            {
                "task_id": "render-delivery-report",
                "operation": "RENDER_REPORT",
                "depends_on": ["read-fixed-orders"],
                "inputs": ["read-fixed-orders artifact with exact source digest"],
                "outputs": ["synthetic-delivery-output.v1 with report title"],
            },
        ],
        "criteria": [
            "snapshot",
            "eligibility",
            "quantities",
            "ranking",
            "traceability",
            "anomalies",
        ],
        "humanResult": "NOT_DECIDED",
    }


def inspect(runtime, kube_context):
    from agent_console.resource_use_domain import canonical_digest

    spec = specification()
    bundle = resource_content()
    validate_delivery_mapping(spec, bundle["skill"]["operations"])
    with psycopg.connect(runtime["databaseUrl"], row_factory=dict_row) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        # No copying of original approvals/resources into another scope.
        preparations = connection.execute(
            "SELECT count(*) AS n FROM execution_authority.run_preparations "
            "WHERE namespace=%s AND security_domain=%s",
            (spec["scope"]["namespace"], spec["scope"]["securityDomain"]),
        ).fetchone()["n"]
    command = ["kubectl", "--context", kube_context]
    crd = subprocess.check_output(
        [*command, "get", "crd", "tasks.agentos.io", "-o", "json"], text=True
    )
    namespaces = subprocess.check_output(
        [
            *command,
            "get",
            "namespace",
            spec["scope"]["namespace"],
            "--ignore-not-found",
            "-o",
            "json",
        ],
        text=True,
    )
    return {
        "observedAt": datetime.now(UTC).isoformat(),
        "specification": spec,
        "specificationDigest": canonical_digest(spec),
        "sourceDigest": canonical_digest(source_document()),
        "taskContract": "VALIDATED_NO_EFFECTS",
        "kubernetesContext": kube_context,
        "taskCrdDigest": hashlib.sha256(crd.encode()).hexdigest(),
        "namespaceExists": bool(namespaces.strip()),
        "existingIsolatedPreparations": preparations,
        "nativeExecuted": False,
        "blockers": [
            "ISOLATED_OWNER_OBJECTS_AND_HUMAN_PLAN_CONFIRMATION_REQUIRED",
            "INDEPENDENT_EXECUTION_ADMISSION_REQUIRED",
            "EXACT_WORKER_AUTHORITY_AND_DELIVERY_MODE_REQUIRED",
        ],
        "historyCopied": False,
        "businessCaseReplaced": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--kube-context", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(json.loads(args.runtime.read_text()), args.kube_context)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "taskContract",
                    "namespaceExists",
                    "existingIsolatedPreparations",
                    "nativeExecuted",
                    "blockers",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
