import {conversationScope} from "./conversationViewState";
import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {listBusinessProblems,readWorkbenchSession,type BusinessProblemRevision} from '../api/businessWorkspace';
import {conversationRequest,type PrivateConversation} from '../api/privateConversation';
import {preparedRequest,type ExecutionView} from '../api/preparedExecution';

type Item={problem:BusinessProblemRevision;works:{execution:ExecutionView;conversation:string}[]};
export function CurrentWorkDirectory({outcomes=false}:{outcomes?:boolean}){
 const [items,setItems]=useState<Item[]|null>(null),[error,setError]=useState(''),[version,setVersion]=useState(0);
 useEffect(()=>{let live=true;const expired=()=>{live=false;setItems(null);setError('登录已失效，请重新登录后读取。')};window.addEventListener('workbench-session-expired',expired);async function load(){
   const scope=conversationScope(await readWorkbenchSession());
   const problems=await listBusinessProblems();
   const refs=new Map<string,{problemId:string;conversation:string}>();
   // Private links are navigation references; every actual execution is read
   // again through its original owner before any facts are displayed.
   try{const conversations=await conversationRequest<{items:{conversation_id:string}[]}>();for(const c of conversations.items){const data=await conversationRequest<PrivateConversation>('/'+c.conversation_id);for(const link of data.links){if(link.readable&&link.target?.executionDigest)refs.set(link.target.executionDigest,{problemId:link.target.problemId,conversation:c.conversation_id})}}}catch{/* Problem entry stays usable if private conversations are disabled. */}
   const works:{execution:ExecutionView;conversation:string}[]=[];
   for(const [digest,ref] of refs){try{const execution=await preparedRequest<ExecutionView>(digest);if(execution.digest===digest&&execution.preparation.semantics.target.problem.resource_id===ref.problemId)works.push({execution,conversation:ref.conversation})}catch{/* Revoked execution is not rendered from a cached link. */}}
   if(conversationScope(await readWorkbenchSession())!==scope)throw new Error('登录身份已变化，请重新读取当前工作。');
   if(live){setItems(problems.problems.map(problem=>({problem,works:works.filter(w=>w.execution.preparation.semantics.target.problem.resource_id===problem.business_problem_id)})));setError('')}
  }void load().catch(e=>{if(live){setItems(null);setError(String(e))}});return()=>{live=false;window.removeEventListener('workbench-session-expired',expired)};},[version]);
 useEffect(()=>{const refresh=()=>{setItems(null);setVersion(v=>v+1)};window.addEventListener('focus',refresh);return()=>window.removeEventListener('focus',refresh)},[]);
 return <main className="px-page px-center-page"><header className="px-page-title"><div><p>{outcomes?'成果与标准评价':'计划与任务'}</p><h1>{outcomes?'查看原工作的证据与成果':'继续当前业务问题的计划与任务'}</h1><span>按当前权限读取问题和原执行记录。</span></div><Link to="/work">返回会话</Link></header><section className="px-center-card"><p>执行详情范围为本人会话已关联的精确工作。其他记录请从原问题继续查看。</p><button onClick={()=>setVersion(v=>v+1)}>重新读取</button>{error?<p role="alert">当前工作读取失败：{error}</p>:items===null?<p role="status">正在读取当前可访问工作…</p>:!items.length?<p>当前没有可读取的业务问题。</p>:<div className="px-record-list">{items.map(({problem,works})=><article key={problem.business_problem_id}><h2>{problem.title}</h2><Link to={'/work?problem='+encodeURIComponent(problem.business_problem_id)}>打开原问题</Link>{!works.length&&<p>当前未取得关联执行的可读记录；请在原问题中查看已保存计划和原记录。</p>}{works.map(({execution:e,conversation})=><section key={e.digest}><h3>{e.preparation.semantics.title}</h3>{outcomes?<><p>业务结果：{e.outcome?.businessResolution??'尚无可读的标准评价'}</p><p>已有产物：{e.artifacts.length} 项</p>{e.outcome?.evaluation.results.map(r=><p key={r.criterionRevisionId}>{r.check??'完成标准'}：{r.result} · {r.reason}</p>)}</>:<><p>原执行状态：{e.progress?.state??(e.executionStarted?'状态待核实':'尚未启动')}</p>{e.preparation.semantics.tasks.map(t=><p key={t.task_id}>{t.title} · {e.progress?.tasks.find(x=>x.task_id===t.task_id)?.state??(e.executionStarted?'状态待核实':'尚未启动')}</p>)}</>}<Link to={'/work?'+new URLSearchParams({problem:problem.business_problem_id,execution:e.digest,returnConversation:conversation})}>查看原任务、证据与成果</Link></section>)}</article>)}</div>}</section></main>;
}
