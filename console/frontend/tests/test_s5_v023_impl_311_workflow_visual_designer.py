from pathlib import Path

ROOT = Path(__file__).parents[3]
FRONTEND = ROOT / "console" / "frontend" / "src"


def source(path: str) -> str:
    return (FRONTEND / path).read_text()


def test_designer_uses_workflow_content_as_its_only_business_state() -> None:
    builder = source("workflows/WorkflowBuilderPage.tsx")
    canvas = source("workflows/WorkflowCanvas.tsx")
    model = source("workflows/workflowDesignerModel.ts")
    assert "content:WorkflowContent" in builder
    assert "onChange:(value:WorkflowContent)=>void" in builder
    assert "task.dependsOn.map" in canvas
    assert "replaceTask(content" in builder
    assert "renameTask(content" in builder
    assert "removeTask(content" in builder
    assert "layout" not in source("api/workflowDefinitions.ts").lower()
    assert "taskId:nextId" in model


def test_designer_preserves_accessible_list_resource_and_error_views() -> None:
    builder = source("workflows/WorkflowBuilderPage.tsx")
    details = source("workflows/WorkflowResourceDetails.tsx")
    api = source("api/workflowDefinitions.ts")
    for value in ("流程画布", "步骤列表", "节点详情", "Workflow 校验错误列表"):
        assert value in builder
    for value in ("资源 ID", "Revision", "Digest", "Input schema", "Output schema"):
        assert value in details
    assert "validationIssues" in api
    assert "item.loc" in api
    assert "item.input" not in api


def test_layout_is_explicitly_view_only_and_responsive() -> None:
    canvas = source("workflows/WorkflowCanvas.tsx")
    styles = source("styles/workflow-designer.css")
    builder = source("workflows/WorkflowBuilderPage.tsx")
    assert "拖动只改变当前视图位置" in canvas
    assert "不写入 Workflow content" in builder
    assert "@media (max-width: 720px)" in styles
    assert "overflow: auto" in styles
    assert 'data-mobile-pane="catalog"' in styles
    assert "workflow-designer__workspace--inspector-collapsed" in styles
    assert "useEffect" in canvas
    assert "initialCanvas" in canvas


def test_workbench_preserves_distinct_creation_actions_and_empty_state() -> None:
    workbench = source("workflows/WorkflowWorkbenchPage.tsx")
    assert workbench.count(">新建 Workflow Definition</button>") == 1
    assert workbench.count(">创建新工作流</button>") == 1
    assert "<h2>选择 Workflow Definition</h2>" in workbench
    assert "DAG、精确资源绑定、digest、消费者与历史会显示在这里。" in workbench
