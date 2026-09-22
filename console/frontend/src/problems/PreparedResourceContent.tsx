import {SchemaDetails} from "../resources/CapabilityResourceDetails";
const record=(v:unknown):Record<string,unknown>=>v&&typeof v==="object"&&!Array.isArray(v)?v as Record<string,unknown>:{};
const text=(v:unknown)=>typeof v==="string"?v:"未声明";
const list=(v:unknown)=>Array.isArray(v)?v:[];
const operationNames:Record<string,string>={"read-source":"读取合成来源","validate":"校验字段","summarize":"汇总成本","analyze":"分析差异","recommend":"形成建议","report":"生成报告"};

/** Display only the exact owner response; no readiness or invocation inference. */
export function PreparedResourceContent({kind,content:c}:{kind:string;content:Record<string,unknown>}){
 return <div className="prepared-resource-content">
  {kind==="skill"&&<><p>{text(c.description)}</p><p>业务规则：{text(c.instructions)}</p><h3>操作与输入输出契约</h3>{list(c.operations).map((value,index)=>{const op=record(value);return <details key={index}><summary>{operationNames[text(op.name)]??text(op.name)} · {op.sideEffectClass==="READ_ONLY"?"只读":text(op.sideEffectClass)}</summary><dl><dt>操作标识</dt><dd>{text(op.name)}</dd><dt>执行器 / 修订</dt><dd>{text(op.executorId)} / {text(op.executorRevision)}</dd><dt>配置摘要</dt><dd>{text(op.executorConfigurationDigest)}</dd></dl><div className="capability-schema-grid"><SchemaDetails label="操作输入" schema={op.inputSchema}/><SchemaDetails label="操作输出" schema={op.outputSchema}/></div></details>})}{!list(c.operations).length&&<p>没有已声明操作；不能据此判断可派发。</p>}</>}
  {kind==="runtime"&&<><h3>期望运行配置</h3><dl><dt>运行提供者</dt><dd>{text(c.provider)}</dd><dt>隔离方式</dt><dd>{c.isolation==="NAMESPACE"?"命名空间隔离":text(c.isolation)}</dd><dt>状态模式</dt><dd>{c.stateMode==="STATELESS"?"无状态":text(c.stateMode)}</dd><dt>CPU 请求 / 上限</dt><dd>{text(record(c.resources).cpuRequest)} / {text(record(c.resources).cpuLimit)}</dd><dt>内存请求 / 上限</dt><dd>{text(record(c.resources).memoryRequest)} / {text(record(c.resources).memoryLimit)}</dd></dl><p>这里展示配置声明；实际分配、准入及运行结果须在执行记录中核对。</p></>}
  {kind==="agent"&&<><h3>职责与业务边界</h3><p>{text(c.businessPurpose)}</p><ul>{list(c.duties).map((v,i)=><li key={i}>{text(v)}</li>)}</ul><h4>声明的能力</h4><ul>{list(c.capabilities).map((v,i)=><li key={i}>{operationNames[text(v)]??text(v)}</li>)}</ul><p>职责定义与实际员工实例、分工及运行分别记录。</p></>}
  {kind==="knowledge"&&<><h3>来源与原文</h3><dl><dt>来源 ID</dt><dd>{text(record(c.source).sourceId)}</dd><dt>来源说明</dt><dd>{text(record(c.source).provenance)}</dd><dt>来源类型</dt><dd>{text(record(c.source).kind)}</dd></dl>{list(c.documents).map((value,i)=>{const doc=record(value);return <section key={i}><h4>{text(doc.documentId)} · 版本 {text(doc.documentVersion)}</h4><p>原文摘要：<code>{text(doc.contentDigest)}</code></p>{list(doc.chunks).map((chunk,j)=><details key={j}><summary>只读原文片段 {j+1}</summary><pre>{text(record(chunk).content)}</pre></details>)}</section>})}<p>来源原文只读；资料发布不表示检索、任务调用或真实业务验证已经完成。</p></>}
 </div>;
}
