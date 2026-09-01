import type { AgentRevision } from "../api/agentDefinitions";

export function AgentVersionComparison({ revisions }: { revisions: AgentRevision[] }) {
  if(revisions.length<2)return null;const current=revisions.at(-1)!;const previous=revisions.at(-2)!;
  const bindings=(revision:AgentRevision)=>revision.content.bindings;
  return <section aria-label="Agent version comparison"><h3>Version comparison</h3><dl><dt>Predecessor</dt><dd className="technical-value">{previous.revisionId}</dd><dt>Successor</dt><dd className="technical-value">{current.revisionId}</dd><dt>Digest changed</dt><dd>{previous.digest===current.digest?"No":"Yes — exact review required"}</dd><dt>Skill bindings</dt><dd>{bindings(previous).skills.length} → {bindings(current).skills.length}</dd><dt>MCP tool bindings</dt><dd>{bindings(previous).mcpTools.length} → {bindings(current).mcpTools.length}</dd><dt>Knowledge bindings</dt><dd>{bindings(previous).knowledge.length} → {bindings(current).knowledge.length}</dd></dl></section>;
}
