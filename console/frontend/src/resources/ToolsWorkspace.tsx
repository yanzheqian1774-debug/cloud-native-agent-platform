import {useEffect,useLayoutEffect,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {listReadableResources,type DirectoryPage} from '../api/resourceDirectory';
import {readMcpTools,toolsScope,type McpTools,type SavedMcpTool} from '../api/mcpTools';
import {ToolDraftCatalog} from './ToolDraftCatalog';
import {SkillCatalogCard} from './SkillCatalogCard';
import {formatTime} from '../journey/formatTime';
import './ToolsWorkspace.css';

const scroller=()=>document.querySelector<HTMLElement>('.skill-frame-content')??document.scrollingElement;
const readScroll=()=>scroller()?.scrollTop??0;
const restoreScroll=(top:number)=>scroller()?.scrollTo(0,top);
const sourceStates=(data:McpTools)=>[...(data.sourceArchived?['来源已归档']:[]),...(!data.sourceEnabled?['来源已停用']:[])];
const text=(v:unknown)=>typeof v==='string'&&v.trim()?v:'未提供';
const object=(v:unknown):Record<string,unknown>|null=>v!==null&&typeof v==='object'&&!Array.isArray(v)?v as Record<string,unknown>:null;
function SchemaFields({title,value}:{title:string;value:unknown}){
 const schema=object(value),properties=object(schema?.properties),required=Array.isArray(schema?.required)?schema.required:[];
 return <section className="f3-tool-section"><h2>{title}</h2>{properties&&Object.keys(properties).length?<div className="f3-tool-table"><table><thead><tr><th>参数</th><th>类型</th><th>说明</th><th>必填</th></tr></thead><tbody>{Object.entries(properties).map(([name,raw])=>{const p=object(raw);return <tr key={name}><td>{name}</td><td>{text(p?.type)}</td><td>{text(p?.description)}</td><td>{required.includes(name)?'是':'未声明必填'}</td></tr>})}</tbody></table></div>:<p>{schema?'已提供结构声明，未提供可展开的属性列表。':'未提供'}</p>}</section>;
}
function SideEffects({tool}:{tool:SavedMcpTool}){
 const labels:Record<string,string>={readOnlyHint:'只读提示',destructiveHint:'破坏性操作提示',idempotentHint:'幂等提示',openWorldHint:'外部系统访问提示'};
 const hints=Object.entries(tool.annotations??{}).filter(([k,v])=>k in labels&&typeof v==='boolean');
 return <section className="f3-tool-section"><h2>副作用声明</h2><p>{text(tool.sideEffect)}</p>{hints.length>0&&<dl>{hints.map(([k,v])=><div key={k}><dt>{labels[k]}</dt><dd>{v?'是':'否'}</dd></div>)}</dl>}<p className="f3-tool-note">这是来源保存的声明，尚不能据此判断当前可用、安全或已获准执行。</p></section>;
}

function InvocationHistory({tool,data}:{tool:SavedMcpTool;data:McpTools}){
 const labels:Record<string,string>={TOOL_RESPONSE_RECEIVED:'工具已返回',TOOL_ERROR:'工具返回错误',CANCELLED_BEFORE_DISPATCH:'调用前已取消',NOT_DISPATCHED:'未发出工具调用',RESULT_UNKNOWN:'调用结果未确认'};
 const rows=tool.invocations??[];
 return <section className="f3-tool-section" aria-label="调用记录"><h2>调用记录</h2>{rows.length?<><p>以下记录对应当前工具及固定来源，不代表业务问题已解决。</p><ul>{[...rows].reverse().map(row=><li key={row.invocationId}><strong>{labels[row.outcome]??'调用结果未确认'}</strong> · {row.invokedAt?formatTime(row.invokedAt):'时间未提供'}{row.outcome==='RESULT_UNKNOWN'&&<p>未能确认调用结果，可能已产生影响。不会自动重试。</p>}</li>)}</ul></>:<p>当前没有可确认准确运行版本的调用回执。</p>}{(tool.invocationsTruncated||data.invocationWindowTruncated)&&<p>当前仅展示最近部分记录，不能据此判断完整调用历史。</p>}{Boolean(data.unattributedSourceInvocationCount)&&<p>此来源存在缺少准确版本的历史调用记录，无法归属于当前工具与版本。</p>}</section>;
}

export function ToolsWorkspace(){
 const [params,setParams]=useSearchParams();
 const query=params.get('query')??'',cursor=params.get('cursor')??'',identity=params.get('source')??'',revision=params.get('revision')??'',digest=params.get('digest')??'';
 const sourceKey=JSON.stringify([identity,revision,digest]),listKey=JSON.stringify([query,cursor]);
 const [directory,setDirectory]=useState<{key:string;value:DirectoryPage}|null>(null),[directoryFailure,setDirectoryError]=useState<{key:string;message:string}|null>(null);
 const [loaded,setLoaded]=useState<{key:string;value:McpTools}|null>(null),[failure,setError]=useState<{key:string;message:string}|null>(null),[retry,setRetry]=useState(0),[expired,setExpired]=useState(false);
 const [search,setSearch]=useState(query);
 const directoryError=directoryFailure?.key===listKey+':'+retry?directoryFailure.message:'';
 const error=failure?.key===sourceKey+':'+retry?failure.message:'';
 const page=!expired&&directory?.key===listKey?directory.value:null;
 const sameScope=!page||!loaded||JSON.stringify([page.subject,page.scope.tenantId,page.scope.securityDomain])===toolsScope(loaded.value);
 const data=!expired&&sameScope&&loaded?.key===sourceKey?loaded.value:null;
 useEffect(()=>{const expire=()=>{setExpired(true);setDirectory(null);setLoaded(null)};window.addEventListener('workbench-session-expired',expire);return()=>window.removeEventListener('workbench-session-expired',expire)},[]);
 useEffect(()=>{
  const abort=new AbortController();let active=true;const timer=window.setTimeout(()=>{if(active){setDirectory(null);setDirectoryError({key:listKey+':'+retry,message:'读取来源等待超时，请重新读取。'});abort.abort()}},30000);
  listReadableResources('mcp',query,'',cursor||null,abort.signal).then(value=>{if(active&&!abort.signal.aborted)setDirectory({key:listKey,value})}).catch(e=>{if(active&&!abort.signal.aborted){setDirectory(null);setDirectoryError({key:listKey+':'+retry,message:String(e.message)})}}).finally(()=>window.clearTimeout(timer));
  return()=>{active=false;abort.abort();window.clearTimeout(timer)};
 },[query,cursor,listKey,retry]);
 useEffect(()=>{
  if(!identity||!revision||!digest)return;
  const abort=new AbortController();let active=true;const timer=window.setTimeout(()=>{if(active){setLoaded(null);setError({key:sourceKey+':'+retry,message:'读取工具等待超时，原来源版本保持不变。'});abort.abort()}},30000);
  readMcpTools({identity,revision,digest},abort.signal).then(value=>{if(active&&!abort.signal.aborted)setLoaded({key:sourceKey,value})}).catch(e=>{if(active&&!abort.signal.aborted){setLoaded(null);setError({key:sourceKey+':'+retry,message:String(e.message)})}}).finally(()=>window.clearTimeout(timer));
  return()=>{active=false;abort.abort();window.clearTimeout(timer)};
 },[identity,revision,digest,sourceKey,retry]);
 const snapshotId=params.get('snapshot'),snapshotDigest=params.get('snapshotDigest'),toolName=params.get('tool');
 const snapshot=data?(snapshotId?data.snapshots.find(s=>s.snapshotId===snapshotId&&s.digest===snapshotDigest):data.snapshots.at(-1)):null;
 const toolQuery=params.get('toolQuery')??'',visibleTools=snapshot?.tools.filter(t=>(t.name+' '+(t.description??'')).toLowerCase().includes(toolQuery.toLowerCase()))??[];
 const tool=toolName?snapshot?.tools.find(t=>t.name===toolName):null;
 const listParams=new URLSearchParams(params);listParams.delete('tool');
 const viewScrollKey=data?'f3-tools-view:'+toolsScope(data)+':'+params.toString():null;
 const saveViewScroll=()=>{if(viewScrollKey)sessionStorage.setItem(viewScrollKey,String(readScroll()))};
 useLayoutEffect(()=>{if(toolName&&viewScrollKey){const n=Number(sessionStorage.getItem(viewScrollKey)??'0');if(Number.isFinite(n))restoreScroll(n)}},[toolName,viewScrollKey]);
 const scrollKey=data?'f3-tools-scroll:'+toolsScope(data)+':'+listParams.toString():null;
 useLayoutEffect(()=>{if(!toolName&&scrollKey){const n=Number(sessionStorage.getItem(scrollKey)??'0');if(Number.isFinite(n))restoreScroll(n)}},[toolName,scrollKey]);
 function openTool(name:string){if(!snapshot||!data)return;const p=new URLSearchParams(params);p.set('snapshot',snapshot.snapshotId);p.set('snapshotDigest',snapshot.digest);p.delete('tool');sessionStorage.setItem('f3-tools-scroll:'+toolsScope(data)+':'+p.toString(),String(readScroll()));p.set('tool',name);setParams(p);restoreScroll(0)}
 function sourceHref(){const p=new URLSearchParams({kind:'mcp',query:identity,selected:identity,resourceRevision:revision,resourceDigest:digest,returnTools:'/tools?'+params.toString()});return '/mcp?'+p}
 const reread=<button type="button" onClick={()=>{setDirectory(null);setLoaded(null);setRetry(v=>v+1)}}>重新读取</button>;
 if(expired)return <main className="f3-tools-workspace"><h1>工具</h1><p role="alert">当前登录已失效，请重新登录后查看。</p></main>;
 return <main className="f3-tools-workspace"><header className="f3-tools-heading"><div><h1>工具</h1><p>查看工具能做什么、需要哪些输入，以及它的准确来源。</p></div></header>
 {import.meta.env.VITE_TOOL_DEFINITIONS_ENABLED === "true"&&<Link to="/tools/import">接入 / 导入工具</Link>}
 {import.meta.env.VITE_TOOL_DEFINITIONS_ENABLED === 'true'&&!toolName&&<ToolDraftCatalog/>}
 <p className="f3-tool-note">MCP 来源工具保留同一来源身份，以下显示已保存的发现记录。</p>
 {toolName?<><Link to={'/tools?'+listParams}>返回工具列表</Link>{data&&snapshot&&!tool?<p role="alert">该快照没有返回此工具，不替换为同名操作。</p>:tool&&snapshot&&data?<article className="f3-tool-detail"><header><h1>{tool.name}</h1><p>{text(tool.description)}</p><p>来源：{data.name} · 发现记录：{snapshot.capturedAt?formatTime(snapshot.capturedAt):'时间未提供'}</p><div className="f3-tool-source-states" aria-label="来源当前状态">{sourceStates(data).map(label=><span key={label}>{label}</span>)}</div><Link to={sourceHref()} onClick={saveViewScroll}>查看来源 MCP</Link></header><SchemaFields title="输入参数" value={tool.inputSchema}/><SchemaFields title="输出内容" value={tool.outputSchema}/><SideEffects tool={tool}/><section className="f3-tool-section"><h2>选用与调用</h2><p>{tool.selectedInSavedSnapshot?'该发现快照中已保存选用记录。':'该发现快照中未读回选用记录。'}选用不授予调用权限。</p></section><InvocationHistory tool={tool} data={data}/><details><summary>查看固定来源与完整声明</summary><dl><dt>来源修订</dt><dd>{data.revisionId}</dd><dt>来源摘要</dt><dd>{data.revisionDigest}</dd><dt>发现快照</dt><dd>{snapshot.snapshotId}</dd><dt>快照摘要</dt><dd>{snapshot.digest}</dd></dl><pre>{JSON.stringify(tool,null,2)}</pre></details></article>:null}</>:<>
 <details className="f3-tools-source-search"><summary>查找其他来源</summary><form className="f3-tools-filters" onSubmit={e=>{e.preventDefault();const p=new URLSearchParams();if(search)p.set('query',search);setParams(p)}}><label>查找 MCP 来源<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="来源名称或标识"/></label><button type="submit">查找来源</button></form></details>
 {directoryError?<div role="alert"><p>来源列表未读回，不能判断是否没有工具。</p>{reread}</div>:!page?<p role="status">正在读取可查看的来源…</p>:<section className="f3-tools-source"><label>工具来源<select aria-label="工具来源" value={page.items.some(i=>i.identity===identity&&i.revisionId===revision)?sourceKey:''} onChange={e=>{if(!e.target.value)return;const [id,rev,hash]=JSON.parse(e.target.value) as string[];const p=new URLSearchParams(params);p.set('source',id);p.set('revision',rev);p.set('digest',hash);for(const k of ['snapshot','snapshotDigest','tool'])p.delete(k);setParams(p)}}><option value="">选择一个可查看的来源版本</option>{page.items.map(i=><option key={i.identity+i.revisionId} value={JSON.stringify([i.identity,i.revisionId,i.digest])}>{i.name} · {i.isCurrentPublished?'当前发布':i.isCurrentDraft?'草稿':'历史版本'} · {i.createdAt?formatTime(i.createdAt):'时间未提供'}</option>)}</select></label><small>当前批次 {page.items.length} 个可读来源版本，不代表全部工具。</small>{cursor&&<button type="button" onClick={()=>{const p=new URLSearchParams(params);p.delete('cursor');setParams(p)}}>返回首批来源</button>}{page.nextCursor&&<button type="button" onClick={()=>{const p=new URLSearchParams(params);p.set('cursor',page.nextCursor!);setParams(p)}}>下一批来源</button>}{page.items.length===0&&<p>当前筛选下未读回可查看的来源。</p>}</section>}
 {data&&<section><div className="f3-tools-source"><h2>{data.name} 的工具操作</h2><Link to={sourceHref()} onClick={saveViewScroll}>查看来源 MCP</Link>{data.snapshots.length>0&&<label>发现记录<select aria-label="发现记录" value={snapshotId??snapshot?.snapshotId??''} onChange={e=>{const s=data.snapshots.find(x=>x.snapshotId===e.target.value);if(!s)return;const p=new URLSearchParams(params);p.set('snapshot',s.snapshotId);p.set('snapshotDigest',s.digest);setParams(p)}}><option value="" disabled>选择固定发现记录</option>{data.snapshots.map((s,index)=><option key={s.snapshotId} value={s.snapshotId}>第 {index+1} 份 · {s.capturedAt?formatTime(s.capturedAt):'时间未提供'}</option>)}</select></label>}</div><p className="f3-tool-note">发现记录不证明当前可用。来源{data.sourceRevisionState==='PUBLISHED'?'已发布':'尚非发布状态'}；不代表工具独立发布或已经调用。{sourceStates(data).join('，')}</p>{data.snapshotsTruncated&&<p role="status">仅展示该来源最近保存的 200 份准确发现记录。</p>}{!snapshotId&&data.availability==='NO_EXACT_SNAPSHOT'?<p role="status">尚无可确认属于此版本的发现快照；旧记录来源不明时不会使用最新版替代。</p>:snapshot&&<>{snapshot.toolsTruncated&&<p role="status">本快照仅展示前 500 项工具声明。</p>}<label className="f3-tool-filter">筛选已加载工具<input aria-label="筛选已加载工具" value={toolQuery} placeholder="工具名称或用途" onChange={e=>{const p=new URLSearchParams(params);p.set('toolQuery',e.target.value);setParams(p,{replace:true})}}/></label>{snapshot.tools.length===0?<p role="status">该固定发现快照明确返回 0 项工具。</p>:visibleTools.length===0?<p role="status">当前已加载快照中没有匹配工具。</p>:<div className="f3-tools-grid">{visibleTools.map(t=><SkillCatalogCard key={snapshot.snapshotId+':'+t.name} icon="tool" name={t.name} purpose={t.description??null} statuses={[{label:'已保存发现记录',tone:'neutral',basis:'validation'},...sourceStates(data).map(label=>({label,tone:'amber' as const,basis:'publication' as const}))]} attribution={data.name+' · '+(snapshot.capturedAt?formatTime(snapshot.capturedAt):'发现时间未提供')} details={<button type="button" className="skill-card-detail" onClick={()=>openTool(t.name)}>查看工具详情</button>}/>)}</div>}</>}</section>}
 </>}
 {!sameScope?<p role="alert">当前身份已变化，请刷新后重新读取工具。</p>:identity&&(!revision||!digest)?<p role="alert">来源版本信息不完整，请重新选择准确来源。</p>:identity&&error?<div role="alert"><p>{error.startsWith('读取工具等待超时')?error:'此版本的工具记录未读回，请核对当前读取资格与来源。'}</p>{reread}<details><summary>核查依据</summary><code>{error}</code></details></div>:identity&&!data?<p role="status">正在核对来源版本与工具发现记录…</p>:!identity?<p>选择来源后查看其中保存的工具操作。</p>:null}
 {data&&snapshotId&&!snapshot&&<p role="alert">原发现快照或摘要未能核对，不替换为更新记录。</p>}
 </main>;
}
