import type {ExecutionView} from '../api/preparedExecution';

export function fixedCycleStatus(state:string|undefined,waitingForAnswer=false){
 if(waitingForAnswer&&state==='RUNNING')return '等待必要回答';
 const labels:Record<string,string>={RECORDED:'方案请求已保存',REQUIRES_REVIEW:'方案需要核对',PREPARED:'方案准备已保存',PENDING:'等待执行',QUEUED:'等待执行',WAITING:'等待前序任务',RUNNING:'正在执行',SUCCEEDED:'执行已完成',FAILED:'执行失败',CANCELLED:'已取消',CANCEL_REQUESTED:'正在核对停止结果',RECOVERY_REQUIRED:'结果待核实',UNKNOWN:'结果待核实'};
 return labels[state??'']??'状态待核实';
}
export function cycleScheduledLabel(scheduledAt:string|null|undefined,timezone:string){
 if(!scheduledAt||!Number.isFinite(Date.parse(scheduledAt)))return '计划时间待核实';
 try{return new Intl.DateTimeFormat('zh-CN',{timeZone:timezone,month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(scheduledAt))+' · '+timezone}catch{return '计划时区待核实'}
}
export function verifyCycleExecution(view:ExecutionView,event:{preparationDigest:string;runId:string},problem:{resource_id:string;revision_id:string;digest:string},source:{resource_id:string;revision_id:string;digest:string}){
 const actual=view.preparation?.semantics?.target?.problem,input=view.preparation?.source_snapshot;
 if(view.digest!==event.preparationDigest||view.workflowRunId!==event.runId||!actual||!input||(['resource_id','revision_id','digest'] as const).some(k=>actual[k]!==problem[k]||input[k]!==source[k]))throw Error('FIXED_CYCLE_EXECUTION_BINDING_MISMATCH');
 return view;
}
