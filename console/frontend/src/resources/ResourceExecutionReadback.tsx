import {verifyDefinitionExecution} from './definitionExecutionBinding';
import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {readWorkbenchSession} from '../api/businessWorkspace';
import {preparedRequest,type ExecutionView} from '../api/preparedExecution';
import {PreparedDeliverySummary} from '../problems/PreparedDeliverySummary';
import {loadResourceReadContext,resourceReadScope,resourceReturnHref,type ResourceReadContext} from './resourceReadContext';
import '../problems/PreparedExecutionPanel.css';
import './ResourceReadback.css';
const states:Record<string,string>={SUCCEEDED:'执行完成',FAILED:'执行失败',CANCELLED:'已取消',RUNNING:'执行中',QUEUED:'排队中',RECOVERY_REQUIRED:'待恢复核对'};

/** Saved execution readback only. No command adapter, draft, authorization or replay. */
export function ResourceExecutionReadback({contextId}:{contextId:string}){
 const [loaded,setLoaded]=useState<{key:string;context:ResourceReadContext;view:ExecutionView}|null>(null),[error,setError]=useState(''),[selected,setSelected]=useState(''),[review,setReview]=useState(false);
 useEffect(()=>{
  let active=true,generation=0;const abort=new AbortController();
  async function load(version:number){
   const before=await readWorkbenchSession(abort.signal),context=loadResourceReadContext(before,contextId);
   const view=await preparedRequest<ExecutionView>(context.execution.digest),after=await readWorkbenchSession(abort.signal);
   if(resourceReadScope(before)!==resourceReadScope(after))throw Error('RESOURCE_DIRECTORY_IDENTITY_CHANGED');
   loadResourceReadContext(after,contextId);
   if(view.digest!==context.execution.digest||view.preparation.semantics.target.problem.resource_id!==context.execution.problemId||!await verifyDefinitionExecution(view,context,abort.signal))throw Error('RESOURCE_EXECUTION_BINDING_MISMATCH');
   const finalSession=await readWorkbenchSession(abort.signal);if(resourceReadScope(before)!==resourceReadScope(finalSession))throw Error('RESOURCE_DIRECTORY_IDENTITY_CHANGED');
   if(active&&version===generation){setLoaded({key:contextId,context,view});setError('')}
  }
  const refresh=()=>{const version=++generation;setLoaded(null);setError('');void load(version).catch(e=>{if(active&&version===generation){setLoaded(null);setError(String(e))}})};
  const expired=()=>{generation++;setLoaded(null);setError('当前登录已失效，原记录保留。')};
  refresh();window.addEventListener('focus',refresh);window.addEventListener('workbench-session-expired',expired);
  return()=>{active=false;abort.abort();window.removeEventListener('focus',refresh);window.removeEventListener('workbench-session-expired',expired)};
 },[contextId]);
 const data=loaded?.key===contextId?loaded:null;
 return <main className="px-page resource-execution-readback"><h1>已有执行的只读核对</h1><p>这里只查看保存的执行与成果，不启动、重试或改变原工作。</p>
 {error?<div role="alert"><h2>原执行暂未读回</h2><p>返回上下文、当前身份或准确版本未通过核对，已清空旧内容。请使用浏览器返回原资源，重新核对读取范围。</p><details><summary>核查依据</summary><code>{error}</code></details></div>:!data?<p role="status">正在核对原执行与准确资源引用…</p>:<>
 <nav aria-label="原执行只读返回"><Link to={resourceReturnHref(contextId,data.context)}>返回同一准确资源</Link>{data.context.conversation&&<Link to={'/work?'+new URLSearchParams({conversation:data.context.conversation})}>返回原会话</Link>}</nav>
 <section className="px-result-card" aria-label="原执行保存绑定"><h2>{data.view.preparation.semantics.title}</h2><p>方案 v{data.view.preparation.plan_version} · {states[data.view.progress?.state??'']??'状态尚待核对'}</p><p>已核对保存的资源、修订和摘要。{data.context.referenceKind==='agent'&&'已同时核对原员工版本中的Agent成员引用。'}保存绑定不是实际调用回执，技术成功与业务验收分别记录。</p><p>调用快照：{data.view.resourceUses.some(u=>u.state==='READ_RESTRICTED')?'当前存在读取受限记录，不能视为未调用。':'仅以当前授权读回的记录为准。'}</p></section>
 {data.view.progress?.state==='SUCCEEDED'?<PreparedDeliverySummary view={data.view} viewKey={'resource-read:'+contextId} selectedArtifact={selected} onArtifact={setSelected} onCloseArtifact={()=>setSelected('')} query="" onReview={()=>setReview(!review)}/>:<p>这里只回看保存的原状态，不推定已有成功成果。</p>}
 {review&&<section className="px-result-card" aria-label="可读验收记录"><h2>可读验收记录</h2><p>{data.view.outcome?'已有当前授权可读的评价记录，业务决定仍需独立核对。':'当前未读回评价记录；这不表示没有历史评价或业务已接受。'}</p></section>}
 </>}
 </main>;
}
