import type {EmployeeAuthoring,EmployeeDefinitionSummary} from '../api/digitalEmployees';
import './EmployeeCollectionCard.css';

export function EmployeeCollectionCard({revisions,value,ready,error,stale=false,selectedRevision,onSelect}:{revisions:EmployeeDefinitionSummary[];value:EmployeeAuthoring|null|undefined;ready:boolean;error?:string;stale?:boolean;selectedRevision?:string;onSelect:(item:EmployeeDefinitionSummary)=>void}){
 const publication=value?.publication.status==='AVAILABLE'?value.publication.definition:null;
 const draft=value?.draft.status==='AVAILABLE'?value.draft.definition:null;
 const listed=revisions.find(item=>item.employeeDefinitionRevisionId===selectedRevision)??revisions[0];
 const primary=publication??draft??listed;
 return <article className="employee-collection-row employee-version-card" aria-label={primary.role}>
  <button className="employee-row-main" onClick={()=>onSelect(primary)}><span className="employee-avatar" aria-hidden="true">员</span><span className="employee-row-copy"><strong>{primary.role}</strong><small>{publication?(stale?'查看已读发布版本':'查看当前发布'):draft?(stale?'查看已读草稿':'查看修改草稿'):'查看已列版本'}</small></span></button>
  {stale&&<p role="status">显示上次核对内容，当前状态待重新确认。{error}</p>}
  <div className="employee-version-options">
   <section><h3>{stale?"上次核对的发布版本":"当前发布"}</h3>{publication?<><p>{publication.responsibilities.slice(0,2).join('；')||'此版本尚未填写职责。'}</p><button onClick={()=>onSelect(publication)}>{stale?"查看已读发布版本":"查看当前发布"}</button></>:<p>{!ready?'正在核对…':value?.publication.status==='WITHDRAWN'?'当前发布已撤销':'当前发布暂未核实'}</p>}</section>
   <section><h3>{stale?"上次核对的草稿":"修改草稿"}</h3>{draft?<><p>{draft.responsibilities.slice(0,2).join('；')||'此草稿尚未填写职责。'}</p><button onClick={()=>onSelect(draft)}>{stale?"查看已读草稿":"查看修改草稿"}</button></>:<p>{!ready?'正在核对…':value?.draft.status==='NONE'?'暂无修改草稿':'修改草稿暂未核实'}</p>}</section>
  </div>
  {ready&&!value&&<p role="status">{error??"版本信息读取未完成，可重新核对。"} 当前发布与草稿仍未确认。</p>}
  <details className="employee-listed-history"><summary>历史与已列版本（{revisions.length}）</summary><p>仅包含当前批次的匹配记录；选择版本不会修改或启动工作。</p><label>选择准确版本<select aria-label={`${primary.role} 选择版本`} value={revisions.some(r=>r.employeeDefinitionRevisionId===selectedRevision)?selectedRevision:''} onChange={event=>{const item=revisions.find(r=>r.employeeDefinitionRevisionId===event.target.value);if(item)onSelect(item)}}><option value="" disabled>请选择已列版本</option>{revisions.map(item=><option key={item.employeeDefinitionRevisionId} value={item.employeeDefinitionRevisionId}>{item.employeeDefinitionRevisionId} · {item.publicationState==='PUBLISHED'?'已发布记录':'未发布记录'}</option>)}</select></label><small>{listed.employeeDefinitionId}</small></details>
 </article>;
}
