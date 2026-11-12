import type {UnderstandingItem} from '../api/draftAssistanceTypes';
import type {ProblemDraft} from './problemConversationModel';
export type UserFactMessage={id:string;text:string};
export const CONTEXT_VERSION='problem-understanding-context.v1';
export const MAX_CONTEXT_BYTES=16_384;

// Do not infer corrections with keywords or truncate away earlier constraints.
// Only exact consecutive repetitions can be compacted without semantic inference.
export function appendUserMessage(messages:UserFactMessage[],text:string):UserFactMessage[]{
  const trimmed=text.trim();
  if(messages.at(-1)?.text===trimmed)return messages;
  return [...messages,{id:`user:${crypto.randomUUID()}`,text:trimmed}];
}
export function understandingContent(messages:UserFactMessage[],uiRevision:number,currentDraft:ProblemDraft|null,previousUnderstanding:UnderstandingItem[]|null,previousQuestion:string|null){
  const content=JSON.stringify({schemaVersion:CONTEXT_VERSION,uiRevision,messages,currentDraft,previousUnderstanding,previousQuestion});
  if(messages.length>32||new TextEncoder().encode(content).length>MAX_CONTEXT_BYTES)throw new Error('当前问题的信息已达到本轮长度上限。请缩小范围或明确整理为新的问题；原内容未被截断。');
  return content;
}
export const fieldLabels={goal:'目标',scope:'范围',time:'时间',constraints:'约束',successCriteria:'成功标准',openItem:'待确认'};
export const sourceLabels={USER_STATEMENT:'你提供的信息',MODEL_SUGGESTION:'建议，尚未采用',UNKNOWN:'尚不清楚'};

// Presentation only: exact full-description echo is not evidence of field extraction.
export function isUnstructuredStatement(item:UnderstandingItem,description:string){
  return item.source==='USER_STATEMENT'&&item.value.trim()===description.trim();
}
export function understandingDisplay(item:UnderstandingItem,description:string){
  return {label:isUnstructuredStatement(item,description)?'你提供的信息':fieldLabels[item.field],
    value:item.source==='UNKNOWN'?'尚未单独整理':item.value};
}

export function conversationUnderstandingContent(messages:UserFactMessage[],previous:import('../api/draftAssistanceTypes').DraftAssistanceResult|undefined){
 const original=JSON.parse(understandingContent(messages.map(message=>({...message,id:message.id.startsWith('user:')?message.id:'user:'+message.id})),messages.length,previous?.draft??null,previous?.understanding??null,previous?.clarificationQuestion??null));
 const content=JSON.stringify({...original,schemaVersion:'conversation-understanding-context.v2',previousAssistantResponse:previous?.resultKind==='DIRECT_ANSWER'&&previous.answer&&previous.conversationDelivery?.state==='SAVED'?{invocationId:previous.invocationId,answer:previous.answer}:null});
 if(new TextEncoder().encode(content).length>MAX_CONTEXT_BYTES)throw Error('会话上下文已达到本轮长度上限，原内容保留。');
 return content;
}
