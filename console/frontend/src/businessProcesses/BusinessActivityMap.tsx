import {Link} from 'react-router-dom';
import {businessProcessHref} from './businessRelationNavigation';
import {BusinessCapabilityRelations} from './BusinessCapabilityRelations';
import {BusinessReferencePicker} from './BusinessReferencePicker';
import {useId,useState} from 'react';
import {handoffIdentity,type BusinessProcessContent,type BusinessReferenceDetails,type FixedBusinessReference} from '../api/businessProcesses';
const events={COMPLETED:'完成后交接',RETURNED:'退回处理',NEEDS_INFORMATION:'缺资料，转去补充'};
const lines=(values:string[])=>values.length?values.join('；'):'待补充';
export function BusinessActivityMap({content,referenceDetails,onActivitySelect,onActivityClear,onHandoffSelect,editing=false,activeActivityId=null,activeHandoffId=null,processReference,initialActivityId=null,initialHandoffId=null}:{content:BusinessProcessContent;processReference?:FixedBusinessReference;initialActivityId?:string|null;initialHandoffId?:string|null;referenceDetails?:BusinessReferenceDetails;onActivitySelect?:(id:string)=>void;onActivityClear?:()=>void;onHandoffSelect?:(id:string)=>void;editing?:boolean;activeActivityId?:string|null;activeHandoffId?:string|null}){
 const [selected,setSelected]=useState<string|null>(initialActivityId),[edge,setEdge]=useState<string|null>(initialHandoffId);
 const selectedActivity=editing?activeActivityId:selected,selectedEdge=editing?activeHandoffId:edge;
 const marker=useId().replaceAll(':','');
 const activity=content.activities.find(item=>item.activity_id===selectedActivity),handoff=content.handoffs.find(item=>handoffIdentity(item)===selectedEdge);
 const width=Math.max(560,content.activities.length*244+24),height=160+content.handoffs.length*36;
 const positions=new Map(content.activities.map((item,index)=>[item.activity_id,136+index*244]));
 const choose=(identity:string)=>{setSelected(identity);setEdge(null);onActivitySelect?.(identity)};
 return <section className="bp-activity-workbench" aria-label="业务活动与交接图">
  <div className="bp-map-toolbar"><h2>流程与活动</h2><span>业务现状</span>{!editing&&(activity||handoff)&&<button type="button" onClick={()=>{setSelected(null);setEdge(null);onActivityClear?.()}}>回到完整图</button>}</div>
  {!content.activities.length?<p>尚未补充业务活动。</p>:<div className="bp-map-layout">
   <div className="bp-map-scroll"><div className="bp-map-canvas" style={{width,height}}>
    <svg width={width} height={height} aria-hidden="true"><defs><marker id={marker} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="currentColor"/></marker></defs>{content.handoffs.map((item,index)=>{const start=positions.get(item.from_activity_id),end=positions.get(item.to_activity_id);if(start===undefined||end===undefined)return null;const lane=160+index*36;return <path key={handoffIdentity(item)} className={item.event==='COMPLETED'?'bp-edge':'bp-edge bp-edge-return'} d={`M ${start-16} 116 V ${lane} H ${end+16} V 118`} fill="none" markerEnd={`url(#${marker})`}/>})}</svg>
    {content.activities.map((item,index)=><button type="button" key={item.activity_id} className="bp-activity-node" title={item.name} style={{left:24+index*244}} aria-pressed={item.activity_id===selectedActivity} onClick={()=>choose(item.activity_id)}><span>活动 {index+1}</span><strong>{item.name}</strong><small>{item.responsible_role||'责任角色待补充'}</small></button>)}
    {content.handoffs.map((item,index)=><button type="button" className="bp-edge-label" key={handoffIdentity(item)} style={{left:Math.max(24,((positions.get(item.from_activity_id)??136)+(positions.get(item.to_activity_id)??136))/2-70),top:143+index*36}} aria-pressed={selectedEdge===handoffIdentity(item)} aria-label={`${events[item.event]}：${content.activities.find(value=>value.activity_id===item.from_activity_id)?.name} → ${content.activities.find(value=>value.activity_id===item.to_activity_id)?.name}`} onClick={()=>{setEdge(handoffIdentity(item));setSelected(null);onHandoffSelect?.(handoffIdentity(item))}}>{events[item.event]}</button>)}
   </div>{!content.handoffs.length&&<p>尚未登记交接关系；活动排列顺序不代表执行依赖。</p>}</div>
   {!editing&&(activity||handoff)&&<aside className="bp-activity-inspector" aria-label="选中活动或交接详情">{activity?<><h3>{activity.name}</h3><dl><div><dt>业务责任角色</dt><dd>{activity.responsible_role||'待补充'}</dd></div><div><dt>活动输入</dt><dd>{lines(activity.inputs)}</dd></div><div><dt>活动输出</dt><dd>{lines(activity.outputs)}</dd></div><div><dt>完成标准</dt><dd>{lines(activity.completion_conditions)}</dd></div><div><dt>人工保留事项</dt><dd>{activity.human_boundary||'待补充'}</dd></div></dl>{activity.employee&&<BusinessReferencePicker kind="employee" selected={[activity.employee]} returnTo={processReference?businessProcessHref(processReference,activity.activity_id):undefined} details={referenceDetails}/ >}{processReference&&!editing&&<p><Link to={'/capabilities?'+new URLSearchParams({processDesign:businessProcessHref(processReference,activity.activity_id)})}>基于活动创建能力草稿</Link></p>}{processReference&&<BusinessCapabilityRelations key={activity.activity_id} side="PROCESS" reference={processReference} activityId={activity.activity_id}/>}</>:handoff&&<><h3>{events[handoff.event]}</h3><p>{content.activities.find(item=>item.activity_id===handoff.from_activity_id)?.name} → {content.activities.find(item=>item.activity_id===handoff.to_activity_id)?.name}</p><p>{handoff.explanation}</p><dl><div><dt>责任角色</dt><dd>{handoff.responsible_role||'待补充'}</dd></div></dl></>}</aside>}
  </div>}
  {!editing&&initialHandoffId&&!handoff&&<p role="status">原交接不在此固定版本中，请核对来源；未自动选择其他交接。</p>}
  {!activity&&!handoff&&<p className="bp-map-hint">点击活动查看责任与输入输出；点击连线标签查看完成、退回或补资料的交接要求。</p>}
 </section>;
}
