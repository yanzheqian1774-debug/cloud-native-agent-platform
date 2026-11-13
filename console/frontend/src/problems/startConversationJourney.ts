import {conversationRequest} from '../api/privateConversation';
export async function startConversationJourney(id:string,csrf:string,text:string,userMessageId:string){
 const current=await conversationRequest<{version:number;state:unknown}>('/'+id+'/journey');
 if(current.state)return;
 await conversationRequest('/'+id+'/journey',csrf,{expectedVersion:0,state:{key:crypto.randomUUID(),phase:'UNDERSTAND',userMessageId,question:text,messages:[{id:'user:'+userMessageId,text}],log:['已收到问题，正在理解你的分析目标。']}});
}
