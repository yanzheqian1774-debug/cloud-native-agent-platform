import {CapabilityUse} from "./CapabilityUse";
import {capabilityMemberHref} from "./capabilityNavigation";
import {useEffect,useRef,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {workbenchPrincipalKey} from '../api/digitalEmployees';
import {capabilitySession,listCapabilities,readCapability,previewCapability,publishCapability,CapabilityRequestError,type CapabilityDetail,type CapabilityItem,type CapabilityPreview,type CapabilityPublishCommand} from '../api/businessCapabilities';
import './businessCapabilities.css';
import {CapabilityEditor} from './CapabilityEditor';

const fieldNames:Record<string,string>={title:'名称',intent:'业务目标',inputs:'所需资料',outputs:'交付结果',business_scope:'适用范围',exclusions:'不包含',manual_involvement:'人工参与',acceptance_criteria:'完成标准',known_limitations:'已知限制',origin:'来源'};
const origins={INDEPENDENT:'独立设计',WORKFLOW_REVISION:'来源于业务流程',SAVED_PREPARATION:'来源于已保存的工作准备'};
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
  const [using,setUsing]=useState(false);
  const [editing,setEditing]=useState<'independent'|'workflow'|'edit'|null>(null);
  const id=params.get('capability')??'',revision=params.get('revision')??'',expectedDigest=params.get('digest');
  const [items,setItems]=useState<CapabilityItem[]>([]),[cursor,setCursor]=useState<string|null>(null);
  const [detail,setDetail]=useState<CapabilityDetail|null>(null),[preview,setPreview]=useState<CapabilityPreview|null>(null);
  const [principal,setPrincipal]=useState(''),[query,setQuery]=useState(''),[reason,setReason]=useState('');
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[retry,setRetry]=useState(0);
  const [command,setCommand]=useState<CapabilityPublishCommand|null>(null);
  const pending=useRef(false),generation=useRef(0);
  useEffect(()=>{
    let active=true;const controller=new AbortController();const epoch=++generation.current;
    pending.current=false;
    const load=async()=>{
      setUsing(false);setEditing(null);setCommand(null);setLoading(true);setError('');setNotice('');setDetail(null);setPreview(null);setItems([]);setCursor(null);setBusy(false);setReason('');
      try{
        const session=await capabilitySession(controller.signal),key=workbenchPrincipalKey(session);
        if(!active)return;setPrincipal(key);
        if(id&&revision){const value=await readCapability(id,revision,key,controller.signal);if(expectedDigest&&value.digest!==expectedDigest)throw new CapabilityRequestError('CAPABILITY_REFERENCE_MISMATCH',409);if(active)setDetail(value)}
        else{const value=await listCapabilities(key,null,controller.signal);if(active){setItems(value.items);setCursor(value.nextCursor)}}
      }catch(cause){if(active)setError(failure(cause))}finally{if(active)setLoading(false)}
    };
    const expire=()=>{active=false;controller.abort();generation.current=epoch+1;setEditing(null);setDetail(null);setItems([]);setPreview(null);setPrincipal('');setBusy(false);setLoading(false);setError('登录已失效，请重新登录后读取。')};
    window.addEventListener('workbench-session-expired',expire);void load();
    return()=>{active=false;controller.abort();generation.current++;window.removeEventListener('workbench-session-expired',expire)};
  },[id,revision,expectedDigest,retry]);
  const choose=(capability:string,version:string)=>{const next=new URLSearchParams(params);next.set('capability',capability);next.set('revision',version);next.delete('digest');setParams(next)};
  const back=()=>{const next=new URLSearchParams(params);next.delete('capability');next.delete('revision');next.delete('digest');setParams(next)};
  const perform=async(action:()=>Promise<void>)=>{
    if(pending.current)return;pending.current=true;setBusy(true);setError('');const epoch=generation.current;
    try{await action()}catch(cause){if(epoch===generation.current)setError(failure(cause))}finally{if(epoch===generation.current){pending.current=false;setBusy(false)}}
  };
  const loadMore=()=>{const epoch=generation.current;void perform(async()=>{const value=await listCapabilities(principal,cursor);if(epoch!==generation.current)return;setItems(old=>[...old,...value.items]);setCursor(value.nextCursor)})};
  const review=()=>{const epoch=generation.current;void perform(async()=>{const value=await previewCapability(id,revision,principal);if(epoch!==generation.current)return;setPreview(value);setCommand(null);setNotice('')})};
  const publish=()=>{const epoch=generation.current;void perform(async()=>{
    if(!preview)return;
    const submitted=command??{expectedVersion:preview.aggregateVersion,digest:preview.revisionDigest,impactDigest:preview.impactDigest,commandId:`capability-publish:${crypto.randomUUID()}`,reason:reason.trim()};
    setCommand(submitted);
    await publishCapability(id,revision,submitted,principal);
    const value=await readCapability(id,revision,principal);
    if(epoch!==generation.current)return;setDetail(value);setPreview(null);setCommand(null);setNotice('已发布。历史工作继续保留原有引用，新工作仍需核对执行条件。');
  })};
  const current=detail?.revision;
  const memberName=(binding:import('../api/businessCapabilities').CapabilityBinding)=>detail?.members?.find(item=>item.kind===binding.kind&&item.resourceId===binding.reference.resource_id&&item.revisionId===binding.reference.revision_id&&item.digest===binding.reference.digest)?.name??'名称尚未读回';
  return <main className="f3-capabilities">
    <header><div><p className="eyebrow">BUSINESS CAPABILITIES</p><h1>{current?.title??'业务能力'}</h1><p>{current?'核对本版本的分工、资源与交付范围。':'按目标查找能力，使用前核对当前版本。'}</p></div>{id?<div className="capability-actions"><button onClick={back}>返回业务能力</button>{detail?.state==='PUBLISHED'&&<button className="capability-primary" onClick={()=>{setEditing(null);setUsing(true)}}>在会话中使用</button>}</div>:<div className="capability-actions"><button disabled={!principal||loading} onClick={()=>setEditing('independent')}>创建独立能力</button><button disabled={!principal||loading} onClick={()=>setEditing('workflow')}>从流程设计能力</button></div>}</header>
    {loading&&<p role="status">正在读取业务能力…</p>}
    {error&&<section role="alert" className="capability-notice"><p>{error}</p><button disabled={busy} onClick={()=>setRetry(n=>n+1)}>重新读取</button></section>}
    {notice&&<p role="status" className="capability-notice">{notice}</p>}
    {using&&detail&&<CapabilityUse key={id+revision} detail={detail} principal={principal} conversation={params.get('returnConversation')} onCancel={()=>setUsing(false)}/>}
    {editing&&<CapabilityEditor key={`${id}:${revision}:${editing}`} base={editing==='edit'?detail??undefined:undefined} principal={principal} fromWorkflow={editing==='workflow'} onCancel={()=>setEditing(null)} onSaved={value=>{setEditing(null);choose(value.revision.capability_id,value.revision.revision_id)}}/>}
    {!editing&&!id&&!loading&&<><label className="capability-search">搜索业务能力<input value={query} onChange={event=>setQuery(event.target.value)} placeholder="想完成什么？例如交付诊断、经营分析"/></label><div className="capability-grid">{items.filter(item=>`${item.title} ${item.intent}`.toLowerCase().includes(query.toLowerCase())).map(item=><article className="capability-panel" key={item.capabilityId}><span className="capability-badge">{item.currentPublished?'已发布':'草稿'}</span><h2><button className="capability-title" onClick={()=>choose(item.capabilityId,item.revisionId)}>{item.title}</button></h2><p>{item.intent}</p><dl className="capability-card-facts"><div><dt>输入</dt><dd>{item.inputs??'尚未读回'}</dd></div><div><dt>产出</dt><dd>{item.outputs??'尚未读回'}</dd></div><div><dt>承担职责</dt><dd>{item.employeeResponsibilities?.join('；')??'查看固定分工'}</dd></div><div><dt>使用边界</dt><dd>{item.exclusions??'查看详情'}</dd></div></dl>{item.originKind&&<p>{origins[item.originKind]}</p>}<div className="capability-actions"><button onClick={()=>choose(item.capabilityId,item.revisionId)}>查看详情</button>{item.currentDraft&&item.currentPublished&&<button onClick={()=>choose(item.capabilityId,item.currentDraft!.revisionId)}>查看修改草稿</button>}</div></article>)}</div>{!items.length&&!error&&<section className="capability-panel"><h2>暂无可读取的业务能力</h2><p>保存的能力将在这里显示，目录不会用演示数据替代真实记录。</p></section>}{cursor&&<button disabled={busy} onClick={loadMore}>加载更多</button>}</>}
    {!using&&!editing&&current&&detail&&<>
      <div className="capability-actions"><span className="capability-badge">{origins[current.origin.kind]}</span><span className="capability-badge">{detail.state==='PUBLISHED'?'已发布定义':'修改草稿'}</span></div>
      <section className="capability-panel"><h2>本版本固定的分工与资源</h2><div className="capability-fixed-table"><table><thead><tr><th>绑定项</th><th>本次采用内容</th></tr></thead><tbody><tr><th>业务目标</th><td>{current.intent}</td></tr>{current.bindings.map(binding=><tr key={`${binding.kind}:${binding.reference.resource_id}`}><th>{kinds[binding.kind]}</th><td>{capabilityMemberHref(binding,detail,params.get('returnConversation'))&&<Link to={capabilityMemberHref(binding,detail,params.get('returnConversation'))!}>{memberName(binding)}</Link>}<p>{binding.purpose}</p><details><summary>查看版本依据</summary><dl><div><dt>资源</dt><dd>{binding.reference.resource_id}</dd></div><div><dt>版本</dt><dd>{binding.reference.revision_id}</dd></div><div><dt>内容标识</dt><dd>{binding.reference.digest}</dd></div></dl></details></td></tr>)}</tbody></table></div><h3>版本更新</h3><p>历史会话与任务保留启动时的固定引用。修改本能力不会改写已有工作。</p></section>
      <section className="capability-panel"><h2>输入输出与人工边界</h2><dl>{([['inputs','必需输入'],['outputs','交付内容'],['manual_involvement','人工参与'],['business_scope','适用范围'],['exclusions','不包含'],['known_limitations','当前限制']] as const).map(([field,label])=><div key={field}><dt>{label}</dt><dd>{current[field]}</dd></div>)}</dl><h3>完成标准</h3><ul>{current.acceptance_criteria.map(item=><li key={item}>{item}</li>)}</ul></section>
      <section className="capability-panel"><details><summary>查看数字人与资源组成</summary>{current.bindings.map(binding=><div className="capability-binding" key={`${binding.kind}:${binding.reference.resource_id}`}><h3>{kinds[binding.kind]}</h3>{capabilityMemberHref(binding,detail,params.get('returnConversation'))&&<Link to={capabilityMemberHref(binding,detail,params.get('returnConversation'))!}>{memberName(binding)}</Link>}<p>{binding.purpose}</p><details><summary>查看固定引用</summary><dl><div><dt>资源</dt><dd>{binding.reference.resource_id}</dd></div><div><dt>版本</dt><dd>{binding.reference.revision_id}</dd></div><div><dt>内容标识</dt><dd>{binding.reference.digest}</dd></div></dl></details></div>)}</details><p>发布检查核对定义和固定资源；实际执行结果以对应工作记录为准。</p></section>
      {detail.headRevisionId===current.revision_id&&<button disabled={busy} onClick={()=>{setPreview(null);setEditing('edit')}}>修改能力</button>}
      {detail.state!=='PUBLISHED'&&detail.headRevisionId===current.revision_id&&<button disabled={busy} onClick={review}>查看变更与发布影响</button>}
      {detail.currentDraftRevisionId&&detail.currentDraftRevisionId!==current.revision_id&&<button onClick={()=>choose(id,detail.currentDraftRevisionId!)}>查看当前修改草稿</button>}
      {preview&&<section className="capability-panel" aria-label="发布变更确认"><h2>本次变更与影响</h2><p>仅发布当前能力定义。历史会话、既有任务及其资源引用保持原样。</p>{preview.fieldChanges.map(change=><div className="capability-change" key={change.field}><h3>{fieldNames[change.field]??change.field}</h3><p>原内容：{valueText(change.before)}</p><p>新内容：{valueText(change.after)}</p></div>)}{preview.bindingChanges.map(change=><div className="capability-change" key={`${change.kind}:${change.resourceId}`}><h3>{kinds[change.kind]} · {change.after?change.before?'调整引用':'新增引用':'移除引用'}</h3><p>{change.after?.purpose??change.before?.purpose}</p><details><summary>核对资源变化</summary><pre>{JSON.stringify({before:change.before,after:change.after},null,2)}</pre></details></div>)}<label>发布说明<textarea maxLength={1000} value={reason} disabled={busy||command!==null} onChange={event=>setReason(event.target.value)}/></label><div className="capability-actions"><button disabled={busy||!reason.trim()} onClick={publish}>{busy?'正在处理…':command?'核实并重试本次发布':'确认并发布'}</button><button disabled={busy} onClick={()=>{setPreview(null);setCommand(null)}}>关闭预览</button></div></section>}
    </>}
    {params.get('returnConversation')&&<Link to={'/work?'+new URLSearchParams({conversation:params.get('returnConversation')!})}>返回原会话</Link>}
  </main>;
}
