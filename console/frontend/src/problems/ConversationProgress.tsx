import {documentBusinessSummary} from './documentRuleSummary';
import type {ExecutionView} from '../api/preparedExecution';

type Props={feedback?:{title:string;detail:string};recoveryState?:string;separatePreparation?:boolean;phase:string;pending?:string;busy:boolean;error?:string;execution:ExecutionView|null;hasExecution:boolean};
const phases:Record<string,number>={UNDERSTAND:0,CLARIFY:0,CREATE:0,CRITERION:1,ACTIVATE:1,PLAN:1,PLANNING_CLARIFY:1,CONFIRM:1,SELECT_RESOURCES:2,RESOURCES:2,EXECUTE:2,RUNNING:3,DONE:4};
const messages:Record<string,string>={
 'source-discovery':'正在核对本次可用的资料，返回后请确认分析范围。',
 understanding:'正在理解你的问题，等待目标整理结果。',
 'create-problem':'已收到目标整理结果，正在保存本次分析目标。',
 criterion:'正在根据目标和所选资料建立完成标准。',
 activate:'正在关联目标、资料和完成标准。',
 planning:'正在结合资料与可用能力制定方案，等待方案返回。',
 confirm:'已收到方案，正在核对执行条件。',
 'select-resources':'正在匹配本次方案所需的执行能力。',
 resources:'正在检查资料和执行资源是否就绪。',
 execute:'正在提交执行请求，等待任务记录返回。',
 'coverage-repair':'当前能力与方案存在缺口，正在核对可调整的范围。',
};
export function ConversationProgress({feedback,recoveryState,phase,pending,busy,error,execution,hasExecution,separatePreparation=false}:Props){
 if(feedback&&!hasExecution)return <section className="journey-progress" aria-label="全流程进展"><p role="status"><strong>{feedback.title}</strong></p><p>{feedback.detail}</p></section>;
 if(['OBSERVED','AUTHORIZATION_PENDING','AUTHORIZED','DISPATCHED','CONTINUING'].includes(recoveryState??''))return <section className="journey-progress" aria-label="全流程进展"><p role="status" aria-live="polite"><strong>{recoveryState==='CONTINUING'?'正在处理恢复请求':recoveryState==='AUTHORIZED'?'已可继续原问题':recoveryState==='DISPATCHED'?'本次处理已提交':'恢复申请已提交，等待核对；当前无需操作。'}</strong></p><p>{recoveryState==='CONTINUING'?'已有进展会持续呈现，结果返回后在原会话继续。':recoveryState==='AUTHORIZED'?'请在原会话选择继续，尚未自动执行。':recoveryState==='DISPATCHED'?'可读取本次处理结果，不会重复提交。':'会持续读取核对进展，不会自动执行任务。'}</p></section>;
 if(phase==='UNDERSTAND'&&!hasExecution)return <section className="journey-progress" aria-label="全流程进展"><p role="status" aria-live="polite"><strong>{error?.includes('CONTEXT_ADMISSION_CONVERSATION_BINDING_REQUIRED')?'本次提问尚未开始处理':error?'本次提问需要核查':busy?'正在理解你的提问':'正在核对提问记录'}</strong></p><p>{error?.includes('CONTEXT_ADMISSION_CONVERSATION_BINDING_REQUIRED')?'会话接入检查未通过，原提问已保留，不会自动重发。':error?'原提问与已有内容已保留，请查看会话中的说明。':'收到回复后会在本会话呈现；需要开展任务时再显示执行进度。'}</p></section>;
 const state=execution?.progress?.state;
 const terminalFailure=['FAILED','RECOVERY_REQUIRED','CANCELLED','CANCELED','UNKNOWN'].includes(state??'');
 const stopped=phase==='UNDERSTANDING_FAILED'||Boolean(error)||['FAILED','RECOVERY_REQUIRED','CANCELLED','CANCELED','UNKNOWN'].includes(state??'');
 const complete=state==='SUCCEEDED';
 const tasks=execution?.progress?.tasks??[];
 const reportIds=new Set(execution?.preparation?.participants?.filter(p=>p.skill.operation==='RENDER_REPORT').map(p=>p.task_id));
 const reporting=tasks.some(t=>reportIds.has(t.task_id)&&t.state==='RUNNING');
 const readingSaved=hasExecution&&!execution?.progress&&!error;
 const index=readingSaved?-1:complete||reporting?4:(phases[phase]??0);
 const unverified=Boolean(pending&&!busy&&!error&&!hasExecution);
 let text=messages[pending??'']??(['CLARIFY','PLANNING_CLARIFY'].includes(phase)?'需要你确认资料或补充一个必要信息，回答后在这里继续。':hasExecution?'执行请求已返回，正在读取任务进展。':'已收到问题，正在准备理解目标。');
 if(hasExecution&&execution?.progress){const done=tasks.filter(t=>t.state==='SUCCEEDED').length;text=`已完成 ${done}/${tasks.length} 个任务，已生成 ${execution.artifacts.length} 份产物。${reporting?'正在整理结果报告。':'下方持续展示实际动作和返回结果。'}`;}
 if(readingSaved)text='正在读取已保存的执行进度与结果；这次打开不会重新提交或执行任务。';
 if(complete)text=(execution&&documentBusinessSummary(execution))??`任务已完成，已生成 ${execution?.artifacts.length??0} 份产物。结果与核验依据在本会话下方；业务是否解决以评价结果为准。`;
 if(stopped)text=state==='RECOVERY_REQUIRED'||state==='UNKNOWN'?'执行结果尚待核实，已有进展保留，不会自动重跑。':state==='FAILED'?(tasks.some(t=>t.state==='FAILED'&&t.reason==='NATIVE_INPUT_EXPIRED')?'本次执行已失败；任务记录显示执行追问等待超时。已有进展保留，不会自动重跑。':'本次执行已失败，已有进展保留，请查看下方记录。'):['CANCELLED','CANCELED'].includes(state??'')?'本次执行已取消，已有进展保留，请查看下方记录。':'最新进展暂无法确认，已有内容保留；请核对下方说明，不会自动重发请求。';
 if(phase==='UNDERSTANDING_FAILED')text='理解结果格式未通过校验，原问题和资料已保留；等待你选择是否沿用原问题继续，不会自动重试。';
 if(unverified)text='上次请求的结果尚待核实，已有进展保留；刷新不会重复提交。';
 if(pending==='source-discovery')return <section className="journey-progress" aria-label="全流程进展"><p role="status"><strong>{busy?'正在读取可用资料':'等待资料读取'}</strong></p><p>原问题已保存，当前正在核对可读取的资料范围。重新读取资料不会重复调用模型或启动执行。</p></section>;
 if(!hasExecution&&['CONTEXT_ADMISSION_SOURCE_MISMATCH','PLANNING_OUTPUT_SOURCE_MISMATCH'].some(code=>error?.includes(code)))return <section className="journey-progress" aria-label="全流程进展"><p role="status"><strong>已暂停：资料不一致</strong></p><p>准备方案时未通过资料一致性校验，尚未进入执行。</p><p>原问题和资料已保留，当前只能暂存补充，不会自动重发。</p></section>;
 if(!hasExecution&&(error?.includes('OUTCOME_UNKNOWN')||unverified))return <section className="journey-progress" aria-label="全流程进展"><p role="status"><strong>结果待核实</strong></p><p>暂时无法确认这次处理结果，已保留请求与已有回答。</p><p>当前未继续执行，不会自动重发请求。</p></section>;
 return <section className="journey-progress" aria-label="全流程进展">{!execution?.progress&&<ol className="journey-stages">{['理解问题','准备方案','准备资源','执行检查','返回结果'].map((label,i)=><li key={label} aria-current={i===index?'step':undefined} data-state={i<index||complete?'done':i===index?'current':'waiting'}><span aria-hidden="true">{i<index||complete?'✓':i+1}</span>{label}</li>)}</ol>}<p role="status" aria-live="polite"><strong>{separatePreparation?"原有工作 · ":""}{stopped?(terminalFailure||phase==='UNDERSTANDING_FAILED'?'需要处理':'需要核查'):unverified?'等待核实':complete?'结果已返回':readingSaved?'正在读取记录':['CLARIFY','PLANNING_CLARIFY'].includes(phase)?'等待你的回答':'当前进展'}：</strong>{text}</p><details><summary>进度说明</summary><small>进度来自已保存的请求、任务和实际返回结果，不额外调用模型生成。</small></details></section>;
}
