import {readConversationJournal,saveConversationJournal,type GoalReference} from '../api/conversationGoals';
export async function startConversationJourney(id:string,csrf:string,text:string,userMessageId:string,goal?:GoalReference|null){
 const current=await readConversationJournal(id,goal);
 if(goal&&current.rootMessageId!==userMessageId)throw Error('CONVERSATION_GOAL_ROOT_MESSAGE_MISMATCH');
 if(current.state)return;
 if(current.version!==0)throw Error('CONVERSATION_EMPTY_JOURNAL_VERSION_MISMATCH');
 await saveConversationJournal(id,csrf,{expectedVersion:0,state:{key:goal?'goal:'+goal.goalId:crypto.randomUUID(),phase:'UNDERSTAND',userMessageId,question:text,messages:[{id:'user:'+userMessageId,text}],log:['已收到问题，正在理解你的分析目标。']}},goal);
}
