import {useRef,useState} from 'react';
import {CapabilityEditor,type CapabilityEditorDraft,type CapabilitySaveDraft} from './CapabilityEditor';
import type {CapabilityDetail} from '../api/businessCapabilities';

type Stored={draft?:CapabilityEditorDraft;command?:CapabilitySaveDraft};
const fields=['title','intent','inputs','outputs','business_scope','exclusions','manual_involvement','known_limitations'];
function validBindings(value:unknown):boolean{
 return Array.isArray(value)&&value.length<=64&&value.every(item=>item&&typeof item==='object'&&['EMPLOYEE','SKILL','MCP','KNOWLEDGE','ONTOLOGY','TOOL','RUNTIME_PROFILE'].includes(item.kind)&&typeof item.purpose==='string'&&item.reference&&typeof item.reference.resource_id==='string'&&typeof item.reference.revision_id==='string'&&typeof item.reference.digest==='string'&&/^[a-f0-9]{64}$/.test(item.reference.digest));
}
function restore(key:string):{value:Stored;error:string}{
 try{
  const raw=sessionStorage.getItem(key),value:Stored=raw?JSON.parse(raw):{};
  if(!value||typeof value!=='object'||Array.isArray(value))throw Error('invalid');
  const d=value.draft,c=value.command;
  if(d&&(!d.fields||!fields.every(k=>typeof (d.fields as Record<string,unknown>)[k]==='string')||typeof d.domain!=='string'||typeof d.criteria!=='string'||typeof d.purpose!=='string'||!validBindings(d.bindings)||!d.origin||!['INDEPENDENT','WORKFLOW_REVISION','SAVED_PREPARATION'].includes(d.origin.kind)))throw Error('invalid');
  if(c&&(typeof c.commandId!=='string'||!c.commandId||c.expectedVersion!==0||!c.revision||c.revision.predecessor_revision_id!==null||typeof c.revision.capability_id!=='string'||typeof c.revision.revision_id!=='string'||!validBindings(c.revision.bindings)||!fields.every(k=>typeof (c.revision as unknown as Record<string,unknown>)[k]==='string')||!Array.isArray(c.revision.acceptance_criteria)||!c.revision.acceptance_criteria.every(v=>typeof v==='string')))throw Error('invalid');
  return {value,error:''};
 }catch{return {value:{},error:'本地编辑记录暂时无法读取，已保留原记录。请恢复浏览器存储后重新打开，不要重复创建。'}}
}
export function IndependentCapabilityDraft({principal,onSaved,onCancel}:{principal:string;onSaved:(value:CapabilityDetail)=>void;onCancel:()=>void}){
 const key='capability-independent-draft:v1:'+principal;
 const [initial]=useState(()=>restore(key)),latest=useRef(initial.value);
 const [storageError,setStorageError]=useState('');
 const persist=(value:Stored)=>{sessionStorage.setItem(key,JSON.stringify(value));latest.current=value;setStorageError('')};
 const draft=(value:CapabilityEditorDraft)=>{try{persist({...latest.current,draft:value})}catch{setStorageError('本地草稿暂存失败，请保留此页并恢复浏览器存储后继续。')}};
 const command=(value:CapabilitySaveDraft|null)=>{try{persist({...latest.current,command:value??undefined})}catch{setStorageError('原提交记录未能保存，尚未发起本次后台保存。请保留此页并恢复浏览器存储。');if(value)throw Error('LOCAL_COMMAND_NOT_SAVED')}};
 const saved=(value:CapabilityDetail)=>{sessionStorage.removeItem(key);latest.current={};onSaved(value)};
 const cancel=()=>{if(storageError)return;try{if(!latest.current.command)sessionStorage.removeItem(key);onCancel()}catch{setStorageError('本地草稿未能清理，请保留此页，恢复浏览器存储后再取消。')}};
 if(initial.error)return <section className="capability-panel" role="alert">{initial.error}</section>;
 return <>{storageError&&<p role="alert">{storageError}</p>}<CapabilityEditor principal={principal} initialDraft={initial.value.draft} initialCommand={initial.value.command} onDraft={draft} onCommand={command} onSaved={saved} onCancel={cancel}/></>;
}
