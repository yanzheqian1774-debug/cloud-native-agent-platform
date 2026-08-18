export type WorkflowPhase =
  | "Pending"
  | "Running"
  | "Succeeded"
  | "Failed";

export type NodePhase =
  | "Pending"
  | "Running"
  | "Succeeded"
  | "Failed"
  | "TimedOut"
  | "Skipped";

export type EdgeType =
  | "control"
  | "data";

export interface WorkflowRunSummary {
  name: string;
  namespace: string;
  phase: WorkflowPhase;
  taskCount: number;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string | null;
}

export interface WorkflowRunList {
  items: WorkflowRunSummary[];
}

export interface AgentReference {
  name: string;
}

export interface UpstreamResult {
  task: string;
  result: string;
}

export interface NodeExecution {
  phase: NodePhase;
  taskRef: string | null;
  declaredInput: string;
  resolvedInput: string | null;
  upstreamResults: UpstreamResult[];
  result: string | null;
  attempts: number | null;
  startedAt: string | null;
  completedAt: string | null;
  reason: string | null;
  message: string | null;
  retryable: boolean | null;
}

export interface WorkflowNode {
  name: string;
  agent: AgentReference;
  dependsOn: string[];
  inputFrom: string[];
  timeoutSeconds: number;
  execution: NodeExecution;
}

export interface WorkflowEdge {
  source: string;
  target: string;
  type: EdgeType;
}

export interface WorkflowExecutionDetail {
  name: string;
  namespace: string;
  phase: WorkflowPhase;
  taskCount: number;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string | null;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}
