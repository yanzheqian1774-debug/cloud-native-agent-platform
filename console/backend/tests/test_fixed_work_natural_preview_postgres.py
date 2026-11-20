"""Actual ordinary authoring owner preview/save; disposable database only."""

import pytest
import test_fixed_work_authoring_postgres as original
from agent_console.workbench_fixed_work import FixedWorkAuthoringOwner
from agent_console.workbench_fixed_work_preview import fixed_work_preview_operations
from fastapi.testclient import TestClient
from test_fixed_work_authoring import body

pytestmark = original.pytestmark


@pytest.fixture
def app(monkeypatch, tmp_path):
    base = original.fixed_work_operations

    def operations(path, clock, cursors):
        return (
            *base(path, clock, cursors),
            *fixed_work_preview_operations(
                FixedWorkAuthoringOwner(path, clock, cursors), enabled=True
            ),
        )

    monkeypatch.setattr(original, "fixed_work_operations", operations)
    generator = original.app.__wrapped__(monkeypatch, tmp_path)
    value = next(generator)
    try:
        yield value
    finally:
        generator.close()


@pytest.mark.parametrize("revise", [True, False])
def test_exact_preview_then_original_save_and_refresh(app, revise):
    with TestClient(app.application, base_url="https://console.example") as client:
        url, headers, _ = original.setup(app, client, revise=revise)
        preview_url = url.replace("/fixed-work-drafts", "/fixed-work-preview")
        instruction = "每个工作日北京时间上午9点半检查交接资料"
        observed = client.post(
            preview_url, json={"instruction": instruction}, headers=headers
        )
        assert observed.status_code == 200, observed.text
        result = observed.json()["result"]
        assert not result["issues"] and not result["modelInvoked"]
        assert result["configurationCanSave"] is revise
        with app.authority.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT count(*) AS n FROM fixed_work_authoring.revisions"
                ).fetchone()["n"]
                == 0
            )
        command = {
            **body(),
            "instruction": instruction,
            "title": result["proposedTitle"],
            "trigger": result["candidateTrigger"],
        }
        saved = client.post(url, json=command, headers=headers)
        assert saved.status_code == (201 if revise else 404), saved.text
        if not revise:
            assert saved.json()["reasonCode"] == "AUTHORIZATION_NOT_FOUND"
            with app.authority.connection_scope() as c:
                assert (
                    c.execute(
                        "SELECT count(*) AS n FROM fixed_work_authoring.revisions"
                    ).fetchone()["n"]
                    == 0
                )
            return
        item = saved.json()["result"]
        again = client.get(url + "/work:1/revisions/revision:1")
        assert again.status_code == 200 and again.json()["result"] == item
        previous = {
            "workId": "work:1",
            "revisionId": "revision:1",
            "digest": item["digest"],
        }
        changed = client.post(
            preview_url,
            json={"instruction": "每天北京时间10点检查资料", "previous": previous},
            headers=headers,
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["result"]["previousTrigger"]["localTime"] == "09:30"
        assert changed.json()["result"]["candidateTrigger"]["localTime"] == "10:00"
        denied = client.post(
            preview_url,
            json={
                "instruction": instruction,
                "previous": {**previous, "digest": "f" * 64},
            },
            headers=headers,
        )
        assert denied.status_code == 409
        assert client.get(url + "/work:1/revisions/revision:1").json()["result"] == item
