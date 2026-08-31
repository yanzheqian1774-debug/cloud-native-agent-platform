import type { ResourceProjection } from "../api/skillMcpResources";

export function SkillMcpTechnicalProjection({
  projection,
}: {
  projection: ResourceProjection;
}) {
  const technical = projection.technicalProjection as {
    resourceId: string;
    namespace: string;
    securityDomain: string;
    aggregateVersion: number;
    publishedRevisionId: string | null;
    revisionDigests: Array<{
      revisionId: string;
      digest: string;
      state: string;
    }>;
    limitations: string[];
  };
  return (
    <section className="agent-technical" aria-label="Technical projection">
      <header>
        <p className="eyebrow">Canonical backend projection</p>
        <h3>Technical inspection</h3>
      </header>
      <dl>
        <dt>Canonical identity</dt>
        <dd>{technical.resourceId}</dd>
        <dt>Scope</dt>
        <dd>
          {technical.namespace} / {technical.securityDomain}
        </dd>
        <dt>Aggregate version</dt>
        <dd>{technical.aggregateVersion}</dd>
        <dt>Published revision</dt>
        <dd>{technical.publishedRevisionId ?? "Not published"}</dd>
      </dl>
      <h4>Revision digests</h4>
      <ul>
        {technical.revisionDigests.map((item) => (
          <li key={item.revisionId}>
            <strong>{item.state}</strong> <code>{item.digest}</code>
          </li>
        ))}
      </ul>
      <p className="agent-limitations">{technical.limitations.join(" · ")}</p>
    </section>
  );
}
