import {readWorkbenchSession} from '../api/businessWorkspace';
import {conversationScope} from './conversationViewState';
import {readDirectoryPage,type DirectoryItem} from './currentWorkDirectoryApi';
import {readSelectedWork,type CurrentWork,type WorkDirectoryRead} from './currentWorkReadback';

// Directory discovery is not content authority; exact owner reads remain required.
export async function readOutcomeDirectory(onProgress:((value:WorkDirectoryRead)=>void)|undefined,signal:AbortSignal):Promise<WorkDirectoryRead>{
 const scope=conversationScope(await readWorkbenchSession(signal));
 const works:CurrentWork[]=[],seen=new Set<string>(),cursors=new Set<string>();
 let cursor='',limited=false;
 const snapshot=(loading:boolean):WorkDirectoryRead=>({scope,works:[...works],limited,unlinkedProblems:0,loading});
 do{
  signal.throwIfAborted();
  const result=await readDirectoryPage({scope:'visible',query:'',state:'all',cursor},signal);
  if(result.viewKey!==scope+':directory:tasks-native')throw Error('登录身份已变化，请重新读取成果。');
  const items:DirectoryItem[]=[];
  for(const item of result.page.items){
   if(seen.has(item.preparationDigest))throw Error('成果目录在读取期间发生变化，请重新读取。');
   seen.add(item.preparationDigest);items.push(item);
  }
  for(let start=0;start<items.length;start+=4){
   const batch=await Promise.all(items.slice(start,start+4).map(async item=>{
    try{
     if(!item.originConversationId){limited=true;return null}
     const value=await readSelectedWork(item.preparationDigest,item.originConversationId,signal);
     if(value.scope!==scope)throw Error('OUTCOME_SCOPE_CHANGED');
     const work=value.work;
     if(work.execution.digest!==item.preparationDigest||work.execution.workflowRunId!==item.workflowRunId||work.problem.business_problem_id!==item.problemId||work.problem.revision_id!==item.problemRevisionId||work.problem.digest!==item.problemDigest||work.conversation!==item.originConversationId||(item.originVerified&&!work.originVerified)){limited=true;return null}
     if(!work.questionsReadable)limited=true;
     return work;
    }catch(error){signal.throwIfAborted();if(error instanceof Error&&error.message==='OUTCOME_SCOPE_CHANGED')throw error;limited=true;return null}
   }));
   works.push(...batch.filter((work):work is CurrentWork=>work!==null));
   if(conversationScope(await readWorkbenchSession(signal))!==scope)throw Error('登录身份已变化，请重新读取成果。');
   onProgress?.(snapshot(true));
  }
  cursor=result.page.nextCursor??'';
  if(cursor&&cursors.has(cursor))throw Error('成果分页未能继续，请重新读取。');
  if(cursor)cursors.add(cursor);
 }while(cursor);
 if(conversationScope(await readWorkbenchSession(signal))!==scope)throw Error('登录身份已变化，请重新读取成果。');
 return snapshot(false);
}
