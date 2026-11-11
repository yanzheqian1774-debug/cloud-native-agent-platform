import {readWorkbenchSession} from '../api/businessWorkspace';
import {conversationScope} from './conversationViewState';
import {readDirectoryPage,type DirectoryItem} from './currentWorkDirectoryApi';
import {readSelectedWork,type CurrentWork,type WorkDirectoryRead} from './currentWorkReadback';

// The directory locates candidates; exact owner reads still authorize the question.
export async function readAttentionDirectory(onProgress:((value:WorkDirectoryRead)=>void)|undefined,signal:AbortSignal,handled=false):Promise<WorkDirectoryRead>{
 const scope=conversationScope(await readWorkbenchSession(signal));
 const works:CurrentWork[]=[],seen=new Set<string>(),cursors=new Set<string>();
 let cursor='',limited=false;
 const snapshot=(loading:boolean):WorkDirectoryRead=>({scope,works:[...works],limited,unlinkedProblems:0,loading});
 do{
  signal.throwIfAborted();
  const result=await readDirectoryPage({scope:'visible',query:'',state:handled?'answered':'waiting',cursor},signal);
  if(result.viewKey!==scope+':directory:tasks-native')throw Error('登录身份已变化，请重新读取待办。');
  limited ||= (handled?result.page.answerHistoryComplete:result.page.questionStatusComplete)!==true;
  const items:DirectoryItem[]=[];
  for(const item of result.page.items){
   if(seen.has(item.preparationDigest))throw Error('待办目录在读取期间发生变化，请重新读取。');
   seen.add(item.preparationDigest);items.push(item);
  }
  for(let start=0;start<items.length;start+=4){
   const batch=await Promise.all(items.slice(start,start+4).map(async item=>{
    try{
     if(!item.originConversationId){limited=true;return null}
     const value=await readSelectedWork(item.preparationDigest,item.originConversationId,signal,{includeCompletedQuestions:handled});
     if(value.scope!==scope)throw Error('ATTENTION_SCOPE_CHANGED');
     const work=value.work;
     if(work.problem.business_problem_id!==item.problemId||work.problem.revision_id!==item.problemRevisionId||work.problem.digest!==item.problemDigest||!work.conversation){limited=true;return null}
     if(!work.questionsReadable)limited=true;
     return work;
    }catch(error){signal.throwIfAborted();if(error instanceof Error&&error.message==='ATTENTION_SCOPE_CHANGED')throw error;limited=true;return null}
   }));
   works.push(...batch.filter((work):work is CurrentWork=>work!==null));
   if(conversationScope(await readWorkbenchSession(signal))!==scope)throw Error('登录身份已变化，请重新读取待办。');
   onProgress?.(snapshot(true));
  }
  cursor=result.page.nextCursor??'';
  if(cursor&&cursors.has(cursor))throw Error('待办分页未能继续，请重新读取。');
  if(cursor)cursors.add(cursor);
 }while(cursor);
 if(conversationScope(await readWorkbenchSession(signal))!==scope)throw Error('登录身份已变化，请重新读取待办。');
 return snapshot(false);
}
