import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {Link,useNavigate,useSearchParams} from 'react-router-dom';
import {readWorkbenchSession,type WorkbenchSession} from '../api/businessWorkspace';
import {readDirectoryResource,type DirectoryDetail,type DirectoryItem,type DirectoryPage} from '../api/resourceDirectory';
import {DefinitionReferenceView,DefinitionContentView} from './DefinitionContentView';
import {PreparedSkillSuccessorPanel} from './PreparedSkillSuccessorPanel';
import {EmployeeResourceReturn} from './EmployeeResourceReturn';
import './F3ResourceDetail.css';
import {NavigationIcon} from '../components/NavigationIcon';
import {formatTime} from '../journey/formatTime';
import {findResourceReadContext,resourceReadScope,saveResourceReadContext,type ResourceReadContext} from './resourceReadContext';

const scopeKey=(subject:string,scope:{tenantId:string;securityDomain:string})=>JSON.stringify([subject,scope.tenantId,scope.securityDomain]);
const itemKey=(item:DirectoryItem)=>JSON.stringify([item.kind,item.identity,item.revisionId,item.digest]);
const text=(value:unknown,fallback='未提供')=>typeof value==='string'?value:fallback;
const capabilityLabels:Record<string,string>={READ_DATA:'读取资料',VALIDATE_DATA:'核对资料',SUMMARIZE:'汇总信息',ANALYZE_DATA:'分析变化',RENDER_REPORT:'形成报告'};
const strings=(value:unknown)=>Array.isArray(value)?value.filter((x):x is string=>typeof x==='string'):[];
function TypeMark({kind}:{kind:'skill'|'mcp'|'knowledge'|'agent'}){return <span className="resource-type-mark" data-resource-kind={kind}><NavigationIcon name={kind}/><span>{kind==='skill'?'Skill 技能':kind==='mcp'?'MCP 连接':kind==='agent'?'Agent职责':'知识资料'}</span></span>}

export function DirectoryResourceWorkspace({page,error,identity,revisionId}:{page:DirectoryPage|null;error:string;identity:string;revisionId:string}){
 const [params]=useSearchParams(),back=new URLSearchParams(params);back.delete('selected');back.delete('resourceRevision');back.delete('resourceDigest');back.delete('fromExecution');back.delete('resourceContext');back.delete('resourceSection');back.delete('resourceView');
 const selected=page?.items.find(item=>(['skill','mcp','knowledge','agent'].includes(item.kind))&&item.identity===identity&&item.revisionId===revisionId);
 const toolsReturn=params.get('returnTools');let safeToolsReturn:string|null=null;try{if(toolsReturn){const u=new URL(toolsReturn,window.location.origin);if(u.origin===window.location.origin&&u.pathname==='/tools')safeToolsReturn=u.pathname+u.search}}catch{/* Invalid view context supplies no return link. */}
 const conversation=params.get('returnConversation'),expectedDigest=params.get('resourceDigest'),sourceExecution=params.get('fromExecution');
 return <section className="resource-directory-workspace" aria-label="资源详情工作区">
  <nav className="resource-detail-list" aria-label="本页可读资源"><h2>本页可读版本</h2>{page?.items.filter(item=>['skill','mcp','knowledge','agent'].includes(item.kind)).map(item=>{const next=new URLSearchParams(params);next.set('selected',item.identity);next.set('resourceRevision',item.revisionId);if(item.identity!==identity||item.revisionId!==revisionId){next.delete('resourceDigest');next.delete('fromExecution');next.delete('resourceContext')}return <Link key={itemKey(item)} to={'?'+next} aria-current={selected===item?'page':undefined}><TypeMark kind={item.kind as 'skill'|'mcp'|'knowledge'|'agent'}/><strong>{item.name}</strong><small>{item.isCurrentPublished?'当前发布版本':item.isCurrentDraft?'当前草稿':'历史版本'}</small></Link>})}</nav>
  <div className="resource-directory-detail" tabIndex={0} role="region" aria-label="资源详情滚动区">
   <div className="resource-detail-return">{conversation?<Link className="f3-detail-return" to={'/work?'+new URLSearchParams({conversation})}>返回原会话</Link>:safeToolsReturn?<Link className="f3-detail-return" to={safeToolsReturn}>返回工具详情</Link>:null}<Link className={conversation||safeToolsReturn?'f3-directory-secondary':'f3-detail-return'} to={'?'+back}>返回资源目录</Link></div>
   {error?<div role="alert"><h1>资源详情暂不可读</h1><p>请核对当前账号和授权范围，原资源与使用记录保留。</p><details><summary>核查依据</summary><code>{error}</code></details></div>:!page?<p role="status">正在读取当前可读版本…</p>:!selected?<div role="status"><h1>当前列表未返回此版本</h1><p>请返回目录核对筛选和当前读取范围。此结果不表示原版本已删除，也不授予管理或执行权限。</p></div>:expectedDigest&&expectedDigest!==selected.digest?<div role="alert"><h1>准确版本未能核对</h1><p>来源绑定的版本摘要与当前目录不一致，原记录保留，请核对后再查看。</p></div>:<ExactResourceDetail key={scopeKey(page.subject,page.scope)+itemKey(selected)} item={selected} expectedScope={scopeKey(page.subject,page.scope)} conversation={conversation} sourceExecution={sourceExecution} versions={page.items.filter(version=>version.kind===selected.kind&&version.identity===selected.identity)} hasMore={!!page.nextCursor}/>}
  </div>
 </section>;
}

function ExactResourceDetail({item,expectedScope,conversation,sourceExecution,versions,hasMore}:{item:DirectoryItem;expectedScope:string;conversation:string|null;sourceExecution:string|null;versions:DirectoryItem[];hasMore:boolean}){
 const [params,setParams]=useSearchParams(),tabs=useRef<HTMLElement>(null);
 const professional=params.get('resourceView')==='professional',sections=[['overview','概览'],['content','内容与定义'],['impact','引用与影响']] as const;
 const history=params.get('resourceSection')==='history';
 const section=professional?'content':sections.some(([key])=>key===params.get('resourceSection'))?params.get('resourceSection')!:'overview';
 const changeView=(value:string)=>setParams(previous=>{const next=new URLSearchParams(previous);if(value==='professional')next.set('resourceView',value);else{next.delete('resourceView');next.set('resourceSection',value)}next.delete('resourceContext');return next},{replace:true});
 const [loaded,setLoaded]=useState<{detail:DirectoryDetail;session:WorkbenchSession;restore:ResourceReadContext|null}|null>(null),[error,setError]=useState(''),[attempt,setAttempt]=useState(0);
 const article=useRef<HTMLElement>(null),navigate=useNavigate(),detail=loaded?.detail;
 useEffect(()=>{
  const abort=new AbortController();let active=true,generation=0;
  const deadline=window.setTimeout(()=>{if(active){generation++;setLoaded(null);setError('读取等待超时，原引用版本保持不变，请重新读取此版本。');abort.abort()}},30000);
  async function load(version:number){
   const before=await readWorkbenchSession(abort.signal);
   if(scopeKey(before.principal.principalId,before.principal)!==expectedScope)throw Error('RESOURCE_DIRECTORY_IDENTITY_CHANGED');
   const value=await readDirectoryResource(item,abort.signal),after=await readWorkbenchSession(abort.signal);
   if(JSON.stringify(before.principal)!==JSON.stringify(after.principal)||!value.scope||scopeKey(value.subject??'',value.scope)!==expectedScope)throw Error('RESOURCE_DIRECTORY_IDENTITY_CHANGED');
   if(value.kind!==item.kind||value.identity!==item.identity||value.revision?.revisionId!==item.revisionId||value.revision?.digest!==item.digest)throw Error('RESOURCE_DIRECTORY_VERSION_MISMATCH');
   const restore=['skill','knowledge','agent'].includes(item.kind)?findResourceReadContext(after,window.location.pathname+window.location.search,{resource_id:item.identity,revision_id:item.revisionId,digest:item.digest},item.kind as 'skill'|'knowledge'|'agent'):null;
   if(active&&version===generation&&!abort.signal.aborted){setLoaded({detail:value,session:after,restore:restore?.context??null});setError('')}
  }
  const refresh=()=>{const version=++generation;setLoaded(null);setError('');void load(version).catch(reason=>{if(active&&version===generation&&!abort.signal.aborted){setLoaded(null);setError(reason instanceof Error?reason.message:'RESOURCE_DIRECTORY_UNAVAILABLE')}}).finally(()=>window.clearTimeout(deadline))};
  const expired=()=>{generation++;window.clearTimeout(deadline);abort.abort();setLoaded(null);setError('当前登录已失效，原版本记录保留。')};
  refresh();window.addEventListener('workbench-session-expired',expired);
  return()=>{active=false;window.clearTimeout(deadline);abort.abort();window.removeEventListener('workbench-session-expired',expired)};
 },[item,expectedScope,attempt]);
 useLayoutEffect(()=>{
  const root=article.current,state=loaded?.restore;if(!root||!state)return;
  const region=root.closest<HTMLElement>('.resource-directory-detail'),list=root.closest('.resource-directory-workspace')?.querySelector<HTMLElement>('.resource-detail-list');
  root.querySelectorAll<HTMLDetailsElement>('details[data-resource-section]').forEach(node=>{node.open=state.openSections.includes(node.dataset.resourceSection!)});
  const restore=()=>{root.querySelector<HTMLElement>(`[data-resource-use="${CSS.escape(state.execution.digest)}"]`)?.focus({preventScroll:true});if(region)region.scrollTop=state.detailScroll;if(list)list.scrollTop=state.listScroll};
  restore();const frame=requestAnimationFrame(restore);return()=>cancelAnimationFrame(frame);
 },[loaded]);
 async function inspectUse(use:NonNullable<DirectoryDetail['usage']>[number]){
  if(!loaded)return;
  try{
   const origin=article.current,href=window.location.pathname+window.location.search;
   const session=await readWorkbenchSession();if(resourceReadScope(session)!==resourceReadScope(loaded.session))throw Error('RESOURCE_DIRECTORY_IDENTITY_CHANGED');
   if(!origin||article.current!==origin||window.location.pathname+window.location.search!==href)return;
   const root=article.current,region=root?.closest<HTMLElement>('.resource-directory-detail'),list=root?.closest('.resource-directory-workspace')?.querySelector<HTMLElement>('.resource-detail-list');
   const saved=saveResourceReadContext(session,{href:window.location.pathname+window.location.search,referenceKind:item.kind as 'skill'|'knowledge'|'agent',reference:{resource_id:item.identity,revision_id:item.revisionId,digest:item.digest},execution:{digest:use.digest,problemId:use.problemId},conversation,detailScroll:region?.scrollTop??0,listScroll:list?.scrollTop??0,openSections:Array.from(root?.querySelectorAll<HTMLDetailsElement>('details[data-resource-section][open]')??[],node=>node.dataset.resourceSection!)});
   navigate('/work?'+new URLSearchParams({resourceRead:saved.id}));
  }catch(reason){setLoaded(null);setError(reason instanceof Error?reason.message:'RESOURCE_RETURN_UNAVAILABLE')}
 }
 if(error)return <>{!conversation&&!params.get('returnTools')&&<EmployeeResourceReturn item={item}/>}<div role="alert"><h1>当前版本详情未读回</h1><p>{error.startsWith('读取等待超时')?error:'这次未能读取，请重新读取或返回资源目录。原资源和已保存的工作不会改变。'}</p><button type="button" onClick={()=>setAttempt(value=>value+1)}>重新读取此版本</button><details><summary>核查依据</summary><code>{error}</code></details></div></>;
 if(!detail)return <p role="status">正在核对准确版本与读取资格…</p>;
 const c=detail.revision!.content,isSkill=item.kind==='skill',published=versions.find(version=>version.isCurrentPublished),draft=versions.find(version=>version.isCurrentDraft);
 const versionLabel=(version:DirectoryItem)=>{if(/^revision:[0-9]+$/.test(version.revisionId))return '修订 '+version.revisionId.split(':')[1];let length=24;while(length<version.revisionId.length&&versions.some(other=>other.revisionId!==version.revisionId&&other.revisionId.slice(-length)===version.revisionId.slice(-length)))length++;return '修订 '+(version.revisionId.length>length?'…':'')+version.revisionId.slice(-length)};
 return <article ref={article} className={"resource-readonly-detail f3-managed-resource"+" f3-read-business"} data-resource-kind={item.kind}>
  {!conversation&&!params.get('returnTools')&&<EmployeeResourceReturn item={item}/>}
  <div className="f3-detail-banner"><span>{item.isCurrentPublished?'当前发布内容':item.isCurrentDraft?'修改草稿':'历史内容'} · 只读</span>{history?<button onClick={()=>changeView('content')}>返回内容</button>:<button onClick={()=>changeView('history')}>历史记录</button>}</div>
  <header className="f3-detail-heading"><div><TypeMark kind={item.kind as 'skill'|'mcp'|'knowledge'|'agent'}/><h1>{detail.name}</h1>{(isSkill||item.kind==='mcp')?<p>{text(c.description,'当前版本未提供用途说明。')}</p>:item.kind==='agent'?<p>{text(c.businessPurpose,'未提供业务用途')}</p>:null}</div></header>
  {professional&&!history&&(isSkill?<section aria-label="当前可读范围"><h2>当前可读范围</h2><p className="resource-detail-boundary">这里只读展示当前授权版本。发布、连接测试、工具发现、工具调用及业务执行分别核对，历史权限或历史成功不代表当前可执行。</p><p>读取身份和范围已与当前会话核对；本页可读不授予管理、维护、发布或使用权限。</p></section>:(item.kind==='mcp'?<p className="resource-detail-boundary">这里只读展示当前授权版本。发布、连接测试、工具发现、工具调用及业务执行分别核对，历史权限或历史成功不代表当前可执行。</p>:<p className="resource-detail-boundary">这里只查看保存的{item.kind==='knowledge'?'知识正文与出处':'Agent职责和绑定'}。已有员工与工作保留原版本；查看和发布不会自动启动{item.kind==='knowledge'?'索引、检索或业务执行':'实例或业务执行'}。</p>))}
  {history&&<section className="f3-detail-card" aria-label="历史记录"><h2>历史记录</h2><p>仅列出当前目录已加载、符合筛选且获准读取的同一资源版本；未显示不代表不存在。{hasMore?'还有更多可读版本，请返回目录加载后查看。':''}</p><ul className="f3-detail-history-list">{versions.map(version=>{const next=new URLSearchParams(params);next.set('selected',version.identity);next.set('resourceRevision',version.revisionId);next.set('resourceDigest',version.digest);next.set('resourceSection','content');next.delete('resourceView');next.delete('resourceContext');if(version.revisionId!==item.revisionId||version.digest!==item.digest)next.delete('fromExecution');return <li key={itemKey(version)}><div><strong>{version.isCurrentPublished?'当前发布内容':version.isCurrentDraft?'修改草稿':'历史内容'}</strong><p>{version.revisionId}</p><small>{version.createdAt?formatTime(version.createdAt):'时间未记录'}</small></div><Link to={'?'+next}>查看内容</Link></li>})}</ul><p>历史内容只读，查看不会修改版本或已有引用。</p></section>}
  {!history&&<>
   <nav ref={tabs} role="tablist" className="f3-detail-tabs" aria-label="资源详情导航" onKeyDown={event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const i=sections.findIndex(([key])=>key===section),n=event.key==='Home'?0:event.key==='End'?2:(i+(event.key==='ArrowRight'?1:2))%3;changeView(sections[n][0]);tabs.current?.querySelectorAll<HTMLButtonElement>('[role=tab]')[n]?.focus()}}>{sections.map(([key,label])=><button key={key} role="tab" aria-selected={section===key} tabIndex={section===key?0:-1} aria-controls={'readonly-'+key} onClick={()=>changeView(key)}>{label}</button>)}</nav>
   {section==='overview'&&<div role="tabpanel" id="readonly-overview" aria-label="概览"><section className="f3-detail-card"><h2>用途与交付</h2><p>{text(c.description,text(c.businessPurpose,'当前版本未提供用途说明。'))}</p><dl className="f3-detail-facts"><div><dt>当前发布</dt><dd>{published?versionLabel(published):'当前读取范围尚未核实'}</dd></div><div><dt>正在查看</dt><dd>{versionLabel(item)} · {item.isCurrentPublished?'当前发布内容':item.isCurrentDraft?'修改草稿':'历史内容'}</dd></div><div><dt>来源</dt><dd>{sourceExecution?(detail.usage?.some(use=>use.digest===sourceExecution)?'已核对原执行保存的版本引用':'原执行引用待核对'):conversation?'从原会话进入，未核对版本绑定':'可读资源目录'}</dd></div><div><dt>修改草稿</dt><dd>{draft?versionLabel(draft):'当前读取范围未返回，不代表不存在'}</dd></div></dl><details><summary>查看准确版本依据</summary><dl><dt>资源</dt><dd>{item.identity}</dd><dt>当前发布修订</dt><dd>{published?.revisionId??'当前读取范围尚未核实'}</dd><dt>正在查看修订</dt><dd>{item.revisionId}</dd><dt>修改草稿修订</dt><dd>{draft?.revisionId??'当前读取范围未返回'}</dd><dt>内容摘要</dt><dd>{item.digest}</dd></dl></details></section><section className="f3-detail-card"><h2>内容与维护</h2><button onClick={()=>changeView('content')}>查看完整定义</button><p>版本依据可在内容与定义中核对；已有工作保留原版本。</p></section></div>}
   {section==='content'&&<div role="tabpanel" id="readonly-content" aria-label="内容与定义"><section className="f3-detail-card">{isSkill?<><h2>办理规则与能力</h2><p className="f3-detail-rules">{text(c.instructions,'当前版本未提供办理规则。')}</p><ul>{strings(c.capabilities).map(x=><li key={x}>{capabilityLabels[x]??x}</li>)}</ul></>:item.kind==='mcp'?<><h2>连接说明</h2><p>{text(c.description,'当前版本未提供连接说明。')}</p><p>连接配置与凭据引用可在下方版本技术记录中核对。当前读取不代表连接可用或工具已获准执行。</p></>:<DefinitionContentView kind={item.kind as 'agent'|'knowledge'} content={c}/>}{isSkill&&<SkillReadableDefinition content={c}/>}<details data-resource-section="configuration"><summary>本版本完整定义与准确依据</summary><dl><dt>资源</dt><dd>{item.identity}</dd><dt>修订</dt><dd>{item.revisionId}</dd><dt>内容摘要</dt><dd>{item.digest}</dd></dl><pre>{JSON.stringify(c,null,2)}</pre></details></section></div>}
  </>}
  {!history&&section==='content'&&<details className="f3-detail-card" data-resource-section="technical" open={professional||undefined}><summary>版本技术记录</summary>
  {isSkill&&<section aria-label="固定版本"><h2>固定版本</h2><dl><dt>资源</dt><dd>{item.identity}</dd><dt>修订</dt><dd>{item.revisionId}</dd><dt>内容摘要</dt><dd>{item.digest}</dd></dl><p>固定查看此修订；详情缺失或摘要不符时不替换为最新版本。</p></section>}
  {isSkill?<section aria-label="技能定义"><h2>技能定义</h2><h3>办理规则与能力</h3><p className="resource-detail-rule">{text(c.instructions,'当前版本未提供办理规则。')}</p><ul>{strings(c.capabilities).map(x=><li key={x}>{x}</li>)}</ul></section>:item.kind!=='mcp'?<DefinitionContentView kind={item.kind as 'agent'|'knowledge'} content={c}/>:<section><h2>连接配置</h2><dl><dt>连接地址</dt><dd>{text(c.endpoint)}</dd><dt>凭据引用</dt><dd>{text(c.secretReference)}</dd></dl><p>连接配置不是业务系统对象，也不代表已发现或授权使用工具。本版本读取接口未返回工具发现和选择记录，不推定其存在。</p></section>}
  {(isSkill||item.kind==='mcp'||strings(c.capabilities).length>0)&&<section><h2>{isSkill?'资源级输入与输出声明':'能力声明'}</h2>{isSkill&&<p>本节仅展示资源级声明；准确操作的输入输出以本版本完整配置中的 operations 为准。</p>}{isSkill?<><h3>输入</h3><pre>{Object.hasOwn(c,'inputSchema')?JSON.stringify(c.inputSchema,null,2):'未返回资源级输入声明'}</pre><h3>输出</h3><pre>{Object.hasOwn(c,'outputSchema')?JSON.stringify(c.outputSchema,null,2):'未返回资源级输出声明'}</pre></>:<ul>{strings(c.capabilities).map(x=><li key={x}>{x}</li>)}</ul>}</section>}
  {isSkill&&<section aria-label="本版本声明信息"><h2>本版本声明信息</h2><details data-resource-section="declarations"><summary>查看保存的依赖与权限声明</summary><h3>依赖声明</h3><p>{!Object.hasOwn(c,'dependencies')?'当前版本未返回依赖声明字段。':c.dependencies===null?'当前版本依赖声明为 null，不能解释为明确无依赖。':Array.isArray(c.dependencies)&&c.dependencies.length===0?'当前保存的依赖声明为空数组；原契约默认值也为空，无法确认是否明确声明无依赖。':Array.isArray(c.dependencies)&&c.dependencies.every(x=>typeof x==='string')?'以下是保存的字符串声明；未提供准确目标版本、用途、来源或兼容性依据，不推定为已核对依赖。':'依赖声明格式尚未核对，不推定有效关系。'}</p>{Array.isArray(c.dependencies)&&c.dependencies.every(x=>typeof x==='string')&&<ul>{c.dependencies.map((x,i)=><li key={i}>{x}</li>)}</ul>}<h3>权限声明</h3><p>只展示保存的资源声明；空声明不代表无需授权，声明不等于当前实际授权。</p><pre>{Object.hasOwn(c,'permissions')?JSON.stringify(c.permissions,null,2):'未返回权限声明字段'}</pre></details><details data-resource-section="operations"><summary>查看准确操作的输入与输出声明</summary>{Array.isArray(c.operations)?c.operations.map((operation,i)=>{const op=operation&&typeof operation==='object'?operation as Record<string,unknown>:null;return <section key={i}><h3>{text(op?.name,'操作名称未提供')}</h3><pre>{JSON.stringify({inputSchema:op?.inputSchema,outputSchema:op?.outputSchema},null,2)}</pre></section>}):<p>当前版本未返回可核对的操作声明列表。</p>}</details></section>}
  {(isSkill||item.kind==='mcp')&&<section><h2>执行边界</h2><dl><dt>副作用</dt><dd>{text(c.sideEffect)}</dd><dt>幂等性</dt><dd>{text(c.idempotency)}</dd><dt>超时秒数</dt><dd>{typeof c.timeoutSeconds==='number'?c.timeoutSeconds:'未提供'}</dd></dl><h3>异常策略</h3><pre>{JSON.stringify(c.errorPolicy??{},null,2)}</pre></section>}
  {isSkill&&item.isCurrentPublished&&<PreparedSkillSuccessorPanel key={itemKey(item)} item={item}/>}
  </details>}
  {!history&&section==='impact'&&<div className="f3-detail-card" role="tabpanel" id="readonly-impact" aria-label="引用与影响">
  {sourceExecution&&<section aria-label="原执行的版本引用"><h2>原执行的版本引用</h2>{detail.usage?.some(use=>use.digest===sourceExecution)?<p role="status">已从当前可读使用记录核对原执行的准确版本引用。</p>:<p role="status">当前可读使用记录尚未证实这项引用，请核对原执行的读取资格与版本。</p>}</section>}
  <section><h2>关联任务中的保存引用</h2>{isSkill&&<p>仅显示本次可读取的引用，可能不完整。保存引用不代表实际调用回执。</p>}{detail.usage?.length?<ul>{detail.usage.map(use=><li key={use.digest}>{['skill','knowledge','agent'].includes(item.kind)?<button type="button" className="resource-use-read" data-resource-use={use.digest} onClick={()=>void inspectUse(use)}>{use.title}</button>:<Link to={'/work?'+new URLSearchParams({problem:use.problemId,execution:use.digest,...(conversation?{returnConversation:conversation}:{})})}>{use.title}</Link>}<span> · 方案 v{use.planVersion} · 关联任务状态：{({SUCCEEDED:'已完成',FAILED:'执行失败',RUNNING:'执行中',QUEUED:'排队中',CANCELLED:'已取消'} as Record<string,string>)[use.state]??'待核对'}</span></li>)}</ul>:<p>当前未读回关联任务的保存引用。</p>}</section>
  {<DefinitionReferenceView item={item} scopeNote={isSkill?'关联任务保存引用最多扫描范围内前 200 条准备执行，没有完整性或分页标记；空列表不能证明未被引用，也不能据此统计全部影响。':undefined}/>}
  </div>}

 </article>;
}

function SchemaSummary({value}:{value:unknown}){
 const schema=value&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:null;
 if(!schema)return <p>当前版本未提供可读字段声明。</p>;
 const properties=schema.properties&&typeof schema.properties==='object'&&!Array.isArray(schema.properties)?Object.entries(schema.properties):[];
 const required=strings(schema.required);
 return <>{typeof schema.description==='string'&&<p>{schema.description}</p>}{properties.length?<ul>{properties.map(([name,raw])=>{const field=raw&&typeof raw==='object'?raw as Record<string,unknown>:{};return <li key={name}><strong>{typeof field.description==='string'&&field.description.trim()?field.description:name}</strong> · {required.includes(name)?'必填':'可选'}{!(typeof field.description==='string'&&field.description.trim())?' · 未提供字段说明':''}</li>})}</ul>:<p>{typeof schema.type==='string'?'声明类型：'+schema.type+'；未提供字段说明。':'未提供字段说明。'}</p>}</>;
}
function SkillReadableDefinition({content:c}:{content:Record<string,unknown>}){
 const operations=Array.isArray(c.operations)?c.operations.filter((value):value is Record<string,unknown>=>!!value&&typeof value==='object'&&!Array.isArray(value)):[];
 return <><h2>输入与输出</h2>{operations.length?operations.map((operation,index)=><section key={index}><h3>{text(operation.name,'未命名操作')}</h3>{typeof operation.description==='string'&&<p>{operation.description}</p>}<h3>需要的输入</h3><SchemaSummary value={operation.inputSchema}/><h3>返回的结果</h3><SchemaSummary value={operation.outputSchema}/></section>):<><p>以下为资源级声明，当前版本未返回可核对的操作列表。</p><h3>需要的输入</h3><SchemaSummary value={c.inputSchema}/><h3>返回的结果</h3><SchemaSummary value={c.outputSchema}/></>}<h2>依赖与适用边界</h2>{strings(c.dependencies).length?<ul>{strings(c.dependencies).map((dependency,index)=><li key={index}>{dependency}</li>)}</ul>:<p>当前声明不足以确认依赖范围，不能解释为无需依赖。</p>}<p>依赖声明不等于已核对准确目标版本或获得执行授权。</p><dl><dt>操作影响</dt><dd>{({READ:'只读',NONE:'无副作用声明',WRITE:'可能写入'} as Record<string,string>)[text(c.sideEffect)]??text(c.sideEffect,'未声明')}</dd><dt>执行时限</dt><dd>{typeof c.timeoutSeconds==='number'?c.timeoutSeconds+' 秒':'未声明'}</dd></dl><h2>测试与发布依据</h2><p>当前读取接口未返回本版本测试与发布校验回执，无法据此判断测试是否通过或当前是否可执行。历史成功不代表当前执行授权。</p></>;
}
