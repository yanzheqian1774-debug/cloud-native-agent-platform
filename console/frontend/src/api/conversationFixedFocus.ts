import {conversationRequest} from './privateConversation';

/** References are claims for the server to verify, never execution authority. */
export type FixedCycleFocus={bindingDigest:string;workDigest:string;eventId:string;receiptDigest:string;preparationDigest:string;runId:string};
export type FixedFocusCommand=FixedCycleFocus&{conversationId:string;commandId:string;expectedConversationVersion:number};
export type FixedFocusReceipt=FixedCycleFocus&{conversationId:string;commandId:string;state:'RECORDED';contentComplete:boolean;excerptedArtifactCount:number;focusLinkId:string;focusDigest:string;conversationVersion?:number;replayed?:boolean};
export type FixedFocusObservation=FixedFocusReceipt|{conversationId:string;commandId:string;state:'NOT_RECORDED'};
const path=(id:string)=>'/'+encodeURIComponent(id)+'/fixed-work-activity/focus';
export function verifyFixedFocus(value:FixedFocusObservation,expected:FixedFocusCommand){
 if(value.conversationId!==expected.conversationId||value.commandId!==expected.commandId)throw Error('FIXED_FOCUS_IDENTITY_MISMATCH');
 if(value.state==='NOT_RECORDED')return value;
 if(value.state!=='RECORDED'||typeof value.contentComplete!=='boolean'||!Number.isSafeInteger(value.excerptedArtifactCount)||value.excerptedArtifactCount<0||(value.contentComplete&&value.excerptedArtifactCount!==0)||!value.focusLinkId||!/^[a-f0-9]{64}$/.test(value.focusDigest)||(['bindingDigest','workDigest','eventId','receiptDigest','preparationDigest','runId'] as const).some(k=>value[k]!==expected[k]))throw Error('FIXED_FOCUS_RECEIPT_MISMATCH');
 return value;
}
export async function readFixedFocus(command:FixedFocusCommand){return verifyFixedFocus(await conversationRequest<FixedFocusObservation>(path(command.conversationId)+'?'+new URLSearchParams({commandId:command.commandId})),command)}
export async function recordFixedFocus(command:FixedFocusCommand,csrf:string){
 const {conversationId,...body}=command;
 const result=verifyFixedFocus(await conversationRequest<FixedFocusObservation>(path(conversationId),csrf,body),command);
 if(result.state!=='RECORDED')throw Error('FIXED_FOCUS_UNCONFIRMED');
 return result;
}
