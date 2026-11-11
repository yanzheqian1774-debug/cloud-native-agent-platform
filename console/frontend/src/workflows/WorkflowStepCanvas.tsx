import {useId,useRef,useState} from 'react';
import {NavigationIcon} from '../components/NavigationIcon';
import type {WorkflowTask} from '../api/workflowDefinitions';

type Props={tasks:WorkflowTask[];selectedId:string;locked:boolean;onSelect:(id:string)=>void;onAdd:()=>void;onInsert:(before:string,after:string)=>void};
const name=(task:WorkflowTask,index:number)=>task.name.trim()||`未命名步骤 ${index+1}`;
export function WorkflowStepCanvas({tasks,selectedId,locked,onSelect,onAdd,onInsert}:Props){
 const [zoom,setZoom]=useState(1),viewport=useRef<HTMLDivElement>(null),marker=useId().replace(/:/g,'');
 const levels=new Map<string,number>(),visiting=new Set<string>();
 function level(id:string):number{if(levels.has(id))return levels.get(id)!;if(visiting.has(id))return 0;visiting.add(id);const task=tasks.find(t=>t.taskId===id),deps=task?.dependsOn.filter(d=>tasks.some(t=>t.taskId===d))??[];const value=deps.length?1+Math.max(...deps.map(level)):0;visiting.delete(id);levels.set(id,value);return value}
 const rows=new Map<number,number>();
 const nodes=tasks.map((task,index)=>{const col=level(task.taskId),row=rows.get(col)??0;rows.set(col,row+1);return {task,index,x:45+col*280,y:100+row*155}});
 const width=Math.max(700,...nodes.map(n=>n.x+255)),height=Math.max(450,...nodes.map(n=>n.y+170));
 const edges=nodes.flatMap(to=>to.task.dependsOn.flatMap(id=>{const from=nodes.find(n=>n.task.taskId===id);return from?[{from,to}]:[]}));
 return <section className="plan-canvas" aria-label="步骤关系画布">
  <div className="plan-canvas-toolbar"><button type="button" aria-label="添加步骤" disabled={locked||tasks.length>=200} onClick={onAdd}>＋ 添加步骤</button><span>按依赖横向排列</span></div>
  <div className="plan-canvas-intro"><strong>{locked?'选中步骤，查看详情':'选中步骤，就地编辑'}</strong><p>{tasks.length} 个步骤 · 连线表示先后关系</p></div>
  <div className="plan-canvas-viewport" ref={viewport} tabIndex={0} aria-label="滚动查看步骤画布">
   <div style={{width:width*zoom,height:height*zoom,position:'relative'}}><div className="plan-canvas-stage" style={{width,height,transform:`scale(${zoom})`}}>
    <svg className="plan-connectors" width={width} height={height} aria-hidden="true"><defs><marker id={marker} markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7" fill="#a8bce8"/></marker></defs>{edges.map(({from,to})=><path key={from.task.taskId+to.task.taskId} d={`M${from.x+210},${from.y+57} C${from.x+245},${from.y+57} ${to.x-35},${to.y+57} ${to.x},${to.y+57}`} fill="none" stroke="#a8bce8" strokeWidth="1.3" markerEnd={`url(#${marker})`}/>)}</svg>
    <div className="plan-step-list">{nodes.map(({task,index,x,y})=><button type="button" key={task.taskId} aria-label={`步骤 ${index+1}：${name(task,index)}`} aria-pressed={selectedId===task.taskId} style={{left:x,top:y}} onClick={()=>onSelect(task.taskId)}><small>步骤 {index+1}</small><strong><NavigationIcon name="flow"/>{name(task,index)}</strong><span>{task.inputs.join('、')||'输入未声明'} → {task.outputs.join('、')||'产出未声明'}</span><span>{task.skillOperationBindings?.length?`${task.skillOperationBindings.length} 项技能操作`:'待选择技能'}</span></button>)}</div>
    {edges.map(({from,to})=><button type="button" className="plan-edge-insert" key={from.task.taskId+to.task.taskId} disabled={locked||tasks.length>=200} style={{left:(from.x+210+to.x)/2-12,top:(from.y+to.y)/2+45}} aria-label={`在“${name(from.task,from.index)}”与“${name(to.task,to.index)}”之间插入步骤`} onClick={()=>onInsert(from.task.taskId,to.task.taskId)}>＋</button>)}
   </div></div>
  </div>
  <div className="plan-canvas-controls"><button type="button" aria-label="缩小画布" disabled={zoom<=.5} onClick={()=>setZoom(v=>Math.max(.5,v-.1))}>−</button><output aria-label="画布缩放比例">{Math.round(zoom*100)}%</output><button type="button" aria-label="放大画布" disabled={zoom>=1.5} onClick={()=>setZoom(v=>Math.min(1.5,v+.1))}>＋</button><button type="button" onClick={()=>{setZoom(Math.max(.5,Math.min(1,(viewport.current?.clientWidth??width)/width)));viewport.current?.scrollTo({top:0,left:0})}}>适应画布</button></div>
 </section>;
}
