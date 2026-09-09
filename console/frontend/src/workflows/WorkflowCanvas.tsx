import {useEffect,useMemo,useRef,useState,type PointerEvent as ReactPointerEvent} from "react";
import type {WorkflowTask} from "../api/workflowDefinitions";
import {inspectWorkflowGraph,layoutWorkflow,type WorkflowNodePosition} from "./workflowDesignerModel";

type DragState={taskId:string;startX:number;startY:number;origin:WorkflowNodePosition};
type PanState={startX:number;startY:number;scrollLeft:number;scrollTop:number};

export function WorkflowCanvas({tasks,selectedTaskId,onSelect,readOnly=false}:{tasks:WorkflowTask[];selectedTaskId:string|null;onSelect:(taskId:string)=>void;readOnly?:boolean}){
  const automatic=useMemo(()=>layoutWorkflow(tasks),[tasks]);
  const issues=useMemo(()=>inspectWorkflowGraph(tasks),[tasks]);
  const [manual,setManual]=useState<Record<string,WorkflowNodePosition>>({}),[zoom,setZoom]=useState(1),[query,setQuery]=useState(""),[expanded,setExpanded]=useState(false);
  const drag=useRef<DragState|null>(null);
  const pan=useRef<PanState|null>(null),viewport=useRef<HTMLDivElement|null>(null);
  const position=(taskId:string)=>manual[taskId]??automatic.positions.get(taskId)??{x:48,y:48};
  const canvasWidth=Math.max(automatic.width,...tasks.map(task=>position(task.taskId).x+250));
  const canvasHeight=Math.max(automatic.height,...tasks.map(task=>position(task.taskId).y+120));
  function pointerDown(event:ReactPointerEvent<HTMLButtonElement>,taskId:string){
    if(readOnly)return;const origin=position(taskId);drag.current={taskId,startX:event.clientX,startY:event.clientY,origin};event.currentTarget.setPointerCapture(event.pointerId);
  }
  function pointerMove(event:ReactPointerEvent<HTMLButtonElement>){
    const active=drag.current;if(!active)return;
    setManual(value=>({...value,[active.taskId]:{x:Math.max(16,active.origin.x+(event.clientX-active.startX)/zoom),y:Math.max(16,active.origin.y+(event.clientY-active.startY)/zoom)}}));
  }
  function pointerUp(){drag.current=null}
  function center(taskId:string){const point=position(taskId),element=viewport.current;if(!element)return;element.scrollTo({left:Math.max(0,(point.x+101)*zoom-element.clientWidth/2),top:Math.max(0,(point.y+45)*zoom-element.clientHeight/2),behavior:"smooth"});onSelect(taskId)}
  function fit(){const element=viewport.current;if(!element)return;const availableWidth=Math.max(240,element.clientWidth-48),availableHeight=Math.max(220,element.clientHeight-48),next=Math.max(.55,Math.min(1.15,availableWidth/canvasWidth,availableHeight/canvasHeight));setZoom(Number(next.toFixed(2)));element.scrollTo({left:0,top:0})}
  function panStart(event:ReactPointerEvent<HTMLDivElement>){if((event.target as Element).closest("button,input"))return;pan.current={startX:event.clientX,startY:event.clientY,scrollLeft:event.currentTarget.scrollLeft,scrollTop:event.currentTarget.scrollTop};event.currentTarget.setPointerCapture(event.pointerId)}
  function panMove(event:ReactPointerEvent<HTMLDivElement>){const active=pan.current;if(!active)return;event.currentTarget.scrollLeft=active.scrollLeft-(event.clientX-active.startX);event.currentTarget.scrollTop=active.scrollTop-(event.clientY-active.startY)}
  const initialCanvas=useRef({width:canvasWidth,height:canvasHeight});
  useEffect(()=>{const frame=requestAnimationFrame(()=>{const element=viewport.current;if(!element)return;const {width,height}=initialCanvas.current,availableWidth=Math.max(240,element.clientWidth-48),availableHeight=Math.max(220,element.clientHeight-48),next=Math.max(.55,Math.min(1.15,availableWidth/width,availableHeight/height));setZoom(Number(next.toFixed(2)));element.scrollTo({left:0,top:0})});return()=>cancelAnimationFrame(frame)},[]);
  const result=tasks.find(task=>`${task.name} ${task.taskId}`.toLowerCase().includes(query.trim().toLowerCase()));
  return <section className={`workflow-designer__canvas${expanded?" workflow-designer__canvas--expanded":""}`} aria-label="Workflow 流程画布">
    <div className="workflow-designer__canvas-controls" aria-label="画布视图控制">
      <div className="workflow-designer__zoom-group" role="group" aria-label="画布缩放">
        <button type="button" className="workflow-designer__icon-button" aria-label="缩小画布" title="缩小画布" onClick={()=>setZoom(value=>Math.max(.55,Number((value-.1).toFixed(2))))}>−</button>
        <button type="button" className="workflow-designer__zoom-value" aria-label="恢复 100%" title="恢复到 100%" onClick={()=>setZoom(1)}>{Math.round(zoom*100)}%</button>
        <button type="button" className="workflow-designer__icon-button" aria-label="放大画布" title="放大画布" onClick={()=>setZoom(value=>Math.min(1.5,Number((value+.1).toFixed(2))))}>＋</button>
      </div>
      <div className="workflow-designer__tool-group" role="group" aria-label="画布布局与定位">
        <button type="button" aria-label="自动布局" title="恢复自动布局，不修改依赖" onClick={()=>{setManual({});requestAnimationFrame(fit)}}>自动布局</button>
        <button type="button" aria-label="适配画布" title="缩放以显示全部节点" onClick={fit}>适配</button>
        <button type="button" aria-label="定位选中节点" title="将当前节点移到视口中心" disabled={!selectedTaskId} onClick={()=>selectedTaskId&&center(selectedTaskId)}>选中节点</button>
        <button type="button" aria-label="定位首个校验问题" title="定位第一个存在配置问题的节点" disabled={!issues[0]?.taskId} onClick={()=>issues[0]?.taskId&&center(issues[0].taskId)}>首个问题</button>
        <button type="button" aria-label={expanded?"退出展开":"展开画布"} title={expanded?"退出全屏画布":"展开画布"} onClick={()=>setExpanded(value=>!value)}>{expanded?"退出展开":"展开"}</button>
      </div>
      <div className="workflow-designer__search-group"><label className="workflow-designer__node-search"><span>查找节点</span><input aria-label="当前 Workflow 节点搜索" value={query} onChange={event=>setQuery(event.target.value)} placeholder="名称或 taskId"/></label><button type="button" aria-label="定位节点" title="定位当前流程中的匹配节点" disabled={!result} onClick={()=>result&&center(result.taskId)}>定位</button></div>
    </div>
    <p className="workflow-designer__view-note">连线直接来自 <code>dependsOn</code>。{readOnly?"当前 revision 只读。":"拖动只改变当前视图位置，不改变步骤 ID、依赖或保存内容。"}</p>
    <div ref={viewport} className="workflow-designer__viewport" tabIndex={0} aria-label="可平移的 Workflow 画布视口" onPointerDown={panStart} onPointerMove={panMove} onPointerUp={()=>{pan.current=null}} onPointerCancel={()=>{pan.current=null}}>
      <div className="workflow-designer__stage" style={{width:canvasWidth,height:canvasHeight,transform:`scale(${zoom})`}}>
        <svg aria-hidden="true" width={canvasWidth} height={canvasHeight} viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}>
          <defs><marker id="workflow-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z"/></marker></defs>
          {tasks.flatMap(task=>task.dependsOn.map(dependency=>{const from=position(dependency),to=position(task.taskId);if(!tasks.some(candidate=>candidate.taskId===dependency))return null;return <path key={`${dependency}->${task.taskId}`} d={`M ${from.x+202} ${from.y+45} C ${from.x+235} ${from.y+45}, ${to.x-35} ${to.y+45}, ${to.x} ${to.y+45}`} markerEnd="url(#workflow-arrow)"/>}))}
        </svg>
        {tasks.map(task=>{const point=position(task.taskId),kinds=Array.from(new Set(task.references.map(reference=>reference.kind))),type=kinds.length===0?"通用步骤":kinds.length===1?kinds[0]:"多资源组合步骤",icon=kinds.length>1?"◈":kinds[0]==="AGENT"?"A":kinds[0]==="SKILL"?"S":kinds[0]==="MCP"?"M":kinds[0]==="KNOWLEDGE"?"K":kinds[0]==="RUNTIME_PROFILE"?"R":"◇",problemCount=issues.filter(issue=>issue.taskId===task.taskId).length;return <button type="button" key={task.taskId} data-workflow-node={`${readOnly?"revision":"editor"}:${task.taskId}`} className={`workflow-designer__node${selectedTaskId===task.taskId?" selected":""}${problemCount?" invalid":""}`} style={{left:point.x,top:point.y}} aria-pressed={selectedTaskId===task.taskId} aria-label={`${readOnly?"查看":"编辑"}步骤 ${task.name||task.taskId}`} onClick={()=>onSelect(task.taskId)} onPointerDown={event=>pointerDown(event,task.taskId)} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={pointerUp}>
          <span><b aria-hidden="true">{icon}</b>{type} · {task.dependsOn.length?`${task.dependsOn.length} 个依赖`:"起点"}</span><strong>{task.name||"未命名步骤"}</strong><code>{task.taskId||"NO_TASK_ID"}</code><small>{task.references.length} 个资源 · {task.skillOperationBindings?.length??0} 个操作</small><em className={problemCount?"has-issues":"complete"}>{problemCount?`${problemCount} 个配置问题`:"配置完整（非运行状态）"}</em>
        </button>})}
      </div>
    </div>
  </section>;
}
