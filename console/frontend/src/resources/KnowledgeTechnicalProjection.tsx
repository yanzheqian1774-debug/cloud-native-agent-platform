import type { KnowledgeProjection } from "../api/knowledgeResources";

export function KnowledgeTechnicalProjection({ projection }: { projection: KnowledgeProjection }) {
  const technical = projection.technicalProjection;
  const knowledge = projection.knowledge;
  return <section aria-label="Knowledge Technical View" className="agent-technical">
    <p className="eyebrow">技术视图 · 同一规范对象</p>
    <h3>权威记录与派生索引</h3>
    <dl>
      <dt>知识包ID</dt><dd className="technical-value">{String(technical.knowledgeId)}</dd>
      <dt>作用域</dt><dd className="technical-value">{String(technical.namespace)} / {String(technical.securityDomain)}</dd>
      <dt>聚合版本</dt><dd>{String(technical.aggregateVersion)}</dd>
      <dt>已发布修订</dt><dd className="technical-value">{String(technical.publishedRevisionId ?? "NOT_PUBLISHED")}</dd>
      <dt>生效索引快照</dt><dd className="technical-value">{String(technical.activeIndexSnapshotId ?? "NOT_INDEXED")}</dd>
    </dl>
    <h4>质量契约</h4>
    <dl>
      <dt>词法分词器</dt><dd className="technical-value">CJK_BIGRAM_V1</dd>
      <dt>混合排序</dt><dd className="technical-value">RECIPROCAL_RANK_FUSION · k=60 · absent ranks=0</dd>
      <dt>摘要提供者</dt><dd className="technical-value">DETERMINISTIC_EXTRACTIVE_V1 · model NOT_APPLICABLE</dd>
      <dt>质量存储边界</dt><dd className="technical-value">质量记录由后端持久化；本页不判定迁移验收状态</dd>
    </dl>
    <h4>不可变修订摘要</h4>
    <table><thead><tr><th>状态</th><th>修订</th><th>摘要</th></tr></thead><tbody>{knowledge.revisions.map((revision) => <tr key={revision.revisionId}><td><span className={`status ${revision.state === "PUBLISHED" ? "success" : "neutral"}`}>{revision.state}</span></td><td className="technical-value">{revision.revisionId}</td><td className="technical-value">sha256:{revision.digest}</td></tr>)}</tbody></table>
    <h4>索引快照历史</h4>
    {knowledge.indexSnapshots.length === 0 ? <p>尚无派生索引快照。</p> : <table><thead><tr><th>状态</th><th>快照</th><th>索引摘要</th></tr></thead><tbody>{knowledge.indexSnapshots.map((snapshot) => <tr key={snapshot.snapshotId}><td><span className="status success">{snapshot.status}</span></td><td className="technical-value">{snapshot.snapshotId}</td><td className="technical-value">sha256:{snapshot.indexDigest}</td></tr>)}</tbody></table>}
    <p className="qto-disclosure">PostgreSQL持有生命周期、身份和摘要。Qdrant仅包含派生向量，不能修复缺失的SQL权威记录。</p>
  </section>;
}
