import '../components/F3DetailTypography.css';
import {useRef,type ReactNode} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import type {SkillMcpResource} from '../api/skillMcpResources';
import {formatTime} from '../journey/formatTime';
import {ResourceVersionImpact} from './ResourceVersionImpact';
import './F3ResourceDetail.css';
import {publishedResourceHref} from './resourceJourneyLinks';

const sections=[['overview','概览'],['content','内容与定义'],['impact','引用与影响']] as const;
const labels:Record<string,string>={READ_DATA:'读取资料',VALIDATE_DATA:'核对资料',SUMMARIZE:'汇总信息',ANALYZE_DATA:'分析变化',RENDER_REPORT:'形成报告'};
const legacySection=(tab:string|null)=>tab==='版本'?'history':tab==='使用追溯'?'impact':tab?'content':'overview';
export function F3ResourceDetail({resource,busy,operations,onBack,onModify,onUpgradeLock,onUpgradeRefresh,onInspectTest}:{resource:SkillMcpResource;busy:boolean;operations:ReactNode;onBack:()=>void;onModify:()=>void;onUpgradeLock?:(locked:boolean)=>void;onUpgradeRefresh?:()=>Promise<void>;onInspectTest?:(id:string)=>void}){
 const [params,setParams]=useSearchParams(),tabs=useRef<HTMLElement>(null);
 const requested=params.get('resourceSection')??legacySection(params.get('resourceTab')),section=requested==='history'||sections.some(([key])=>key===requested)?requested:'overview';
 const maintenanceTab=params.get('resourceTab');
 const target=params.get('viewRevision')??resource.publishedRevisionId??resource.currentDraftRevisionId;
 const revision=resource.revisions.find(r=>r.revisionId===target),draft=resource.revisions.find(r=>r.revisionId===resource.currentDraftRevisionId);
 const update=(values:Record<string,string|null>)=>setParams(previous=>{const next=new URLSearchParams(previous);next.delete('resourceView');for(const [key,value] of Object.entries(values)){if(value===null)next.delete(key);else next.set(key,value)}return next},{replace:true});
 function select(value:string){update({resourceSection:value,resourceTab:null})}
 function maintain(tab:string){update({resourceSection:'content',resourceTab:tab})}
 const conversation=params.getAll('returnConversation').length===1?params.get('returnConversation'):null;
 const returnHref=conversation&&conversation.length<=200?'/work?'+new URLSearchParams({conversation}):null;
 const back=returnHref?<Link className="f3-detail-return" to={returnHref}>返回原会话</Link>:<button onClick={onBack}>返回来源</button>;
 if(!revision)return <section className="f3-managed-resource" aria-label="当前资源配置">{back}<div role="alert" className="f3-detail-card"><h1>当前版本未能核对</h1><p>原版本记录保留；不会改为展示其他修订。</p></div></section>;
 const currentPublished=revision.revisionId===resource.publishedRevisionId,isDraft=revision.revisionId===resource.currentDraftRevisionId,kind=resource.kind==='skill'?'技能':'MCP连接';
 const publishedHref=publishedResourceHref(resource);
 const title=currentPublished?'当前发布内容':isDraft?'修改草稿':'历史内容';
 const view=(id:string)=>update({viewRevision:id,resourceSection:'content',resourceTab:null});
 const showMaintenance=!!maintenanceTab&&!['版本','使用追溯'].includes(maintenanceTab);
 return <section className="f3-managed-resource" data-resource-kind={resource.kind} aria-label="当前资源配置">
  <div className="f3-detail-banner"><span>{title}{currentPublished&&draft?' · 有一份修改草稿，尚未生效':''}</span><button onClick={()=>select(section==='history'?'overview':'history')}>{section==='history'?'返回内容':'历史记录'}</button></div>
  <header className="f3-detail-heading"><div><h1>{resource.name}</h1><p>{kind} · {title}{!resource.enabled?' · 已停用':''}</p></div><div className="f3-detail-actions">{back}<button className="primary" disabled={busy} onClick={onModify}>{draft?'编辑草稿':'创建修改草稿'}</button></div></header>
  {section!=='history'&&<nav ref={tabs} className="f3-detail-tabs" role="tablist" aria-label="资源详情导航" onKeyDown={event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const i=sections.findIndex(([key])=>key===section),index=event.key==='Home'?0:event.key==='End'?sections.length-1:(i+(event.key==='ArrowRight'?1:sections.length-1))%sections.length;select(sections[index][0]);tabs.current?.querySelectorAll<HTMLButtonElement>('[role=tab]')[index]?.focus()}}>{sections.map(([key,label])=><button key={key} role="tab" tabIndex={section===key?0:-1} aria-selected={section===key} aria-controls={'f3-detail-'+key} onClick={()=>select(key)}>{label}</button>)}</nav>}
  {section==='overview'&&<div role="tabpanel" id="f3-detail-overview" aria-label="概览">
   <article className="f3-detail-card"><h2>用途与交付</h2><p>{revision.content.description||'当前版本尚未填写用途说明。'}</p><dl className="f3-detail-facts"><div><dt>当前发布</dt><dd>{resource.publishedRevisionId?<span>已发布 · {resource.publishedRevisionId.slice(-12)}</span>:'尚未发布'}</dd></div><div><dt>正在查看</dt><dd>{title} · {revision.revisionId.slice(-12)}</dd></div><div><dt>资源类型</dt><dd>{kind}</dd></div><div><dt>来源记录</dt><dd>{resource.relationships.length?`${resource.relationships.length} 条已保存关联，详见来源依据`:'未记录导入或关联来源'}</dd></div><div><dt>修改草稿</dt><dd>{draft?<button className="text" onClick={()=>view(draft.revisionId)}>查看修改草稿</button>:'暂无'}</dd></div></dl><details><summary>版本与来源依据</summary><dl><dt>当前发布修订</dt><dd>{resource.publishedRevisionId??'尚未发布'}</dd><dt>查看修订</dt><dd>{revision.revisionId}</dd><dt>内容摘要</dt><dd>{revision.digest}</dd><dt>前序修订</dt><dd>{revision.predecessorRevisionId??'未记录前序修订'}</dd></dl>{resource.relationships.length?<pre>{JSON.stringify(resource.relationships,null,2)}</pre>:<p>未记录导入或关联来源，不能据此推断创建来源。</p>}</details></article>
   <article className="f3-detail-card"><h2>内容与维护</h2><div className="f3-detail-actions"><button onClick={()=>select('content')}>查看完整定义</button><button className="text" onClick={()=>maintain(resource.kind==='skill'?'测试':'执行设置')}>{resource.kind==='skill'?'测试与验证':'连接与工具检查'}</button></div></article>
  </div>}
  {section==='content'&&<div role="tabpanel" id="f3-detail-content" aria-label="内容与定义">
   {!showMaintenance&&<article className="f3-detail-card"><h2>{title}</h2><p>{revision.content.description}</p><h2>{resource.kind==='skill'?'办理规则':'连接说明'}</h2><p className="f3-detail-rules">{resource.kind==='skill'?revision.content.instructions||'尚未填写办理规则。':revision.content.endpoint||'当前版本未填写连接地址。'}</p><h2>能力范围</h2><ul>{revision.content.capabilities.map(x=><li key={x}>{labels[x]??x}</li>)}</ul><details><summary>本版本完整定义与准确依据</summary><dl><dt>资源标识</dt><dd>{resource.resourceId}</dd><dt>修订标识</dt><dd>{revision.revisionId}</dd><dt>内容摘要</dt><dd>{revision.digest}</dd></dl><pre>{JSON.stringify(revision.content,null,2)}</pre></details></article>}
   {!showMaintenance&&<article className="f3-detail-card"><h2>验证与维护</h2><p>{draft?'以下维护操作针对当前修改草稿，当前发布内容及历史任务保持原版本。修改后的内容须重新验证。':'以下核对当前发布内容的测试与使用记录；修改会先创建草稿。'}</p><div className="f3-detail-actions"><button onClick={()=>maintain(resource.kind==='skill'?'输入输出':'执行设置')}>{resource.kind==='skill'?'输入输出与执行设置':'连接与工具检查'}</button>{resource.kind==='skill'&&<button onClick={()=>maintain('测试')}>测试与验证</button>}<button onClick={()=>maintain('发布检查')}>发布检查</button><button onClick={()=>maintain('管理')}>资源管理</button></div></article>}
   {showMaintenance&&<div className="f3-inline-maintenance">{operations}</div>}
  </div>}
  {section==='impact'&&<div role="tabpanel" id="f3-detail-impact" aria-label="引用与影响"><article className="f3-detail-card"><h2>引用与变更影响</h2><p>{draft?'以下核对当前修改草稿与已有引用；当前发布内容继续保留。':'以下核对当前发布内容与已有引用。'}已有数字人和任务不会自动改用新版本。</p><ResourceVersionImpact resource={resource} view="使用追溯" onInspectTest={id=>{onInspectTest?.(id);maintain('测试')}}/></article></div>}
  {section==='history'&&<div role="tabpanel" id="f3-detail-history" aria-label="版本记录"><article className="f3-detail-card"><h2>版本记录</h2>{publishedHref&&<Link to={publishedHref}>查看发布版本与使用记录</Link>}<p>选择查看已保存的内容，不修改版本，也不会触发执行。</p><ul className="f3-detail-history-list">{[...resource.revisions].reverse().map(r=><li key={r.revisionId}><div><strong>{r.revisionId===resource.publishedRevisionId?'当前发布内容':r.revisionId===resource.currentDraftRevisionId?'修改草稿':r.state==='PUBLISHED'?'历史发布内容':'历史草稿'}</strong><p>{r.content.description}</p><small>{formatTime(r.createdAt)}</small></div><button onClick={()=>view(r.revisionId)}>查看内容</button></li>)}</ul></article><ResourceVersionImpact resource={resource} view="版本记录" onUpgradeLock={onUpgradeLock} onUpgradeRefresh={onUpgradeRefresh}/></div>}
  {returnHref&&<footer className="f3-detail-directory-fallback"><button className="text" onClick={onBack}>查看资源目录</button></footer>}
 </section>;
}
