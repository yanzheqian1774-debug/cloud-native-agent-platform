import {CapabilityEditorRecovery} from './CapabilityEditorRecovery';
import {CapabilityProcessDesign} from './CapabilityProcessDesign';
import {safeBusinessProcessReturn} from '../businessProcesses/businessRelationNavigation';
import {BusinessCapabilityRelations} from '../businessProcesses/BusinessCapabilityRelations';
import {NavigationIcon} from '../components/NavigationIcon';
import {useCapabilityCatalogueScroll} from './useCapabilityCatalogueScroll';
import {useCapabilityCataloguePreferences} from './useCapabilityCataloguePreferences';
import {CapabilityUse} from "./CapabilityUse";
import {capabilityMemberHref} from "./capabilityNavigation";
import {useEffect,useEffectEvent,useLayoutEffect,useRef,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {workbenchPrincipalKey} from '../api/digitalEmployees';
import {capabilitySession,listCapabilities,listCapabilityDomains,readCapability,previewCapability,publishCapability,CapabilityRequestError,type CapabilityDetail,type CapabilityItem,type CapabilityPreview,type CapabilityPublishCommand} from '../api/businessCapabilities';
import './businessCapabilities.css';
import {CapabilityResourceUpdates} from './CapabilityResourceUpdates';
import {CapabilityWorkflowSource} from './CapabilityWorkflowSource';

const fieldNames:Record<string,string>={title:'名称',intent:'业务目标',inputs:'所需资料',outputs:'交付结果',business_scope:'适用范围',business_domain:'业务领域',exclusions:'不包含',manual_involvement:'人工参与',acceptance_criteria:'完成标准',known_limitations:'已知限制',origin:'来源'};
const origins={INDEPENDENT:'直接创建定义',WORKFLOW_REVISION:'来源于执行方案',SAVED_PREPARATION:'来源于已保存的工作准备'};
const kinds:Record<string,string>={EMPLOYEE:'数字人',SKILL:'技能',MCP:'MCP 服务',KNOWLEDGE:'知识',ONTOLOGY:'本体',TOOL:'工具',RUNTIME_PROFILE:'运行环境'};
function failure(error:unknown){
  if(error instanceof CapabilityRequestError){
    if(error.outcomeUnknown)return '提交结果尚未核实。请先读回当前记录；如需重试，将沿用本次提交，不会创建重复发布。';
    if(error.status===401)return '登录已失效，请重新登录后读取。';
    if(error.status===403||error.status===404)return '当前无法读取这项能力或其所需资源，请检查当前账号和使用范围。';
    if(error.code.includes('NOT_PUBLISHED'))return '组成资源尚未全部发布，请先完成资源发布后再预览。';
    if(error.status===409)return '内容或登录身份已变化，请重新读取并核对后操作。';
  }
  return '暂时无法获取能力信息，请稍后重试。';
}
function valueText(value:unknown):string{
  if(value===null||value===undefined)return '无';
  if(Array.isArray(value))return value.map(valueText).join('；');
  if(typeof value==='object'){
    const origin=value as {kind?:keyof typeof origins};
    if(origin.kind&&origin.kind in origins)return origins[origin.kind];
    return JSON.stringify(value);
  }
  return String(value);
}
export function BusinessCapabilitiesPage(){
  const [params,setParams]=useSearchParams();
  const editMode=params.get('edit')==='true';
  const createMode=params.get('create')==='independent'?'independent':params.get('create')==='workflow'?'workflow':null;
  const createRoute=(mode:'independent'|'workflow'|null)=>{const next=new URLSearchParams(params);next.delete('edit');if(mode)next.set('create',mode);else next.delete('create');setParams(next)};
  const [using,setUsing]=useState(false),[useDetail,setUseDetail]=useState<CapabilityDetail|null>(null);
  const [upgrading,setUpgrading]=useState(false);
  const [editing,setEditing]=useState<'independent'|'workflow'|'edit'|null>(null);
  const id=params.get('capability')??'',revision=params.get('revision')??'',expectedDigest=params.get('digest');
  const [items,setItems]=useState<CapabilityItem[]>([]),[cursor,setCursor]=useState<string|null>(null);
  const [detail,setDetail]=useState<CapabilityDetail|null>(null),[preview,setPreview]=useState<CapabilityPreview|null>(null);
  const [principal,setPrincipal]=useState(''),[reason,setReason]=useState('');
  const preferences=useCapabilityCataloguePreferences(principal);
  const {query,domain,layout,favorites,favoritesOnly}=preferences.state;
  const [favoriteCount,setFavoriteCount]=useState<number|null>(null);
  const [domains,setDomains]=useState<string[]>([]),[hasUnassigned,setHasUnassigned]=useState(false),[domainError,setDomainError]=useState('');
  const listGeneration=useRef(0),root=useRef<HTMLElement>(null);
  const restoreCount=useEffectEvent(()=>preferences.state.loadedCount);
  const setQuery=(value:string)=>preferences.update({query:value,scrollTop:0,loadedCount:50});
  const setLayout=(value:'cards'|'list')=>preferences.update({layout:value,scrollTop:0});
  const favorite=(identity:string)=>preferences.update({favorites:favorites.includes(identity)?favorites.filter(item=>item!==identity):[...favorites,identity]});
  const favoriteButton=(identity:string,title:string)=><button className="capability-favorite" disabled={!preferences.ready||!!preferences.error} aria-pressed={favorites.includes(identity)} aria-label={(favorites.includes(identity)?'取消收藏':'收藏')+title} onClick={()=>favorite(identity)}>{favorites.includes(identity)?'★ 已收藏':'☆ 收藏'}</button>;
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[retry,setRetry]=useState(0);
  const [command,setCommand]=useState<CapabilityPublishCommand|null>(null);
  const pending=useRef(false),generation=useRef(0);
  useCapabilityCatalogueScroll(root,!id&&!editing&&!loading&&preferences.ready&&!preferences.error&&!error&&(!favoritesOnly||preferences.favoritesReady),JSON.stringify([principal,query,domain,layout,favoritesOnly]),preferences.state.scrollTop,value=>preferences.update({scrollTop:value}));
  useLayoutEffect(()=>{if(id){const node=root.current?.closest<HTMLElement>('.skill-frame-content');if(node)node.scrollTop=0}},[id]);
  useEffect(()=>{
    let active=true;const controller=new AbortController();const epoch=++generation.current;
    pending.current=false;
    const load=async()=>{
      setUpgrading(false);setUsing(false);setUseDetail(null);setEditing(!id?createMode:editMode?'edit':null);setCommand(null);setLoading(true);setError('');setNotice('');setDetail(null);setPreview(null);setItems([]);setCursor(null);setBusy(false);setReason('');
      try{
        const session=await capabilitySession(controller.signal),key=workbenchPrincipalKey(session);
        if(!active)return;setPrincipal(key);
        if(id&&revision){const value=await readCapability(id,revision,key,controller.signal);if(value.revision.capability_id!==id||value.revision.revision_id!==revision||(expectedDigest!==null&&value.digest!==expectedDigest))throw new CapabilityRequestError('CAPABILITY_REFERENCE_MISMATCH',409);if(active)setDetail(value)}

      }catch(cause){if(active){setError(failure(cause));setLoading(false)}}finally{if(active&&id)setLoading(false)}
    };
    const expire=()=>{active=false;controller.abort();generation.current=epoch+1;setEditing(null);setUseDetail(null);setUsing(false);setDetail(null);setItems([]);setPreview(null);setPrincipal('');setBusy(false);setLoading(false);setError('登录已失效，请重新登录后读取。')};
    window.addEventListener('workbench-session-expired',expire);void load();
    return()=>{active=false;controller.abort();generation.current++;window.removeEventListener('workbench-session-expired',expire)};
  },[id,revision,expectedDigest,retry,createMode,editMode]);
  useEffect(()=>{
    if(!principal||id||!preferences.ready||preferences.error||(favoritesOnly&&!preferences.favoritesReady))return;
    const controller=new AbortController(),epoch=++listGeneration.current;
    const load=async()=>{
      setLoading(true);setError('');setItems([]);setCursor(null);
      try{await new Promise(resolve=>window.setTimeout(resolve,180));if(controller.signal.aborted)return;const wanted=restoreCount(),signal=AbortSignal.any([controller.signal,AbortSignal.timeout(30_000)]),seen=new Set<string>();let next:string|null=null;const restored:CapabilityItem[]=[];
        do{const page=await listCapabilities(principal,next,signal,{query,domain,favoritesOnly});restored.push(...page.items);next=page.nextCursor;if(next&&seen.has(next))throw new CapabilityRequestError('CAPABILITY_PAGE_REPEATED',503);if(next)seen.add(next)}while(next&&restored.length<wanted);
        if(epoch===listGeneration.current&&!signal.aborted){setItems(restored);setCursor(next)}}
      catch(cause){if(!controller.signal.aborted&&epoch===listGeneration.current)setError(failure(cause))}
      finally{if(!controller.signal.aborted&&epoch===listGeneration.current)setLoading(false)}
    };
    void load();return()=>{controller.abort();listGeneration.current=epoch+1};
  },[principal,id,createMode,query,domain,favoritesOnly,preferences.ready,preferences.error,preferences.favoritesReady,retry]);
  useEffect(()=>{
    if(!principal||!preferences.ready||!preferences.favoritesReady)return;
    const controller=new AbortController();
    const load=async()=>{setDomains([]);setHasUnassigned(false);setFavoriteCount(null);setDomainError('');try{const value=await listCapabilityDomains(principal,controller.signal);if(!controller.signal.aborted){if(!Array.isArray(value.domains))throw Error('Invalid domains');setDomains(value.domains);setHasUnassigned(value.hasUnassigned);setFavoriteCount(Number.isInteger(value.readableFavoriteCount)&&value.readableFavoriteCount>=0?value.readableFavoriteCount:null)}}catch{if(!controller.signal.aborted)setDomainError('业务领域暂时无法读取，请重新读取目录。')}};
    void load();return()=>controller.abort();
  },[principal,retry,id,preferences.ready,preferences.favoritesReady]);
  const choose=(capability:string,version:string)=>{const next=new URLSearchParams(params);next.delete('create');next.delete('edit');next.set('capability',capability);next.set('revision',version);next.delete('digest');setParams(next)};
  const back=()=>{const next=new URLSearchParams(params);next.delete('edit');next.delete('capability');next.delete('revision');next.delete('digest');setParams(next)};
  const perform=async(action:()=>Promise<void>)=>{
    if(pending.current)return;pending.current=true;setBusy(true);setError('');const epoch=generation.current;
    try{await action()}catch(cause){if(epoch===generation.current)setError(failure(cause))}finally{if(epoch===generation.current){pending.current=false;setBusy(false)}}
  };
  const loadMore=()=>{const epoch=listGeneration.current;void perform(async()=>{const value=await listCapabilities(principal,cursor,undefined,{query,domain,favoritesOnly});if(epoch!==listGeneration.current)return;setItems(old=>[...old,...value.items]);setCursor(value.nextCursor);preferences.update({loadedCount:Math.min(10_000,items.length+value.items.length)})})};
  const review=()=>{const epoch=generation.current;void perform(async()=>{const value=await previewCapability(id,revision,principal);if(epoch!==generation.current)return;setPreview(value);setCommand(null);setNotice('')})};
  const publish=()=>{const epoch=generation.current;void perform(async()=>{
    if(!preview)return;
    const submitted=command??{expectedVersion:preview.aggregateVersion,digest:preview.revisionDigest,impactDigest:preview.impactDigest,commandId:`capability-publish:${crypto.randomUUID()}`,reason:reason.trim()};
    setCommand(submitted);
    await publishCapability(id,revision,submitted,principal);
    const value=await readCapability(id,revision,principal);
    if(epoch!==generation.current)return;setDetail(value);setPreview(null);setCommand(null);setNotice('已发布。历史工作继续保留原有引用，新工作仍需核对执行条件。');
  })};
  const visibleItems=items.filter(item=>(!favoritesOnly||favorites.includes(item.capabilityId))&&(!domain||(item.businessDomain??'__UNASSIGNED__')===domain)&&`${item.title} ${item.intent} ${item.employeeResponsibilities?.join(' ')??''}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
  const openUse=(item:CapabilityItem)=>{const epoch=generation.current;void perform(async()=>{
    const value=await readCapability(item.capabilityId,item.revisionId,principal);
    if(epoch!==generation.current)return;
    if(value.digest!==item.digest||value.state!=='PUBLISHED')throw new CapabilityRequestError('CAPABILITY_REFERENCE_MISMATCH',409);
    setUseDetail(value);setUsing(true);setEditing(null);
    root.current?.closest<HTMLElement>('.skill-frame-content')?.scrollTo({top:0});
  })};
  const renderUseButton=(item:CapabilityItem)=>item.currentPublished?<button className="capability-primary" disabled={busy} onClick={()=>openUse(item)}>在会话中使用</button>:<span className="capability-use-unavailable">发布后可使用</span>;
  const employeeLabel=(item:CapabilityItem)=>[...(item.employeeNames??[]),...(item.employeeNamesUnavailable?['部分名称当前不可读取']:[])].join('；')||'名称尚未读回';
  const versionInfo=(item:CapabilityItem)=><details className="capability-version"><summary>查看版本</summary><span>{item.revisionId}</span></details>;
  const activeUseDetail=useDetail??detail;
  const current=detail?.revision;
  const businessProcessReturn=safeBusinessProcessReturn(params.get('businessProcessReturn'));
  const memberName=(binding:import('../api/businessCapabilities').CapabilityBinding)=>detail?.members?.find(item=>item.kind===binding.kind&&item.resourceId===binding.reference.resource_id&&item.revisionId===binding.reference.revision_id&&item.digest===binding.reference.digest)?.name??'名称尚未读回';
  if(params.has('processDesign')&&principal&&!id)return <CapabilityProcessDesign key={principal+params.get('processDesign')} source={params.get('processDesign')!} principal={principal}/>;
  return <main ref={root} className="f3-capabilities">
    <header><div><p className="eyebrow">BUSINESS CAPABILITIES</p><h1>{current?.title??'业务能力'}</h1><p>{current?'核对本版本的分工、资源与交付范围。':'按目标查找能力，使用前核对当前版本。'}</p></div>{id?<div className="capability-actions"><button onClick={back}>返回业务能力</button>{detail?.state==='PUBLISHED'&&<button className="capability-primary" onClick={()=>{setUpgrading(false);setEditing(null);setUsing(true)}}>在会话中使用</button>}</div>:<div className="capability-actions"><button disabled={!principal||loading} onClick={()=>{setEditing('independent');createRoute('independent')}}>创建独立能力</button><button disabled={!principal||loading} onClick={()=>{setEditing('workflow');createRoute('workflow')}}>从执行方案设计能力</button></div>}</header>
    {loading&&!preferences.error&&<p role="status">正在读取业务能力…</p>}
    {error&&<section role="alert" className="capability-notice"><p>{error}</p><button disabled={busy} onClick={()=>setRetry(n=>n+1)}>重新读取</button></section>}
    {domainError&&<p role="alert">{domainError}<button onClick={()=>setRetry(n=>n+1)}>重新读取目录</button></p>}
    {notice&&<p role="status" className="capability-notice">{notice}</p>}
    <>{preferences.error&&<section role="alert" className="capability-notice"><p>{preferences.error}</p><button onClick={preferences.reload}>重新读取目录设置</button></section>}<p className="capability-preference-status" aria-live="polite">{preferences.saving?'正在保存目录设置…':''}</p></>
    {using&&activeUseDetail&&<CapabilityUse key={activeUseDetail.revision.capability_id+activeUseDetail.revision.revision_id} detail={activeUseDetail} principal={principal} conversation={params.get('returnConversation')} onCancel={()=>{setUsing(false);setUseDetail(null)}}/>}
    {upgrading&&detail&&<CapabilityResourceUpdates detail={detail} principal={principal} onSaved={value=>{setUpgrading(false);choose(value.revision.capability_id,value.revision.revision_id)}} onCancel={()=>setUpgrading(false)}/>}
    {editing&&principal&&(editing!=='edit'||(!loading&&detail))&&<CapabilityEditorRecovery key={`${principal}:${editing}:${id}:${revision}:${detail?.digest??''}`} base={editing==='edit'?detail??undefined:undefined} principal={principal} fromWorkflow={editing==='workflow'} onCancel={()=>{setEditing(null);createRoute(null)}} onSaved={value=>{setEditing(null);choose(value.revision.capability_id,value.revision.revision_id)}}/>}
    {!using&&!editing&&!id&&preferences.ready&&<><label className="capability-domain">业务领域<select aria-label="业务领域" disabled={!preferences.ready||!!preferences.error} value={domain} onChange={event=>preferences.update({domain:event.target.value,scrollTop:0,loadedCount:50})}><option value="">全部领域</option>{hasUnassigned&&<option value="__UNASSIGNED__">未设置</option>}{domains.map(value=><option key={value} value={value}>{value}</option>)}{domain&&domain!=='__UNASSIGNED__'&&!domains.includes(domain)&&<option value={domain}>{domain}（当前无可读能力）</option>}</select></label><div className="capability-filter-row"><label className="capability-search"><span className="capability-search-label">搜索业务能力</span><input aria-label="搜索业务能力" maxLength={500} disabled={!preferences.ready||!!preferences.error} value={query} onChange={event=>setQuery(event.target.value)} placeholder="想完成什么？例如交付诊断、经营分析"/></label><div className="capability-layout" role="group" aria-label="能力展示方式"><button disabled={!preferences.ready||!!preferences.error} aria-pressed={!favoritesOnly} onClick={()=>preferences.update({favoritesOnly:false,scrollTop:0,loadedCount:50})}>全部能力</button><button disabled={!preferences.ready||!!preferences.error} aria-label="我的收藏" title="当前可读取的全部收藏，不受关键词和分页影响" aria-pressed={favoritesOnly} onClick={()=>preferences.update({favoritesOnly:true,scrollTop:0,loadedCount:50})}>我的收藏（{preferences.favoritesReady&&favoriteCount!==null?favoriteCount:'…'}）</button><button disabled={!preferences.ready||!!preferences.error} aria-pressed={layout==='cards'} onClick={()=>setLayout('cards')}>卡片</button><button disabled={!preferences.ready||!!preferences.error} aria-pressed={layout==='list'} onClick={()=>setLayout('list')}>列表</button></div></div>{layout==='cards'?<div className="capability-grid">{visibleItems.map(item=><article className="capability-panel" key={item.capabilityId}><div className="capability-card-top"><span className="capability-package-icon"><NavigationIcon name="agent"/></span><span className="capability-badge" data-state={item.currentPublished?'PUBLISHED':'DRAFT'}>{item.currentPublished?'已发布':'草稿'}</span>{favoriteButton(item.capabilityId,item.title)}</div><h2><button className="capability-title" onClick={()=>choose(item.capabilityId,item.revisionId)}>{item.title}</button></h2><p>{item.intent}</p><dl className="capability-card-facts"><div><dt>输入</dt><dd>{item.inputs??'尚未读回'}</dd></div><div><dt>产出</dt><dd>{item.outputs??'尚未读回'}</dd></div><div><dt>承担数字人</dt><dd><span>{employeeLabel(item)}</span><small className="capability-responsibility">{item.employeeResponsibilities?.join('；')??'查看固定分工'}</small></dd></div><div><dt>使用边界</dt><dd>{item.exclusions??'查看详情'}</dd></div></dl><div className="capability-card-meta">{item.originKind&&<span className="capability-badge">{origins[item.originKind]}</span>}<span className="capability-badge">{item.businessDomain??'未设置领域'}</span>{versionInfo(item)}</div><div className="capability-actions capability-card-actions"><button className="capability-detail-link" onClick={()=>choose(item.capabilityId,item.revisionId)}>查看详情</button>{renderUseButton(item)}{item.currentDraft&&item.currentPublished&&<button onClick={()=>choose(item.capabilityId,item.currentDraft!.revisionId)}>查看修改草稿</button>}</div></article>)}</div>:<div className="capability-catalogue-table"><table><thead><tr><th>能力与用途</th><th>状态 / 来源</th><th>输入与产出</th><th>职责与边界</th><th>操作</th></tr></thead><tbody>{visibleItems.map(item=><tr key={item.capabilityId}><td><button className="capability-title" onClick={()=>choose(item.capabilityId,item.revisionId)}>{item.title}</button><p>{item.intent}</p></td><td><span className="capability-badge">{item.businessDomain??'未设置领域'}</span><span className="capability-badge" data-state={item.currentPublished?'PUBLISHED':'DRAFT'}>{item.currentPublished?'已发布':'草稿'}</span>{versionInfo(item)}{item.originKind&&<p>{origins[item.originKind]}</p>}</td><td><dl><div><dt>输入</dt><dd>{item.inputs??'尚未读回'}</dd></div><div><dt>产出</dt><dd>{item.outputs??'尚未读回'}</dd></div></dl></td><td><dl><div><dt>承担数字人</dt><dd>{employeeLabel(item)}</dd></div><div><dt>承担职责</dt><dd>{item.employeeResponsibilities?.join('；')??'查看固定分工'}</dd></div><div><dt>使用边界</dt><dd>{item.exclusions??'查看详情'}</dd></div></dl></td><td><div className="capability-actions">{favoriteButton(item.capabilityId,item.title)}{renderUseButton(item)}<button onClick={()=>choose(item.capabilityId,item.revisionId)}>查看详情</button>{item.currentDraft&&item.currentPublished&&<button onClick={()=>choose(item.capabilityId,item.currentDraft!.revisionId)}>查看修改草稿</button>}</div></td></tr>)}</tbody></table></div>}{!loading&&!visibleItems.length&&(!!query.trim()||!!domain||favoritesOnly)&&!error&&<p role="status" className="capability-notice">没有匹配的可读能力。请调整关键词、业务领域或收藏筛选。</p>}{!loading&&!items.length&&!query.trim()&&!domain&&!favoritesOnly&&!error&&<section className="capability-panel"><h2>暂无可读取的业务能力</h2><p>保存的能力将在这里显示，目录不会用演示数据替代真实记录。</p></section>}{cursor&&<button disabled={busy||loading||items.length>=10_000||(favoritesOnly&&!preferences.favoritesReady)} onClick={loadMore}>加载更多</button>}{items.length>=10_000&&<p>已展示一万项能力，请缩小筛选范围后继续查找。</p>}</>}
    {!using&&!editing&&!upgrading&&current&&detail&&<>
      <div className="capability-actions">{favoriteButton(current.capability_id,current.title)}<span className="capability-badge">{origins[current.origin.kind]}</span><span className="capability-badge">{detail.state==='PUBLISHED'?'已发布定义':'修改草稿'}</span></div>
      <section className="capability-panel"><h2>本版本固定的分工与资源</h2><div className="capability-fixed-table"><table><thead><tr><th>绑定项</th><th>本次采用内容</th></tr></thead><tbody><tr><th>业务目标</th><td>{current.intent}</td></tr>{current.bindings.map(binding=><tr key={`${binding.kind}:${binding.reference.resource_id}`}><th>{kinds[binding.kind]}</th><td>{capabilityMemberHref(binding,detail,params.get('returnConversation'),params.get('returnHome')==='1')&&<Link to={capabilityMemberHref(binding,detail,params.get('returnConversation'),params.get('returnHome')==='1')!}>{memberName(binding)}</Link>}<p>{binding.purpose}</p><details><summary>查看版本依据</summary><dl><div><dt>资源</dt><dd>{binding.reference.resource_id}</dd></div><div><dt>版本</dt><dd>{binding.reference.revision_id}</dd></div><div><dt>内容标识</dt><dd>{binding.reference.digest}</dd></div></dl></details></td></tr>)}</tbody></table></div><h3>版本更新</h3><button onClick={()=>setUpgrading(true)}>检查资源更新</button><p>历史会话与任务保留启动时的固定引用。修改本能力不会改写已有工作。</p></section>
      {current.origin.kind==='WORKFLOW_REVISION'&&current.origin.workflow&&<CapabilityWorkflowSource key={`${current.capability_id}:${current.revision_id}:${principal}`} reference={current.origin.workflow} principal={principal}/>}
      {import.meta.env.VITE_BUSINESS_PROCESS_DEFINITIONS_ENABLED==='true'&&<BusinessCapabilityRelations side="CAPABILITY" reference={{resource_id:current.capability_id,revision_id:current.revision_id,digest:detail.digest}} principal={principal}/>}
      <section className="capability-panel"><h2>输入输出与人工边界</h2><p>业务领域：{current.business_domain??'未设置'}</p><dl>{([['inputs','必需输入'],['outputs','交付内容'],['manual_involvement','人工参与'],['business_scope','适用范围'],['exclusions','不包含'],['known_limitations','当前限制']] as const).map(([field,label])=><div key={field}><dt>{label}</dt><dd>{current[field]}</dd></div>)}</dl><h3>完成标准</h3><ul>{current.acceptance_criteria.map(item=><li key={item}>{item}</li>)}</ul></section>
      <section className="capability-panel"><details><summary>查看数字人与资源组成</summary>{current.bindings.map(binding=><div className="capability-binding" key={`${binding.kind}:${binding.reference.resource_id}`}><h3>{kinds[binding.kind]}</h3>{capabilityMemberHref(binding,detail,params.get('returnConversation'),params.get('returnHome')==='1')&&<Link to={capabilityMemberHref(binding,detail,params.get('returnConversation'),params.get('returnHome')==='1')!}>{memberName(binding)}</Link>}<p>{binding.purpose}</p><details><summary>查看固定引用</summary><dl><div><dt>资源</dt><dd>{binding.reference.resource_id}</dd></div><div><dt>版本</dt><dd>{binding.reference.revision_id}</dd></div><div><dt>内容标识</dt><dd>{binding.reference.digest}</dd></div></dl></details></div>)}</details><p>发布检查核对定义和固定资源；实际执行结果以对应工作记录为准。</p></section>
      {detail.headRevisionId===current.revision_id&&<button disabled={busy} onClick={()=>{setPreview(null);const next=new URLSearchParams(params);next.set('edit','true');setParams(next)}}>修改能力</button>}
      {detail.state!=='PUBLISHED'&&detail.headRevisionId===current.revision_id&&<button disabled={busy} onClick={review}>查看变更与发布影响</button>}
      {detail.currentDraftRevisionId&&detail.currentDraftRevisionId!==current.revision_id&&<button onClick={()=>choose(id,detail.currentDraftRevisionId!)}>查看当前修改草稿</button>}
      {preview&&<section className="capability-panel" aria-label="发布变更确认"><h2>本次变更与影响</h2><p>仅发布当前能力定义。历史会话、既有任务及其资源引用保持原样。</p>{preview.fieldChanges.map(change=><div className="capability-change" key={change.field}><h3>{fieldNames[change.field]??change.field}</h3><p>原内容：{valueText(change.before)}</p><p>新内容：{valueText(change.after)}</p></div>)}{preview.bindingChanges.map(change=><div className="capability-change" key={`${change.kind}:${change.resourceId}`}><h3>{kinds[change.kind]} · {change.after?change.before?'调整引用':'新增引用':'移除引用'}</h3><p>{change.after?.purpose??change.before?.purpose}</p><details><summary>核对资源变化</summary><pre>{JSON.stringify({before:change.before,after:change.after},null,2)}</pre></details></div>)}<label>发布说明<textarea maxLength={1000} value={reason} disabled={busy||command!==null} onChange={event=>setReason(event.target.value)}/></label><div className="capability-actions"><button disabled={busy||!reason.trim()} onClick={publish}>{busy?'正在处理…':command?'核实并重试本次发布':'确认并发布'}</button><button disabled={busy} onClick={()=>{setPreview(null);setCommand(null)}}>关闭预览</button></div></section>}
    </>}
    {businessProcessReturn&&<Link to={businessProcessReturn}>返回流程活动</Link>}
    {params.get('returnHome')==='1'&&<Link to="/dashboard">返回工作台</Link>}
    {params.get('returnConversation')&&<Link to={'/work?'+new URLSearchParams({conversation:params.get('returnConversation')!})}>返回原会话</Link>}
  </main>;
}
