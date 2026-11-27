import {useEffect,useState} from 'react';
import {conversationRequest} from '../api/privateConversation';
import {goalPath,verifyGoalJournal,verifyGoalReference,type GoalReference,type GoalJournal} from '../api/conversationGoals';
import {readWorkbenchSession,type WorkbenchSession} from '../api/businessWorkspace';
import {conversationScope} from './conversationViewState';
export function useSelectedConversationGoal(chat:string|null,id:string|null,session:WorkbenchSession,enabled:boolean){
 const [goal,setGoal]=useState<GoalReference|null>(null),[error,setError]=useState('');
 const scope=conversationScope(session);
 useEffect(()=>{if(!chat||!id||!enabled)return;let live=true;const abort=new AbortController();
  const verify=async()=>{if(conversationScope(await readWorkbenchSession())!==scope)throw Error('GOAL_IDENTITY_CHANGED')};
  const invalidate=()=>{live=false;abort.abort();setGoal(null);setError('登录已失效，请重新读取原问题。')};window.addEventListener('workbench-session-expired',invalidate);
  void(async()=>{await verify();const value=await conversationRequest<GoalJournal>(goalPath(chat)+'/'+encodeURIComponent(id)+'/journey',undefined,undefined,abort.signal);await verify();const ref=verifyGoalReference(value);if(ref.goalId!==id)throw Error('GOAL_REFERENCE_MISMATCH');verifyGoalJournal(value,ref);if(live){setGoal({goalId:ref.goalId,goalDigest:ref.goalDigest});setError('')}})().catch(()=>{if(live){setGoal(null);setError('暂时不能核实这项问题的记录。原会话目标仍保留，不用其他工作代替。')}});
  return()=>{live=false;abort.abort();window.removeEventListener('workbench-session-expired',invalidate)};
 },[chat,id,enabled,scope]);
 return {goal:goal?.goalId===id?goal:null,error:id&&!enabled?'当前未开放多项工作接续，原记录保留。':error};
}
