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
      <h4>Operational inspection</h4>
      <dl>
        <dt>Saved tests / results</dt>
        <dd>{projection.resource.savedTests.length} / {projection.resource.testResults.length}</dd>
        <dt>Discovery snapshots / drift</dt>
        <dd>{projection.resource.discoverySnapshots.length} / {projection.resource.driftRecords.length}</dd>
        <dt>Governed Tool selections</dt>
        <dd>{projection.resource.toolSelections.length}</dd>
        <dt>Invocation Evidence</dt>
        <dd>{projection.resource.invocations.length} record(s), credential material not recorded</dd>
      </dl>
      {projection.resource.kind === "mcp" && <><h4>Exact MCP binding facts</h4><dl><dt>Endpoint</dt><dd><code>{projection.resource.revisions.at(-1)?.content.endpoint ?? "NOT_CONFIGURED"}</code></dd><dt>Credential reference</dt><dd><code>{projection.resource.revisions.at(-1)?.content.secretReference ?? "NOT_CONFIGURED"}</code> (external reference only)</dd><dt>Trust configuration</dt><dd>NOT_EXPOSED_BY_CURRENT_API</dd><dt>Latest discovery snapshot</dt><dd><code>{projection.resource.discoverySnapshots.at(-1)?.snapshotId ?? "NOT_DISCOVERED"}</code></dd><dt>Selected tools</dt><dd>{projection.resource.toolSelections.at(-1)?.toolNames.join(", ") || "NOT_SELECTED"}</dd></dl><h4>Discovered input schemas</h4><ul>{projection.resource.discoverySnapshots.at(-1)?.catalog.tools.map(tool=><li key={tool.name}><strong>{tool.name}</strong> <code>{JSON.stringify(tool.inputSchema??{})}</code></li>)}</ul><p>连接、发现、选择与管理调用是不同事实；均不授予 Attempt-level invocation authority。</p></>}
      <p className="agent-limitations">{technical.limitations.join(" · ")}</p>
    </section>
  );
}
