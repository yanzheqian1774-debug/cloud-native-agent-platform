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
