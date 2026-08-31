import type { KnowledgeProjection } from "../api/knowledgeResources";

export function KnowledgeTechnicalProjection({ projection }: { projection: KnowledgeProjection }) {
  const technical = projection.technicalProjection;
  const knowledge = projection.knowledge;
  return <section aria-label="Knowledge Technical View" className="agent-technical">
    <p className="eyebrow">Technical View · same canonical object</p>
    <h3>Authority and derived index</h3>
    <dl>
      <dt>Knowledge Pack identity</dt><dd className="technical-value">{String(technical.knowledgeId)}</dd>
      <dt>Scope</dt><dd className="technical-value">{String(technical.namespace)} / {String(technical.securityDomain)}</dd>
      <dt>Aggregate version</dt><dd>{String(technical.aggregateVersion)}</dd>
      <dt>Published revision</dt><dd className="technical-value">{String(technical.publishedRevisionId ?? "NOT_PUBLISHED")}</dd>
      <dt>Active index snapshot</dt><dd className="technical-value">{String(technical.activeIndexSnapshotId ?? "NOT_INDEXED")}</dd>
    </dl>
    <h4>Quality contract</h4>
    <dl>
      <dt>Lexical tokenizer</dt><dd className="technical-value">CJK_BIGRAM_V1</dd>
      <dt>Hybrid fusion</dt><dd className="technical-value">RECIPROCAL_RANK_FUSION · k=60 · absent ranks=0</dd>
      <dt>Summary provider</dt><dd className="technical-value">DETERMINISTIC_EXTRACTIVE_V1 · model NOT_APPLICABLE</dd>
      <dt>Quality schema</dt><dd className="technical-value">0005 · final chain validation pending migration 0004</dd>
    </dl>
    <h4>Immutable revision digests</h4>
    <table><thead><tr><th>State</th><th>Revision</th><th>Digest</th></tr></thead><tbody>{knowledge.revisions.map((revision) => <tr key={revision.revisionId}><td><span className={`status ${revision.state === "PUBLISHED" ? "success" : "neutral"}`}>{revision.state}</span></td><td className="technical-value">{revision.revisionId}</td><td className="technical-value">sha256:{revision.digest}</td></tr>)}</tbody></table>
    <h4>Index snapshot history</h4>
    {knowledge.indexSnapshots.length === 0 ? <p>No derived index snapshot recorded.</p> : <table><thead><tr><th>Status</th><th>Snapshot</th><th>Index digest</th></tr></thead><tbody>{knowledge.indexSnapshots.map((snapshot) => <tr key={snapshot.snapshotId}><td><span className="status success">{snapshot.status}</span></td><td className="technical-value">{snapshot.snapshotId}</td><td className="technical-value">sha256:{snapshot.indexDigest}</td></tr>)}</tbody></table>}
    <p className="qto-disclosure">PostgreSQL owns lifecycle, identity and digests. Qdrant contains derived vectors only and cannot repair missing PostgreSQL authority.</p>
  </section>;
}
