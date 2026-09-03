import importlib.util
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).parents[1]
    / "scripts"
    / "preview"
    / "bootstrap_v022_public_preview.py"
)
SPEC = importlib.util.spec_from_file_location("pv103_bootstrap", SCRIPT)
assert SPEC and SPEC.loader
bootstrap_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bootstrap_module
SPEC.loader.exec_module(bootstrap_module)


def published(identity_key, identity):
    return {
        identity_key: identity,
        "name": bootstrap_module.PREFIX + identity,
        "aggregateVersion": 4,
        "lifecycleState": "PUBLISHED",
        "publishedRevisionId": identity + ":revision",
        "currentDraftRevisionId": None,
        "revisions": [
            {
                "revisionId": identity + ":revision",
                "digest": "a" * 64,
                "state": "PUBLISHED",
            }
        ],
    }


class ReadbackClient:
    def __init__(self):
        self.calls = []
        self.knowledge = {
            **published("knowledgeId", "knowledge:pv103"),
            "name": bootstrap_module.PREFIX + "供应商质量知识包",
            "lifecycleState": "AVAILABLE",
            "activeIndexSnapshotId": "index-snapshot:pv103",
        }
        self.runtime = published("runtimeProfileId", "runtime-profile:pv103")
        self.workflow = published("workflowDefinitionId", "workflow-definition:pv103")
        self.agent = published("definitionId", "agent-definition:pv103")
        self.runtime["name"] = bootstrap_module.PREFIX + "声明式 Runtime Profile"
        self.workflow["name"] = bootstrap_module.PREFIX + "质量分析 Workflow Definition"
        self.agent["name"] = bootstrap_module.PREFIX + "供应商质量分析数字员工"

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path.endswith("/knowledge"):
            return [self.knowledge]
        if path.endswith("/runtime-profiles"):
            return [self.runtime]
        if path.endswith("/workflow-definitions"):
            return [self.workflow]
        if path.endswith("/agent-definitions"):
            return [self.agent]
        if path.endswith("/digital-employee-templates"):
            return [
                {
                    "templateId": "digital-employee-template:pv103",
                    "agentDefinition": {"identity": self.agent["definitionId"]},
                    "executionAuthority": "NONE",
                }
            ]
        raise AssertionError((method, path, body))


def test_bootstrap_is_idempotent_and_reads_back_exact_template(monkeypatch):
    client = ReadbackClient()
    skill = published("resourceId", "skill:pv103")
    mcp = published("resourceId", "mcp:pv103")
    mcp["toolSelections"] = [{"snapshotId": "mcp-snapshot:pv103"}]
    monkeypatch.setattr(
        bootstrap_module,
        "ensure_simple",
        lambda _client, kind, _name, _content: skill if kind == "skill" else mcp,
    )

    first = bootstrap_module.bootstrap(client)
    second = bootstrap_module.bootstrap(client)

    assert first == second
    assert first["owner"] == "human:public-preview-owner"
    assert first["template"]["executionAuthority"] == "NONE"
    assert first["prohibitedLifecycleCreated"] is False
    assert all(method == "GET" for method, _, _ in client.calls)


def test_script_contains_no_v023_execution_or_secret_material():
    source = SCRIPT.read_text()
    prohibited_routes = (
        "/assignments",
        "/workflow-runs",
        "/task-runs",
        "/attempts",
        "/placements",
        "/runtime-instances",
        "/agent-instances",
    )
    assert not any(route in source for route in prohibited_routes)
    assert "private-key" not in source.lower()
    assert "api-key" not in source.lower()
    assert "http://127.0.0.1:8765/mcp" in source


def test_cleanup_is_scoped_to_owned_preview_resources():
    class CleanupClient:
        def __init__(self):
            self.posts = []

        def request(self, method, path, body=None):
            if method == "GET":
                return [
                    {
                        "name": bootstrap_module.PREFIX + "owned",
                        "resourceId": path.rsplit("/", 1)[-1] + ":pv103",
                        "aggregateVersion": 4,
                        "lifecycleState": "PUBLISHED",
                    },
                    {
                        "name": "unrelated",
                        "resourceId": "unrelated",
                        "aggregateVersion": 1,
                        "lifecycleState": "DRAFT",
                    },
                ]
            self.posts.append((path, body))
            return {}

    client = CleanupClient()
    result = bootstrap_module.cleanup(client)
    assert len(client.posts) == 2
    assert all(
        body["reason"] == "PV103 deterministic cleanup" for _, body in client.posts
    )
    assert result["historyDeleted"] is False
