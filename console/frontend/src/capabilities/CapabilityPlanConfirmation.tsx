import {useCapabilityAdvance} from './useCapabilityAdvance';
import {useEffect,useRef,useState} from 'react';
import {capabilitySession,type CapabilityExecutionContract} from '../api/businessCapabilities';
import {workbenchPrincipalKey} from '../api/digitalEmployees';
import {conversationRequest} from '../api/privateConversation';
import {planningRequest,type Invocation} from '../planning/planningRequests';
import type {History,ProposalRead,Confirmation} from '../planning/api';
import {capabilityJournalPath,readCapabilityJournal,type CapabilityJournal} from './capabilityWorkJournal';

export function CapabilityPlanConfirmation({conversation,messageId,principal,journal,result,onRefresh,autoContinue=false,onStop}:{conversation:string;messageId:string;principal:string;journal:CapabilityJournal;result:Invocation|null;onRefresh:()=>void;autoContinue?:boolean;onStop?:()=>void}){
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[confirmed,setConfirmed]=useState<Confirmation|null>(null);
 const flight=useRef(false),alive=useRef(true);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[]);
 async function session(){const value=await capabilitySession();if(!alive.current||workbenchPrincipalKey(value)!==principal)throw Error('登录身份或当前工作已变化，请重新读取。');return value}
 async function act(){
  if(flight.current)return;flight.current=true;setBusy(true);setError('');
  try{
   const s=await session(),expected={principal:JSON.stringify(s.principal),isCurrent:()=>alive.current};
   const current=await readCapabilityJournal(conversation,messageId,principal,AbortSignal.timeout(30_000));
   if(current.contractDigest!==journal.contractDigest||current.state?.problemId!==journal.state?.problemId||current.version!==journal.version)throw Error('当前进展已变化，请重新读取。');
   const state=current.state!;
   const source=await conversationRequest<CapabilityExecutionContract>('/'+encodeURIComponent(conversation)+'/sources/'+encodeURIComponent(messageId)+'/execution-contract');
   if(source.contractDigest!==journal.contractDigest||source.contract.conversationId!==conversation||source.contract.sourceMessageId!==messageId)throw Error('原会话目标未能核对，停止确认。');
   const pending=state.phase==='PLAN_CONFIRMING'||state.phase==='PLAN_CONFIRMED';
   const proposalId=pending?state.proposalId:result?.result.proposal?.proposal_id;
   const revision=pending?state.proposalRevision:result?.result.proposal?.revision;
   const digest=pending?state.proposalDigest:result?.result.proposal_digest;
   if(!proposalId||!revision||!digest||(!pending&&(state.phase!=='PLAN_READY'||result?.result.technical_status!=='SUCCEEDED'||result.invocation.target.invocation_id!==state.invocationId)))throw Error('尚未读回本次可确认方案，请先读取原方案调用。');
   const path='planning-v2/'+encodeURIComponent(proposalId);
   const owned=await planningRequest<ProposalRead>(path+'?version='+revision,undefined,{},expected);
   if(owned.digest!==digest||owned.proposal.revision!==revision||owned.proposal.proposal_id!==proposalId||owned.proposal.semantics.target.problem.resource_id!==state.problemId)throw Error('方案版本或目标不一致，停止确认。');
   const read=()=>planningRequest<History>(path+'/history',undefined,{},expected);
   const find=(history:History)=>{
    const matches=history.plans.filter(item=>item.plan.plan_id===proposalId&&item.plan.source_proposal_revision===revision&&item.plan.source_proposal_digest===digest&&JSON.stringify(item.plan.semantics.target)===JSON.stringify(owned.proposal.semantics.target));
    if(matches.length>1)throw Error('存在多份确认记录，需要核对后继续。');return matches[0];
   };
   let history=await read(),value=find(history),latest=current;
   async function save(phase:string,extra:Partial<NonNullable<CapabilityJournal['state']>>){
    const auth=await session();await conversationRequest(capabilityJournalPath(conversation,messageId),auth.csrfToken,{expectedVersion:latest.version,idempotencyKey:'capability:'+journal.contractDigest+':journal:'+latest.version,contractDigest:journal.contractDigest,state:{...latest.state,phase,...extra}});
    latest=await readCapabilityJournal(conversation,messageId,principal,AbortSignal.timeout(30_000));
    if(latest.contractDigest!==journal.contractDigest||latest.state?.problemId!==state.problemId||latest.state.phase!==phase)throw Error('确认进展尚未核实，请读取原记录。');
   }
   if(!value){
    if(pending)throw Error('尚未读回确认记录；保留原请求，不会自动再次提交。');
    const version=Math.max(0,...history.plans.map(item=>item.plan.version));
    await save('PLAN_CONFIRMING',{proposalId,proposalRevision:revision,proposalDigest:digest});onRefresh();
    await planningRequest(path+'/confirmation/automatic',{problem:owned.proposal.semantics.target.problem,revision,digest,expectedPlanVersion:version,idempotencyKey:'capability-confirm:'+digest,capabilityConversationId:conversation,capabilityMessageId:messageId,capabilityContractDigest:journal.contractDigest},{},expected);
    history=await read();value=find(history);
   }
   if(!value)throw Error('确认已提交，但结果尚未读回，请读取原确认记录。');
   await session();
   if(latest.state?.phase!=='PLAN_CONFIRMED')await save('PLAN_CONFIRMED',{proposalId,proposalRevision:revision,proposalDigest:digest,confirmedPlan:{id:value.plan.plan_id,version:value.plan.version,digest:value.digest}});
   await session();setConfirmed(value);onRefresh();
  }catch(cause){onStop?.();if(alive.current)setError(cause instanceof Error&&/[\u4e00-\u9fff]/.test(cause.message)?cause.message:'确认响应尚未核实，请读取原确认记录。')}
  finally{flight.current=false;if(alive.current)setBusy(false)}
 }
 useCapabilityAdvance(autoContinue&&journal.state?.phase==='PLAN_READY',JSON.stringify([principal,conversation,messageId,journal.contractDigest,'PLAN_READY']),()=>act());
 const phase=journal.state?.phase;
 if(!['PLAN_READY','PLAN_CONFIRMING','PLAN_CONFIRMED'].includes(phase??''))return null;
 return <section aria-label="本次方案确认"><button type="button" disabled={busy} onClick={()=>void act()}>{busy?'正在核对方案确认…':phase==='PLAN_READY'?'确认本次方案': '读取原确认记录'}</button>{busy&&<p role="status">正在核对原目标、完成标准和方案记录，不会再次调用模型。</p>}{error&&<p role="alert">{error}</p>}{confirmed&&<p>方案确认已读回，接下来准备本次固定资源。尚未启动执行。</p>}</section>;
}
