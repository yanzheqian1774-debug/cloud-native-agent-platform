"""Dedicated 323 HTTPS replay and side-effect receipt; never calls a provider."""

import json
import re
from pathlib import Path

import httpx
import psycopg
from psycopg import sql

RUNTIME = Path("/Users/tristan/Documents/s5-v023-arch-323-acceptance")
DATABASE = "postgresql://postgres@127.0.0.1:25432/planning323_browser"
BASE = "https://127.0.0.1:19324"
PREFIX = "/api/workbench/v1"


def counts():
    with psycopg.connect(DATABASE) as conn:
        tables = conn.execute(
            "SELECT schemaname,tablename FROM pg_tables WHERE schemaname "
            "NOT IN ('pg_catalog','information_schema','browser_session',"
            "'authorization_admin','workflow_planning')"
        ).fetchall()
        result = {}
        for schema, table in tables:
            result[f"{schema}.{table}"] = conn.execute(
                sql.SQL("SELECT count(*) FROM {}.{}").format(
                    sql.Identifier(schema), sql.Identifier(table)
                )
            ).fetchone()[0]
        for table in (
            "proposals",
            "plans",
            "approvals",
            "invocations",
            "invocation_results",
        ):
            result["workflow_planning." + table] = conn.execute(
                sql.SQL("SELECT count(*) FROM workflow_planning.{}").format(
                    sql.Identifier(table)
                )
            ).fetchone()[0]
        return result


def main():
    saved = json.loads((RUNTIME / "browser-receipt.json").read_text())
    with httpx.Client(base_url=BASE, verify=False) as client:
        form = client.get(PREFIX + "/login")
        nonce = re.search(r'name="loginNonce" value="([^"]+)"', form.text).group(1)
        response = client.post(
            PREFIX + "/session",
            data={
                "loginNonce": nonce,
                "bootstrapCredential": json.loads(
                    (RUNTIME / "credentials.json").read_text()
                )["browser"],
            },
            headers={"origin": BASE},
        )
        assert response.status_code == 303
        csrf = client.get(PREFIX + "/session").json()["csrfToken"]
        headers = {"origin": BASE, "X-CSRF-Token": csrf}
        path = PREFIX + "/planning-v2/" + saved["proposalId"]
        before = counts()
        history = client.get(path + "/history").json()["result"]
        assert history == saved["history"]
        proposal = client.get(path, params={"version": 1}).json()["result"]
        body = {
            "version": 1,
            "digest": proposal["digest"],
            "expectedPlanVersion": 1,
            "idempotencyKey": "323-readback-replay",
        }
        assert client.post(path + "/confirm", json=body).status_code in (403, 401)
        for _ in range(2):
            response = client.post(path + "/confirm", json=body, headers=headers)
            assert response.status_code == 200, response.text
            response = client.post(
                path + "/resources", json={"version": 1}, headers=headers
            )
            assert response.status_code == 200, response.text
            assert len(response.json()["result"]["pending_required"]) == 6
        assert client.get(path + "/history").json()["result"] == history
        assert (
            client.get(PREFIX + "/planning-v2/nonexistent/history").status_code == 404
        )
        after = counts()
        assert after == before, {
            k: (v, after[k]) for k, v in before.items() if after[k] != v
        }
        with psycopg.connect(DATABASE) as conn:
            linked = conn.execute(
                "SELECT count(*) FROM workflow_planning.invocations i "
                "JOIN contextual_resource_use.uses u ON u.context_id=i.invocation_id "
                "JOIN model_evidence.records e "
                "ON e.record->>'invocationId'=i.invocation_id "
                "WHERE u.context_kind='PLAN_SUGGESTION_INVOCATION'"
            ).fetchone()[0]
        assert linked == before["workflow_planning.invocations"]
        (RUNTIME / "side-effects-receipt.json").write_text(
            json.dumps(
                {
                    "counts": after,
                    "unchanged": True,
                    "linkedModelEvidence": linked,
                    "realModelCalls": 0,
                    "transport": "CONTROLLED_TEST_PROVIDER",
                },
                indent=2,
            )
        )
        print(
            "HTTPS replay/CSRF/owner/history PASS; counts unchanged; Evidence:",
            linked,
        )


if __name__ == "__main__":
    main()
