export type WorkflowPhase =
  | "Pending"
  | "Running"
  | "Succeeded"
  | "Failed";

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
