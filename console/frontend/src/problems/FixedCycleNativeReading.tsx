import {useEffect,useRef,useState} from 'react';
import {readWorkbenchSession,type WorkbenchSession} from '../api/businessWorkspace';
import {conversationScope} from './conversationViewState';
import {ConversationPlacement} from './ConversationPlacement';
import {NativeStepOutput} from './NativeStepOutput';

export type FixedCycleQuestion={invocationId:string;questionKey:string;questionDigest:string;question:string;expiresAt:string;answer:string|null;expired:boolean};
type Step={id:string;at?:string;decision:{action:string;tool?:string;question?:string};output:unknown;toolState:string};
type NativeReading={runId:string;steps:Step[];questions:FixedCycleQuestion[]};
/** Original Native GET only; selected questions are verified by the separate delegated-answer owner. */
export function FixedCycleNativeReading({digest,runId,session,rail,onWaiting,terminal,uncertain,onQuestion,delegationEnabled=false}:{delegationEnabled?:boolean;onQuestion?:(question:FixedCycleQuestion|null)=>void;digest:string;runId:string;session:WorkbenchSession;rail:HTMLElement|null;onWaiting:(value:boolean)=>void;terminal:boolean;uncertain:boolean}){
 const [value,setValue]=useState<NativeReading|null>(null),[error,setError]=useState(false),[observedAt,setObservedAt]=useState(0),[selected,setSelected]=useState('');const scope=conversationScope(session);
 useEffect(()=>{let live=true,inflight=false;const controller=new AbortController();async function read(){if(inflight||!live)return;inflight=true;try{
  if(conversationScope(await readWorkbenchSession(controller.signal))!==scope)throw Error('SESSION_CHANGED');
  const response=await fetch('/api/workbench/v1/prepared-executions/'+encodeURIComponent(digest)+'/native-progress',{credentials:'same-origin',headers:{Accept:'application/json'},signal:controller.signal});if(!response.ok)throw Error('NATIVE_READ_UNAVAILABLE');
  const data=(await response.json()).result as NativeReading;if(data?.runId!==runId||!Array.isArray(data.steps)||!Array.isArray(data.questions)||data.questions.some(q=>!q.invocationId||!q.questionKey||!q.questionDigest||typeof q.question!=='string'||!Number.isFinite(Date.parse(q.expiresAt))))throw Error('NATIVE_RUN_MISMATCH');
  if(conversationScope(await readWorkbenchSession(controller.signal))!==scope)throw Error('SESSION_CHANGED');
  if(live){setObservedAt(Date.now());setValue(data);setError(false);onWaiting(!terminal&&!uncertain&&data.questions.some(q=>!q.answer&&!q.expired&&Date.parse(q.expiresAt)>Date.now()))}
 }catch{if(live){setValue(null);setError(true);onWaiting(false)}}finally{inflight=false}}
 const expired=()=>{live=false;controller.abort();setValue(null);setError(true);onWaiting(false)};void read();const timer=window.setInterval(()=>void read(),15000);window.addEventListener('workbench-session-expired',expired);return()=>{live=false;controller.abort();clearInterval(timer);window.removeEventListener('workbench-session-expired',expired);onWaiting(false)};
 },[digest,runId,scope,terminal,uncertain,onWaiting]);
 const questionReceiver=useRef(onQuestion);useEffect(()=>{questionReceiver.current=onQuestion},[onQuestion]);
 useEffect(()=>{const pending=value?.questions.filter(q=>!q.answer&&!q.expired&&Date.parse(q.expiresAt)>Date.now())??[];questionReceiver.current?.(delegationEnabled&&!error&&!terminal&&!uncertain&&pending.length===1?pending[0]:null)},[value,error,terminal,uncertain,delegationEnabled]);
 useEffect(()=>()=>questionReceiver.current?.(null),[digest,runId]);
 const chosen=value?.steps.find(s=>s.id===selected);
 return <><ConversationPlacement target={rail}><section aria-label="本周期实际步骤"><h3>实际步骤</h3>{error?<p>必要追问与工具步骤暂未核实；不会代为回答。</p>:!value?<p>正在读取本次已保存步骤…</p>:<ol className="native-real-steps">{value.steps.map((step,i)=><li key={step.id}><button type="button" onClick={()=>setSelected(step.id)} aria-expanded={selected===step.id}>{i+1}. {step.decision.tool??({CLARIFY:'必要信息核对',FINISH:'完成核验'}[step.decision.action]??'处理步骤')} · {step.toolState==='COMPLETED'?'已返回':step.toolState==='FAILED'?'失败':step.toolState==='RUNNING'?'处理中':'状态待核实'}</button></li>)}</ol>}</section></ConversationPlacement>
 {chosen&&<section aria-label="本周期步骤详情"><h3>{chosen.decision.tool??'处理步骤'}</h3><button type="button" onClick={()=>setSelected('')}>收起步骤详情</button>{chosen.output!=null&&<NativeStepOutput viewKey={digest+':'+runId} stepId={chosen.id} value={chosen.output} documentExpected={chosen.decision.tool==='read_document'}/>}</section>}
 {value?.questions.map(q=><blockquote key={q.questionKey+q.questionDigest}><p>{q.question}</p><p>{q.answer?'本题回答已保存。':q.expired||Date.parse(q.expiresAt)<=observedAt?'本题等待已到期，原记录保留。':terminal?'本题属于已结束运行，原记录保留。':uncertain?'运行状态待核实，本题保留，不据此重新提交或重试。':delegationEnabled?'系统正在等待你的补充；可在会话下方回答这条问题。':'本次运行等待必要信息；当前尚无合法回答委托入口，读取不会代为回答。'}</p>{delegationEnabled&&!q.answer&&!q.expired&&!terminal&&!uncertain&&Date.parse(q.expiresAt)>observedAt&&<button type="button" onClick={()=>questionReceiver.current?.(q)}>回答这条问题</button>}</blockquote>)}
 </>;
}
