import type {
  WorkflowExecutionDetail,
  WorkflowRunList,
} from "../types/workflow";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "";

export async function listWorkflows(): Promise<WorkflowRunList> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/workflows`,
  );

  if (!response.ok) {
    throw new Error(
      `Failed to load workflows: HTTP ${response.status}`,
    );
  }

  return response.json() as Promise<WorkflowRunList>;
}

export async function getWorkflow(
  namespace: string,
  name: string,
): Promise<WorkflowExecutionDetail> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/workflows/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}`,
  );

  if (!response.ok) {
    throw new Error(
      `Failed to load workflow: HTTP ${response.status}`,
    );
  }

  return response.json() as Promise<WorkflowExecutionDetail>;
}
