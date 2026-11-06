import {readWorkbenchSession} from '../api/businessWorkspace';
import {conversationRequest,type PrivateConversation} from '../api/privateConversation';
import type {Ref} from '../api/preparedExecution';

/** Link uncertainty never resubmits an execution or an unknown link command. */
export async function linkExecution(conversation:string,problem:Ref,executionDigest:string,principal:string,isCurrent:()=>boolean){
 const target={problemId:problem.resource_id,revisionId:problem.revision_id,problemDigest:problem.digest,executionDigest};
 const key='execution:'+executionDigest,marker='execution-link:'+JSON.stringify([principal,conversation,key]);
 const read=()=>conversationRequest<PrivateConversation>('/'+encodeURIComponent(conversation),undefined,undefined,AbortSignal.timeout(8000));
 const matches=(c:PrivateConversation)=>c.links.some(l=>l.readable&&l.target&&l.target.problemId===target.problemId&&l.target.revisionId===target.revisionId&&l.target.problemDigest===target.problemDigest&&l.target.executionDigest===target.executionDigest);
 const current=await read();if(!isCurrent()||matches(current))return;
 if(sessionStorage.getItem(marker))throw Error('EXECUTION_LINK_OUTCOME_UNKNOWN');
 const session=await readWorkbenchSession();
 if(JSON.stringify(session.principal)!==principal)throw Error('EXECUTION_LINK_IDENTITY_CHANGED');
 if(!isCurrent())return;
 sessionStorage.setItem(marker,key);
 try{await conversationRequest('/'+encodeURIComponent(conversation)+'/links',session.csrfToken,{idempotencyKey:key,expectedVersion:current.conversation.version,target},AbortSignal.timeout(8000))}
 catch(e){if(matches(await read()))return;throw e;}
 if(!matches(await read()))throw Error('EXECUTION_LINK_NOT_VERIFIED');
}
