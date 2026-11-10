import {useRef,type ReactNode} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import type {SkillMcpResource} from '../api/skillMcpResources';
import {formatTime} from '../journey/formatTime';
import {ResourceVersionImpact} from './ResourceVersionImpact';
import './F3ResourceDetail.css';

const sections=[['overview','概览'],['content','内容与定义'],['impact','引用与影响']] as const;
const labels:Record<string,string>={READ_DATA:'读取资料',VALIDATE_DATA:'核对资料',SUMMARIZE:'汇总信息',ANALYZE_DATA:'分析变化',RENDER_REPORT:'形成报告'};
export function F3ResourceDetail({resource,busy,editor,onBack,onModify,onProfessional}:{resource:SkillMcpResource;busy:boolean;editor:ReactNode;onBack:()=>void;onModify:()=>void;onProfessional:(tab?:string)=>void}){
 const [params,setParams]=useSearchParams(),tabs=useRef<HTMLElement>(null);
 const requested=params.get('resourceSection')??'overview',section=requested==='history'||sections.some(([key])=>key===requested)?requested:'overview';
 const target=params.get('viewRevision')??resource.publishedRevisionId??resource.currentDraftRevisionId;
 const revision=resource.revisions.find(r=>r.revisionId===target),draft=resource.revisions.find(r=>r.revisionId===resource.currentDraftRevisionId);
 const update=(values:Record<string,string|null>)=>setParams(previous=>{const next=new URLSearchParams(previous);for(const [key,value] of Object.entries(values)){if(value===null)next.delete(key);else next.set(key,value)}return next},{replace:true});
 function select(value:string){update({resourceSection:value})}
 if(!revision)return <section className="f3-managed-resource" aria-label="当前资源配置"><button onClick={onBack}>← 返回目录</button><div role="alert" className="f3-detail-card"><h1>当前版本未能核对</h1><p>原版本记录保留；不会改为展示其他修订。</p></div></section>;
 const currentPublished=revision.revisionId===resource.publishedRevisionId,isDraft=revision.revisionId===resource.currentDraftRevisionId,kind=resource.kind==='skill'?'技能':'MCP连接';
 const title=currentPublished?'当前发布内容':isDraft?'修改草稿':'历史内容';
 const view=(id:string)=>update({viewRevision:id,resourceSection:'overview'});
 return <section className="f3-managed-resource" data-resource-kind={resource.kind} aria-label="当前资源配置">
  <button className="f3-detail-back" onClick={onBack}>← 返回目录</button>
  <div className="f3-detail-banner"><span>{title}</span><button onClick={()=>select(section==='history'?'overview':'history')}>{section==='history'?'返回内容':'历史记录'}</button></div>
  <header className="f3-detail-heading"><div><h1>{resource.name}</h1><p>{kind} · {title}{!resource.enabled?' · 已停用':''}</p></div><div className="f3-detail-actions"><button onClick={onBack}>返回来源</button><button className="primary" disabled={busy} onClick={onModify}>{draft?'继续修改草稿':'修改当前发布内容'}</button></div></header>
  {params.get('returnConversation')&&<Link className="f3-detail-conversation-return" to={'/work?'+new URLSearchParams({conversation:params.get('returnConversation')!})}>返回原会话</Link>}
  {section!=='history'&&<nav ref={tabs} className="f3-detail-tabs" role="tablist" aria-label="资源详情导航" onKeyDown={event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const i=sections.findIndex(([key])=>key===section),index=event.key==='Home'?0:event.key==='End'?2:(i+(event.key==='ArrowRight'?1:2))%3;select(sections[index][0]);tabs.current?.querySelectorAll<HTMLButtonElement>('[role=tab]')[index]?.focus()}}>{sections.map(([key,label])=><button key={key} role="tab" tabIndex={section===key?0:-1} aria-selected={section===key} aria-controls={'f3-detail-'+key} onClick={()=>select(key)}>{label}</button>)}</nav>}
  {section==='overview'&&<div role="tabpanel" id="f3-detail-overview" aria-label="概览">
   <article className="f3-detail-card"><h2>用途与交付</h2><p>{revision.content.description||'当前版本尚未填写用途说明。'}</p><dl className="f3-detail-facts"><div><dt>当前发布</dt><dd>{resource.publishedRevisionId?'已有发布内容':'尚未发布'}</dd></div><div><dt>正在查看</dt><dd>{title}</dd></div><div><dt>资源类型</dt><dd>{kind}</dd></div><div><dt>修改草稿</dt><dd>{draft?<button className="text" onClick={()=>view(draft.revisionId)}>查看修改草稿</button>:'暂无'}</dd></div></dl></article>
   <article className="f3-detail-card"><h2>内容与维护</h2><div className="f3-detail-actions"><button onClick={()=>select('content')}>查看完整定义</button><button className="text" onClick={()=>onProfessional()}>查看专业详情</button></div></article>
  </div>}
  {section==='content'&&<div role="tabpanel" id="f3-detail-content" aria-label="内容与定义">
   <article className="f3-detail-card"><h2>用途说明</h2><p>{revision.content.description}</p><h2>{resource.kind==='skill'?'办理规则':'连接说明'}</h2><p className="f3-detail-rules">{resource.kind==='skill'?revision.content.instructions||'尚未填写办理规则。':'连接配置、凭据引用和工具发现记录可在专业详情中查看。'}</p><h2>能力范围</h2><ul>{revision.content.capabilities.map(x=><li key={x}>{labels[x]??x}</li>)}</ul><details><summary>本版本完整定义与准确依据</summary><dl><dt>资源标识</dt><dd>{resource.resourceId}</dd><dt>修订标识</dt><dd>{revision.revisionId}</dd><dt>内容摘要</dt><dd>{revision.digest}</dd></dl><pre>{JSON.stringify(revision.content,null,2)}</pre></details></article>
   {editor&&<article className="f3-detail-card" aria-label="修改当前草稿">{editor}</article>}
   <article className="f3-detail-card"><h2>验证与发布</h2><p>{draft?'修改后的草稿须重新测试和验证。已有员工与任务保留原版本。':'当前没有修改草稿；历史测试与使用记录继续保留。'}</p><div className="f3-detail-actions"><button disabled={busy} onClick={()=>onProfessional(resource.kind==='skill'?'测试':'执行设置')}>{resource.kind==='skill'?'测试与验证':'连接与工具检查'}</button><button disabled={busy} onClick={()=>onProfessional('发布检查')}>发布检查</button></div></article>
  </div>}
  {section==='impact'&&<div role="tabpanel" id="f3-detail-impact" aria-label="引用与影响"><article className="f3-detail-card"><h2>引用与变更影响</h2><p>{draft?'以下核对当前修改草稿与已有引用；当前发布内容继续保留。':'以下核对当前发布内容与已有引用。'}已有数字人和任务不会自动改用新版本。</p><ResourceVersionImpact resource={resource} view="输入输出"/><button onClick={()=>onProfessional('使用追溯')}>查看实际使用与测试记录</button></article></div>}
  {section==='history'&&<article className="f3-detail-card"><h2>历史记录</h2><p>选择查看已保存的内容，不修改版本，也不会触发执行。</p><ul className="f3-detail-history-list">{[...resource.revisions].reverse().map(r=><li key={r.revisionId}><div><strong>{r.revisionId===resource.publishedRevisionId?'当前发布内容':r.revisionId===resource.currentDraftRevisionId?'修改草稿':r.state==='PUBLISHED'?'历史发布内容':'历史草稿'}</strong><p>{r.content.description}</p><small>{formatTime(r.createdAt)}</small></div><button onClick={()=>view(r.revisionId)}>查看内容</button></li>)}</ul></article>}
 </section>;
}
