import type {FixedCycleFocus} from '../api/conversationFixedFocus';
import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {FixedCycleNativeReading} from './FixedCycleNativeReading';
import type {WorkbenchSession} from '../api/businessWorkspace';
import {conversationScope} from './conversationViewState';
import {ConversationPlacement} from './ConversationPlacement';
import {FixedCycleRunSelection} from './FixedCycleRunSelection';
import {FixedCycleExecutionReading} from './FixedCycleExecutionReading';
import {fixedCycleStatus,cycleScheduledLabel} from './fixedCyclePresentation';
import {useFixedConversationCycles} from './useFixedConversationCycles';
import {readViewString,saveViewString} from './workViewState';
import './FixedCycleConversation.css';

export function ConversationFixedCycles({conversation,session,rail,hidden,onBound,onFocus,returnFocus}:{returnFocus?:{key:string;focus:FixedCycleFocus}|null;onFocus?:(focus:FixedCycleFocus|null)=>void;conversation:string;session:WorkbenchSession;rail:HTMLElement|null;hidden:boolean;onBound:(bound:boolean)=>void}){
 const cycle=useFixedConversationCycles(conversation,session),section=useRef<HTMLElement>(null),restore=useRef(false);
 const [waiting,setWaiting]=useState(false),[returnIssue,setReturnIssue]=useState(false);
 const returnKey=useRef<string|null>(null),expectedReturn=useRef<FixedCycleFocus|null>(null);
 const key=conversationScope(session)+':fixed-cycle:'+conversation;
 const bound=cycle.page?.state==='BOUND';
 useEffect(()=>{if(cycle.page?.state==='BOUND')onBound(true);else if(cycle.page?.state==='NO_BOUND_WORK')onBound(false)},[cycle.page?.state,onBound]);
 useEffect(()=>()=>onBound(false),[onBound]);
 const row=cycle.page?.items.find(x=>x.eventId===cycle.selected),options=cycle.page?.items.filter(x=>x.phase==='PLANNING'||x.readState==='READABLE').map(x=>({eventId:x.eventId,scheduledAt:x.scheduledAt,recordedAt:x.recordedAt,state:x.phase==='PLANNING'?x.planningState:x.execution?.state}))??[];

 useEffect(()=>{onFocus?.(cycle.page?.state==='BOUND'&&row?.phase==='EXECUTION'&&cycle.view&&!cycle.error&&!cycle.readError&&!returnIssue?{bindingDigest:cycle.page.bindingDigest,workDigest:cycle.page.work.digest,eventId:row.eventId,receiptDigest:row.receiptDigest,preparationDigest:row.preparationDigest,runId:row.runId}:null);return()=>onFocus?.(null)},[cycle.page,cycle.view,cycle.error,cycle.readError,row,onFocus,returnIssue]);
 useEffect(()=>{if(!returnFocus||returnKey.current===returnFocus.key)return;returnKey.current=returnFocus.key;expectedReturn.current=returnFocus.focus;cycle.select(returnFocus.focus.eventId);},[returnFocus,cycle]);
 useEffect(()=>{const expected=expectedReturn.current;if(!expected||!cycle.page)return;const item=cycle.page.items.find(i=>i.eventId===expected.eventId);if(!item)return;const mismatch=cycle.page.bindingDigest!==expected.bindingDigest||cycle.page.work.digest!==expected.workDigest||item.phase!=='EXECUTION'||item.receiptDigest!==expected.receiptDigest||item.preparationDigest!==expected.preparationDigest||item.runId!==expected.runId;void Promise.resolve().then(()=>setReturnIssue(mismatch));},[cycle.page]);
 // A successful exact read may precede the next directory projection.
 if(row?.phase==='EXECUTION'&&cycle.view&&!options.some(x=>x.eventId===row.eventId))options.push({eventId:row.eventId,scheduledAt:row.scheduledAt,recordedAt:row.recordedAt,state:cycle.view.progress?.state});
 function select(event:string){expectedReturn.current=null;setReturnIssue(false);const stream=section.current?.closest('.px-message-stream');if(stream&&cycle.selected)saveViewString(key+':'+cycle.selected,'scroll',String(stream.scrollTop));restore.current=true;cycle.select(event)}
 useLayoutEffect(()=>{if(!restore.current||!cycle.view)return;restore.current=false;const stream=section.current?.closest('.px-message-stream'),saved=readViewString(key+':'+cycle.selected,'scroll');if(stream){const top=saved?Number(saved):stream.scrollTop+(section.current!.getBoundingClientRect().top-stream.getBoundingClientRect().top);if(Number.isFinite(top)){stream.dispatchEvent(new Event('wheel',{bubbles:true}));stream.scrollTop=top}}},[cycle.view,cycle.selected,key]);
 if(!bound&&!cycle.error)return null;
 const newest=options[0],newRun=Boolean(newest&&cycle.selected&&newest.eventId!==cycle.selected);
 const status=returnIssue?'结果身份待核实':fixedCycleStatus(cycle.view?.progress?.state??(row?.phase==='PLANNING'?row.planningState:row?.execution?.state),waiting);
 return <section ref={section} className="fixed-cycle-conversation journey-progress" aria-label="固定工作周期结果" hidden={hidden}>
  <p className="fixed-cycle-origin">固定工作{cycle.page?.workTitle?' · '+cycle.page.workTitle:''}{row?' · '+cycleScheduledLabel(row.scheduledAt,row.timezone):''} · {row?.phase==='PLANNING'?'系统准备记录':'系统运行记录'}</p>
  <h2>{row?.phase==='PLANNING'?'本周期方案准备':row?'本次运行与成果':'固定工作运行记录'}</h2>
  {cycle.error?<p role="alert" className="fixed-cycle-read-error">{cycle.error}</p>:bound&&<>
   {!cycle.page!.items.length&&<p>{cycle.page!.partial?'当前仅取得部分记录，不能认定尚无运行。':'当前尚无已提交的运行记录。保存安排与实际触发分别核对。'}</p>}
   {row?.phase==='PLANNING'&&<p>已发现本周期的方案准备记录，尚未建立执行与成果；这里不会启动或补发任务。</p>}
   {row&&<p className="fixed-cycle-status">{status}。{!returnIssue&&cycle.view?.progress?.state==='SUCCEEDED'?'执行完成不等于业务结论已确认。':'不会因刷新重新启动或重试。'}</p>}
   {cycle.readError&&<p role="status" className="fixed-cycle-read-error">{cycle.readError}</p>}
   {returnIssue&&<p role="alert">原消息所关联的周期身份尚未核实，不用其他结果替代。</p>}
   {!returnIssue&&cycle.view&&row&&<FixedCycleExecutionReading key={key+':'+row.eventId} viewKey={key+':'+row.eventId} view={cycle.view} conversation={conversation}/>}
   {cycle.page!.partial&&<p>部分记录暂不可读，当前结果不代表全部周期。</p>}
  </>}
  {!returnIssue&&cycle.readExpired&&<button type="button" disabled={cycle.busy} onClick={()=>void cycle.renewRead()}>恢复本次结果读取</button>}
  <button type="button" disabled={cycle.busy} onClick={cycle.refresh}>核对周期记录</button>
  {cycle.page?.hasMore&&<button type="button" disabled={cycle.busy} onClick={cycle.more}>读取更早运行</button>}
  <ConversationPlacement target={hidden?null:rail}><section aria-label="周期运行进展">
   <FixedCycleRunSelection items={options} selected={cycle.selected} timezone={row?.timezone??cycle.page?.trigger.timezone??'UTC'} onSelect={select} newRun={newRun} onReadNew={()=>{if(newest)select(newest.eventId)}}/>
   <strong>{cycle.error?'读取待核实':row?status:'等待运行记录'}</strong>
   {!returnIssue&&cycle.view&&<p>{cycle.view.progress?.tasks.filter(x=>x.state==='SUCCEEDED').length??0}/{cycle.view.preparation.semantics.tasks.length} 项任务完成 · {cycle.view.artifacts.length} 份已保存产物</p>}
   <p>仅显示本次运行的过程、资源与成果。</p>
   <details><summary>必要追问的处理边界</summary><p>执行问题须有本题与本次运行的正式回答入口；当前未接通回答委托，读取结果不会代为回答。</p></details>
  </section></ConversationPlacement>
   {!returnIssue&&cycle.view&&row?.phase==='EXECUTION'&&<FixedCycleNativeReading key={row.eventId+row.runId} digest={row.preparationDigest} runId={row.runId} session={session} rail={hidden?null:rail} onWaiting={setWaiting} terminal={['SUCCEEDED','FAILED','CANCELLED'].includes(cycle.view.progress?.state??'')} uncertain={['RECOVERY_REQUIRED','UNKNOWN'].includes(cycle.view.progress?.state??'')}/>}
 </section>;
}
