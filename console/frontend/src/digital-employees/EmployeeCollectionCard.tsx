import type {EmployeeAuthoring,EmployeeDefinitionSummary} from '../api/digitalEmployees';
import './EmployeeCollectionCard.css';

export function EmployeeCollectionCard({revisions,value,ready,selectedRevision,onSelect}:{revisions:EmployeeDefinitionSummary[];value:EmployeeAuthoring|null|undefined;ready:boolean;selectedRevision?:string;onSelect:(item:EmployeeDefinitionSummary)=>void}){
 const publication=value?.publication.status==='AVAILABLE'?value.publication.definition:null;
 const draft=value?.draft.status==='AVAILABLE'?value.draft.definition:null;
 const listed=revisions.find(item=>item.employeeDefinitionRevisionId===selectedRevision)??revisions[0];
 const primary=publication??draft??listed;
 return <article className="employee-collection-row employee-version-card" aria-label={primary.role}>
  <button className="employee-row-main" onClick={()=>onSelect(primary)}><span className="employee-avatar" aria-hidden="true">员</span><span className="employee-row-copy"><strong>{primary.role}</strong><small>{publication?'查看当前发布':draft?'查看修改草稿':'查看已列版本'}</small></span></button>
  <div className="employee-version-options">
   <section><h3>当前发布</h3>{publication?<><p>{publication.responsibilities.slice(0,2).join('；')||'此版本尚未填写职责。'}</p><button onClick={()=>onSelect(publication)}>查看当前发布</button></>:<p>{!ready?'正在核对…':value?.publication.status==='WITHDRAWN'?'当前发布已撤销':'当前发布暂未核实'}</p>}</section>
   <section><h3>修改草稿</h3>{draft?<><p>{draft.responsibilities.slice(0,2).join('；')||'此草稿尚未填写职责。'}</p><button onClick={()=>onSelect(draft)}>查看修改草稿</button></>:<p>{!ready?'正在核对…':value?.draft.status==='NONE'?'暂无修改草稿':'修改草稿暂未核实'}</p>}</section>
  </div>
  <details className="employee-listed-history"><summary>历史与已列版本（{revisions.length}）</summary><p>仅包含当前批次的匹配记录；选择版本不会修改或启动工作。</p><label>选择准确版本<select aria-label={`${primary.role} 选择版本`} value={revisions.some(r=>r.employeeDefinitionRevisionId===selectedRevision)?selectedRevision:''} onChange={event=>{const item=revisions.find(r=>r.employeeDefinitionRevisionId===event.target.value);if(item)onSelect(item)}}><option value="" disabled>请选择已列版本</option>{revisions.map(item=><option key={item.employeeDefinitionRevisionId} value={item.employeeDefinitionRevisionId}>{item.employeeDefinitionRevisionId} · {item.publicationState==='PUBLISHED'?'已发布记录':'未发布记录'}</option>)}</select></label><small>{listed.employeeDefinitionId}</small></details>
 </article>;
}
