import {useCallback,useEffect,useRef,useState} from 'react';
import {readGoals,type ConversationGoal} from '../api/conversationGoals';
import {readWorkbenchSession,type WorkbenchSession} from '../api/businessWorkspace';
import {conversationScope} from './conversationViewState';
import {readViewString,saveViewString} from './workViewState';

// Reading a selection never creates a goal or changes either journal.
export function useConversationGoals(chat:string|null,session:WorkbenchSession,enabled:boolean){
 const scope=conversationScope(session),identity=scope+':'+chat;
 const [items,setItems]=useState<ConversationGoal[]>([]),[selectedId,setSelectedId]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[cursor,setCursor]=useState<string|null>(null);
 const invalidated=useRef(false),epoch=useRef(0),flight=useRef(false),seen=useRef(new Set<string>());
 const load=useCallback(async(after?:string)=>{
  if(!enabled||!chat||flight.current||invalidated.current)return;
  const token=epoch.current;flight.current=true;setBusy(true);setError('');
  try{
   const before=await readWorkbenchSession();if(conversationScope(before)!==scope)throw Error('CONVERSATION_IDENTITY_CHANGED');
   const page=await readGoals(chat,after);
   const current=await readWorkbenchSession();if(invalidated.current||conversationScope(current)!==scope)throw Error('CONVERSATION_IDENTITY_CHANGED');
   if(token!==epoch.current)return;
   if(after&&page.items.some(item=>seen.current.has(item.goalId)))throw Error('CONVERSATION_GOAL_PAGE_OVERLAP');
   if(after&&page.nextCursor===after)throw Error('CONVERSATION_GOAL_CURSOR_UNCHANGED');
   if(!after)seen.current.clear();
   page.items.forEach(item=>seen.current.add(item.goalId));
   setItems(old=>after?[...old,...page.items]:page.items);setCursor(page.hasMore?page.nextCursor:null);
  }catch{if(token===epoch.current)setError('暂时无法核对本会话的工作，已保存内容保留。')}
  finally{if(token===epoch.current){flight.current=false;setBusy(false)}}
 },[chat,enabled,scope]);
 useEffect(()=>{
  let active=true;invalidated.current=false;epoch.current++;flight.current=false;seen.current.clear();const cancel=()=>{active=false;epoch.current++};
  void Promise.resolve().then(()=>{if(!active)return;setItems([]);setCursor(null);setBusy(false);setError('');setSelectedId(readViewString(identity,'selected-goal'));void load()});
  const invalidate=()=>{invalidated.current=true;epoch.current++;flight.current=false;setItems([]);setCursor(null);setBusy(false);setError('登录状态已变化，请重新核对工作。')};
  window.addEventListener('workbench-session-expired',invalidate);
  return()=>{cancel();window.removeEventListener('workbench-session-expired',invalidate)};
 },[identity,load]);
 const selected=items.find(item=>item.goalId===selectedId)??null;
 function select(id:string){if(id&&!items.some(item=>item.goalId===id))return;setSelectedId(id);saveViewString(identity,'selected-goal',id)}
 return {items,selected,selectedId,selectionUnavailable:Boolean(selectedId&&!selected),error,busy,hasMore:cursor!==null,select,reload:()=>load(),more:()=>cursor?load(cursor):Promise.resolve()};
}
