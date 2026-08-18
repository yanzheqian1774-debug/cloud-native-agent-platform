export const messages = {
  "en-US": {
    "app.name": "AgentOS Console",

    "nav.workflowRuns": "Workflow Runs",

    "workflow.title": "Workflow Runs",
    "workflow.description":
      "Inspect multi-agent workflow executions running on Kubernetes.",
    "workflow.workflow": "Workflow",
    "workflow.namespace": "Namespace",
    "workflow.status": "Status",
    "workflow.tasks": "Tasks",
    "workflow.created": "Created",
    "workflow.started": "Started",
    "workflow.completed": "Completed",
    "workflow.empty": "No workflow executions found.",
    "workflow.noNodes": "No workflow nodes found.",
    "workflow.loading": "Loading workflows...",
    "workflow.loadingDetail": "Loading workflow...",
    "workflow.loadFailed": "Failed to load workflows",
    "workflow.notFound": "Workflow not found",
    "workflow.invalidRoute": "Invalid workflow route",

    "workflow.executionDag": "Execution DAG",
    "workflow.executionDag.description":
      "Workflow topology and current node execution state.",

    "workflow.dependencies": "Dependencies",
    "workflow.dependencies.description":
      "Control and data dependencies declared by the workflow.",

    "workflow.source": "Source",
    "workflow.target": "Target",
    "workflow.type": "Type",

    "node.inspector": "Node Inspector",
    "node.agent": "Agent",
    "node.task": "Task",
    "node.attempts": "Attempts",
    "node.timeout": "Timeout",
    "node.started": "Started",
    "node.completed": "Completed",

    "node.identity": "Identity",
    "node.execution": "Execution",
    "node.input": "Input",
    "node.output": "Output",
    "node.failure": "Failure",

    "node.declaredInput": "Declared Input",
    "node.resolvedInput": "Resolved Input",
    "node.upstreamResults": "Upstream Results",
    "node.result": "Result",
    "node.reason": "Reason",
    "node.retryable": "Retryable",
    "node.message": "Message",
    "node.noExecution": "No task execution",

    "phase.Pending": "Pending",
    "phase.Running": "Running",
    "phase.Succeeded": "Succeeded",
    "phase.Failed": "Failed",
    "phase.TimedOut": "Timed Out",
    "phase.Skipped": "Skipped",

    "reason.InternalError": "Internal Error",
    "reason.RateLimited": "Rate Limited",
    "reason.UpstreamUnavailable": "Upstream Unavailable",
    "reason.NetworkError": "Network Error",
    "reason.UpstreamTimeout": "Upstream Timeout",
    "reason.ExecutionTimeout": "Execution Timeout",
    "reason.InvalidRequest": "Invalid Request",
    "reason.AuthenticationError": "Authentication Error",
    "reason.AuthorizationError": "Authorization Error",
    "reason.AgentNotFound": "Agent Not Found",
    "reason.InvalidResponse": "Invalid Response",
    "reason.DependencyFailed": "Dependency Failed",
    "reason.DependencySkipped": "Dependency Skipped",
    "reason.InternalErrorFallback": "Internal Error",

    "edge.control": "control",
    "edge.data": "data",

    "attempt.one": "attempt",
    "attempt.other": "attempts",

    "common.yes": "Yes",
    "common.no": "No",
    "common.close": "Close",
    "common.notAvailable": "—",
  },

  "zh-CN": {
    "app.name": "AgentOS 控制台",

    "nav.workflowRuns": "工作流运行",

    "workflow.title": "工作流运行",
    "workflow.description":
      "查看运行在 Kubernetes 上的多 Agent 工作流执行情况。",
    "workflow.workflow": "工作流",
    "workflow.namespace": "命名空间",
    "workflow.status": "状态",
    "workflow.tasks": "任务数",
    "workflow.created": "创建时间",
    "workflow.started": "开始时间",
    "workflow.completed": "完成时间",
    "workflow.empty": "暂无工作流执行记录。",
    "workflow.noNodes": "未找到工作流节点。",
    "workflow.loading": "正在加载工作流...",
    "workflow.loadingDetail": "正在加载工作流...",
    "workflow.loadFailed": "工作流加载失败",
    "workflow.notFound": "未找到工作流",
    "workflow.invalidRoute": "无效的工作流地址",

    "workflow.executionDag": "执行 DAG",
    "workflow.executionDag.description":
      "工作流拓扑及各节点当前执行状态。",

    "workflow.dependencies": "依赖关系",
    "workflow.dependencies.description":
      "工作流声明的控制依赖与数据依赖。",

    "workflow.source": "来源",
    "workflow.target": "目标",
    "workflow.type": "类型",

    "node.inspector": "节点详情",
    "node.agent": "Agent",
    "node.task": "任务",
    "node.attempts": "尝试次数",
    "node.timeout": "超时时间",
    "node.started": "开始时间",
    "node.completed": "完成时间",

    "node.identity": "节点信息",
    "node.execution": "执行信息",
    "node.input": "输入",
    "node.output": "输出",
    "node.failure": "失败信息",

    "node.declaredInput": "声明输入",
    "node.resolvedInput": "解析后输入",
    "node.upstreamResults": "上游结果",
    "node.result": "执行结果",
    "node.reason": "原因",
    "node.retryable": "可重试",
    "node.message": "错误信息",
    "node.noExecution": "暂无任务执行",

    "phase.Pending": "等待中",
    "phase.Running": "运行中",
    "phase.Succeeded": "成功",
    "phase.Failed": "失败",
    "phase.TimedOut": "已超时",
    "phase.Skipped": "已跳过",

    "reason.InternalError": "内部错误",
    "reason.RateLimited": "请求限流",
    "reason.UpstreamUnavailable": "上游服务不可用",
    "reason.NetworkError": "网络错误",
    "reason.UpstreamTimeout": "上游请求超时",
    "reason.ExecutionTimeout": "执行超时",
    "reason.InvalidRequest": "无效请求",
    "reason.AuthenticationError": "认证失败",
    "reason.AuthorizationError": "无访问权限",
    "reason.AgentNotFound": "Agent 不存在",
    "reason.InvalidResponse": "无效响应",
    "reason.DependencyFailed": "依赖任务失败",
    "reason.DependencySkipped": "依赖任务已跳过",
    "reason.InternalErrorFallback": "内部错误",

    "edge.control": "控制",
    "edge.data": "数据",

    "attempt.one": "次尝试",
    "attempt.other": "次尝试",

    "common.yes": "是",
    "common.no": "否",
    "common.close": "关闭",
    "common.notAvailable": "—",
  },
} as const;

export type Locale = keyof typeof messages;

export type MessageKey =
  keyof (typeof messages)["en-US"];

export const DEFAULT_LOCALE: Locale = "en-US";
