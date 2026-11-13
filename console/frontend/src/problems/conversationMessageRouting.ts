import type {PrivateMessage} from '../api/privateConversation';

/** A retained model relation is not an owner acceptance or execution receipt. */
export function hasSavedCurrentQuestionRelation(message:PrivateMessage,messages:PrivateMessage[]){
 if(message.kind||!message.author_id)return false;
 const facts=messages.filter(item=>item.kind==='SOURCE').map(item=>item.facts).filter(f=>f?.assistantResponse===true&&f.readable!==false&&f.state==='SUCCEEDED'&&f.source?.kind==='DRAFT'&&Boolean(f.source.invocationId)&&f.invokedBy===message.author_id&&f.userMessageId===message.message_id&&Boolean(f.requestKey));
 return facts.length>0&&facts.every(f=>f!.response?.conversationRoute?.relation==='CURRENT_QUESTION'&&['CURRENT_QUESTION_ANSWER','DRAFT_READY','NEEDS_DATA','NEEDS_CLARIFICATION'].includes(f!.response?.resultKind??''));
}
