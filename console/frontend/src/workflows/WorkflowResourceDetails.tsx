import type {ExactReference,WorkflowTask} from "../api/workflowDefinitions";
import type {WorkflowSkillOperationEntry} from "../api/workflowSkillOperations";

const missing="未接通正式详情";
const referenceKey=(reference:ExactReference)=>`${reference.kind}:${reference.resourceId}:${reference.revisionId}:${reference.digest??"NO_DIGEST"}`;

export function WorkflowResourceDetails({task,runtimeProfile,directory,directoryState}:{task:WorkflowTask;runtimeProfile:ExactReference;directory:WorkflowSkillOperationEntry[];directoryState:"LOADING"|"READY"|"UNAVAILABLE"}){
  const references=[runtimeProfile,...task.references];
  return <section className="workflow-designer__resources" aria-label={`步骤 ${task.taskId} 的资源详情`}>
    <header><p className="eyebrow">Resource details</p><h4>精确资源与 operation</h4></header>
    <p>身份来自 Workflow GET 与正式 Skill GET；页面不计算或改写 digest。</p>
    <div className="workflow-designer__resource-list">{references.map(reference=>{
      const matches=reference.kind==="SKILL"?directory.filter(entry=>entry.skillId===reference.resourceId&&entry.skillRevisionId===reference.revisionId):[];
      const name=matches[0]?.skillName;
      return <article key={referenceKey(reference)}>
        <strong>{name??reference.kind}</strong><span className="binding-status verified">{reference.kind}</span>
        <dl><div><dt>资源名称</dt><dd>{name??missing}</dd></div><div><dt>资源 ID</dt><dd className="technical-value">{reference.resourceId}</dd></div><div><dt>Revision</dt><dd className="technical-value">{reference.revisionId}</dd></div><div><dt>Digest</dt><dd className="technical-value">{reference.digest??"GET 未返回"}</dd></div></dl>
        {reference.kind!=="SKILL"&&<p className="workflow-designer__unavailable">当前已授权前端读取未提供该资源的名称、schema 或约束；未建立绕过 BFF/认证的读取通道。</p>}
        {reference.kind==="SKILL"&&directoryState!=="READY"&&<p className="workflow-designer__unavailable">正式 Skill operation 目录{directoryState==="LOADING"?"读取中":"不可用"}；保留 Workflow GET 返回的精确身份。</p>}
        {matches.map(entry=><details key={entry.operation.name}><summary>Operation · {entry.operation.name}</summary><dl><div><dt>Input schema</dt><dd><pre>{JSON.stringify(entry.operation.inputSchema,null,2)}</pre></dd></div><div><dt>Output schema</dt><dd><pre>{JSON.stringify(entry.operation.outputSchema,null,2)}</pre></dd></div><div><dt>Side effect</dt><dd>{entry.operation.sideEffectClass}</dd></div><div><dt>Executor</dt><dd className="technical-value">{entry.operation.executorId} · {entry.operation.executorRevision} · {entry.operation.executorConfigurationDigest}</dd></div><div><dt>I/O constraints</dt><dd>{entry.operation.ioLimits.maxInputBytes} / {entry.operation.ioLimits.maxOutputBytes} bytes · {entry.operation.ioLimits.timeoutMs} ms</dd></div><div><dt>Policy</dt><dd className="technical-value">{entry.operation.sideEffectPolicy.policyId} · {entry.operation.sideEffectPolicy.policyRevision} · {entry.operation.sideEffectPolicy.policyDigest}</dd></div></dl></details>)}
      </article>})}</div>
    {task.skillOperationBindings?.map(binding=><article className="workflow-designer__binding-identity" key={`${binding.skillId}:${binding.skillRevisionId}:${binding.operation}`}><strong>已保存的 Skill operation binding</strong><code>{binding.skillId}</code><code>{binding.skillRevisionId}</code><code>{binding.skillDigest}</code><code>{binding.operation}</code></article>)}
    <p className="binding-authority-note">资源绑定有效仅表示 Definition 配置可校验，不表示执行成功，也不授予发布后的执行权限。</p>
  </section>;
}
