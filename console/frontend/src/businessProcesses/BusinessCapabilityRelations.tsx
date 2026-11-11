import {formatTime} from '../journey/formatTime';
import {BusinessRelationWithdrawal} from './BusinessRelationWithdrawal';
import {useBusinessRelationAccess} from './useBusinessRelationAccess';
import {BusinessRelationEditor} from './BusinessRelationEditor';
import {businessProcessHref} from './businessRelationNavigation';
import {useEffect,useRef,useState} from 'react';
import {Link} from 'react-router-dom';
import {getWorkbenchSession,workbenchPrincipalKey} from '../api/digitalEmployees';
import {listBusinessCapabilityRelations,type BusinessRelationEntry,type FixedBusinessReference} from '../api/businessProcesses';
import './businessRelations.css';

export function BusinessCapabilityRelations({side,reference,activityId,principal}:{side:'PROCESS'|'CAPABILITY';reference:FixedBusinessReference;activityId?:string;principal?:string}){
 const [items,setItems]=useState<BusinessRelationEntry[]>([]),[cursor,setCursor]=useState<string|null>(null),[busy,setBusy]=useState(true),[error,setError]=useState(''),[retry,setRetry]=useState(0);
 const request=useRef<AbortController|null>(null),subject=useRef(''),running=useRef(false);
 const {resource_id,revision_id,digest}=reference;
 const access=useBusinessRelationAccess(resource_id,side==='PROCESS'&&!!activityId);
 useEffect(()=>{const abort=new AbortController();request.current=abort;let active=true;subject.current=principal??'';running.current=true;
  void (async()=>{await Promise.resolve();if(!active)return;setBusy(true);setError('');setItems([]);setCursor(null);try{const key=workbenchPrincipalKey(await getWorkbenchSession(AbortSignal.any([abort.signal,AbortSignal.timeout(30_000)])));if(subject.current&&subject.current!==key)throw Error('IDENTITY_CHANGED');subject.current=key;const result=await listBusinessCapabilityRelations(side,{resource_id,revision_id,digest},key,abort.signal);if(active){setItems(result.items);setCursor(result.nextCursor)}}catch{if(active)setError('关联记录暂时无法读取，请核对当前账号与访问范围后重试。')}finally{if(active){setBusy(false);running.current=false}}})();
  const expire=()=>{active=false;abort.abort();setItems([]);setCursor(null);setBusy(false);setError('登录已变化，请重新读取关联记录。')};window.addEventListener('workbench-session-expired',expire);return()=>{active=false;abort.abort();window.removeEventListener('workbench-session-expired',expire)};
 },[side,resource_id,revision_id,digest,principal,retry]);
 async function more(){
  const controller=request.current,key=subject.current;
  if(running.current||!cursor||!controller||controller.signal.aborted)return;
  const current=()=>request.current===controller&&!controller.signal.aborted&&subject.current===key;
  running.current=true;setBusy(true);
  try{const result=await listBusinessCapabilityRelations(side,reference,key,controller.signal,cursor);if(current()){setItems(old=>[...new Map([...old,...result.items].map(item=>[item.relationRevisionId,item])).values()]);setCursor(result.nextCursor)}}
  catch{if(current()){setItems([]);setCursor(null);setError('关联记录未能继续读取，请重新读取。')}}
  finally{if(current()){running.current=false;setBusy(false)}}
 }

 const visible=activityId?items.filter(item=>item.record.activity_ids.includes(activityId)):items;
 const capabilityHref=(item:BusinessRelationEntry)=>'/capabilities?'+new URLSearchParams({capability:item.record.capability.resource_id,revision:item.record.capability.revision_id,digest:item.record.capability.digest,businessProcessReturn:businessProcessHref(item.record.process,activityId??item.record.activity_ids[0])});
 const groups=[...new Set(visible.map(item=>item.relationId))].map(id=>visible.filter(item=>item.relationId===id).sort((a,b)=>b.relationVersion-a.relationVersion));
 const recordView=(item:BusinessRelationEntry,editable:boolean)=><article key={item.relationRevisionId}><div className="bp-relation-heading"><strong>{item.record.relation_type==='SUPPORTS_ACTIVITY'?'能力支撑活动':'能力来源于流程设计'}</strong><small>关系修订 {item.relationVersion}</small></div>{side==='PROCESS'?<Link to={capabilityHref(item)}>{item.capabilityTitle}</Link>:<Link to={businessProcessHref(item.record.process,item.record.activity_ids[0])}>{item.processName}</Link>}<p>{item.record.coverage_description}</p><ul>{item.activities.map(activity=><li key={activity.activityId}>{side==='CAPABILITY'?<Link to={businessProcessHref(item.record.process,activity.activityId)}>{activity.name}</Link>:activity.name}</li>)}</ul><details data-bp-state-key={'relation-evidence:'+item.relationRevisionId}><summary>固定版本依据</summary><p>流程：{item.record.process.revision_id}</p><p>能力：{item.record.capability.revision_id}</p><p>关系：{item.relationRevisionId}</p><p>记录时间：{formatTime(item.recordedAt)}</p><p>精确时间：{item.recordedAt}</p></details>{editable&&side==='PROCESS'&&activityId&&<BusinessRelationEditor access={access} key={item.relationRevisionId} base={item} reference={item.record.process} activityId={activityId} onSaved={()=>setRetry(value=>value+1)}/>} {!item.withdrawal&&side==='PROCESS'&&activityId&&<BusinessRelationWithdrawal allowNew={editable} key={'withdraw:'+item.relationRevisionId} entry={item} access={access} onSaved={()=>setRetry(value=>value+1)}/>}</article>;
 return <section className="bp-relations" aria-label={side==='PROCESS'?'活动能力关联':'关联流程与活动'}><h3>{side==='PROCESS'?'能力支撑与来源':'关联流程与活动'}</h3><p>关联固定双方版本；历史修订保留供追溯，不代表已有执行结果。</p>
 {busy&&<p role="status">正在读取关联记录…</p>}{error&&<p role="alert">{error} <button type="button" onClick={()=>setRetry(value=>value+1)}>重新读取关联记录</button></p>}
 {!error&&groups.map(group=>{const latest=group[0],withdrawal=latest.withdrawal,currentKnownByServer=group.some(item=>typeof item.isCurrentRelationRevision==='boolean'),current=group.find(item=>item.isCurrentRelationRevision===true),display=current??latest,history=group.filter(item=>item!==display),currentKnown=!currentKnownByServer||!!current;
 return <div className="bp-relation-group" key={latest.relationId}>
 {withdrawal?<><div className="bp-relation-withdrawn"><strong>当前关系已撤回</strong><p>{side==='PROCESS'?latest.capabilityTitle:latest.processName}</p><p>{withdrawal.reason}</p>{withdrawal.recordedAt&&<small>撤回时间：{formatTime(withdrawal.recordedAt)}</small>}</div><details data-bp-state-key={'relation-history:'+latest.relationId} className="bp-relation-history"><summary>查看撤回关系的历史修订（{group.length}）</summary><p>以下为当时版本内容，当前撤回状态不改写历史。</p>{group.map(item=>recordView(item,false))}<details data-bp-state-key={'relation-withdrawal:'+latest.relationId}><summary>撤回时间依据</summary><p>{withdrawal.recordedAt??'时间待核实'}</p></details></details>{side==='PROCESS'&&activityId&&<BusinessRelationWithdrawal entry={latest} access={access} onSaved={()=>setRetry(value=>value+1)}/>}</>:<><p className="bp-relation-version-label">{current?'当前关系修订':currentKnownByServer?'历史关联 · 当前修订不在已加载范围':'已加载关系修订'}</p>{recordView(display,currentKnown)}{history.length>0&&<details data-bp-state-key={'relation-history:'+latest.relationId} className="bp-relation-history"><summary>查看历史修订（{history.length}）</summary>{history.map(item=>recordView(item,false))}</details>}</>}
 </div>})}
 {!busy&&!error&&!visible.length&&<p>{cursor?'当前已加载范围暂无此活动的可读关联，可继续加载。':'当前未读取到可见的关联记录。'}</p>}{!error&&cursor&&<button type="button" disabled={busy} onClick={()=>void more()}>加载更多关联记录</button>}
 {side==='PROCESS'&&activityId&&<BusinessRelationEditor access={access} reference={reference} activityId={activityId} onSaved={()=>setRetry(value=>value+1)}/>}
 </section>;
}
