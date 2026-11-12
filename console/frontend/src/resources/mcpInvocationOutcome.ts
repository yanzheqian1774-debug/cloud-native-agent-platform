import type {SkillMcpResource} from '../api/skillMcpResources';
export function mcpInvocationOutcome(item:SkillMcpResource['invocations'][number]){
 const exact=Boolean(item.revisionId&&item.revisionDigest&&item.snapshotId&&item.snapshotDigest);
 if(!exact)return {label:'历史调用结果待核实',note:'历史记录缺少准确来源版本，无法根据选用记录推断实际调用来源或结果。'};
 if(item.dispatchState==='NOT_DISPATCHED')return {label:item.status==='CANCELLED'?'调用前已取消':'未发出工具调用',note:''};
 if(item.dispatchState==='RESPONSE_RECEIVED'){
  if(item.reasonCode==='MCP_TOOL_REPORTED_ERROR')return {label:'工具返回错误',note:''};
  if(item.status==='SUCCEEDED')return {label:'工具已返回',note:''};
 }
 return {label:'调用结果未确认',note:'未能确认调用结果，可能已产生影响。不会自动重试。'};
}
