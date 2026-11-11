import type {ModelProgress} from '../api/modelStream';
import type {Invocation} from '../planning/planningRequests';
import type {CapabilityJournal} from './capabilityWorkJournal';

export function CapabilityPlanningRail({journal,busy,stage,error,stream,result}:{journal:CapabilityJournal;busy:boolean;stage:string;error:string;stream:ModelProgress|null;result:Invocation|null}){
 const phase=journal.state?.phase;
 const returned=result?.result.technical_status==='SUCCEEDED';
 const clarification=returned&&result.result.kind==='NEEDS_CLARIFICATION';
 const proposed=returned&&Boolean(result.result.proposal);
 const confirmationSaved=phase==='PLAN_CONFIRMED',confirming=phase==='PLAN_CONFIRMING';
 const resourcePhase=['RESOURCE_SELECTING','RESOURCES_SELECTED','RESOURCES_PREPARING','RESOURCES_READY'].includes(phase??'');
 const title=error?'需要处理':busy?'正在准备方案':resourcePhase?'资源办理记录已保存':confirmationSaved?'确认记录已保存':confirming?'等待核对确认':clarification?'等待你的补充':proposed?'方案已返回':phase==='PREPARE_PLAN'?'准备方案':phase==='PLANNING_PENDING'?'等待核实':'读取已保存进展';
 const message=error|| (busy?stage:resourcePhase?'本次固定资源办理记录已保存，请读取原记录核实；尚未启动执行。':confirmationSaved?'方案确认记录已保存，可读取原记录核实；资源准备与执行尚未完成。':confirming?'确认请求已记录，请读取原确认记录，避免重复提交。':clarification?'请在下方固定输入区补充；回答后沿用原工作继续。':proposed?'方案已读回，尚未确认或启动执行。':phase==='PREPARE_PLAN'?'目标和完成标准已保存，下一步核对资料与工具并准备方案。':'已保存的办理记录仍保留；请读取原方案调用，刷新不会重复派发。');
 return <section className="capability-live-status journey-progress" aria-label="当前工作方案进展"><h2>当前工作 · {title}</h2><p role="status" aria-live="polite">{message}</p><ol className="journey-stages">{['准备方案','准备资源','执行检查','返回结果'].map((label,index)=><li key={label} data-state={index===(resourcePhase?1:0)?'current':index<(resourcePhase?1:0)?'complete':'waiting'} aria-current={index===(resourcePhase?1:0)?'step':undefined}><span aria-hidden="true">{index+1}</span>{label}</li>)}</ol>{busy&&stream&&<small>正在接收模型返回，已收到 {stream.characters??stream.preview?.length??0} 个字符。生成内容尚未核验。</small>}<small>进展来自当前请求和原记录，不额外调用模型。这里不表示任务已经执行完成。</small></section>;
}
