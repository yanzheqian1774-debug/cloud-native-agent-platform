import {useEffect,useRef,useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {readWorkbenchSession} from '../api/businessWorkspace';
import {continuationQuery} from '../api/conversationActions';
import {useAutomaticReadback} from '../journey/useAutomaticReadback';
import {journeyScope,rememberContinuous} from './continuousJourney';
import * as api from './api';

/** Selection uses the original owner and Plan key; it never starts execution. */
export function AutomaticResourceSelection({id,approved,enabled,expectedScope}:{id:string;approved:api.Confirmation;enabled:boolean;expectedScope:string}){
 const navigate=useNavigate(),epoch=useRef(0),flight=useRef(false);
 const [issue,setIssue]=useState(''),[pending,setPending]=useState(false),[gaps,setGaps]=useState<api.ResourceCoverage|null>(null);
 const identity=JSON.stringify([id,approved.plan.version,approved.digest]);
 const locator=useRef<{key:string;subject:string;tenant:string;domain:string;until:number}|null>(null);
 async function verifySubject(saved:NonNullable<typeof locator.current>){
  const now=(await readWorkbenchSession()).principal;
  if(now.principalId!==saved.subject||now.tenantId!==saved.tenant||now.securityDomain!==saved.domain)throw Error('RESOURCE_SELECTION_IDENTITY_CHANGED');
 }
 async function accept(value:api.AutomaticSelection,token:number){
  const saved=locator.current;if(!saved)throw Error('RESOURCE_SELECTION_CONTEXT_MISMATCH');
  await verifySubject(saved);
  const proof=value.automaticCoverage,plan=value.confirmation.plan;
  const same=(a:api.ExactRef|undefined|null,b:api.ExactRef)=>Boolean(a&&a.resource_id===b.resource_id&&a.revision_id===b.revision_id&&a.digest===b.digest);
  const employees=plan.semantics.requirements.filter(r=>r.kind==='EMPLOYEE');
  if(!proof.selection||value.proposal.proposal_id!==id||value.proposal.revision!==plan.source_proposal_revision||value.digest!==plan.source_proposal_digest||!same(value.proposal.origin?.predecessor_plan,{resource_id:id,revision_id:String(approved.plan.version),digest:approved.digest})||!employees.length||employees.some(r=>!same(r.selected,proof.selection!))||JSON.stringify(plan.semantics)!==JSON.stringify(value.proposal.semantics))throw Error('RESOURCE_SELECTION_CONTEXT_MISMATCH');
  if(proof.subject!==saved.subject||proof.scope.tenantId!==saved.tenant||proof.scope.securityDomain!==saved.domain||proof.planId!==id||proof.planVersion!==approved.plan.version||proof.planDigest!==approved.digest||plan.plan_id!==id||plan.version<=approved.plan.version||value.proposal.origin?.kind!=='POLICY_RESOURCE_PREPARATION'||JSON.stringify(plan.semantics.target)!==JSON.stringify(approved.plan.semantics.target)||JSON.stringify(plan.semantics.tasks)!==JSON.stringify(approved.plan.semantics.tasks))throw Error('RESOURCE_SELECTION_CONTEXT_MISMATCH');
  if(token!==epoch.current)return;
  setPending(false);setIssue('');
  const session=await readWorkbenchSession();
  if(session.principal.principalId!==saved.subject||session.principal.tenantId!==saved.tenant||session.principal.securityDomain!==saved.domain)throw Error('RESOURCE_SELECTION_IDENTITY_CHANGED');
  rememberContinuous(journeyScope(session),id,value.confirmation.digest);
  if(token!==epoch.current)return;
  navigate(`/work/planning/${encodeURIComponent(id)}?revision=${plan.source_proposal_revision}${continuationQuery()}`,{replace:true});
 }
 useEffect(()=>{
  if(!enabled)return;
  const token=++epoch.current;let active=true;
  async function begin(){
   setPending(true);setIssue('');setGaps(null);
   try{
    const session=await readWorkbenchSession(),p=session.principal;
    if(JSON.stringify(p)!==expectedScope)throw Error('RESOURCE_SELECTION_IDENTITY_CHANGED');
    const raw=JSON.stringify([p.principalId,p.tenantId,p.securityDomain,identity]);
    const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(raw));
    const key='auto-resources:'+Array.from(new Uint8Array(digest),x=>x.toString(16).padStart(2,'0')).join('');
    locator.current={key,subject:p.principalId,tenant:p.tenantId,domain:p.securityDomain,until:Date.now()+60000};
    if(!active||token!==epoch.current)return;
    try{await accept(await api.readAutomaticSelection(id,approved.plan.version,key),token);return}
    catch(e){if(!(e&&typeof e==='object'&&'status'in e&&e.status===404))throw e;}
    // A lost POST stays GET-only on reload. Storage locates uncertainty; owner
    // receipt and current authorization alone prove a successful selection.
    if(sessionStorage.getItem(key)){setIssue('RESOURCE_SELECTION_OUTCOME_UNKNOWN');return;}
    const coverage=await api.readResourceCoverage(id,approved.plan.version);
    await verifySubject(locator.current);
    if(!active||token!==epoch.current)return;
    if(coverage.planId!==id||coverage.planVersion!==approved.plan.version||coverage.planDigest!==approved.digest||coverage.subject!==p.principalId)throw Error('RESOURCE_SELECTION_CONTEXT_MISMATCH');
    if(coverage.state!=='SELECTION_AVAILABLE'){setGaps(coverage);setPending(false);return;}
    sessionStorage.setItem(key,String(Date.now()));
    try{await accept(await api.selectAutomaticResources(id,approved,key,session.csrfToken),token)}
    catch(e){if(active&&token===epoch.current){setIssue(e instanceof Error?e.message:'RESOURCE_SELECTION_OUTCOME_UNKNOWN');} }
   }catch(e){if(active&&token===epoch.current){setIssue(e instanceof Error?e.message:'RESOURCE_SELECTION_UNAVAILABLE');setPending(false);}}
  }
  void begin();return()=>{active=false;if(epoch.current===token)epoch.current=token+1};
 // Only immutable source Plan identity can initiate a selection command.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[identity,enabled,expectedScope]);
 useAutomaticReadback({identity,enabled:enabled&&pending&&Boolean(issue),read:async()=>{
  const saved=locator.current;if(!saved||flight.current)return false;
  flight.current=true;const token=epoch.current;
  try{await accept(await api.readAutomaticSelection(id,approved.plan.version,saved.key),token);return false}
  catch(e){const status=e&&typeof e==='object'&&'status'in e?Number(e.status):0;
   if([401,403,409,422].includes(status)||Date.now()>=saved.until||e instanceof Error&&/IDENTITY_CHANGED|CONTEXT_MISMATCH/.test(e.message)){if(token===epoch.current)setPending(false);return false;}
   throw e;
  }finally{flight.current=false;}
 }});
 if(!enabled)return null;
 return <section className="planning-card" aria-label="平台自动选择能力" aria-live="polite"><h2>正在匹配本次办理能力</h2>
  {gaps?<><p>现有可用能力尚未覆盖本次任务，已保留具体缺口，不会启动执行。</p><ul>{[...new Set(gaps.candidates.filter(c=>c.reason).map(c=>c.reason!))].map(reason=><li key={reason}>{reason==='TASK_MEMBER_OPERATION_UNAVAILABLE'?'缺少本次任务所需的技能操作':reason==='APPROVED_SOURCE_EXACT_VERSION_REQUIRED'?'资料版本与本次已确认来源不一致':reason==='LIVE_RUNTIME_NOT_AVAILABLE'?'运行环境当前不可用':'现有候选未通过精确版本、来源或权限核验'}</li>)}</ul></>:<p>{pending?'平台正在核对现有已发布能力、准确来源和任务输入输出；无需逐项选择角色或资源。':'本次能力选择尚待核查，原方案与请求保留。'}</p>}
  {issue&&<details><summary>查看核查依据</summary><code>{issue}</code><p>只读核对原选择回执，不会重新派发未知请求。</p></details>}
 </section>;
}
