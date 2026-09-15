import {useMemo,useState} from "react";
import type {ResourceKind,SkillMcpResource} from "../api/skillMcpResources";

type DirectoryView="cards"|"compact";
const pageSize=6;

export function CapabilityCenterDirectory({kind,items,loading,busy,query,lifecycle,selectedId,onQueryChange,onLifecycleChange,onSelect,onCreate}:{
  kind:ResourceKind;
  items:SkillMcpResource[];
  loading:boolean;
  busy:boolean;
  query:string;
  lifecycle:string;
  selectedId?:string;
  onQueryChange:(value:string)=>void;
  onLifecycleChange:(value:string)=>void;
  onSelect:(resourceId:string)=>void;
  onCreate:()=>void;
}){
  const [view,setView]=useState<DirectoryView>("cards");
  const [page,setPage]=useState(1);
  const filtered=useMemo(()=>{
    const normalized=query.trim().toLocaleLowerCase("zh-CN");
    return items.filter(item=>{
      if(lifecycle!=="ALL"&&item.lifecycleState!==lifecycle)return false;
      if(!normalized)return true;
      const revision=item.revisions.find(candidate=>candidate.revisionId===item.currentDraftRevisionId)
        ??item.revisions.find(candidate=>candidate.revisionId===item.publishedRevisionId)
        ??item.revisions.at(-1);
      const searchable=[item.name,item.resourceId,revision?.content.description,...(revision?.content.capabilities??[])].join(" ").toLocaleLowerCase("zh-CN");
      return searchable.includes(normalized);
    });
  },[items,lifecycle,query]);
  const ordered=useMemo(()=>{
    const selected=filtered.find(item=>item.resourceId===selectedId);
    return selected?[selected,...filtered.filter(item=>item.resourceId!==selectedId)]:filtered;
  },[filtered,selectedId]);
  const pageCount=Math.max(1,Math.ceil(ordered.length/pageSize));
  const currentPage=Math.min(page,pageCount);
  const pageItems=ordered.slice((currentPage-1)*pageSize,currentPage*pageSize);

  return <aside className="capability-directory" aria-label={`${kind.toUpperCase()} 能力目录`}>
    <div className="agent-list-heading"><div><p className="eyebrow">能力目录</p><h2>{kind==="skill"?"Skills":"MCP servers"}</h2></div><button className="primary" onClick={onCreate} disabled={busy||loading}>Create governed {kind.toUpperCase()}</button></div>
    <div className="capability-directory-controls">
      <label>搜索能力<input aria-label="Search catalog" value={query} onChange={event=>{setPage(1);onQueryChange(event.target.value)}} placeholder="中文名称、说明、能力或规范 ID"/></label>
      <label>状态筛选<select aria-label="Lifecycle filter" value={lifecycle} onChange={event=>{setPage(1);onLifecycleChange(event.target.value)}}><option value="ALL">全部状态</option><option value="DRAFT">DRAFT</option><option value="VALIDATED">VALIDATED</option><option value="HUMAN_REVIEWED">HUMAN_REVIEWED</option><option value="PUBLISHED">PUBLISHED</option><option value="DEPRECATED">DEPRECATED</option></select></label>
      <div className="capability-view-switch" role="group" aria-label="目录显示方式"><button type="button" aria-pressed={view==="cards"} onClick={()=>setView("cards")}>卡片</button><button type="button" aria-pressed={view==="compact"} onClick={()=>setView("compact")}>紧凑列表</button></div>
    </div>
    <p className="capability-directory-summary" aria-live="polite">当前完整响应共 {items.length} 项，筛选后 {filtered.length} 项</p>
    {!loading&&filtered.length===0?<div className="agent-empty"><h3>没有匹配的能力资源</h3><p>可清除搜索或状态筛选；新建资源只会创建 Draft。</p></div>:<ul className={`agent-list capability-directory-list view-${view}`}>{pageItems.map(item=>{
      const revision=item.revisions.find(candidate=>candidate.revisionId===item.currentDraftRevisionId)??item.revisions.find(candidate=>candidate.revisionId===item.publishedRevisionId)??item.revisions.at(-1);
      return <li key={item.resourceId}><button className={selectedId===item.resourceId?"selected":""} aria-current={selectedId===item.resourceId?"true":undefined} onClick={()=>onSelect(item.resourceId)}><span className={`agent-status status-${item.lifecycleState.toLowerCase()}`}>{item.lifecycleState}</span><strong>{item.name}</strong><span className="capability-directory-description">{revision?.content.description||"暂无说明"}</span><small><code>{revision?.revisionId??"NO_REVISION"}</code> · Aggregate v{item.aggregateVersion}</small></button></li>;
    })}</ul>}
    {filtered.length>pageSize&&<nav className="capability-pagination" aria-label="能力目录分页"><button type="button" disabled={currentPage===1} onClick={()=>setPage(current=>current-1)}>上一页</button><span>第 {currentPage} / {pageCount} 页</span><button type="button" disabled={currentPage===pageCount} onClick={()=>setPage(current=>current+1)}>下一页</button></nav>}
  </aside>;
}
