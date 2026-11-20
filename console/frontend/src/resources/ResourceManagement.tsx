import {publishedTestResourcesChanged} from '../components/testResourcePreparation';
import {workbenchPrincipalKey} from '../api/digitalEmployees';
import {createPortal} from 'react-dom';
import {useEffect,useRef,useState} from 'react';
import {readWorkbenchSession,type WorkbenchSession} from '../api/businessWorkspace';
import type {ResourceContent,SkillMcpResource} from '../api/skillMcpResources';
import {NavigationIcon} from '../components/NavigationIcon';
import './ResourceManagement.css';
import {SkillTestingPanel} from './SkillTestingPanel';
import {ResourceDetailView} from './ResourceDetailView';
import {useSearchParams} from 'react-router-dom';
import {ResourceBatchImport} from './ResourceBatchImport';
type Kind='skill'|'mcp';
import {decodeManagementIntent,verifyManagementReceipt,verifyManagedResource,type ManagementCommandIntent,type ManagementReceipt} from './managementCommandState';
export type ManagedResourceDirectory={subject:string;scope:{tenantId:string;securityDomain:string};items:SkillMcpResource[]};
const stateNames:Record<string,string>={DRAFT:'草稿',VALIDATED:'验证通过',POLICY_REVIEWED:'策略核验通过',PUBLISHED:'已发布',DEPRECATED:'已弃用'};
function completedOperation(action:string){
 const messages:Record<string,string>={
  create:'草稿已保存。',import:'配置已导入为新草稿。',edit:'草稿修改已保存，请按当前内容重新验证。',
  successor:'修改草稿已创建，原发布版本和已有引用保持不变。',
  validate:'当前配置验证已完成；发布状态以当前版本为准。',
  publish:'配置已发布；已有引用保持原版本，执行资格需另行核对。',
  'publish-tested':'当前版本已完成操作测试核验并发布；已有引用保持原版本。',
  test:'本次测试结果已记录，请查看测试是否通过及具体依据。',
  health:'连接检查结果已记录，请查看当前修订的连接状态。',
  discover:'工具与资料发现结果已记录。','select-tools':'本版本的工具选择已保存。',
  enable:'资源已启用，实际执行仍需核对当前条件。',disable:'资源已停用，历史版本和使用记录保留。',
  access:'当前资源的管理资格已核对。',
 };
 return messages[action]??'本次操作结果已记录。';
}
class ManagementError extends Error{status:number;constructor(reason:string,status:number){super(reason);this.status=status}}
async function request<T>(path:string,init?:RequestInit):Promise<T>{const response=await fetch('/api/workbench/v1/resource-management/'+path,{credentials:'same-origin',...init});const body=await response.json().catch(()=>null);if(response.status===401){const currentUser=await readWorkbenchSession().then(()=>true,()=>false);if(currentUser)throw new ManagementError('RESOURCE_POLICY_SERVICE_UNAVAILABLE',401)}if(!response.ok)throw new ManagementError(body?.reasonCode??'RESOURCE_MANAGEMENT_UNAVAILABLE',response.status);if(!body?.result)throw new ManagementError('RESOURCE_RESPONSE_UNKNOWN',503);return body.result}
function sameScope(session:WorkbenchSession,d:ManagedResourceDirectory){return d.subject===session.principal.principalId&&d.scope.tenantId===session.principal.tenantId&&d.scope.securityDomain===session.principal.securityDomain}
export function ResourceManagement({kind,onChanged,onDetailChange,onDirectoryChange,hideOwnedList=false,primaryTarget,secondaryTarget}:{primaryTarget?:HTMLElement|null;secondaryTarget?:HTMLElement|null;kind:Kind;onChanged:()=>void;onDetailChange?:(open:boolean)=>void;onDirectoryChange?:(value:ManagedResourceDirectory|null)=>void;hideOwnedList?:boolean}){
 const [params,setParams]=useSearchParams(),requestedResource=params.get('managedResource');
 const commandIntent=useRef<ManagementCommandIntent|null>(null),writeFlight=useRef(false),accessScope=useRef<string|null>(null),view=useRef({active:false,epoch:0});
 const [upgradeLocked,setUpgradeLocked]=useState(false);
 const [items,setItems]=useState<SkillMcpResource[]>([]),[selected,setSelected]=useState<SkillMcpResource|null>(null),[mode,setMode]=useState<'create'|'edit'|'import'|null>(null),[name,setName]=useState(''),[description,setDescription]=useState(''),[capabilities,setCapabilities]=useState(''),[instructions,setInstructions]=useState(''),[endpoint,setEndpoint]=useState(''),[secretRef,setSecretRef]=useState(''),[advanced,setAdvanced]=useState('{}'),[manifest,setManifest]=useState(''),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState(''),[available,setAvailable]=useState(false),[loaded,setLoaded]=useState(false),[tools,setTools]=useState<string[]>([]),[pendingKey,setPendingKey]=useState<string|null>(null);
 useEffect(()=>{onDetailChange?.(!!selected)},[selected,onDetailChange]);
 async function read(expectedPrincipal?:string,assertCurrent=()=>{}){
  assertCurrent();const before=await readWorkbenchSession();assertCurrent();
  if(expectedPrincipal&&JSON.stringify(before.principal)!==expectedPrincipal)throw Error('RESOURCE_DIRECTORY_IDENTITY_CHANGED');
  const value=await request<ManagedResourceDirectory>(kind);assertCurrent();const after=await readWorkbenchSession();assertCurrent();
  if(JSON.stringify(before.principal)!==JSON.stringify(after.principal)||!sameScope(after,value)||(expectedPrincipal&&JSON.stringify(after.principal)!==expectedPrincipal))throw Error('RESOURCE_DIRECTORY_IDENTITY_CHANGED');
  setItems(value.items);setAvailable(true);onDirectoryChange?.(value);return value;
 }
 async function refreshPublishedResource(){
  if(!selected||!accessScope.current)throw Error('RESOURCE_ACCESS_CONTEXT_CHANGED');
  const identity=selected.resourceId,assertCurrent=guard(identity);
  const value=await read(accessScope.current,assertCurrent);assertCurrent();
  const updated=value.items.find(x=>x.resourceId===identity);
  if(!updated)throw Error('RESOURCE_DETAIL_UNAVAILABLE');
  setSelected(updated);
 }
 function guard(identity?:string){const epoch=view.current.epoch,path=location.pathname;return()=>{if(!view.current.active||view.current.epoch!==epoch||location.pathname!==path||(identity!==undefined&&new URLSearchParams(location.search).get('managedResource')!==identity))throw Error('RESOURCE_ACCESS_CONTEXT_CHANGED')}}
 useEffect(() => {
  const lifecycle=view.current; lifecycle.active=true; lifecycle.epoch++;
  let live=true, pinned:string|null=null;
  readWorkbenchSession().then(async session => {
   const value=await request<ManagedResourceDirectory>(kind),after=await readWorkbenchSession();
   if(!live || JSON.stringify(session.principal)!==JSON.stringify(after.principal) || !sameScope(after,value))return;
   pinned=JSON.stringify(after.principal); accessScope.current=pinned;
   const marker='resource-management:'+session.principal.principalId+':'+session.principal.tenantId+':'+session.principal.securityDomain+':'+kind;
   const key=sessionStorage.getItem(marker);
   if(key){
    setPendingKey(key);
    try{
     let saved=sessionStorage.getItem(marker+':intent');
     // Preserve the original access command created by the previous Console.
     if(!saved && key.startsWith('resource-access:')){
      const old=JSON.parse(sessionStorage.getItem(marker+':access-intent')??'null');
      if(old?.commandKey!==key || old.principal!==pinned || old.kind!==kind)throw Error();
      saved=JSON.stringify({version:1,commandKey:key,action:'access',kind,principal:pinned,identity:old.identity,viewResource:old.identity});
     }
     commandIntent.current=decodeManagementIntent(saved,key,kind,pinned);
    }catch{commandIntent.current=null;setError('原操作的核对依据尚未恢复；保留原命令，不重新提交。')}
   }
   setItems(value.items);setAvailable(true);onDirectoryChange?.(value);
   const restore=value.items.find(x=>x.resourceId===new URLSearchParams(location.search).get('managedResource'));
   if(restore)setSelected(restore);
  }).catch(()=>{if(live){setAvailable(false);onDirectoryChange?.(null)}}).finally(()=>{if(live)setLoaded(true)});
  const withdraw=()=>{onDirectoryChange?.(null);lifecycle.epoch++;accessScope.current=null;commandIntent.current=null;setItems([]);setSelected(null);setAvailable(false);setMode(null)};
  const focus=()=>{void readWorkbenchSession().then(s=>{if(live&&pinned&&JSON.stringify(s.principal)!==pinned)withdraw()}).catch(()=>{if(live)withdraw()})};
  window.addEventListener('focus',focus);window.addEventListener('workbench-session-expired',withdraw);
  return()=>{onDirectoryChange?.(null);live=false;lifecycle.active=false;lifecycle.epoch++;accessScope.current=null;window.removeEventListener('focus',focus);window.removeEventListener('workbench-session-expired',withdraw)};
 },[kind,onDirectoryChange]);
 function form(resource?:SkillMcpResource){setError('');setMessage('');setTools([]);if(resource){const revision=resource.revisions.find(r=>r.revisionId===resource.currentDraftRevisionId);if(!revision)return;const c=revision.content;setMode('edit');setName(resource.name);setDescription(c.description);setCapabilities(c.capabilities.join('、'));setInstructions(c.instructions??'');setEndpoint(c.endpoint??'');setSecretRef(c.secretReference??'');setAdvanced(JSON.stringify(c,null,2));setSelected(resource)}else{setMode('create');setName('');setDescription('');setCapabilities('');setInstructions('');setEndpoint('');setSecretRef('');setAdvanced('{}');setSelected(null)}}
 function intentGuard(intent:ManagementCommandIntent){
  const assertMounted=guard();
  return()=>{assertMounted();if(new URLSearchParams(location.search).get('managedResource')!==intent.viewResource)throw Error('RESOURCE_ACCESS_CONTEXT_CHANGED')};
 }
 function clearPending(marker:string){
  sessionStorage.removeItem(marker);sessionStorage.removeItem(marker+':intent');sessionStorage.removeItem(marker+':access-intent');
  commandIntent.current=null;setPendingKey(null);
 }
 async function applyReceipt(value:unknown,intent:ManagementCommandIntent,assertCurrent:()=>void){
  let result:ManagementReceipt;try{result=verifyManagementReceipt(value,intent)}catch(reason){if(intent.action==='access')throw Error('RESOURCE_ACCESS_RECEIPT_MISMATCH',{cause:reason});throw reason}assertCurrent();
  const fresh=await read(intent.principal,assertCurrent);assertCurrent();
  const current=fresh.items.find(x=>x.resourceId===result.identity);
  if(!current){setSelected(null);throw Error('RESOURCE_RESULT_NOT_CURRENTLY_READABLE')}
  try{verifyManagedResource(current)}catch(reason){setSelected(null);throw reason}
  if(current.kind!==intent.kind || current.aggregateVersion<result.aggregateVersion)throw Error('RESOURCE_COMMAND_RECEIPT_MISMATCH');
  setSelected(current);
  const currentParams=new URLSearchParams(location.search);
  const followEditedDraft=intent.action==='edit'&&current.currentDraftRevisionId&&currentParams.get('viewRevision')===selected?.currentDraftRevisionId;
  if(currentParams.get('managedResource')!==result.identity||followEditedDraft){
   currentParams.set('managedResource',result.identity);if(followEditedDraft)currentParams.set('viewRevision',current.currentDraftRevisionId!);setParams(currentParams,{replace:true});
  }
  if(['publish','publish-tested'].includes(intent.action))window.dispatchEvent(new Event(publishedTestResourcesChanged));
  setMode(null);setTools([]);onChanged();return current;
 }
 async function submit(action:string,extra:Record<string,unknown>={},resource=selected){
  if(writeFlight.current||busy||pendingKey||upgradeLocked)return;
  writeFlight.current=true;const assertMounted=guard();setBusy(true);setError('');setMessage('');let marker='';
  try{
   assertMounted();const session=await readWorkbenchSession();assertMounted();
   const principal=JSON.stringify(session.principal);
   if(principal!==accessScope.current)throw Error('RESOURCE_DIRECTORY_IDENTITY_CHANGED');
   if(resource&&sessionStorage.getItem('selected-upgrade:'+workbenchPrincipalKey(session)+':'+resource.resourceId))throw Error('原整批发布结果待核实，请返回版本页读取原发布结果。');
   if(action==='access'&&extra.identity!==requestedResource)throw Error('RESOURCE_ACCESS_CONTEXT_CHANGED');
   marker='resource-management:'+session.principal.principalId+':'+session.principal.tenantId+':'+session.principal.securityDomain+':'+kind;
   const commandKey=(action==='access'?'resource-access:':'')+crypto.randomUUID();
   const intent:ManagementCommandIntent={version:1,commandKey,action,kind,principal,viewResource:new URLSearchParams(location.search).get('managedResource'),
    ...(resource?{identity:resource.resourceId,expectedVersion:resource.aggregateVersion}:{}),...(action==='access'?{identity:String(extra.identity)}:{})};
   decodeManagementIntent(JSON.stringify(intent),commandKey,kind,principal);
   // Store the complete binding before POST. Never replace an unresolved key.
   if(sessionStorage.getItem(marker))throw Error('RESOURCE_COMMAND_STILL_PENDING');
   sessionStorage.setItem(marker+':intent',JSON.stringify(intent));sessionStorage.setItem(marker,commandKey);
   commandIntent.current=intent;setPendingKey(commandKey);const assertCurrent=intentGuard(intent);
   let result:unknown;
   try{result=await request<ManagementReceipt>(kind+'/commands',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrfToken},body:JSON.stringify({action,commandKey,...(resource?{identity:resource.resourceId,expectedVersion:resource.aggregateVersion}:{}),...extra})})}
   catch(reason){assertCurrent();try{result=await request<ManagementReceipt>(kind+'/commands/'+encodeURIComponent(commandKey))}catch{throw reason}}
   assertCurrent();const after=await readWorkbenchSession();assertCurrent();
   if(principal!==JSON.stringify(after.principal))throw Error('RESOURCE_DIRECTORY_IDENTITY_CHANGED');
   const current=await applyReceipt(result,intent,assertCurrent);clearPending(marker);
   setMessage(completedOperation(action));return current;
  }catch(reason){
   if(!view.current.active)return;
   const text=reason instanceof Error?reason.message:'RESOURCE_MANAGEMENT_UNAVAILABLE';setError(text);
   if(text==='RESOURCE_DIRECTORY_IDENTITY_CHANGED'||text==='RESOURCE_POLICY_SERVICE_UNAVAILABLE'){setSelected(null);setItems([]);setAvailable(false);accessScope.current=null;onDirectoryChange?.(null)}
   if(reason instanceof ManagementError&&reason.status>=400&&reason.status<500&&marker)clearPending(marker);
  }finally{writeFlight.current=false;if(view.current.active)setBusy(false)}
 }
 async function modifyCurrent(){
  if(!selected||busy||pendingKey)return;
  const assertCurrent=guard(selected.resourceId);
  try{
   const current=selected.currentDraftRevisionId?selected:await submit('successor');assertCurrent();
   if(!current?.currentDraftRevisionId)return;
   form(current);setParams(previous=>{const next=new URLSearchParams(previous);next.delete('resourceView');next.delete('resourceTab');next.set('resourceSection','content');next.set('resourceTab',kind==='skill'?'业务规则':'执行设置');next.set('viewRevision',current.currentDraftRevisionId!);return next},{replace:true});
  }catch{/* A navigation or identity change keeps the original result in its owner. */}
 }
 async function recover(){
  if(!pendingKey||busy||writeFlight.current)return;
  const intent=commandIntent.current;
  if(!intent){setError('原操作的核对依据尚未恢复；保留原命令，不重新提交。');return}
  const assertCurrent=intentGuard(intent);writeFlight.current=true;setBusy(true);
  try{
   assertCurrent();const session=await readWorkbenchSession();assertCurrent();
   if(JSON.stringify(session.principal)!==intent.principal)throw Error('RESOURCE_DIRECTORY_IDENTITY_CHANGED');
   const result=await request<ManagementReceipt>(kind+'/commands/'+encodeURIComponent(pendingKey));assertCurrent();
   const after=await readWorkbenchSession();assertCurrent();
   if(JSON.stringify(after.principal)!==intent.principal)throw Error('RESOURCE_DIRECTORY_IDENTITY_CHANGED');
   await applyReceipt(result,intent,assertCurrent);
   clearPending('resource-management:'+session.principal.principalId+':'+session.principal.tenantId+':'+session.principal.securityDomain+':'+kind);
   setError('');setMessage('已读回原操作及当前正式记录，没有再次提交。'+completedOperation(intent.action));
  }catch(reason){
   if(!view.current.active)return;
   setSelected(null);
   if(reason instanceof Error&&reason.message==='RESOURCE_DIRECTORY_IDENTITY_CHANGED'){setItems([]);setAvailable(false);accessScope.current=null;onDirectoryChange?.(null)}
   setError('尚未确认原操作与当前访问范围。原记录保留，不自动重试；可稍后再次读取。');
  }finally{writeFlight.current=false;if(view.current.active)setBusy(false)}
 }
 function save(){try{if(mode==='import'){const value=JSON.parse(manifest);void submit('import',{manifest:value},null);return}const extra=JSON.parse(advanced);if(!extra||typeof extra!=='object'||Array.isArray(extra))throw Error();const content:ResourceContent={...extra,description,capabilities:capabilities.split(/[、,，\n]/).map(v=>v.trim()).filter(Boolean),sideEffect:extra.sideEffect??'READ',...(kind==='skill'?{instructions}:{endpoint,secretReference:secretRef||null})};void submit(mode==='edit'?'edit':'create',{name,content},mode==='edit'?selected:null)}catch{setError('请输入有效的配置对象或导入清单。')}}
 const revision=selected?.revisions.find(r=>r.revisionId===(selected.currentDraftRevisionId??selected.publishedRevisionId)),savedSnapshot=selected?.discoverySnapshots.at(-1),snapshot=savedSnapshot?.revisionId===revision?.revisionId&&savedSnapshot?.revisionDigest===revision?.digest?savedSnapshot:undefined,currentHealth=selected?.healthObservations.filter(o=>o.revisionId===revision?.revisionId&&o.revisionDigest===revision?.digest).at(-1);
 function exportSelected(){if(!selected||!revision)return;const blob=new Blob([JSON.stringify({manifestVersion:'skill-mcp-workbench/v1',kind,name:selected.name,content:revision.content,sourceRevisionId:revision.revisionId,sourceDigest:revision.digest,credentialMaterial:'NOT_INCLUDED'},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=kind+'-配置.json';a.click();URL.revokeObjectURL(url)}
 const editor=mode&&<form className="rm-form" aria-label={mode==='import'?'导入资源配置':'资源配置表单'} onSubmit={e=>{e.preventDefault();save()}}><h3>{mode==='import'?'导入资源草稿':mode==='edit'?'编辑草稿':'新建资源草稿'}</h3>{mode==='import'?<><label>选择配置文件<input aria-label="选择配置文件" type="file" accept=".json,application/json" onChange={e=>{const file=e.target.files?.[0];if(file){if(file.size>200000){setError('文件超过200KB限制');return}void file.text().then(setManifest)}}}/></label><label>配置清单<textarea aria-label="配置清单" required value={manifest} onChange={e=>setManifest(e.target.value)} rows={9}/></label><p>只支持现有资源清单格式，导入后为新草稿，不继承发布、权限或调用资格。</p></>:<><div className="rm-grid"><label>名称<input required maxLength={120} readOnly={mode==='edit'} value={name} onChange={e=>setName(e.target.value)}/></label><label>用途说明<input required value={description} onChange={e=>setDescription(e.target.value)}/></label><label>能力名称<input required placeholder="多个能力用顿号分隔" value={capabilities} onChange={e=>setCapabilities(e.target.value)}/></label>{kind==='skill'?<label>办理说明<textarea aria-label="办理说明" required value={instructions} onChange={e=>setInstructions(e.target.value)}/></label>:<><label>服务地址<input required type="url" placeholder="http://127.0.0.1:端口/mcp" value={endpoint} onChange={e=>setEndpoint(e.target.value)}/></label><label>凭据引用（可选）<input placeholder="secret-ref:资料标识" value={secretRef} onChange={e=>setSecretRef(e.target.value)}/></label></>}</div><details><summary>高级配置与输入输出契约</summary><label>配置对象<textarea aria-label="配置对象" value={advanced} onChange={e=>setAdvanced(e.target.value)} rows={10}/></label><p>已有操作契约将保留；保存配置不会安装新的执行器。</p></details></>}<div className="rm-actions"><button className="rm-primary" disabled={busy||!!pendingKey||upgradeLocked} type="submit">保存草稿</button><button type="button" disabled={busy} onClick={()=>setMode(null)}>取消</button></div></form>;
 if(!loaded)return <section className="resource-management" aria-label="资源配置状态"><p role="status">正在核对资源配置访问资格…</p></section>;
 if(!available)return <section className="resource-management" aria-label="资源配置状态"><p role="status">资源配置入口当前未就绪，已授权的版本仍可在下方查看。</p></section>;
 return <section className={'resource-management'+(selected?' rd-detail-mode':'')} aria-label={kind==='skill'?'技能创建与配置':'MCP连接创建与配置'}><header hidden={!!selected||!!secondaryTarget}><details className="rm-maintenance-guidance"><summary>维护说明</summary><p>保存草稿、核验发布和实际使用分别记录，历史版本继续保留。</p></details><div className="rm-actions">{primaryTarget?createPortal(<button disabled={busy||!!pendingKey||upgradeLocked} onClick={()=>form()}>创建技能</button>,primaryTarget):<button disabled={busy||!!pendingKey||upgradeLocked} onClick={()=>form()}><NavigationIcon name="resource"/>{kind==='skill'?'创建技能':'新建MCP连接'}</button>}{secondaryTarget?createPortal(<button disabled={busy||!!pendingKey||upgradeLocked} onClick={()=>{setMode('import');setSelected(null);setManifest('');setError('')}}>导入配置</button>,secondaryTarget):<button disabled={busy||!!pendingKey||upgradeLocked} onClick={()=>{setMode('import');setSelected(null);setManifest('');setError('')}}>导入配置</button>}</div></header>
 {!selected&&requestedResource&&!mode&&<section aria-label="原资源访问恢复" className="rm-pending"><h3>原资源详情尚未恢复</h3><p>当前目录未返回这个链接对应的可管理资源，不能据此认定原资源已删除。</p><p>可核对本账号创建的原资源访问资格。符合当前策略范围时，会重新授权管理原资源并读取其版本；此请求不修改配置或启动执行。</p><button disabled={busy||!!pendingKey||upgradeLocked} onClick={()=>void submit('access',{identity:requestedResource},null)}>核对原资源访问资格</button></section>}
 {!selected&&(secondaryTarget?createPortal(<ResourceBatchImport compact kind={kind} onImported={()=>{void read();onChanged()}}/>,secondaryTarget):<ResourceBatchImport kind={kind} onImported={()=>{void read();onChanged()}}/>)}
 {message&&<p role="status" className="rm-success">{message}</p>}{error&&<div role="alert" className="rm-error"><p>{error.includes('CREDENTIAL_RESOLVER')?'凭据引用已保留，但当前未安装凭据解析能力，不能进行认证连接测试。':error==='RESOURCE_ACCESS_CONTEXT_CHANGED'?'账号、范围或原资源链接已变化；请核对原页面后再请求访问资格。':error==='RESOURCE_ACCESS_RECEIPT_MISMATCH'?'访问回执与原请求不一致；保留原命令，不恢复为可管理资源。':error==='RESOURCE_MANAGEMENT_NOT_FOUND'?'当前未取得这个原资源的管理资格；请核对原账号与链接。':error==='RESOURCE_POLICY_DISABLED'||error==='RESOURCE_POLICY_WORK_SCOPE_DENIED'?'当前策略未允许恢复管理资格；原资源与使用记录保留。':error.includes('RESOURCE_POLICY_SERVICE_UNAVAILABLE')?'资源维护服务当前不可用，原配置保留；请稍后重新进入。':error.includes('RESOURCE_RESULT_NOT_CURRENTLY_READABLE')?'原操作已返回，但当前配置尚未获准读回；保留原操作记录，不重复提交。':error.includes('RESOURCE_COMMAND_RECEIPT_MISMATCH')?'操作回执与原请求不一致，保留原操作记录，请核对后再读取。':error.includes('CURRENT_OPERATION_TESTS_REQUIRED')?'当前准确版本的所有操作均需真实测试通过，才可验证后发布。':error.includes('STALE')?'配置已发生变化，请重新读取后核对。':error.includes('SECRET')||error.includes('CREDENTIALS_DENIED')?'配置不能包含明文凭据，请使用凭据引用。':error.includes('DESTINATION')?'当前只支持本机隔离连接，目标地址未获准。':error}</p></div>}{pendingKey&&<div className="rm-pending"><p>正在确认原命令结果，不会自动再次提交。</p><button disabled={busy} onClick={()=>void recover()}>读取原操作结果</button></div>}
 {mode!=='edit'&&editor}

 {!selected&&!hideOwnedList&&items.length>0&&<div className="rm-owned"><h3>本账号创建的配置</h3><div className="rm-resource-list">{items.map(item=><button key={item.resourceId} aria-pressed={false} onClick={()=>{setSelected(item);setMode(null);setTools([]);setError('');setParams(previous=>{const next=new URLSearchParams(previous);next.set('managedResource',item.resourceId);return next},{replace:true})}}><strong>{item.name}</strong><span>{stateNames[item.lifecycleState]??item.lifecycleState} · {item.revisions.length}个修订</span></button>)}</div></div>}
 {selected&&revision&&<ResourceDetailView onUpgradeRefresh={refreshPublishedResource} onUpgradeLock={setUpgradeLocked} key={selected.resourceId} resource={selected} busy={busy||!!pendingKey||upgradeLocked} onEdit={()=>form(selected)} onModify={()=>void modifyCurrent()} onExport={exportSelected} onCommand={action=>void submit(action)} onBack={()=>{setSelected(null);setMode(null);setParams(previous=>{const next=new URLSearchParams(previous);next.delete('managedResource');return next},{replace:true})}} actions={<div className="rm-actions">{revision.state==='DRAFT'&&selected.currentDraftRevisionId&&<><button disabled={busy||!!pendingKey||upgradeLocked} onClick={()=>form(selected)}>编辑草稿</button><button disabled={busy||!!pendingKey||upgradeLocked} onClick={()=>void submit('validate')}>验证配置</button></>}{selected.currentDraftRevisionId&&<button disabled={busy||!!pendingKey||upgradeLocked} onClick={()=>void submit('publish')}>{kind==='skill'?'发布配置（不代表执行已验证）':'核验并发布'}</button>}{!selected.currentDraftRevisionId&&selected.publishedRevisionId&&<button disabled={busy||!!pendingKey||upgradeLocked} onClick={()=>void submit('successor')}>修改</button>}<button disabled={busy||!!pendingKey||upgradeLocked} onClick={()=>void submit(selected.enabled?'disable':'enable')}>{selected.enabled?'停用':'启用'}</button><button onClick={exportSelected}>导出配置</button></div>} connection={<>{kind==='mcp'&&<section className="rm-connection"><h4>连接与工具</h4><p>服务地址：{revision.content.endpoint}</p><p>{revision.content.secretReference?'已配置凭据引用；实际解析支持需单独核验。':'无认证本机连接；只进行初始化与目录读取。'}</p><div className="rm-actions"><button disabled={busy||!!pendingKey||upgradeLocked} onClick={()=>void submit('health')}>测试连接</button><button disabled={busy||!!pendingKey||upgradeLocked} onClick={()=>void submit('discover')}>发现工具与资料</button></div><p>当前修订连接状态：{currentHealth?(currentHealth.status==='HEALTHY'?'初始化成功':'测试未通过'):'尚未测试'}</p><details><summary>连接测试历史（不作为当前修订就绪依据）</summary><ul>{selected.healthObservations.map(o=><li key={o.observationId}>{o.status==='HEALTHY'?'连接初始化成功':'连接不可用'} · {o.reasonCode}</li>)}</ul></details>{!snapshot&&<p>当前修订尚无工具发现记录；修改配置后需重新发现并选择。</p>}{snapshot&&<><p>已发现{snapshot.catalog.tools.length}项工具、{snapshot.catalog.resources.length}项资料、{snapshot.catalog.prompts.length}项提示。</p><fieldset><legend>选择本版本可用工具</legend>{snapshot.catalog.tools.map(t=><label key={t.name} className="rm-checkbox"><input type="checkbox" checked={tools.includes(t.name)} onChange={()=>setTools(old=>old.includes(t.name)?old.filter(n=>n!==t.name):[...old,t.name])}/>{t.name} · {t.description}</label>)}</fieldset><button disabled={busy||!!pendingKey||upgradeLocked||!tools.length} onClick={()=>void submit('select-tools',{snapshotId:snapshot.snapshotId,toolNames:tools})}>保存工具选择</button><p>已保存选择：{selected.toolSelections.at(-1)?.toolNames.join('、')||'尚未选择'}</p></>}<p>连接成功和工具发现不代表已调用工具，也不代表业务执行完成。</p></section>}</>} editor={mode==='edit'?editor:null} tests={kind==='skill'?<SkillTestingPanel resource={selected} busy={busy||!!pendingKey||upgradeLocked} onCommand={(action,payload)=>void submit(action,payload)}/>:null}/>}

 </section>;
}
