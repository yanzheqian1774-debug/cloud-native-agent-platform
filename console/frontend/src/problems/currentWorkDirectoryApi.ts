import {readWorkbenchSession,WorkbenchRequestError,type WorkbenchSession} from '../api/businessWorkspace';
import {conversationScope} from './conversationViewState';
import {readViewString} from './workViewState';
export type WorkScope='visible'|'initiated';
export type DirectoryItem={workflowRunId:string;preparationDigest:string;title:string;createdAt:string;initiatorId:string|null;executionState:string;displayState:string;progressVersion:number|null;problemId:string;problemRevisionId:string;problemDigest:string;pendingQuestionCount:number|null;artifactCount:number;businessResolution:string|null;originConversationId:string|null;originVerified:boolean;planVersion:number|null;participantCount:number|null;completedTaskCount:number|null;taskCount:number|null;updatedAt:string|null};
export type DirectoryPage={schemaVersion:'current-work-directory.v1';scopeFilter:WorkScope;subject:string;tenantId:string;securityDomain:string;complete:true;questionStatusComplete?:boolean;readAt:string;total:number;counts:Record<string,number>;items:DirectoryItem[];nextCursor:string|null};
export const directoryViewKey=(session:WorkbenchSession)=>conversationScope(session)+':directory:tasks-native';
export async function readDirectoryPage(input:{scope?:string;query:string;state:string;cursor:string},signal:AbortSignal){
 const session=await readWorkbenchSession(signal),viewKey=directoryViewKey(session),scope=input.scope||readViewString(viewKey,'scope');
 const query=new URLSearchParams({query:input.query,state:input.state,pageSize:'25'});
 if(scope==='visible'||scope==='initiated')query.set('scopeFilter',scope);
 if(input.cursor)query.set('cursor',input.cursor);
 const response=await fetch('/api/workbench/v1/current-work?'+query,{credentials:'same-origin',headers:{Accept:'application/json'},signal});
 if(response.status===401)window.dispatchEvent(new Event('workbench-session-expired'));
 const body=await response.json();
 if(!response.ok)throw new WorkbenchRequestError(body.reasonCode??'CURRENT_WORK_UNAVAILABLE',response.status);
 const page=body.result as DirectoryPage;
 if(page?.schemaVersion!=='current-work-directory.v1'||page.subject!==session.principal.principalId||page.tenantId!==session.principal.tenantId||page.securityDomain!==session.principal.securityDomain||page.complete!==true||!['visible','initiated'].includes(page.scopeFilter)||!Array.isArray(page.items)||!Number.isSafeInteger(page.total)||page.total<page.items.length||!page.counts||Object.values(page.counts).some(v=>!Number.isSafeInteger(v)||v<0)||Object.values(page.counts).reduce((a,b)=>a+b,0)!==page.total||page.items.some(i=>typeof i.workflowRunId!=='string'||!/^[0-9a-f]{64}$/.test(i.preparationDigest)||typeof i.title!=='string'||!Number.isFinite(Date.parse(i.createdAt))))throw Error('任务目录返回内容尚未核实，请重新读取。');
 if(conversationScope(await readWorkbenchSession(signal))!==conversationScope(session))throw Error('登录身份已变化，请重新读取当前工作。');
 return {page,viewKey};
}
