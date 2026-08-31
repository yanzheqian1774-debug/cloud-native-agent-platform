export type AgentContent = {
  title: string;
  duties: string[];
  data: string[];
  knowledge: string[];
  skills: string[];
  capabilities: string[];
  runtimes: string[];
};

export type AgentRevision = {
  revisionId: string;
  predecessorRevisionId: string | null;
  state: string;
  digest: string;
  content: AgentContent;
  createdAt: string;
};

export type AgentDefinition = {
  definitionId: string;
  name: string;
  aggregateVersion: number;
  lifecycleState: string;
  enabled: boolean;
  archived: boolean;
  currentDraftRevisionId: string | null;
  publishedRevisionId: string | null;
  revisions: AgentRevision[];
  reviews: Array<{ reviewId: string; digest: string; decision: string }>;
  facts: Array<{ factId: string; event: string; recordedAt: string }>;
  relationships: unknown[];
  limitations: string[];
};

export type AgentProjection = {
  definition: AgentDefinition;
  productProjection: Record<string, unknown>;
  technicalProjection: Record<string, unknown>;
};

export class AgentDefinitionRequestError extends Error {
  reasonCode: string;
  status: number;
  constructor(reasonCode: string, status: number) {
    super(reasonCode);
    this.reasonCode = reasonCode;
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: { Accept: "application/json", "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new AgentDefinitionRequestError("AGENT_DEFINITION_NETWORK_UNAVAILABLE", 503);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new AgentDefinitionRequestError(body?.detail?.reasonCode ?? "AGENT_DEFINITION_UNAVAILABLE", response.status);
  return body as T;
}

const root = "/api/internal/v0.2.2/agent-definitions";
export const listAgentDefinitions = () => request<AgentDefinition[]>(root);
export const getAgentDefinition = (id: string) => request<AgentProjection>(`${root}/${encodeURIComponent(id)}`);
export const createAgentDefinition = (name: string, content: AgentContent) => request<AgentProjection>(root, { method: "POST", body: JSON.stringify({ name, content }) });
export const validateAgentDefinition = (id: string, expectedVersion: number) => request<AgentProjection>(`${root}/${encodeURIComponent(id)}/validation`, { method: "POST", body: JSON.stringify({ expectedVersion }) });
export const reviewAgentDefinition = (id: string, expectedVersion: number, digest: string) => request<AgentProjection>(`${root}/${encodeURIComponent(id)}/reviews`, { method: "POST", body: JSON.stringify({ expectedVersion, digest, decision: "APPROVE", reason: "Human verified the exact digest for publication" }) });
export const publishAgentDefinition = (id: string, expectedVersion: number, digest: string, reviewId: string) => request<AgentProjection>(`${root}/${encodeURIComponent(id)}/publications`, { method: "POST", body: JSON.stringify({ expectedVersion, digest, reviewId }) });
export const lifecycleAgentDefinition = (id: string, action: string, expectedVersion: number) => request<AgentProjection>(`${root}/${encodeURIComponent(id)}/${action.toLowerCase()}`, { method: "POST", body: JSON.stringify({ expectedVersion, reason: `Human requested ${action}` }) });
export const successorAgentDefinition = (id: string, expectedVersion: number) => request<AgentProjection>(`${root}/${encodeURIComponent(id)}/successors`, { method: "POST", body: JSON.stringify({ expectedVersion }) });
