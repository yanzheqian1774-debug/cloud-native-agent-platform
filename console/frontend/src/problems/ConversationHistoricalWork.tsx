import {useEffect,useState,type ReactNode} from 'react';
import type {WorkbenchSession} from '../api/businessWorkspace';
import {readWorkbenchSession} from '../api/businessWorkspace';
import {preparedRequest,type ExecutionView} from '../api/preparedExecution';
import type {WorkLink} from '../api/privateConversation';
import {conversationScope} from './conversationViewState';
import {ConversationPlacement} from './ConversationPlacement';
import {PreparedDeliverySummary} from './PreparedDeliverySummary';
import {Link} from 'react-router-dom';

const states:Record<string,string>={SUCCEEDED:'历史执行已完成',RUNNING:'执行中',QUEUED:'排队中',FAILED:'执行失败',UNKNOWN:'结果待核实',RECOVERY_REQUIRED:'需要恢复核查',CANCELLED:'已取消',CANCELED:'已取消'};

/** Existing exact work only. Reading never creates a journey or retries execution. */
export function ConversationHistoricalWork({link,links,conversation,session,rail,onSelect,associationControls}:{link:WorkLink;links:WorkLink[];conversation:string;session:WorkbenchSession;rail:HTMLElement|null;onSelect:(id:string)=>void;associationControls:ReactNode}){
 const target=link.target!,digest=target.executionDigest!,scope=conversationScope(session);
 const key=JSON.stringify([scope,conversation,link.link_id,digest,target.problemId,target.revisionId,target.problemDigest]);
 const [loaded,setLoaded]=useState<{key:string;view:ExecutionView}|null>(null),[error,setError]=useState(''),[selected,setSelected]=useState(''),[review,setReview]=useState(false);
 useEffect(()=>{
  let active=true,generation=0;
  async function refresh(){const current=++generation;setLoaded(null);setError('');try{
   const before=await readWorkbenchSession();if(conversationScope(before)!==scope)throw Error('CONVERSATION_IDENTITY_CHANGED');
   const view=await preparedRequest<ExecutionView>(digest),after=await readWorkbenchSession();
   const problem=view.preparation.semantics.target.problem;
   if(conversationScope(after)!==scope||view.digest!==digest||problem.resource_id!==target.problemId||problem.revision_id!==target.revisionId||problem.digest!==target.problemDigest)throw Error('HISTORICAL_WORK_BINDING_MISMATCH');
   if(active&&current===generation)setLoaded({key,view});
  }catch(e){if(active&&current===generation){setLoaded(null);setError(String(e))}}}
  const expired=()=>{generation++;setLoaded(null);setError('当前登录已失效，历史记录保留。')};
  void refresh();window.addEventListener('focus',refresh);window.addEventListener('workbench-session-expired',expired);
  return()=>{active=false;generation++;window.removeEventListener('focus',refresh);window.removeEventListener('workbench-session-expired',expired)};
 },[key,scope,digest,target.problemId,target.revisionId,target.problemDigest]);
 const view=loaded?.key===key?loaded.view:null;
 const status=view?states[view.progress?.state??'']??'历史状态待核实':'正在读取历史工作';
 return <section className="conversation-history" aria-label="关联历史工作">
  <div className="conversation-assistant-bubble"><p className="conversation-history-label">历史工作 · 已保存记录</p><h2>{link.title??'关联工作'}</h2><p>以下为此前保存的工作与成果，不代表本会话发起了新的执行。</p>
   {error?<div role="alert"><p>历史工作暂未读回，原记录保留。</p><details><summary>核查依据</summary><code>{error}</code></details></div>:!view?<p role="status">正在读取历史进度与成果…</p>:<>
    <p>{status}。业务是否解决以原评价为准。</p>
    {view.progress?.state==='SUCCEEDED'&&view.artifacts.length>0?<PreparedDeliverySummary view={view} viewKey={key} selectedArtifact={selected} onArtifact={setSelected} onCloseArtifact={()=>setSelected('')} query="" onReview={()=>setReview(v=>!v)}/>:<p>{view.artifacts.length?'已有中间产物，完整结果尚未确认。':'当前未读到交付成果。'}</p>}
    {review&&<p>{view.outcome?'已有可读评价记录，不能仅凭执行完成认定业务已解决。':'当前未读回评价，不代表没有历史记录。'}</p>}
   </>}
  </div>
  <ConversationPlacement target={rail}><section className="conversation-history-rail" aria-label="历史工作进展"><h3>历史工作</h3><strong>{error?'读取需要核查':status}</strong><p>{link.title}</p><h3>成果与依据</h3><p>{view?`${view.artifacts.length} 份当前可读产物`:'正在核对原成果'}</p><p>结果与引用在左侧正文查看。</p>
   {view&&<><h3>资料范围</h3><Link to={'/knowledge?'+new URLSearchParams({kind:'knowledge',query:view.preparation.source_snapshot.resource_id,selected:view.preparation.source_snapshot.resource_id,resourceRevision:view.preparation.source_snapshot.revision_id,resourceDigest:view.preparation.source_snapshot.digest,fromExecution:view.digest,returnConversation:conversation})}>查看原资料与固定版本</Link></>}
   <details><summary>切换关联工作</summary>{links.filter(item=>item.readable&&item.target?.executionDigest).map(item=><button type="button" key={item.link_id} aria-pressed={item.link_id===link.link_id} onClick={()=>onSelect(item.link_id)}>{item.title??'历史工作'}</button>)}</details>
   <details><summary>管理关联工作</summary>{associationControls}</details>
  </section></ConversationPlacement>
 </section>;
}
