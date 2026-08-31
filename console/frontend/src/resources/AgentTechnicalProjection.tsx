import type { AgentProjection } from "../api/agentDefinitions";

export function AgentTechnicalProjection({ projection }: { projection: AgentProjection }) {
  const technical = projection.technicalProjection;
  return <section className="agent-technical" aria-label="Agent Definition Technical View">
    <p className="eyebrow">Technical View · same canonical object</p>
    <h3>Identity and revision bindings</h3>
    <dl>
      <dt>Definition identity</dt><dd className="technical-value">{String(technical.definitionId)}</dd>
      <dt>Scope</dt><dd className="technical-value">{String(technical.namespace)} / {String(technical.securityDomain)}</dd>
      <dt>Aggregate version</dt><dd>{String(technical.aggregateVersion)}</dd>
      <dt>Published revision</dt><dd className="technical-value">{String(technical.publishedRevisionId ?? "NOT_PUBLISHED")}</dd>
    </dl>
    <h4>Immutable revision digests</h4>
    <ul>{(technical.revisionDigests as Array<{revisionId:string;digest:string;state:string}>).map(item=><li key={item.revisionId}><strong>{item.state}</strong><span className="technical-value">{item.revisionId}</span><span className="technical-value">sha256:{item.digest}</span></li>)}</ul>
    <p className="qto-disclosure">Publication grants governed discovery and matching eligibility only. It does not authorize execution.</p>
  </section>;
}
