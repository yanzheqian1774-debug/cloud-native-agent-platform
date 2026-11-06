import {conversationScope} from './conversationViewState';
import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {listBusinessProblems,readWorkbenchSession,type BusinessProblemRevision} from '../api/businessWorkspace';
import {conversationRequest,type PrivateConversation} from '../api/privateConversation';
import {preparedRequest,type ExecutionView} from '../api/preparedExecution';

type Work={execution:ExecutionView;conversation:string};
type Item={problem:BusinessProblemRevision;works:Work[]};
function attentionReason(e:ExecutionView){
 if(e.progress&&['FAILED','OUTCOME_UNKNOWN','UNKNOWN','RECOVERY_REQUIRED','CANCELLED'].includes(e.progress.state))return '执行需要核查，请查看原任务与恢复记录。';
 if(e.progress?.tasks.some(t=>['FAILED','OUTCOME_UNKNOWN','UNKNOWN','RECOVERY_REQUIRED'].includes(t.state)))return '部分任务需要核查，请查看原任务依据。';
 if(e.outcome?.businessResolution==='UNDETERMINED'&&!e.outcome.confirmationId)return '业务结果尚未判定，请核对交付证据与完成标准。';
 if(e.executionStarted&&!e.progress)return '尚未取得执行进度，请在原工作中核查。';
 return '';
}
export function CurrentWorkDirectory({outcomes=false,attention=false}:{outcomes?:boolean;attention?:boolean}){
 const [items,setItems]=useState<Item[]|null>(null),[error,setError]=useState(''),[limited,setLimited]=useState(false),[version,setVersion]=useState(0);
 useEffect(()=>{let live=true;const expired=()=>{live=false;setItems(null);setError('登录已失效，请重新登录后读取。')};window.addEventListener('workbench-session-expired',expired);async function load(){
   const scope=conversationScope(await readWorkbenchSession());
   const problems=await listBusinessProblems();let incomplete=false;
   const refs=new Map<string,{problemId:string;conversation:string}>();
   // Links locate work. Its original owner reauthorizes every displayed fact.
   try{const conversations=await conversationRequest<{items:{conversation_id:string}[]}>();for(const c of conversations.items){try{const data=await conversationRequest<PrivateConversation>('/'+c.conversation_id);for(const link of data.links){if(link.readable&&link.target?.executionDigest)refs.set(link.target.executionDigest,{problemId:link.target.problemId,conversation:c.conversation_id});else if(!link.readable)incomplete=true;}}catch{incomplete=true;}}}catch{incomplete=true;}
   const works:Work[]=[];
   for(const [digest,ref] of refs){try{const execution=await preparedRequest<ExecutionView>(digest);if(execution.digest===digest&&execution.preparation.semantics.target.problem.resource_id===ref.problemId)works.push({execution,conversation:ref.conversation});else incomplete=true;}catch{incomplete=true;}}
   if(conversationScope(await readWorkbenchSession())!==scope)throw new Error('登录身份已变化，请重新读取当前工作。');
   if(live){setItems(problems.problems.map(problem=>({problem,works:works.filter(w=>w.execution.preparation.semantics.target.problem.resource_id===problem.business_problem_id)})));setLimited(incomplete);setError('');}
  }void load().catch(e=>{if(live){setItems(null);setError(String(e));}});return()=>{live=false;window.removeEventListener('workbench-session-expired',expired)};},[version]);
 useEffect(()=>{const refresh=()=>{setItems(null);setVersion(v=>v+1)};window.addEventListener('focus',refresh);return()=>window.removeEventListener('focus',refresh)},[]);
 const visible=attention?items?.map(item=>({...item,works:item.works.filter(w=>attentionReason(w.execution))})).filter(item=>item.works.length):items;
 return <main className="px-page px-center-page"><header className="px-page-title"><div><p>{attention?'待处理事项':outcomes?'成果与标准评价':'计划与任务'}</p><h1>{attention?'核对当前工作的待处理事项':outcomes?'查看原工作的证据与成果':'继续当前业务问题的计划与任务'}</h1><span>按当前权限读取问题和原执行记录。</span></div><Link to="/work">返回会话</Link></header><section className="px-center-card"><p>{attention?'这里只展示本人会话已关联、当前可读的执行核查与业务结果确认事项。审批与其他领域事项仍在各自入口处理。':'执行详情范围为本人会话已关联的精确工作。其他记录请从原问题继续查看。'}</p><button onClick={()=>{setItems(null);setVersion(v=>v+1)}}>重新读取</button>{limited&&<p role="status">部分关联记录当前未能读取。本页只展示已核实事项，不能据此认定全部工作均已处理。</p>}{error?<p role="alert">当前工作读取失败：{error}</p>:visible==null?<p role="status">正在读取当前可访问工作…</p>:!visible.length?<p>{attention?'当前可读的关联工作中，没有发现上述待处理事项。':'当前没有可读取的业务问题。'}</p>:<div className="px-record-list">{visible.map(({problem,works})=><article key={problem.business_problem_id}><h2>{problem.title}</h2><Link to={'/work?problem='+encodeURIComponent(problem.business_problem_id)}>打开原问题</Link>{!works.length&&<p>当前未取得关联执行的可读记录；请在原问题中查看已保存计划和原记录。</p>}{works.map(({execution:e,conversation})=><section key={e.digest}><h3>{e.preparation.semantics.title}</h3>{attention?<p>{attentionReason(e)}</p>:outcomes?<><p>业务结果：{e.outcome?.businessResolution??'尚无可读的标准评价'}</p><p>已有产物：{e.artifacts.length} 项</p>{e.outcome?.evaluation.results.map(r=><p key={r.criterionRevisionId}>{r.check??'完成标准'}：{r.result} · {r.reason}</p>)}</>:<><p>原执行状态：{e.progress?.state??(e.executionStarted?'状态待核实':'尚未启动')}</p>{e.preparation.semantics.tasks.map(t=><p key={t.task_id}>{t.title} · {e.progress?.tasks.find(x=>x.task_id===t.task_id)?.state??(e.executionStarted?'状态待核实':'尚未启动')}</p>)}</>}<Link to={'/work?'+new URLSearchParams({problem:problem.business_problem_id,execution:e.digest,returnConversation:conversation})}>查看原任务、证据与成果</Link></section>)}</article>)}</div>}</section></main>;
}
