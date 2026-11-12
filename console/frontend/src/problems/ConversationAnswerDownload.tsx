import {useEffect,useRef,useState} from 'react';
import {conversationRequest,type PrivateConversation,type PrivateMessage} from '../api/privateConversation';
import {readWorkbenchSession,type WorkbenchSession} from '../api/businessWorkspace';
import {conversationScope} from './conversationViewState';

/** Export the authorized saved answer, not a new model result or execution artifact. */
export function ConversationAnswerDownload({conversation,message,session}:{conversation:string;message:PrivateMessage;session:WorkbenchSession}){
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 const active=useRef(true),flight=useRef(false),controller=useRef<AbortController|null>(null);
 useEffect(()=>{active.current=true;return()=>{active.current=false;controller.current?.abort()}},[]);
 async function download(){
  if(flight.current)return;flight.current=true;setBusy(true);setError('');
  const abort=new AbortController();controller.current=abort;const timer=setTimeout(()=>abort.abort(),20000);
  try{
   const scope=conversationScope(session);
   if(conversationScope(await readWorkbenchSession())!==scope)throw Error('identity');
   const current=await conversationRequest<PrivateConversation>('/'+encodeURIComponent(conversation),undefined,undefined,abort.signal);
   const saved=current.messages.find(item=>item.message_id===message.message_id);
   if(current.conversation.conversation_id!==conversation||!saved||saved.kind!=='SOURCE'||saved.facts?.assistantResponse!==true||saved.facts.readable===false||saved.facts.state!=='SUCCEEDED'||saved.facts.response?.resultKind!=='DIRECT_ANSWER'||saved.content!==message.content||JSON.stringify(saved.facts.source)!==JSON.stringify(message.facts?.source))throw Error('unavailable');
   if(conversationScope(await readWorkbenchSession())!==scope)throw Error('identity');
   if(!active.current||abort.signal.aborted)return;
   const provenance={会话:conversation,答复:saved.message_id,记录时间:saved.created_at??null,来源调用:saved.facts.source,使用资料:saved.facts.response.inputSource??null,说明:'导出已保存答复及其来源记录，未重新分析或执行任务。'};
   const text=saved.content+'\n\n---\n\n## 导出记录\n\n'+JSON.stringify(provenance,null,2).split('\n').map(line=>'    '+line).join('\n')+'\n';
   const url=URL.createObjectURL(new Blob([text],{type:'text/markdown;charset=utf-8'})),link=document.createElement('a');
   link.href=url;link.download='会话答复-'+saved.message_id.replace(/[^a-zA-Z0-9_-]/g,'').slice(0,64)+'.md';document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(reason){if(active.current)setError(abort.signal.aborted?'核对答复超时，未下载文件，可稍后再试。':String(reason).includes('identity')?'登录身份已变化，未下载文件。请重新打开会话后核对。':'暂不能下载这条答复，请确认当前仍有权查看原答复及资料。');}
  finally{clearTimeout(timer);flight.current=false;if(active.current)setBusy(false)}
 }
 return <div className="conversation-answer-download"><button type="button" disabled={busy} onClick={()=>void download()}>{busy?'正在核对答复…':'下载答复与来源（Markdown）'}</button>{error&&<p role="alert">{error}</p>}</div>;
}
