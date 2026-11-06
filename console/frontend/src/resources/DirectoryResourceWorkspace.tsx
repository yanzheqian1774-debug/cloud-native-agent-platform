import {useEffect,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {readWorkbenchSession} from '../api/businessWorkspace';
import {readDirectoryResource,type DirectoryDetail,type DirectoryItem,type DirectoryPage} from '../api/resourceDirectory';
import {NavigationIcon} from '../components/NavigationIcon';

const scopeKey=(subject:string,scope:{tenantId:string;securityDomain:string})=>JSON.stringify([subject,scope.tenantId,scope.securityDomain]);
const itemKey=(item:DirectoryItem)=>JSON.stringify([item.kind,item.identity,item.revisionId,item.digest]);
const text=(value:unknown,fallback='未提供')=>typeof value==='string'?value:fallback;
const strings=(value:unknown)=>Array.isArray(value)?value.filter((x):x is string=>typeof x==='string'):[];
function TypeMark({kind}:{kind:'skill'|'mcp'}){return <span className="resource-type-mark" data-resource-kind={kind}><NavigationIcon name={kind}/><span>{kind==='skill'?'Skill 技能':'MCP 连接'}</span></span>}

export function DirectoryResourceWorkspace({page,error,identity,revisionId}:{page:DirectoryPage|null;error:string;identity:string;revisionId:string}){
 const [params]=useSearchParams(),back=new URLSearchParams(params);back.delete('selected');back.delete('resourceRevision');
 const selected=page?.items.find(item=>(item.kind==='skill'||item.kind==='mcp')&&item.identity===identity&&item.revisionId===revisionId);
 const conversation=params.get('returnConversation');
 return <section className="resource-directory-workspace" aria-label="资源详情工作区">
  <nav className="resource-detail-list" aria-label="本页可读资源"><h2>本页可读版本</h2>{page?.items.filter(item=>item.kind==='skill'||item.kind==='mcp').map(item=>{const next=new URLSearchParams(params);next.set('selected',item.identity);next.set('resourceRevision',item.revisionId);return <Link key={itemKey(item)} to={'?'+next} aria-current={selected===item?'page':undefined}><TypeMark kind={item.kind as 'skill'|'mcp'}/><strong>{item.name}</strong><small>{item.isCurrentPublished?'当前发布版本':item.isCurrentDraft?'当前草稿':'历史版本'}</small></Link>})}</nav>
  <div className="resource-directory-detail" tabIndex={0} role="region" aria-label="资源详情滚动区">
   <div className="resource-detail-return"><Link to={'?'+back}>返回资源目录</Link>{conversation&&<Link to={'/work?'+new URLSearchParams({conversation})}>返回原会话</Link>}</div>
   {error?<div role="alert"><h1>资源详情暂不可读</h1><p>请核对当前账号和授权范围，原资源与使用记录保留。</p><details><summary>核查依据</summary><code>{error}</code></details></div>:!page?<p role="status">正在读取当前可读版本…</p>:!selected?<div role="status"><h1>当前列表未返回此版本</h1><p>请返回目录核对筛选和当前读取范围。此结果不表示原版本已删除，也不授予管理或执行权限。</p></div>:<ExactResourceDetail key={scopeKey(page.subject,page.scope)+itemKey(selected)} item={selected} expectedScope={scopeKey(page.subject,page.scope)} conversation={conversation}/>}
  </div>
 </section>;
}

function ExactResourceDetail({item,expectedScope,conversation}:{item:DirectoryItem;expectedScope:string;conversation:string|null}){
 const [detail,setDetail]=useState<DirectoryDetail|null>(null),[error,setError]=useState('');
 useEffect(()=>{
  const abort=new AbortController();
  async function load(){
   const before=await readWorkbenchSession(abort.signal);
   if(scopeKey(before.principal.principalId,before.principal)!==expectedScope)throw Error('RESOURCE_DIRECTORY_IDENTITY_CHANGED');
   const value=await readDirectoryResource(item,abort.signal),after=await readWorkbenchSession(abort.signal);
   if(JSON.stringify(before.principal)!==JSON.stringify(after.principal)||!value.scope||scopeKey(value.subject??'',value.scope)!==expectedScope)throw Error('RESOURCE_DIRECTORY_IDENTITY_CHANGED');
   if(value.kind!==item.kind||value.identity!==item.identity||value.revision?.revisionId!==item.revisionId||value.revision?.digest!==item.digest)throw Error('RESOURCE_DIRECTORY_VERSION_MISMATCH');
   if(!abort.signal.aborted)setDetail(value);
  }
  void load().catch(reason=>{if(!abort.signal.aborted){setDetail(null);setError(reason instanceof Error?reason.message:'RESOURCE_DIRECTORY_UNAVAILABLE')}});
  return()=>abort.abort();
 },[item,expectedScope]);
 if(error)return <div role="alert"><h1>当前版本详情未读回</h1><p>不展示旧配置或推定就绪状态，请返回目录核对。</p><details><summary>核查依据</summary><code>{error}</code></details></div>;
 if(!detail)return <p role="status">正在核对准确版本与读取资格…</p>;
 const c=detail.revision!.content,isSkill=item.kind==='skill';
 return <article className="resource-readonly-detail" data-resource-kind={item.kind}>
  <header><TypeMark kind={item.kind as 'skill'|'mcp'}/><h1>{detail.name}</h1><p>{text(c.description,'当前版本未提供用途说明。')}</p><span className="resource-version-state" data-state={item.state}>{item.state==='PUBLISHED'?'已发布':item.state==='DRAFT'?'草稿':item.state}</span></header>
  <p className="resource-detail-boundary">这里只读展示当前授权版本。发布、连接测试、工具发现、工具调用及业务执行分别核对，历史权限或历史成功不代表当前可执行。</p>
  {isSkill?<section><h2>办理规则与能力</h2><p className="resource-detail-rule">{text(c.instructions,'当前版本未提供办理规则。')}</p><ul>{strings(c.capabilities).map(x=><li key={x}>{x}</li>)}</ul></section>:<section><h2>连接配置</h2><dl><dt>连接地址</dt><dd>{text(c.endpoint)}</dd><dt>凭据引用</dt><dd>{text(c.secretReference)}</dd></dl><p>连接配置不是业务系统对象，也不代表已发现或授权使用工具。本版本读取接口未返回工具发现和选择记录，不推定其存在。</p></section>}
  <section><h2>{isSkill?'资源级输入与输出声明':'能力声明'}</h2>{isSkill&&<p>本节仅展示资源级声明；准确操作的输入输出以本版本完整配置中的 operations 为准。</p>}{isSkill?<><h3>输入</h3><pre>{JSON.stringify(c.inputSchema??{},null,2)}</pre><h3>输出</h3><pre>{JSON.stringify(c.outputSchema??{},null,2)}</pre></>:<ul>{strings(c.capabilities).map(x=><li key={x}>{x}</li>)}</ul>}</section>
  <section><h2>执行边界</h2><dl><dt>副作用</dt><dd>{text(c.sideEffect)}</dd><dt>幂等性</dt><dd>{text(c.idempotency)}</dd><dt>超时秒数</dt><dd>{typeof c.timeoutSeconds==='number'?c.timeoutSeconds:'未提供'}</dd></dl><h3>异常策略</h3><pre>{JSON.stringify(c.errorPolicy??{},null,2)}</pre></section>
  <section><h2>本版本可查看的使用记录</h2>{detail.usage?.length?<ul>{detail.usage.map(use=><li key={use.digest}><Link to={'/work?'+new URLSearchParams({problem:use.problemId,execution:use.digest,...(conversation?{returnConversation:conversation}:{})})}>{use.title}</Link><span> · 方案 v{use.planVersion} · {use.state==='SUCCEEDED'?'执行完成':use.state}</span></li>)}</ul>:<p>当前未读回可查看的使用记录。</p>}</section>
  <section><h2>准确版本依据</h2><dl><dt>资源</dt><dd>{item.identity}</dd><dt>修订</dt><dd>{item.revisionId}</dd><dt>内容摘要</dt><dd>{item.digest}</dd></dl><details><summary>查看本版本配置</summary><pre>{JSON.stringify(c,null,2)}</pre></details></section>
 </article>;
}
