import {useState} from "react";
import type {WorkflowContent} from "../api/workflowDefinitions";
import type {WorkflowSkillOperationEntry} from "../api/workflowSkillOperations";
import "../styles/workflow-designer.css";
import {WorkflowCanvas} from "./WorkflowCanvas";
import {WorkflowResourceDetails} from "./WorkflowResourceDetails";

export function WorkflowRevisionDesigner({content,selectedTaskId,onSelect,directory,directoryState}:{content:WorkflowContent;selectedTaskId:string|null;onSelect:(taskId:string|null)=>void;directory:WorkflowSkillOperationEntry[];directoryState:"LOADING"|"READY"|"UNAVAILABLE"}){
  const [view,setView]=useState<"canvas"|"list"|"config">("canvas");
  const selected=content.tasks.find(task=>task.taskId===selectedTaskId)??null;
  function select(taskId:string){onSelect(taskId);if(window.matchMedia("(max-width: 720px)").matches)setView("config")}
  return <section className="workflow-designer workflow-designer--readonly" data-current-view={view} aria-label="Workflow revision visual design">
    <div className="workflow-designer__tabs" role="tablist" aria-label="Workflow revision views"><button type="button" role="tab" aria-selected={view==="canvas"} onClick={()=>setView("canvas")}>流程画布</button><button type="button" role="tab" aria-selected={view==="list"} onClick={()=>setView("list")}>步骤列表</button><button type="button" role="tab" aria-selected={view==="config"} disabled={!selected} onClick={()=>setView("config")}>节点详情</button></div>
    <div className={`workflow-designer__workspace${selected?"":" workflow-designer__workspace--inspector-collapsed"}`}>
      <div className={`workflow-designer__primary ${view==="config"?"workflow-designer__mobile-hidden":""}`}>{view!=="list"?<WorkflowCanvas tasks={content.tasks} selectedTaskId={selectedTaskId} onSelect={select} readOnly/>:<section className="workflow-designer__list" aria-label="等价 Workflow 步骤列表"><ol>{content.tasks.map(task=><li key={task.taskId}><button type="button" aria-pressed={selectedTaskId===task.taskId} onClick={()=>select(task.taskId)}><strong>{task.name}</strong><code>{task.taskId}</code><span>依赖：{task.dependsOn.join("、")||"无"}</span><span>{task.references.length} 个精确资源 · {task.skillOperationBindings?.length??0} 个 Skill operation · 重试 {task.retryLimit} · 超时 {task.timeoutSeconds}s · {task.failurePolicy}</span></button></li>)}</ol></section>}</div>
      <aside className={`workflow-designer__inspector${selected?"":" is-collapsed"}${view==="config"?" is-active":""}`} aria-label="Workflow 节点详情">{selected?<><button type="button" className="workflow-designer__close" onClick={()=>{const id=selected.taskId;onSelect(null);setView("canvas");requestAnimationFrame(()=>document.querySelector<HTMLButtonElement>(`[data-workflow-node="${CSS.escape(`revision:${id}`)}"]`)?.focus())}}>收起节点详情</button><header className="workflow-designer__readonly-node-header"><p className="eyebrow">节点详情 · 只读</p><h4>{selected.name}</h4><code>{selected.taskId}</code></header><section className="workflow-designer__readonly-group"><h5>基本信息与输入输出</h5><dl><div><dt>输入</dt><dd>{selected.inputs.join(", ")||"无"}</dd></div><div><dt>输出</dt><dd>{selected.outputs.join(", ")||"无"}</dd></div><div><dt>能力标识</dt><dd>{selected.capabilityRequirements.join(", ")||"无"}</dd></div></dl></section><section className="workflow-designer__readonly-group"><h5>依赖与执行策略</h5><dl><div><dt>依赖</dt><dd>{selected.dependsOn.join(", ")||"无"}</dd></div><div><dt>超时 / 重试</dt><dd>{selected.timeoutSeconds}s / {selected.retryLimit}</dd></div><div><dt>失败策略</dt><dd>{selected.failurePolicy}</dd></div></dl></section><WorkflowResourceDetails task={selected} runtimeProfile={content.runtimeProfile} directory={directory} directoryState={directoryState}/></>:<p>请选择节点查看 Definition 配置；这里不是运行进度。</p>}</aside>
    </div>
  </section>;
}
