import {useEffect,useMemo,useState} from "react";
import type {WorkflowContent,WorkflowTask} from "../api/workflowDefinitions";
import type {WorkflowSkillOperationEntry} from "../api/workflowSkillOperations";
import "../styles/workflow-designer.css";
import {WorkflowCanvas} from "./WorkflowCanvas";
import {WorkflowNodeForm} from "./WorkflowNodeForm";
import {WorkflowResourceDetails} from "./WorkflowResourceDetails";
import {inspectWorkflowGraph,nextTaskId,removeTask,renameTask,replaceTask} from "./workflowDesignerModel";

const csv=(value:string)=>value.split(",").map(item=>item.trim()).filter(Boolean);
const emptyTask=(taskId:string):WorkflowTask=>({taskId,name:"",dependsOn:[],inputs:[],outputs:[],capabilityRequirements:[],references:[],retryLimit:0,timeoutSeconds:300,failurePolicy:"FAIL_WORKFLOW"});
type DesignerView="canvas"|"list"|"config";

export function WorkflowBuilderPage({content,onChange,operationDirectory=[],operationDirectoryState="UNAVAILABLE",operationDirectoryReason,isLocked=()=>false}:{content:WorkflowContent;onChange:(value:WorkflowContent)=>void;operationDirectory?:WorkflowSkillOperationEntry[];operationDirectoryState?:"LOADING"|"READY"|"UNAVAILABLE";operationDirectoryReason?:string|null;isLocked?:()=>boolean}){
  const [selectedTaskId,setSelectedTaskId]=useState<string|null>(content.tasks[0]?.taskId??null),[view,setView]=useState<DesignerView>("canvas");
  const effectiveTaskId=content.tasks.some(task=>task.taskId===selectedTaskId)?selectedTaskId:(content.tasks[0]?.taskId??null);
  const selected=content.tasks.find(task=>task.taskId===effectiveTaskId)??null;
  const issues=useMemo(()=>inspectWorkflowGraph(content.tasks),[content.tasks]);
  useEffect(()=>{
    const narrow=window.matchMedia("(max-width: 720px)");
    const enterNarrow=(event:MediaQueryListEvent|MediaQueryList)=>{if(event.matches&&effectiveTaskId)setView("config")};
    enterNarrow(narrow);
    narrow.addEventListener("change",enterNarrow);
    return()=>narrow.removeEventListener("change",enterNarrow);
  },[effectiveTaskId]);
  function select(taskId:string){setSelectedTaskId(taskId);if(window.matchMedia("(max-width: 720px)").matches)setView("config")}
  function update(task:WorkflowTask){if(!isLocked())onChange(replaceTask(content,task.taskId,task))}
  function rename(nextId:string){if(!selected||isLocked())return;const prior=selected.taskId;onChange(renameTask(content,prior,nextId));setSelectedTaskId(nextId)}
  function remove(){if(!selected||isLocked())return;const index=content.tasks.findIndex(task=>task.taskId===selected.taskId),next=content.tasks[index+1]??content.tasks[index-1]??null;onChange(removeTask(content,selected.taskId));setSelectedTaskId(next?.taskId??null);setView("canvas")}
  function add(){if(isLocked())return;const taskId=nextTaskId(content.tasks);onChange({...content,tasks:[...content.tasks,emptyTask(taskId)]});setSelectedTaskId(taskId);setView("config")}
  function focusIssue(taskId:string|undefined,field:string){if(taskId){setSelectedTaskId(taskId);setView("config");requestAnimationFrame(()=>document.getElementById(`workflow-task-${taskId.replace(/[^a-zA-Z0-9_-]/g,"_")}-${field}`)?.focus())}}
  return <section className="workbench-card resource-form workflow-designer" aria-label="Workflow Builder" data-current-view={view}>
    <header><div><p className="eyebrow">Definition Designer</p><h3>Workflow Definition 编写器 · 可视化流程设计器</h3><p>画布、列表和节点表单都编辑同一个正式 Definition；这里不创建 Workflow Run、Task Run 或 Attempt。</p></div><span className="workflow-designer__status">{issues.length?`${issues.length} 个待处理图问题`:"本地结构检查通过（非执行状态）"}</span></header>
    <section className="workflow-designer__definition"><label>用途说明<textarea value={content.description} onChange={event=>{if(!isLocked())onChange({...content,description:event.target.value})}}/></label><div className="resource-form-grid"><label>Workflow 输入（逗号分隔）<input value={content.inputs.join(", ")} onChange={event=>{if(!isLocked())onChange({...content,inputs:csv(event.target.value)})}}/></label><label>Workflow 输出（逗号分隔）<input value={content.outputs.join(", ")} onChange={event=>{if(!isLocked())onChange({...content,outputs:csv(event.target.value)})}}/></label></div><fieldset><legend>精确 Runtime Profile 绑定</legend><label>资源 ID<input value={content.runtimeProfile.resourceId} onChange={event=>{if(!isLocked())onChange({...content,runtimeProfile:{...content.runtimeProfile,resourceId:event.target.value}})}}/></label><label>修订 ID<input value={content.runtimeProfile.revisionId} onChange={event=>{if(!isLocked())onChange({...content,runtimeProfile:{...content.runtimeProfile,revisionId:event.target.value}})}}/></label><label>Digest（GET 已有时保留）<input value={content.runtimeProfile.digest??""} onChange={event=>{if(!isLocked())onChange({...content,runtimeProfile:{...content.runtimeProfile,digest:event.target.value||null}})}}/></label></fieldset></section>
    <div className="workflow-designer__tabs" role="tablist" aria-label="Workflow 设计器视图"><button type="button" role="tab" aria-selected={view==="canvas"} onClick={()=>setView("canvas")}>流程画布</button><button type="button" role="tab" aria-selected={view==="list"} onClick={()=>setView("list")}>步骤列表</button><button type="button" role="tab" aria-selected={view==="config"} disabled={!selected} onClick={()=>setView("config")}>节点配置</button></div>
    {issues.length>0&&<section className="workflow-designer__errors" aria-label="Workflow 校验错误列表" tabIndex={-1}><h4>需要修正的步骤与依赖</h4><ul>{issues.map(issue=><li key={issue.id}>{issue.taskId?<button type="button" onClick={()=>focusIssue(issue.taskId,issue.field)}>{issue.message}</button>:issue.message}</li>)}</ul><p>这些前端提示不会替代后端权威校验。</p></section>}
    <div className="workflow-designer__workspace">
      <section className={`workflow-designer__primary ${view==="config"?"workflow-designer__mobile-hidden":""}`}>
        {view!=="list"?<WorkflowCanvas tasks={content.tasks} selectedTaskId={effectiveTaskId} onSelect={select}/>:<section className="workflow-designer__list" aria-label="等价 Workflow 步骤列表"><h4>步骤与真实依赖</h4><ol>{content.tasks.map(task=><li key={task.taskId}><button type="button" aria-pressed={effectiveTaskId===task.taskId} onClick={()=>select(task.taskId)}><strong>{task.name||"未命名步骤"}</strong><code>{task.taskId}</code><span>依赖：{task.dependsOn.join("、")||"无"}</span><span>{task.inputs.length} inputs · {task.outputs.length} outputs · {task.references.length} references · {task.skillOperationBindings?.length??0} operations</span></button></li>)}</ol></section>}
        <button type="button" className="workflow-designer__add" aria-label="添加步骤" onClick={add}>＋ 添加未连接步骤</button>
      </section>
      <aside className={`workflow-designer__inspector ${view==="config"?"is-active":""}`} aria-label="Workflow 节点侧边配置">
        {selected?<><button type="button" className="workflow-designer__close" onClick={()=>{const id=selected.taskId;setSelectedTaskId(null);setView("canvas");requestAnimationFrame(()=>document.querySelector<HTMLButtonElement>(`[data-workflow-node="${CSS.escape(`editor:${id}`)}"]`)?.focus())}}>关闭节点配置</button><WorkflowNodeForm task={selected} content={content} onUpdate={update} onRename={rename} onRemove={remove} directory={operationDirectory} directoryState={operationDirectoryState} directoryReason={operationDirectoryReason} isLocked={isLocked}/><WorkflowResourceDetails task={selected} runtimeProfile={content.runtimeProfile} directory={operationDirectory} directoryState={operationDirectoryState}/></>:<div className="empty-state"><h3>选择步骤</h3><p>从画布或等价列表选择节点以查看配置与资源身份。</p></div>}
      </aside>
    </div>
    <p className="workflow-designer__layout-boundary">自动布局为默认；拖动位置仅保留在当前页面视图，不写入 Workflow content，也不会跨设备保存。</p>
  </section>;
}
