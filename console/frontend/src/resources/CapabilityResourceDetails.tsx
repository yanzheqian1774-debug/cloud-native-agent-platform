import type {ResourceKind,ResourceRevision,SkillMcpResource} from "../api/skillMcpResources";

type SkillOperationPreview={name:string;executorId?:string;executorRevision?:string;sideEffectClass?:string};
const record=(value:unknown):value is Record<string,unknown>=>Boolean(value)&&typeof value==="object"&&!Array.isArray(value);
function skillOperations(revision:ResourceRevision|undefined):SkillOperationPreview[]{
  const operations=(revision?.content as Record<string,unknown>|undefined)?.operations;
  if(!Array.isArray(operations))return [];
  return operations.flatMap(value=>record(value)&&typeof value.name==="string"?[{name:value.name,executorId:typeof value.executorId==="string"?value.executorId:undefined,executorRevision:typeof value.executorRevision==="string"?value.executorRevision:undefined,sideEffectClass:typeof value.sideEffectClass==="string"?value.sideEffectClass:undefined}]:[]);
}

export function CapabilityResourceDetails({kind,resource}:{kind:ResourceKind;resource:SkillMcpResource}){
  const exactRevision=resource.revisions.find(item=>item.revisionId===resource.currentDraftRevisionId)
    ??resource.revisions.find(item=>item.revisionId===resource.publishedRevisionId)
    ??resource.revisions.at(-1);
  const operations=kind==="skill"?skillOperations(exactRevision):[];
  const tools=kind==="mcp"?(resource.discoverySnapshots.at(-1)?.catalog.tools??[]):[];
  const sourceRelationships=resource.relationships.filter(item=>item.sourceResourceId||item.sourceRevisionId||item.sourceDigest);
  return <section className="capability-resource-identity" aria-label="正式资源身份与能力">
    <header><div><p className="eyebrow">正式资源身份</p><h3>{kind==="skill"?"Skill Definition":"MCP Server"}</h3></div></header>
    <dl className="capability-identity-grid"><div><dt>规范资源 ID</dt><dd><code>{resource.resourceId}</code></dd></div><div><dt>当前详情 revision</dt><dd><code>{exactRevision?.revisionId??"NO_REVISION"}</code></dd></div><div><dt>当前 Draft revision</dt><dd><code>{resource.currentDraftRevisionId??"NO_CURRENT_DRAFT"}</code></dd></div><div><dt>已发布 revision</dt><dd><code>{resource.publishedRevisionId??"NOT_PUBLISHED"}</code></dd></div><div><dt>Revision digest</dt><dd><code>{exactRevision?.digest??"NO_DIGEST"}</code></dd></div><div><dt>Aggregate version</dt><dd>{resource.aggregateVersion}</dd></div></dl>
    <div className="capability-taxonomy">
      <section aria-label={`${kind.toUpperCase()} capabilities`}><h4>{kind==="skill"?"Skill capabilities":"MCP capabilities"}</h4>{exactRevision?.content.capabilities.length?<ul>{exactRevision.content.capabilities.map(capability=><li key={capability}><code>{capability}</code></li>)}</ul>:<p>未声明 capability。</p>}</section>
      {kind==="skill"?<section aria-label="Skill operations"><h4>Skill operations</h4>{operations.length?<ul>{operations.map(operation=><li key={operation.name}><strong>{operation.name}</strong><small>{[operation.sideEffectClass,operation.executorId,operation.executorRevision].filter(Boolean).join(" · ")}</small></li>)}</ul>:<p>当前 revision 未声明 operation；capability 不会被当作 operation 展示。</p>}</section>:<section aria-label="MCP tools"><h4>MCP Tools</h4>{tools.length?<ul>{tools.map(tool=><li key={tool.name}><strong>{tool.name}</strong><small>{tool.description??"暂无 Tool 说明"}</small></li>)}</ul>:<p>当前没有已发现的 Tool；capability 不会被当作 Tool 展示。</p>}</section>}
    </div>
    <section aria-label="Recorded source relationships" className="capability-source-relationships"><h4>Recorded source relationships</h4>{sourceRelationships.length?<ul>{sourceRelationships.map((relationship,index)=><li key={`${relationship.type}-${index}`}><strong>{relationship.type}</strong><dl><dt>Source resource</dt><dd><code>{relationship.sourceResourceId??"NOT_RECORDED"}</code></dd><dt>Source revision</dt><dd><code>{relationship.sourceRevisionId??"NOT_RECORDED"}</code></dd><dt>Source digest</dt><dd><code>{relationship.sourceDigest??"NOT_RECORDED"}</code></dd></dl></li>)}</ul>:<p>No source relationship is recorded by the backend for this resource.</p>}</section>
  </section>;
}
