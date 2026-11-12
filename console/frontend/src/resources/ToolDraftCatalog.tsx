import {useEffect,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {getWorkbenchSession,workbenchPrincipalKey} from '../api/digitalEmployees';
import {listToolDrafts} from '../api/toolDefinitions';
import {SkillCatalogCard} from './SkillCatalogCard';
export function ToolDraftCatalog(){
 const [params,setParams]=useSearchParams(),cursor=params.get('draftCursor')??'';
 const [data,setData]=useState<{cursor:string;value:Awaited<ReturnType<typeof listToolDrafts>>}|null>(null),[error,setError]=useState<string|null>(null),[retry,setRetry]=useState(0),[expired,setExpired]=useState(false);
 useEffect(()=>{const controller=new AbortController();const expire=()=>{controller.abort();setData(null);setExpired(true)};window.addEventListener('workbench-session-expired',expire);
 getWorkbenchSession(controller.signal).then(session=>listToolDrafts(cursor,workbenchPrincipalKey(session),controller.signal)).then(value=>{if(!controller.signal.aborted){setData({cursor,value});setError(null)}}).catch(()=>{if(!controller.signal.aborted)setError('工具草稿列表未能读回，不能判断是否没有草稿。')});
 return()=>{controller.abort();window.removeEventListener('workbench-session-expired',expire)}},[cursor,retry]);
 const value=data?.cursor===cursor?data.value:null;
 function move(next:string){const p=new URLSearchParams(params);if(next)p.set('draftCursor',next);else p.delete('draftCursor');setParams(p)}
 if(expired)return null;
 return <section aria-label="导入的工具草稿"><h2>导入的工具草稿</h2>{error?<p role="alert">{error}<button onClick={()=>setRetry(x=>x+1)}>重新读取草稿</button></p>:!value?<p role="status">正在读取草稿…</p>:<>{!value.items.length?<p>当前批次没有可读取的工具草稿。</p>:<div className="f3-tools-grid">{value.items.map(item=><SkillCatalogCard key={item.toolId} icon="tool" name={item.name} purpose={item.purpose} statuses={[{label:'草稿',tone:'neutral',basis:'publication'}]} attribution={item.sourceKind==='API'?'API 描述':'平台插件'} details={<Link className="skill-card-detail" to={'/tools/draft?'+new URLSearchParams({id:item.toolId,revision:item.revisionId})}>查看和编辑草稿</Link>}/>)}</div>}{cursor&&<button onClick={()=>move('')}>返回首批草稿</button>}{value.nextCursor&&<button onClick={()=>move(value.nextCursor!)}>下一批草稿</button>}</>}</section>;
}
