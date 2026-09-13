import {useMemo,useState} from "react";
import {referenceSupportsBinding,type WorkflowTask} from "../api/workflowDefinitions";
import type {WorkflowSkillOperationEntry} from "../api/workflowSkillOperations";

const missing="未提供";
type DirectoryState="LOADING"|"READY"|"UNAVAILABLE";

const key=(entry:WorkflowSkillOperationEntry)=>`${entry.skillId}:${entry.skillRevisionId}:${entry.skillDigest}:${entry.operation.name}`;
const matches=(entry:WorkflowSkillOperationEntry,binding:NonNullable<WorkflowTask["skillOperationBindings"]>[number])=>entry.skillId===binding.skillId&&entry.skillRevisionId===binding.skillRevisionId&&entry.skillDigest===binding.skillDigest&&entry.operation.name===binding.operation;

function OperationDetails({entry}:{entry?:WorkflowSkillOperationEntry}){
  if(!entry)return <dl><div><dt>Input schema</dt><dd>{missing}（正式 operation 目录未返回精确匹配）</dd></div><div><dt>Output schema</dt><dd>{missing}（正式 operation 目录未返回精确匹配）</dd></div><div><dt>Operation constraints</dt><dd>{missing}（不使用 revision 级声明冒充 operation 约束）</dd></div></dl>;
  const operation=entry.operation;
  return <dl><div><dt>Input schema</dt><dd><pre className="technical-value">{JSON.stringify(operation.inputSchema,null,2)}</pre></dd></div><div><dt>Output schema</dt><dd><pre className="technical-value">{JSON.stringify(operation.outputSchema,null,2)}</pre></dd></div><div><dt>Side-effect class</dt><dd>{operation.sideEffectClass}</dd></div><div><dt>Executor identity</dt><dd className="technical-value">{operation.executorId} · {operation.executorRevision} · {operation.executorConfigurationDigest}</dd></div><div><dt>Side-effect policy</dt><dd className="technical-value">{operation.sideEffectPolicy.policyId} · {operation.sideEffectPolicy.policyRevision} · {operation.sideEffectPolicy.policyDigest}</dd></div><div><dt>I/O policy</dt><dd className="technical-value">{operation.ioLimits.policyId} · {operation.ioLimits.policyRevision}</dd></div><div><dt>Input / output bytes</dt><dd>{operation.ioLimits.maxInputBytes} / {operation.ioLimits.maxOutputBytes}</dd></div><div><dt>Depth / properties / timeout</dt><dd>{operation.ioLimits.maxObjectDepth} / {operation.ioLimits.maxProperties} / {operation.ioLimits.timeoutMs} ms</dd></div></dl>;
}

export function WorkflowSkillOperationBindingEditor({task,readOnly=false,directory=[],directoryState="UNAVAILABLE",directoryReason,onChange,isLocked=()=>false}:{task:WorkflowTask;readOnly?:boolean;directory?:WorkflowSkillOperationEntry[];directoryState?:DirectoryState;directoryReason?:string|null;onChange?:(task:WorkflowTask)=>void;isLocked?:()=>boolean}){
  const bindings=task.skillOperationBindings;
  const [skillId,setSkillId]=useState(""),[revisionId,setRevisionId]=useState(""),[operationName,setOperationName]=useState(""),[editingIndex,setEditingIndex]=useState<number|null>(null);
  const skills=useMemo(()=>Array.from(new Map(directory.map(entry=>[entry.skillId,entry])).values()),[directory]);
  const revisions=useMemo(()=>Array.from(new Map(directory.filter(entry=>entry.skillId===skillId).map(entry=>[entry.skillRevisionId,entry])).values()),[directory,skillId]);
  const operations=directory.filter(entry=>entry.skillId===skillId&&entry.skillRevisionId===revisionId);
  const selected=operations.find(entry=>entry.operation.name===operationName);
  const duplicate=Boolean(selected&&bindings?.some((binding,index)=>index!==editingIndex&&matches(selected,binding)));
  function reset(){if(isLocked())return;setSkillId("");setRevisionId("");setOperationName("");setEditingIndex(null)}
  function edit(index:number){if(isLocked())return;const binding=bindings?.[index];if(!binding)return;setEditingIndex(index);setSkillId(binding.skillId);setRevisionId(binding.skillRevisionId);setOperationName(binding.operation)}
  function apply(){if(isLocked()||!selected||!onChange||duplicate)return;const prior=editingIndex===null?null:bindings?.[editingIndex]??null,binding={skillId:selected.skillId,skillRevisionId:selected.skillRevisionId,skillDigest:selected.skillDigest,operation:selected.operation.name};const next=[...(bindings??[])];if(editingIndex===null)next.push(binding);else next[editingIndex]=binding;let references=task.references.filter(reference=>!prior||reference.kind!=="SKILL"||reference.resourceId!==prior.skillId||reference.revisionId!==prior.skillRevisionId||next.some(item=>item.skillId===prior.skillId&&item.skillRevisionId===prior.skillRevisionId));const selectedReference=references.find(reference=>reference.kind==="SKILL"&&reference.resourceId===selected.skillId&&reference.revisionId===selected.skillRevisionId);references=selectedReference?references.map(reference=>reference===selectedReference?{...reference,digest:selected.skillDigest}:reference):[...references,{kind:"SKILL" as const,resourceId:selected.skillId,revisionId:selected.skillRevisionId,digest:selected.skillDigest}];onChange({...task,references,skillOperationBindings:next});reset()}
  return <section className="workflow-skill-binding" aria-label={`步骤 ${task.taskId} 的 Skill operation 绑定`}>
    <header><div><p className="eyebrow">Skill operation binding</p><h4>步骤 {task.taskId} 的精确技能操作</h4></div><span className={`binding-status ${bindings?.length?"bound":"unbound"}`}>{bindings?.length?"已绑定":"未绑定"}</span></header>
    {!bindings?.length&&readOnly&&<div className="binding-unavailable" role="status"><strong>此版本没有 Skill operation binding</strong><p>历史版本保持未绑定；页面不会自动选择或补写。</p></div>}
    {bindings?.length?<ol className="workflow-skill-binding-list">{bindings.map((binding,index)=>{const entry=directory.find(candidate=>matches(candidate,binding)),supported=referenceSupportsBinding(task,binding),referenceIdentity=task.references.some(reference=>reference.kind==="SKILL"&&reference.resourceId===binding.skillId&&reference.revisionId===binding.skillRevisionId);return <li key={`${binding.skillId}:${binding.skillRevisionId}:${binding.operation}:${index}`}>
      <div className="binding-heading"><strong>{binding.operation}</strong><span className={`binding-status ${supported&&entry?"verified":"invalid"}`}>{!supported?(referenceIdentity?"SKILL reference digest 不一致":"缺少对应 SKILL reference"):entry?"目录身份已核对":"目录未核对"}</span></div>
      <dl><div><dt>Skill resource ID</dt><dd className="technical-value">{binding.skillId||missing}</dd></div><div><dt>Skill revision ID</dt><dd className="technical-value">{binding.skillRevisionId||missing}</dd></div><div><dt>Skill digest</dt><dd className="technical-value">{binding.skillDigest||missing}</dd></div><div><dt>Operation identity</dt><dd className="technical-value">{binding.operation||missing}</dd></div></dl><OperationDetails entry={entry}/>
      {!readOnly&&<div className="binding-edit-actions"><button type="button" disabled={directoryState!=="READY"||directory.length===0} onClick={()=>edit(index)}>显式更换此绑定</button><p className="binding-lock-note">当前契约不支持仅删除已有 binding；省略、null 或空集合都会被后端拒绝。</p></div>}
    </li>})}</ol>:null}
    {!readOnly&&<fieldset className="binding-picker" disabled={directoryState!=="READY"||directory.length===0}><legend>{editingIndex===null?"添加精确绑定":"替换精确绑定"}</legend>
      <label>Skill resource<select aria-label={`步骤 ${task.taskId} 选择 Skill`} value={skillId} onChange={event=>{if(isLocked())return;setSkillId(event.target.value);setRevisionId("");setOperationName("")}}><option value="">请选择已发布、启用且合格的 Skill</option>{skills.map(entry=><option key={entry.skillId} value={entry.skillId}>{entry.skillName} · {entry.skillId}</option>)}</select></label>
      <label>Skill revision<select aria-label={`步骤 ${task.taskId} 选择 Skill revision`} value={revisionId} onChange={event=>{if(isLocked())return;setRevisionId(event.target.value);setOperationName("")}}><option value="">请选择精确 revision</option>{revisions.map(entry=><option key={entry.skillRevisionId} value={entry.skillRevisionId}>{entry.skillRevisionId} · {entry.skillDigest}</option>)}</select></label>
      <label>Operation<select aria-label={`步骤 ${task.taskId} 选择 operation`} value={operationName} onChange={event=>{if(!isLocked())setOperationName(event.target.value)}}><option value="">请选择正式 operation identity</option>{operations.map(entry=><option key={key(entry)} value={entry.operation.name}>{entry.operation.name}</option>)}</select></label>
      {selected&&<div className="binding-selection-preview" aria-label="Selected Skill operation details"><strong>将保存的精确身份</strong><p className="technical-value">{selected.skillId} · {selected.skillRevisionId} · {selected.skillDigest} · {selected.operation.name}</p><OperationDetails entry={selected}/></div>}
      {duplicate&&<p role="alert">相同 Skill revision、digest 与 operation 已绑定，不能重复添加。</p>}
      <div className="binding-edit-actions"><button type="button" disabled={!selected||duplicate} onClick={apply}>保存精确 Skill operation binding</button>{editingIndex!==null&&<button type="button" onClick={reset}>取消更换</button>}</div>
    </fieldset>}
    {!readOnly&&directoryState!=="READY"&&<div className="binding-unavailable" role="status"><strong>{directoryState==="LOADING"?"正在读取正式 Skill operation 目录…":"Skill operation 目录不可用"}</strong><p>{directoryState==="UNAVAILABLE"?(directoryReason??"后端未提供可审查的正式 operation 目录。当前输入已保留，但不能新增或更换绑定。"):"不会默认选择首个 Skill、revision 或 operation。"}</p></div>}
    {!readOnly&&directoryState==="READY"&&directory.length===0&&<div className="binding-unavailable" role="status"><strong>没有合格的 Skill operation</strong><p>未找到已发布、启用、未归档、未弃用且带有效 READ_ONLY operation 的精确 revision；不能提交为有效绑定。</p></div>}
    <p className="binding-authority-note">绑定和发布只保存精确身份，不授予执行、调度、凭据或 MCP dispatch 权限。</p>
  </section>;
}
