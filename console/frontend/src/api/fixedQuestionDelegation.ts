import type {WorkbenchSession} from './businessWorkspace';
import {conversationRequest} from './privateConversation';
import type {FixedCycleFocus} from './conversationFixedFocus';

export type FixedQuestionSelection=FixedCycleFocus&{invocationId:string;questionKey:string;questionDigest:string;question:string;expiresAt:string};
export type QuestionIdentity={tenantId:string;securityDomain:string;conversationId:string;bindingDigest:string;work:{digest:string};eventId:string;receiptDigest:string;preparationDigest:string;runId:string;taskId:string;attemptId:string;commandId:string;invocationId:string;questionKey:string;questionDigest:string;checkpointDigest:string;executionSubject:string;serviceCredentialId:string;generation:number;recoveryEpoch:number;sourceSnapshot:{resource_id:string;revision_id:string;digest:string}};
export type QuestionPresentation={schemaVersion:'fixed-question-presentation.v1';presentationId:string;identity:QuestionIdentity;actorId:string;commandId:string;focusLinkId:string;currentQuestionToken:string;question:{question:string;expiresAt:string};expiresAt:string};
export type PresentationResult={state:'RECORDED';presentation:QuestionPresentation;presentationDigest:string;modelDispatched:false;continuationDispatched:false}|{state:'NOT_RECORDED';conversationId:string;commandId:string};
export type AnswerResult={state:'RECORDED';receipt:{presentationId:string;presentationDigest:string;actorId:string;executionSubject:string;commandId:string;inputMessageId:string;interpretationInvocationId:string};receiptDigest:string;modelDispatched:false;continuationDispatched:false}|{state:'NOT_RECORDED';conversationId:string;presentationId:string;commandId:string};
export const questionPath=(conversation:string)=>'/'+encodeURIComponent(conversation)+'/fixed-work-activity/questions';
const hex=(value:unknown)=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
export function sameQuestion(i:QuestionIdentity,q:FixedQuestionSelection,conversation:string,session:WorkbenchSession){
 return i?.tenantId===session.principal.tenantId&&i.securityDomain===session.principal.securityDomain&&i.conversationId===conversation&&i.bindingDigest===q.bindingDigest&&i.work?.digest===q.workDigest&&i.eventId===q.eventId&&i.receiptDigest===q.receiptDigest&&i.preparationDigest===q.preparationDigest&&i.runId===q.runId&&i.invocationId===q.invocationId&&i.questionKey===q.questionKey&&i.questionDigest===q.questionDigest&&hex(i.checkpointDigest)&&!!i.taskId&&!!i.attemptId&&i.executionSubject?.startsWith('service:')&&!!i.serviceCredentialId;
}
export function verifyPresentation(result:PresentationResult,q:FixedQuestionSelection,conversation:string,session:WorkbenchSession,command:string){
 if(result.state!=='RECORDED')throw Error('尚未读到本题的办理回执，不会重复准备。');
 const p=result.presentation;
 if(!sameQuestion(p.identity,q,conversation,session)||p.schemaVersion!=='fixed-question-presentation.v1'||p.commandId!==command||p.actorId!==session.principal.principalId||!p.presentationId||!p.focusLinkId||!hex(p.currentQuestionToken)||!hex(result.presentationDigest)||p.question?.question!==q.question||!Number.isFinite(Date.parse(p.expiresAt))||Date.parse(p.expiresAt)<=Date.now()||Date.parse(p.expiresAt)>Date.parse(q.expiresAt)||result.modelDispatched!==false||result.continuationDispatched!==false)throw Error('本题身份或可回答状态已变化，未提交回答。');
 return result;
}
export function readPresentation(conversation:string,commandId:string){return conversationRequest<PresentationResult>(questionPath(conversation)+'/presentations?'+new URLSearchParams({commandId}))}
export function readAnswer(conversation:string,presentationId:string,commandId:string){return conversationRequest<AnswerResult>(questionPath(conversation)+'/answers?'+new URLSearchParams({presentationId,commandId}))}
