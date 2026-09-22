import type {ResourceKind, SkillMcpResource} from "../api/skillMcpResources";
import "./CapabilityResourceDetails.css";

// Exact identity/source projection adapted from PR #168 (388b6e3).
// S04/M07: schema declarations are not availability or execution authorization.
const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);
const text = (value: unknown, fallback = "未声明") =>
  typeof value === "string" && value.length > 0 ? value : fallback;

export function SchemaDetails({label, schema}: {label: string; schema: unknown}) {
  if (!isRecord(schema)) return <section><h5>{label}</h5><p>未声明 Schema，不能推断输入输出兼容。</p></section>;
  const properties = isRecord(schema.properties) ? Object.entries(schema.properties) : [];
  const required = Array.isArray(schema.required) ? schema.required : [];
  return <section className="capability-schema"><h5>{label}</h5>
    {properties.length > 0 ? <div className="capability-schema-scroll" tabIndex={0} role="region" aria-label={`${label}字段`}><table><thead><tr><th>字段名称</th><th>类型</th><th>必填</th><th>说明</th></tr></thead><tbody>
      {properties.map(([name, value]) => <tr key={name}><td><code>{name}</code></td><td>{isRecord(value) ? text(value.type) : "未声明"}</td><td>{required.includes(name) ? "是" : "否"}</td><td>{isRecord(value) ? text(value.description, "暂无说明") : "暂无说明"}</td></tr>)}
    </tbody></table></div> : <p>没有可展开的对象字段；请查看完整 Schema。</p>}
    <details><summary>完整 Schema 与校验约束</summary><pre>{JSON.stringify(schema, null, 2)}</pre></details>
  </section>;
}

export function CapabilityResourceDetails({kind, resource}: {kind: ResourceKind; resource: SkillMcpResource}) {
  const revision = resource.revisions.find(item => item.revisionId === resource.currentDraftRevisionId)
    ?? resource.revisions.find(item => item.revisionId === resource.publishedRevisionId)
    ?? resource.revisions.at(-1);
  const content = revision?.content as Record<string, unknown> | undefined;
  const operations = kind === "skill" && Array.isArray(content?.operations) ? content.operations.filter(isRecord) : [];
  const snapshot = resource.discoverySnapshots.at(-1);
  const sources = resource.relationships.filter(item => item.sourceResourceId || item.sourceRevisionId || item.sourceDigest);
  return <section className="agent-section capability-resource-details" aria-label="精确资源与输入输出">
    <header><div><p className="eyebrow">资源准备</p><h3>精确版本与输入输出</h3></div></header>
    <dl className="capability-exact-grid">
      <div><dt>资源 ID</dt><dd><code>{resource.resourceId}</code></dd></div>
      <div><dt>当前展示修订</dt><dd><code>{revision?.revisionId ?? "暂无修订"}</code></dd></div>
      <div><dt>已发布修订</dt><dd><code>{resource.publishedRevisionId ?? "尚未发布"}</code></dd></div>
      <div><dt>当前修订摘要</dt><dd><code>{revision?.digest ?? "暂无摘要"}</code></dd></div>
    </dl>
    {revision?.revisionId === resource.currentDraftRevisionId && <p className="capability-draft-note">当前展示草稿。执行准备须另行固定已发布版本，并在派发前校验权限与可用性。</p>}
    {kind === "skill" ? <>
      <h4>已声明操作</h4>
      {operations.length ? operations.map(operation => <article key={text(operation.name)} className="capability-operation">
        <h4><code>{text(operation.name)}</code></h4><p>副作用：{operation.sideEffectClass === "READ_ONLY" ? "只读" : text(operation.sideEffectClass, "未知")}</p>
        <dl className="capability-exact-grid"><div><dt>执行器与修订</dt><dd><code>{text(operation.executorId)} · {text(operation.executorRevision)}</code></dd></div><div><dt>执行器配置摘要</dt><dd><code>{text(operation.executorConfigurationDigest)}</code></dd></div></dl>
        <div className="capability-schema-grid"><SchemaDetails label="操作输入" schema={operation.inputSchema}/><SchemaDetails label="操作输出" schema={operation.outputSchema}/></div>
      </article>) : <p>当前修订未声明受管操作。能力标签不能代替可派发操作。</p>}
      <details><summary>资源级 Schema</summary><div className="capability-schema-grid"><SchemaDetails label="资源输入" schema={content?.inputSchema}/><SchemaDetails label="资源输出" schema={content?.outputSchema}/></div></details>
    </> : <>
      <h4>发现快照中的工具</h4><p>已发现不等于已选择、已授权或支持只读执行。</p>
      {snapshot ? <><dl className="capability-exact-grid"><div><dt>发现快照</dt><dd><code>{snapshot.snapshotId}</code></dd></div><div><dt>快照摘要</dt><dd><code>{snapshot.digest}</code></dd></div></dl>
        {snapshot.catalog.tools.map(tool => <article key={tool.name} className="capability-operation"><h4><code>{tool.name}</code></h4><p>{tool.description ?? "暂无工具说明"}</p><SchemaDetails label="工具输入" schema={tool.inputSchema}/><p>当前发现契约未提供输出 Schema 或副作用声明，执行准备不能据此判定兼容或只读。</p></article>)}
        {!snapshot.catalog.tools.length && <p>快照中没有工具。</p>}
      </> : <p>暂无发现快照。</p>}
    </>}
    <details><summary>已记录的来源关系（{sources.length}）</summary>
      {sources.length ? <ul>{sources.map((source, index) => <li key={`${source.type}-${index}`}><strong>{source.type}</strong><dl className="capability-exact-grid"><div><dt>来源资源</dt><dd><code>{source.sourceResourceId ?? "未记录"}</code></dd></div><div><dt>来源修订</dt><dd><code>{source.sourceRevisionId ?? "未记录"}</code></dd></div><div><dt>来源摘要</dt><dd><code>{source.sourceDigest ?? "未记录"}</code></dd></div></dl></li>)}</ul> : <p>后端未记录来源关系。</p>}
    </details>
  </section>;
}
