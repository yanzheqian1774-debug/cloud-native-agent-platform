import {useEffect,useState,type ReactNode} from 'react';
import {Link} from 'react-router-dom';
import type {EmployeeDefinition,EmployeeMember} from '../api/digitalEmployees';
import {listReadableResources,type DirectoryItem,type DirectoryKind} from '../api/resourceDirectory';
import {employeeMemberHref,exactSkillMcpHref} from '../resources/resourceJourneyLinks';
import {exactDefinitionHref} from '../resources/definitionJourney';
import './EmployeeResourceComposition.css';

const kinds:Record<EmployeeMember['kind'],{name:string;directory:DirectoryKind}>={
 SKILL:{name:'技能',directory:'skill'},MCP:{name:'MCP',directory:'mcp'},KNOWLEDGE:{name:'知识',directory:'knowledge'},
 AGENT:{name:'职责定义',directory:'agent'},WORKFLOW:{name:'工作流',directory:'workflow'},RUNTIME_PROFILE:{name:'运行配置',directory:'runtime'},
};
const memberKey=(m:EmployeeMember)=>JSON.stringify([m.kind,m.resourceId,m.revisionId,m.digest]);
export function EmployeeBoundResourceCard({member,item}:{member:EmployeeMember;item:EmployeeDefinition}){
 const [attempt,setAttempt]=useState(0);
 const key=memberKey(member)+":"+attempt,kind=kinds[member.kind];
 const [result,setResult]=useState<{key:string;value:DirectoryItem|null}|null>(null);
 useEffect(()=>{
  let active=true;const controller=new AbortController();
  const withdraw=()=>{active=false;controller.abort();setResult({key,value:null})};
  void listReadableResources(kind.directory,member.resourceId,'',null,AbortSignal.any([controller.signal,AbortSignal.timeout(8000)])).then(page=>{
   const matches=page.items.filter(value=>value.kind===kind.directory&&value.identity===member.resourceId&&value.revisionId===member.revisionId&&value.digest===member.digest.replace(/^sha256:/,''));
   if(active)setResult({key,value:matches.length===1?matches[0]:null});
  }).catch(()=>{if(active)setResult({key,value:null})});
  window.addEventListener('workbench-session-expired',withdraw);
  return()=>{active=false;controller.abort();window.removeEventListener('workbench-session-expired',withdraw)};
 },[key,kind.directory,member.resourceId,member.revisionId,member.digest]);
 const loaded=result?.key===key,resultValue=loaded?result.value:null;
 const href=member.kind==='SKILL'||member.kind==='MCP'?exactSkillMcpHref(member.kind==='SKILL'?'skill':'mcp',member.resourceId,member.revisionId,member.digest)
  :member.kind==='AGENT'||member.kind==='KNOWLEDGE'?exactDefinitionHref(member.kind==='AGENT'?'agent':'knowledge',member.resourceId,member.revisionId,member.digest.replace(/^sha256:/,'')):null;
 return <article className="employee-resource-card" aria-label={kind.name+'绑定资源'}>
  <div><strong>{resultValue?.name||(loaded?'已绑定'+kind.name+' · 名称暂未核对':'正在核对'+kind.name+'名称…')}</strong><p>{resultValue?.businessPurpose||'保留员工定义中的固定版本引用。'}</p>
   <details><summary>版本依据</summary><dl><dt>资源</dt><dd>{member.resourceId}</dd><dt>修订</dt><dd>{member.revisionId}</dd><dt>摘要</dt><dd>{member.digest}</dd></dl></details>
  </div>
  <div className="employee-resource-card-action"><span>{resultValue?'本次绑定版本':loaded?'准确名称未读回':'正在核对…'}</span>{loaded&&!resultValue&&<button onClick={()=>setAttempt(v=>v+1)}>重新核对名称</button>}{href?<Link to={employeeMemberHref(href,item)}>查看详情</Link>:<span>详情入口尚未接通</span>}</div>
 </article>;
}

export function EmployeeResourceComposition({item,view="composition",summaryControls,versionLabel,compact=false}:{item:EmployeeDefinition;summaryControls?:ReactNode;versionLabel?:string;compact?:boolean;view?:"composition"|"duties"|"summary"}){
 const business=item.members.filter(member=>["SKILL","MCP","KNOWLEDGE"].includes(member.kind)),internalCount=item.members.length-business.length;
 const entries=Object.entries(kinds) as [EmployeeMember['kind'],typeof kinds[EmployeeMember['kind']]][];
 return <section className="employee-resource-composition" aria-label="员工资源组成">
  {compact?<div className="employee-saved-resource-count">{business.length} 项业务资源{internalCount>0&&<> · <details><summary>{internalCount} 项内部依赖</summary><p>固定引用保持不变，可在专业管理中核对。</p></details></>}</div>:<section className="employee-composition-summary"><div><h3>{versionLabel??(item.publicationState==='PUBLISHED'?'所选已发布记录':'所选未发布修订')}</h3><p>{business.length} 项业务资源 · 已有任务保持原快照</p>{summaryControls}{internalCount>0&&<details className="employee-internal-reference"><summary>{internalCount} 项内部依赖</summary><p>可在专业管理中核对，不计入业务资源数量。</p></details>}</div><div className="employee-composition-counts">{entries.filter(([kind])=>business.some(member=>member.kind===kind)).map(([kind,label])=><span key={kind}>{label.name} <strong>{business.filter(member=>member.kind===kind).length}</strong></span>)}</div></section>}
  <section className="employee-composition-duties"><h3>职能职责</h3>{item.responsibilities.length?<ul>{item.responsibilities.map((d,i)=><li key={i}>{d}</li>)}</ul>:<p>当前定义未填写职责。</p>}</section>
  {compact&&Boolean(item.responsibilityBindings?.length)&&<section aria-label="已保存的职责资源关联"><h3>已保存的职责资源关联</h3>{item.responsibilityBindings!.map(b=><div key={JSON.stringify([b.responsibility,memberKey(b.member)])}><h4>{b.responsibility}</h4><EmployeeBoundResourceCard member={b.member} item={item}/></div>)}</section>}
  {view==='summary'?null:view==='duties'?<section aria-label="职责与资源关联">{item.responsibilities.map((d,i)=><article className="employee-composition-duties" key={i}><h3>{d}</h3>{item.responsibilityBindings?.some(b=>b.responsibility===d)?item.responsibilityBindings.filter(b=>b.responsibility===d).map(b=><EmployeeBoundResourceCard key={memberKey(b.member)} member={b.member} item={item}/>):<p>本版本未记录此项职责与资源的对应关系；版本已绑定的资源见资源组成。</p>}</article>)}</section>:entries.map(([kind,label])=>{const members=business.filter(member=>member.kind===kind);return members.length?<section key={kind} aria-label={label.name+'资源组'}><h3>{label.name} <small>{members.length} 项</small></h3>{members.map(member=><EmployeeBoundResourceCard key={memberKey(member)} member={member} item={item}/>)}</section>:null})}
 </section>;
}
