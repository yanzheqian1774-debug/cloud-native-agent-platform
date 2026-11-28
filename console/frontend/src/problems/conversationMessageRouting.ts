import type {PrivateConversation,PrivateMessage} from '../api/privateConversation';

/** A retained model relation is not an owner acceptance or execution receipt. */
export function hasSavedCurrentQuestionRelation(message:PrivateMessage,messages:PrivateMessage[]){
 if(message.kind||!message.author_id)return false;
 const facts=messages.filter(item=>item.kind==='SOURCE').map(item=>item.facts).filter(f=>f?.assistantResponse===true&&f.readable!==false&&f.state==='SUCCEEDED'&&f.source?.kind==='DRAFT'&&Boolean(f.source.invocationId)&&f.invokedBy===message.author_id&&f.userMessageId===message.message_id&&Boolean(f.requestKey));
 return facts.length>0&&facts.every(f=>f!.response?.conversationRoute?.relation==='CURRENT_QUESTION'&&['CURRENT_QUESTION_ANSWER','DRAFT_READY','NEEDS_DATA','NEEDS_CLARIFICATION'].includes(f!.response?.resultKind??''));
}

/** Only exact saved responses to every original user turn establish answer-only UI. */
export function isSavedDirectAnswerConversation(data:PrivateConversation|null){
 if(!data||data.links.length||!data.messages.length)return false;
 const users=data.messages.filter(message=>!message.kind);
 if(!users.length||data.messages.some(message=>message.focus_link_id||message.goalId||message.kind&&!(message.kind==='SOURCE'&&message.facts?.assistantResponse===true)))return false;
 return users.every(user=>{
  if(!user.author_id||user.disposition!=='GOAL_RECORDED')return false;
  const responses=data.messages.filter(message=>message.kind==='SOURCE'&&message.facts?.userMessageId===user.message_id);
  return responses.length>0&&responses.every(message=>{
   const facts=message.facts;
   return facts?.assistantResponse===true&&facts.readable!==false&&facts.state==='SUCCEEDED'&&facts.source?.kind==='DRAFT'&&Boolean(facts.source.invocationId)&&facts.invokedBy===user.author_id&&Boolean(facts.requestKey)&&facts.response?.resultKind==='DIRECT_ANSWER'&&(!facts.response.conversationRoute||facts.response.conversationRoute.relation==='INDEPENDENT');
  });
 })&&data.messages.filter(message=>message.kind==='SOURCE').every(message=>users.some(user=>user.message_id===message.facts?.userMessageId));
}
