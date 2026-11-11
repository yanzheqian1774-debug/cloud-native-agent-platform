import {useBusinessProcessViewState} from './useBusinessProcessViewState';
import {businessProcessHref} from './businessRelationNavigation';
import {BusinessReferencePicker} from './BusinessReferencePicker';
import {BusinessProcessPublication} from "./BusinessProcessPublication";
import {BusinessActivityMap} from "./BusinessActivityMap";
import {BusinessProcessEditor} from "./BusinessProcessEditor";
import {useEffect,useRef,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {getWorkbenchSession,workbenchPrincipalKey} from '../api/digitalEmployees';
import {BusinessProcessRequestError,checkBusinessProcessEditorAccess,listBusinessProcesses,readBusinessArchitecture,readBusinessProcess,type BusinessArchitecture,type BusinessProcessContent,type BusinessProcessItem,type BusinessProcessRecord} from '../api/businessProcesses';
import './businessProcesses.css';

const bands={MANAGEMENT:'管理流程',CORE:'核心流程',SUPPORT:'支持流程'};
function failure(error:unknown){
  if(error instanceof BusinessProcessRequestError){
    if(error.status===401)return '登录已失效，请重新登录。';
    if(error.status===403||error.status===404)return '当前账号无法读取这项业务流程或其所属架构。';
    if(error.status===409)return '登录身份或引用版本已变化，请重新读取。';
    if(error.code==='READ_TIMEOUT')return '读取等待时间较长，请重新读取；不会重复提交或执行工作。';
  }
  return '业务流程暂时无法读取，请稍后重试。';
}
const missing=(text:string|null|undefined)=>text||'待补充';
export function BusinessProcessesPage(){
  const [params,setParams]=useSearchParams();
  const id=params.get('process')??'',revision=params.get('revision')??'',expectedDigest=params.get('digest');
  const query=params.get('query')??'',domain=params.get('domain')??'',group=params.get('group')??'',cursor=params.get('cursor')??'';
  const architectureView=params.get('view')==='architecture';
  const editing=params.get('edit');
  const root=useRef<HTMLElement>(null),[viewPrincipal,setViewPrincipal]=useState('');
  const [architecture,setArchitecture]=useState<BusinessArchitecture|null>(null);
  const [items,setItems]=useState<BusinessProcessItem[]>([]);
  const [detail,setDetail]=useState<BusinessProcessRecord<BusinessProcessContent>|null>(null);
  const [nextCursor,setNextCursor]=useState<string|null>(null);
  const [access,setAccess]=useState<'checking'|'allowed'|'readonly'|'unavailable'>('checking');
  const [loading,setLoading]=useState(true),[error,setError]=useState(''),[retry,setRetry]=useState(0);
  useEffect(()=>{
    let active=true;const controller=new AbortController();let currentPrincipal='',accessRequest=0;
    const checkAccess=async(principal:string)=>{
      const request=++accessRequest;setAccess('checking');
      try{
        const value=await checkBusinessProcessEditorAccess(id?'PROCESS':architectureView?'ARCHITECTURE':'PROCESS',id|| (architectureView?'architecture':'new'),id||architectureView?'REVISE':'CREATE',principal,controller.signal);
        if(active&&request===accessRequest)setAccess(value.allowed===true?'allowed':'unavailable');
      }catch(cause){if(active&&request===accessRequest)setAccess(cause instanceof BusinessProcessRequestError&&(cause.status===403||cause.status===404)?'readonly':'unavailable')}
    };
    const focus=()=>{if(active&&currentPrincipal)void checkAccess(currentPrincipal)};
    const load=async()=>{
      setLoading(true);setAccess('checking');setError('');setItems([]);setDetail(null);setArchitecture(null);setNextCursor(null);setViewPrincipal('');
      try{
        const session=await getWorkbenchSession(AbortSignal.any([controller.signal,AbortSignal.timeout(30_000)]));
        const principal=workbenchPrincipalKey(session);currentPrincipal=principal;void checkAccess(principal);
        if(id){
          if(!revision)throw new BusinessProcessRequestError('MISSING_VERSION',409);
          const value=await readBusinessProcess(id,revision,principal,controller.signal);
          if(value.objectId!==id||value.revisionId!==revision||(expectedDigest!==null&&value.digest!==expectedDigest))throw new BusinessProcessRequestError('REFERENCE_MISMATCH',409);
          const reference=value.record.architectureReference;
          if(!reference)throw new BusinessProcessRequestError('REFERENCE_MISSING',503);
          const source=value.architecture??await readBusinessArchitecture(principal,controller.signal,reference.revisionId);
          if(source.revisionId!==reference.revisionId||source.digest!==reference.digest)throw new BusinessProcessRequestError('REFERENCE_MISMATCH',409);
          if(active){setViewPrincipal(principal);setDetail(value);setArchitecture(source.record.content)}
        }else{
          const [source,page]=await Promise.all([readBusinessArchitecture(principal,controller.signal),architectureView?Promise.resolve(null):listBusinessProcesses(principal,controller.signal,{query,domainId:domain,groupId:group,cursor})]);
          if(active){setArchitecture(source.record.content);setItems(page?.items??[]);setNextCursor(page?.nextCursor??null)}
        }
      }catch(cause){if(active)setError(failure(cause))}finally{if(active)setLoading(false)}
    };
    const expire=()=>{setAccess('unavailable');currentPrincipal='';active=false;controller.abort();setItems([]);setDetail(null);setArchitecture(null);setNextCursor(null);setViewPrincipal('');setLoading(false);setError('登录已失效，请重新登录。')};
    window.addEventListener('workbench-session-expired',expire);window.addEventListener('focus',focus);void load();
    return()=>{active=false;controller.abort();window.removeEventListener('workbench-session-expired',expire);window.removeEventListener('focus',focus)};
  },[id,revision,expectedDigest,query,domain,group,cursor,architectureView,retry]);
  const navigate=(changes:Record<string,string|null>)=>{const next=new URLSearchParams(params);if(changes.edit===null)next.delete('draft');if('revision' in changes||'process' in changes){next.delete('digest');next.delete('activity');next.delete('handoff')}for(const [key,value] of Object.entries(changes)){if(value)next.set(key,value);else next.delete(key)}setParams(next)};
  const listHref=(processId:string,revisionId:string)=>{const next=new URLSearchParams(params);next.delete('digest');next.delete('activity');next.set('process',processId);next.set('revision',revisionId);return '/business-processes?'+next};
  const domainName=(identity:string)=>architecture?.domains.find(item=>item.domain_id===identity)?.name??'所属领域未能核对';
  const groupName=(identity:string)=>architecture?.groups.find(item=>item.group_id===identity)?.name??'所属流程组未能核对';
  const content=detail?.record.content;
  const saveView=useBusinessProcessViewState(root,!editing&&detail&&viewPrincipal?JSON.stringify([viewPrincipal,detail.objectId,detail.revisionId,detail.digest,params.get('activity'),params.get('handoff')]):null);
  const lifecycle=detail?.publicationState;
  const statusLabels={CURRENT_PUBLISHED:'当前发布版',MODIFICATION_DRAFT:lifecycle?.published?'修改草稿':'登记草稿 · 尚未发布',HISTORICAL_PUBLISHED:'历史发布版',HISTORICAL_DRAFT:'历史草稿',PUBLISHED_VERSION:'已发布版本 · 当前状态不可读',DRAFT_VERSION:'草稿版本 · 当前状态不可读'};
  const statusLabel=lifecycle?statusLabels[lifecycle.selectedState]:'登记草稿 · 尚未发布';
  if(editing==='architecture'||editing==='process')return <main className="f3-business-processes"><BusinessProcessEditor key={editing+id+(params.get('draft')??'')} resumeDraftId={params.get('draft')??''} kind={editing==='architecture'?'ARCHITECTURE':'PROCESS'} processId={editing==='process'?id:''} onCancel={()=>navigate({edit:null})} onSaved={value=>{navigate({edit:null,...(editing==='process'?{process:value.objectId,revision:value.revisionId}:{})});setRetry(value=>value+1)}}/></main>;
  return <main ref={root} className="f3-business-processes" onClickCapture={event=>{const link=(event.target as HTMLElement).closest<HTMLAnchorElement>('a[href]');if(link&&new URL(link.href,window.location.origin).pathname!=='/business-processes')saveView()}}>
    <header><div><p className="bp-eyebrow">业务流程</p><h1>{content?.name??(architectureView?'业务架构全景':'选择要改善的业务流程')}</h1>{content&&<span className="bp-badge bp-draft-status">{statusLabel}</span>}<p>{id?'查看业务责任、活动和交接要求。':architectureView?'按管理、核心和支持流程查看已登记的业务领域与流程组。':'先确认流程和当前状态，再查看业务活动与待完善内容。'}</p></div>
      <div className="bp-actions">{!loading&&!error&&access==='allowed'&&<button onClick={()=>navigate({edit:id?'process':architectureView?'architecture':'process'})}>{id?(lifecycle?.selectedState==='CURRENT_PUBLISHED'&&!lifecycle.draft?'修改业务定义':'修改当前草稿'):architectureView?'维护领域与流程组':'登记业务流程'}</button>}{id?<button onClick={()=>navigate({process:null,revision:null})}>返回流程目录</button>:<button onClick={()=>navigate({view:architectureView?null:'architecture',cursor:null})}>{architectureView?'返回流程目录':'业务架构全景'}</button>}</div>
    </header>
    {!loading&&!error&&access==='readonly'&&<p className="bp-footnote">当前账号可查看，不能修改此项内容。</p>}
    {!loading&&!error&&access==='unavailable'&&<p className="bp-notice" role="status">操作权限暂未核实，当前内容仍可查看。<button onClick={()=>setRetry(value=>value+1)}>重新核对操作权限</button></p>}
    {loading&&<p role="status">正在读取业务流程…</p>}
    {error&&<section className="bp-notice" role="alert"><p>{error}</p><button onClick={()=>setRetry(value=>value+1)}>重新读取</button></section>}
    {!loading&&!error&&architecture&&<>
      {!id&&architectureView&&<div className="bp-architecture">{Object.entries(bands).map(([band,label])=><section className="bp-band" key={band}><h2>{label}</h2><div className="bp-grid">{architecture.domains.filter(item=>item.band===band).map(item=><article className="bp-card" key={item.domain_id}><h3>{item.name}</h3>{architecture.groups.filter(value=>value.domain_id===item.domain_id).map(value=><button key={value.group_id} onClick={()=>navigate({view:null,domain:item.domain_id,group:value.group_id,query:null,cursor:null})}>{value.name}</button>)}{!architecture.groups.some(value=>value.domain_id===item.domain_id)&&<p>尚未登记流程组</p>}</article>)}</div>{!architecture.domains.some(item=>item.band===band)&&<p>尚未登记业务领域</p>}</section>)}</div>}
      {!id&&!architectureView&&<>
        <form className="bp-search" key={`${query}-${domain}-${group}`} onSubmit={event=>{event.preventDefault();const data=new FormData(event.currentTarget);navigate({query:String(data.get('query')??'').trim(),domain:String(data.get('domain')??''),group:null,cursor:null})}}>
          <input name="query" aria-label="搜索业务流程" placeholder="搜索流程名称、编号或负责人" defaultValue={query} maxLength={160}/>
          <select name="domain" aria-label="业务领域" defaultValue={domain}><option value="">全部领域</option>{architecture.domains.map(item=><option value={item.domain_id} key={item.domain_id}>{item.name}</option>)}</select><button type="submit">搜索</button>
        </form>
        {group&&<p>当前流程组：{groupName(group)} <button onClick={()=>navigate({group:null,cursor:null})}>清除流程组筛选</button></p>}
        <div className="bp-grid">{items.map(item=><article className="bp-card" key={item.processId}><div className="bp-card-top"><span className="bp-badge">{domainName(item.domainId)}</span><span className="bp-badge">{item.state==='PUBLISHED'?'当前发布版':item.hasPublishedVersion?'修改草稿':'登记草稿'}</span></div><h2>{item.name}</h2><dl><div><dt>流程组</dt><dd>{groupName(item.groupId)}</dd></div><div><dt>业务负责人</dt><dd>{missing(item.ownerDescription)}</dd></div></dl><Link className="bp-primary" to={listHref(item.processId,item.revisionId)}>查看流程与活动</Link></article>)}</div>
        {!items.length&&<p className="bp-notice">{nextCursor?'本页没有可读流程，可继续查看下一页。':'没有匹配的业务流程；可调整筛选，或等待业务流程登记。'}</p>}
        <div className="bp-actions">{cursor&&<button onClick={()=>navigate({cursor:null})}>返回第一页</button>}{nextCursor&&<button onClick={()=>navigate({cursor:nextCursor})}>下一页</button>}</div>
        <p className="bp-footnote">可查看当前发布版与修改草稿。发布仅固定业务定义；关联记录可在活动详情查看；实际执行仍需另行验证。</p>
      </>}
      {content&&<>
        <section className="bp-card bp-definition-compact"><h2>此版本业务定义</h2><dl><div><dt>所属领域 / 流程组</dt><dd>{domainName(content.domain_id)} / {groupName(content.group_id)}</dd></div><div><dt>流程编号</dt><dd>{missing(content.business_code)}</dd></div><div><dt>业务负责人</dt><dd>{missing(content.owner_description)}</dd></div><div><dt>业务目的</dt><dd>{missing(content.purpose)}</dd></div><div><dt>改善事项</dt><dd>{missing(content.improvement_notes)}</dd></div></dl></section>
        {detail?.definitionValidation&&<section className="bp-card bp-definition-validation" aria-label="定义校验">
          <h2>{detail.definitionValidation.status==='COMPLETE'?'定义信息已齐全':`待完善 ${detail.definitionValidation.issues.length} 项`}</h2>
          <p>仅核对本版本的定义信息；发布状态以发布记录为准，资源与执行需另行验证。</p>
          {detail.definitionValidation.issues.length>0&&<details data-bp-state-key="definition-validation" open={detail.definitionValidation.issues.length<=5}><summary>查看待完善内容</summary><ul>{detail.definitionValidation.issues.map(issue=><li key={issue.path+issue.code}>{issue.message}</li>)}</ul></details>}
        </section>}
        {detail&&<BusinessProcessPublication key={detail.objectId+detail.revisionId} detail={detail} onNavigate={revision=>navigate({revision})} onRefresh={()=>setRetry(value=>value+1)}/>}
        <BusinessActivityMap key={detail?.revisionId+':'+(params.get('activity')??'')+':'+(params.get('handoff')??'')} content={content} referenceDetails={detail?.referenceDetails} processReference={detail?.revisionId&&detail.digest?{resource_id:detail.objectId,revision_id:detail.revisionId,digest:detail.digest}:undefined} initialActivityId={params.get('activity')} initialHandoffId={params.get('handoff')} onActivitySelect={activity=>navigate({activity,handoff:null})} onHandoffSelect={handoff=>navigate({handoff,activity:null})} onActivityClear={()=>navigate({activity:null,handoff:null})}/>
        {!!content.source_materials?.length&&<section className="bp-card bp-source-card"><BusinessReferencePicker key={'sources:'+detail?.revisionId} kind="knowledge" selected={content.source_materials} returnTo={detail?.revisionId&&detail.digest?businessProcessHref({resource_id:detail.objectId,revision_id:detail.revisionId,digest:detail.digest},params.get('activity')??undefined,params.get('handoff')??undefined):undefined} details={detail?.referenceDetails}/></section>}
        <p className="bp-footnote">资料与数字人关联用于说明业务定义；执行授权与运行结果仍需单独验证。</p>
      </>}
    </>}
  </main>;
}
