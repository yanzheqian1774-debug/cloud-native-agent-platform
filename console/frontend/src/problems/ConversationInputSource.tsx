import {useEffect,useState} from 'react';
import {readExactDirectoryResource,type DirectoryDetail} from '../api/resourceDirectory';
import {KnowledgeBody} from '../resources/KnowledgeBody';
import type {ConversationInputSourceReference} from '../api/draftAssistanceTypes';
export function ConversationInputSource({source}:{source?:ConversationInputSourceReference}){
 const [open,setOpen]=useState(false),[loaded,setLoaded]=useState<DirectoryDetail|null>(null),[error,setError]=useState('');
 const identity=source?.source.resource_id,revision=source?.source.revision_id,digest=source?.source.digest;
 useEffect(()=>{
  if(!open||!identity||!revision||!digest)return;
  let active=true;const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
  const expired=()=>{controller.abort();if(active){setLoaded(null);setError('当前登录已失效，请重新登录后核对原资料。')}};
  window.addEventListener('workbench-session-expired',expired);
  void readExactDirectoryResource('knowledge',identity,revision,digest,controller.signal).then(value=>{if(active&&!controller.signal.aborted)setLoaded(value)}).catch(()=>{if(active)setError('暂时无法读取本次使用的资料版本，请核对当前权限或稍后重试。原回答保留。')}).finally(()=>clearTimeout(timer));
  return()=>{active=false;clearTimeout(timer);controller.abort();window.removeEventListener('workbench-session-expired',expired)};
 },[open,identity,revision,digest]);
 if(!source)return <p>这条历史答复未记录准确资料版本，不能据此定位原文。</p>;
 return <section aria-label="本次回答使用的资料"><p>使用资料：{source.name}</p><button type="button" aria-expanded={open} onClick={()=>{setLoaded(null);setError('');setOpen(value=>!value)}}>{open?'收起原文':'查看本次使用的原文'}</button>{open&&<>{error?<p role="alert">{error}</p>:loaded?.revision?<KnowledgeBody content={loaded.revision.content}/>:<p role="status">正在核对原资料版本与读取权限…</p>}</>}</section>;
}
