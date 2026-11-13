import type {EmployeeAuthoring,EmployeeDefinitionSummary,EmployeeDefinition} from '../api/digitalEmployees';
import './EmployeeCollectionCard.css';
const resourceKinds={SKILL:'技能',MCP:'MCP',KNOWLEDGE:'知识'} as const;
export function EmployeeCollectionCard({revisions,value,ready,error,stale=false,selectedRevision,onSelect}:{revisions:EmployeeDefinitionSummary[];value:EmployeeAuthoring|null|undefined;ready:boolean;error?:string;stale?:boolean;selectedRevision?:string;onSelect:(item:EmployeeDefinitionSummary)=>void}){
 const publication=value?.publication.status==='AVAILABLE'?value.publication.definition:null;
 const draft=value?.draft.status==='AVAILABLE'?value.draft.definition:null;
 const listed=revisions.find(item=>item.employeeDefinitionRevisionId===selectedRevision)??revisions[0];
 const primary=publication??draft??listed,definition:EmployeeDefinition|null=publication??draft??(value?.head.status==='AVAILABLE'&&value.head.definition.employeeDefinitionRevisionId===primary.employeeDefinitionRevisionId?value.head.definition:null);
 const members=definition?[...new Map(definition.members.map(member=>[JSON.stringify(member),member])).values()]:null;
 return <article className="employee-collection-row employee-version-card" aria-label={primary.role}>
  <div className="employee-member-card-head"><span className="employee-avatar" aria-hidden="true"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2M20 14h2M15 13v2M9 13v2"/></svg></span><span className="employee-member-state">{publication?(stale?'已读发布 · 待核对':'当前发布'):draft?(stale?'已读草稿 · 待核对':'修改草稿'):'发布状态待核实'}</span></div>
  <h3>{primary.role}</h3><p className="employee-member-duty">{definition?definition.responsibilities.slice(0,2).join('；')||'此版本尚未填写职责。':ready?'职责摘要暂未核实':'正在核对职责…'}</p>
  {stale&&<p role="status">显示上次核对内容，当前状态待重新确认。{error}</p>}
  {members?<div className="employee-member-resource-counts" aria-label="所选版本资源分类">{Object.entries(resourceKinds).filter(([kind])=>members.some(member=>member.kind===kind)).map(([kind,label])=><span key={kind}>{label} <strong>{members.filter(member=>member.kind===kind).length}</strong></span>)}{members.length===0&&<span>此版本已登记的资源绑定为 0 项</span>}{members.length>0&&!members.some(member=>member.kind in resourceKinds)&&<span>此版本未登记技能、MCP或知识的直接绑定</span>}</div>:<p className="employee-member-resource-unknown">资源组成暂未核实</p>}
  <div className="employee-member-primary"><button onClick={()=>onSelect(primary)}>查看数字人</button></div>
  <div className="employee-version-options">
   {!publication&&<p>{!ready?'正在核对发布…':value?.publication.status==='WITHDRAWN'?'当前发布已撤销':'当前发布暂未核实'}</p>}
   {draft?<div><button onClick={()=>onSelect(draft)}>{stale?'查看已读草稿':'查看修改草稿'}</button><small>{publication?'已有修改草稿；发布内容保持不变':'当前可读草稿，发布状态另行核对'}</small></div>:<p>{!ready?'正在核对草稿…':value?.draft.status==='NONE'?'暂无修改草稿':'修改草稿暂未核实'}</p>}
  </div>
  {ready&&!value&&<p role="status">{error??'版本信息读取未完成，可重新核对。'} 当前发布与草稿仍未确认。</p>}
  <details className="employee-listed-history"><summary>历史与版本依据</summary><p>仅包含当前批次的 {revisions.length} 条匹配记录；选择版本不会修改或启动工作。资源分类仅按所查看版本的直接绑定统计，不推定嵌套工具或本体数量。</p><label>选择准确版本<select aria-label={`${primary.role} 选择版本`} value={revisions.some(r=>r.employeeDefinitionRevisionId===selectedRevision)?selectedRevision:''} onChange={event=>{const item=revisions.find(r=>r.employeeDefinitionRevisionId===event.target.value);if(item)onSelect(item)}}><option value="" disabled>请选择已列版本</option>{revisions.map(item=><option key={item.employeeDefinitionRevisionId} value={item.employeeDefinitionRevisionId}>{item.employeeDefinitionRevisionId} · {item.publicationState==='PUBLISHED'?'已发布记录':'未发布记录'}</option>)}</select></label><small>{listed.employeeDefinitionId}</small></details>
 </article>;
}
