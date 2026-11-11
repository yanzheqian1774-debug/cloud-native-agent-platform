import {capabilitySession,type CapabilityExecutionContract} from '../api/businessCapabilities';
import {workbenchPrincipalKey} from '../api/digitalEmployees';
import {conversationRequest} from '../api/privateConversation';

export type CapabilityJournal={version:number;contractDigest:string;sourceMessageId:string;state:{phase:string;problemId:string;criterionRevisionId?:string;proposalId?:string;proposalRevision?:number;proposalDigest?:string;confirmedPlan?:{id:string;version:number;digest:string};selectedPlan?:{id:string;version:number;digest:string};resourcePreparationKey?:string;executionDigest?:string;planningRequestKey?:string;invocationId?:string;predecessorInvocationId?:string;predecessorRequestKey?:string;clarificationAnswers?:string[];log?:string[]}|null};
export const capabilityJournalPath=(conversation:string,message:string)=>'/'+encodeURIComponent(conversation)+'/sources/'+encodeURIComponent(message)+'/journey';
export async function readCapabilityJournal(conversation:string,message:string,principal:string,signal:AbortSignal){
 const session=await capabilitySession(signal);
 if(workbenchPrincipalKey(session)!==principal)throw Error('登录身份已变化，请重新读取原会话。');
 const journal=await conversationRequest<CapabilityJournal>(capabilityJournalPath(conversation,message),undefined,undefined,signal);
 const after=await capabilitySession(signal);
 if(workbenchPrincipalKey(after)!==principal)throw Error('登录身份已变化，请重新读取原会话。');
 if(!Number.isInteger(journal.version)||journal.version<0||journal.sourceMessageId!==message||!/^[a-f0-9]{64}$/.test(journal.contractDigest)||(journal.version===0?journal.state!==null:!journal.state||typeof journal.state.phase!=='string'||typeof journal.state.problemId!=='string'))throw Error('已保存进展未能核对，请重新读取。');
 return journal;
}
export async function retainCapabilityPreparation(resolved:CapabilityExecutionContract,work:{problemId:string;criterionRevisionId:string},principal:string,signal:AbortSignal){
 const {conversationId,sourceMessageId}=resolved.contract;
 const current=await readCapabilityJournal(conversationId,sourceMessageId,principal,signal);
 if(current.contractDigest!==resolved.contractDigest||current.state&&current.state.problemId!==work.problemId)throw Error('已保存进展与本次工作不一致，停止更新。');
 if(current.version>0)return current;
 const session=await capabilitySession(signal);
 if(workbenchPrincipalKey(session)!==principal)throw Error('登录身份已变化，请重新读取原会话。');
 await conversationRequest(capabilityJournalPath(conversationId,sourceMessageId),session.csrfToken,{expectedVersion:0,idempotencyKey:'capability:'+resolved.contractDigest+':prepared',contractDigest:resolved.contractDigest,state:{phase:'PREPARE_PLAN',...work,log:['目标和完成标准已核验，尚未调用模型或启动执行。']}},signal);
 const saved=await readCapabilityJournal(conversationId,sourceMessageId,principal,signal);
 if(saved.contractDigest!==resolved.contractDigest||saved.state?.problemId!==work.problemId)throw Error('准备记录已提交，但进展尚未核实，请沿用原记录继续。');
 return saved;
}
