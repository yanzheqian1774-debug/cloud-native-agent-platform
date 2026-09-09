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
    <div className="workflow-designer__workspace">
      <div className={`workflow-designer__primary ${view==="config"?"workflow-designer__mobile-hidden":""}`}>{view!=="list"?<WorkflowCanvas tasks={content.tasks} selectedTaskId={selectedTaskId} onSelect={select} readOnly/>:<section className="workflow-designer__list" aria-label="等价 Workflow 步骤列表"><ol>{content.tasks.map(task=><li key={task.taskId}><button type="button" aria-pressed={selectedTaskId===task.taskId} onClick={()=>select(task.taskId)}><strong>{task.name}</strong><code>{task.taskId}</code><span>depends on {task.dependsOn.join(", ")||"nothing"}</span><span>{task.references.length} exact reference(s) · {task.skillOperationBindings?.length??0} Skill operation binding(s) · retry {task.retryLimit} · timeout {task.timeoutSeconds}s · {task.failurePolicy}</span></button></li>)}</ol></section>}</div>
      <aside className={`workflow-designer__inspector ${view==="config"?"is-active":""}`} aria-label="Workflow 节点详情">{selected?<><button type="button" className="workflow-designer__close" onClick={()=>{const id=selected.taskId;onSelect(null);setView("canvas");requestAnimationFrame(()=>document.querySelector<HTMLButtonElement>(`[data-workflow-node="${CSS.escape(`revision:${id}`)}"]`)?.focus())}}>关闭节点详情</button><h4>{selected.name}</h4><dl><div><dt>步骤 ID</dt><dd><code>{selected.taskId}</code></dd></div><div><dt>输入</dt><dd>{selected.inputs.join(", ")||"无"}</dd></div><div><dt>输出</dt><dd>{selected.outputs.join(", ")||"无"}</dd></div><div><dt>能力标识</dt><dd>{selected.capabilityRequirements.join(", ")||"无"}</dd></div><div><dt>依赖</dt><dd>{selected.dependsOn.join(", ")||"无"}</dd></div><div><dt>Timeout / retry</dt><dd>{selected.timeoutSeconds}s / {selected.retryLimit}</dd></div><div><dt>Failure policy</dt><dd>{selected.failurePolicy}</dd></div></dl><WorkflowResourceDetails task={selected} runtimeProfile={content.runtimeProfile} directory={directory} directoryState={directoryState}/></>:<div className="empty-state"><h4>选择节点查看内容</h4><p>这是 Definition 配置，不是运行进度。</p></div>}</aside>
    </div>
  </section>;
}
