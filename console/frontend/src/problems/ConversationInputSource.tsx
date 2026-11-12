import {useEffect,useState} from 'react';
import {readExactDirectoryResource,type DirectoryDetail} from '../api/resourceDirectory';
import {KnowledgeBody} from '../resources/KnowledgeBody';
import type {ConversationInputSourceReference} from '../api/draftAssistanceTypes';
export function ConversationInputSource({source}:{source?:ConversationInputSourceReference}){
 const [open,setOpen]=useState(false),[attempt,setAttempt]=useState(0),[loaded,setLoaded]=useState<DirectoryDetail|null>(null),[error,setError]=useState('');
 const identity=source?.source.resource_id,revision=source?.source.revision_id,digest=source?.source.digest;
 useEffect(()=>{
  if(!open||!identity||!revision||!digest)return;
  let active=true;const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
  const expired=()=>{controller.abort();if(active){setLoaded(null);setError('当前登录已失效，请重新登录后核对原资料。')}};
  window.addEventListener('workbench-session-expired',expired);
  void readExactDirectoryResource('knowledge',identity,revision,digest,controller.signal,'content').then(value=>{if(active&&!controller.signal.aborted)setLoaded(value)}).catch(reason=>{if(active)setError(controller.signal.aborted?'原文读取等待超时，可重新读取；原回答保留。':reason?.status===403||reason?.status===404?'当前无权读取此资料版本，或该版本不可用。原回答保留。':String(reason).includes('VERSION_MISMATCH')?'资料版本核对不一致，未显示其他版本。原回答保留。':'暂时无法读取本次使用的资料版本，可稍后重新读取。原回答保留。')}).finally(()=>clearTimeout(timer));
  return()=>{active=false;clearTimeout(timer);controller.abort();window.removeEventListener('workbench-session-expired',expired)};
 },[open,identity,revision,digest,attempt]);
 if(!source)return <p>这条答复未记录准确资料版本，不能据此定位原文。</p>;
 return <section className="conversation-input-source" data-open={open} aria-label="本次回答使用的资料"><p>使用资料：{source.name}</p><button type="button" aria-expanded={open} onClick={()=>{setLoaded(null);setError('');setOpen(value=>!value)}}>{open?'收起原文':'查看本次使用的原文'}</button>{open&&<><details><summary>核对资料版本</summary><p>版本：{revision}</p><p>摘要：{digest}</p></details>{error?<div role="alert"><p>{error}</p><button type="button" onClick={()=>{setLoaded(null);setError('');setAttempt(n=>n+1)}}>重新读取原文</button></div>:loaded?.revision?<div className="conversation-source-reading" tabIndex={0} aria-label="原文阅读区"><KnowledgeBody content={loaded.revision.content} metadataTitles/></div>:<p role="status">正在核对原资料版本与读取权限…</p>}</>}</section>;
}
