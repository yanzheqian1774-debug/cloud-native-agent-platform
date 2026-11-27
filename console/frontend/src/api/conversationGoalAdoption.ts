import {conversationRequest} from './privateConversation';
import {verifyGoalReference,type GoalReference} from './conversationGoals';
export type IndependentAdoptionCommand={conversationId:string;commandId:string;messageId:string;requestKey:string;expectedConversationVersion:number};
export type IndependentAdoptionReceipt=GoalReference&{state:'RECORDED';conversationId:string;commandId:string;messageId:string;requestKey:string;adoptionDigest:string;invocationId:string;modelDispatched:false;replayed:boolean;journal:{version:number;state:unknown}};
const path=(chat:string)=>'/'+encodeURIComponent(chat)+'/goals/adoptions';
function checked(value:IndependentAdoptionReceipt,command:IndependentAdoptionCommand){
 for(const key of ['conversationId','commandId','messageId','requestKey'] as const)if(value[key]!==command[key])throw Error('CONVERSATION_GOAL_ADOPTION_MISMATCH');
 verifyGoalReference(value);
 if(value.state!=='RECORDED'||value.modelDispatched!==false||typeof value.replayed!=='boolean'||!/^[a-f0-9]{64}$/.test(value.adoptionDigest)||!value.invocationId||!Number.isSafeInteger(value.journal?.version)||value.journal.version<0||!value.journal.state)throw Error('CONVERSATION_GOAL_ADOPTION_UNVERIFIED');
 return value;
}
export async function adoptIndependentResult(command:IndependentAdoptionCommand,csrf:string){const {conversationId,...body}=command;return checked(await conversationRequest<IndependentAdoptionReceipt>(path(conversationId),csrf,body),command)}
export async function readIndependentAdoption(command:IndependentAdoptionCommand){
 const value=await conversationRequest<IndependentAdoptionReceipt|{state:'NOT_RECORDED';conversationId:string;commandId:string}>(path(command.conversationId)+'?'+new URLSearchParams({commandId:command.commandId}));
 if(value.state==='NOT_RECORDED'){if(value.conversationId!==command.conversationId||value.commandId!==command.commandId)throw Error('CONVERSATION_GOAL_ADOPTION_MISMATCH');return value}
 return checked(value,command);
}
