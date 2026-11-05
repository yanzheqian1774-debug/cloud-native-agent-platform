import type {Requirement} from './api';
import {NavigationIcon} from '../components/NavigationIcon';
import {resourceKinds} from './planningPresentation';
export function PlanningResourceSummary({requirements,status,executed}:{requirements:Requirement[];status:(r:Requirement)=>string;executed:boolean}){
 const labels:Record<string,string>={MATCHED:'声明已匹配',MISSING:'待准备',UNKNOWN:'适配待核实',UNREADABLE:'读取范围待核对',VERSION_MISMATCH:'版本需核对',UNAVAILABLE:'暂不可用',NOT_REQUIRED:'可选未选择'};
 function reveal(id:string){const node=document.getElementById('requirement-'+id);if(node instanceof HTMLDetailsElement){node.open=true;node.scrollIntoView({block:'center'});node.focus()}}
 return <section className="planning-card planning-preparation-overview" aria-label="资源准备概况"><h2><NavigationIcon name="resource"/>资源准备 · 平台核验，按需介入</h2><p>{executed?'下表保留制定方案时的资源依据；实际运行与使用情况以正式执行记录为准。':'平台继续核验资源与已有权限，关键准备情况直接展示。未通过核验时保留原方案。'}</p><div className="planning-table-scroll"><table><thead><tr><th>资源类型</th><th>推荐资源</th><th>当前状态</th><th>推荐理由</th><th>操作</th></tr></thead><tbody>{requirements.map(r=><tr key={r.requirement_id}><td>{resourceKinds[r.kind]??r.kind}</td><td>{r.name}</td><td><span className={'planning-badge is-'+status(r).toLowerCase()}>{labels[status(r)]??'待核实'}</span></td><td>{r.purpose}</td><td><button type="button" onClick={()=>reveal(r.requirement_id)}>查看准备详情</button></td></tr>)}</tbody></table></div><p className="journey-muted">匹配说明、已发布版本、实际分工和执行准入分别核验；资源声明不等同于可执行。</p></section>;
}
