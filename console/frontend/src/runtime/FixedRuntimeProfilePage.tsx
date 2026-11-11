import {useEffect,useState} from 'react';
import {useSearchParams} from 'react-router-dom';
import {NavigationIcon} from '../components/NavigationIcon';
import {readExactDirectoryResource,type DirectoryDetail} from '../api/resourceDirectory';
import '../resources/ResourceDetailWorkspace.css';
import './FixedRuntimeProfilePage.css';
const labels:Record<string,string>={NATIVE_KUBERNETES:'Native Kubernetes',OPENCLAW:'OpenClaw',NAMESPACE:'命名空间隔离',DEDICATED_RUNTIME:'独立运行环境',STATELESS:'无状态',EXTERNAL_REFERENCE:'外部状态引用',NONE:'无',REQUIRED:'需要',PUBLISHED:'已发布',DRAFT:'草稿',VALIDATED:'验证通过',HUMAN_REVIEWED:'审核通过'};
const text=(value:unknown)=>typeof value==='string'?(labels[value]??value):'未提供';
export function FixedRuntimeProfilePage(){
 const [params]=useSearchParams(),id=params.get('resourceId')??'',revision=params.get('resourceRevision')??'',digest=params.get('resourceDigest')??'';
 const valid=['resourceId','resourceRevision','resourceDigest'].every(key=>params.getAll(key).length===1)&&id.length>0&&id.length<=200&&revision.length>0&&revision.length<=200&&/^(?:sha256:)?[a-f0-9]{64}$/.test(digest);
 const [data,setData]=useState<DirectoryDetail|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[retry,setRetry]=useState(0);
 useEffect(()=>{
  const controller=new AbortController();let active=true;
  const load=async()=>{
   setData(null);setError('');setLoading(true);
   try{
    if(!valid)throw new Error('RESOURCE_DIRECTORY_VERSION_MISMATCH');
    const value=await readExactDirectoryResource('runtime',id,revision,digest,AbortSignal.any([controller.signal,AbortSignal.timeout(30_000)]));
    if(active)setData(value);
   }catch(cause){if(active)setError(cause instanceof Error&&cause.message==='RESOURCE_DIRECTORY_VERSION_MISMATCH'?'来源绑定的运行环境版本未能核对，请返回能力确认原引用。':'当前运行环境版本暂时无法读取，请核对登录和访问范围后重试。')}
   finally{if(active)setLoading(false)}
  };
  const expire=()=>{active=false;controller.abort();setData(null);setLoading(false);setError('登录已失效，请重新登录后查看原版本。')};
  window.addEventListener('workbench-session-expired',expire);void load();
  return()=>{active=false;controller.abort();window.removeEventListener('workbench-session-expired',expire)};
 },[id,revision,digest,valid,retry]);
 const content=data?.revision?.content,resources=content?.resources&&typeof content.resources==='object'?content.resources as Record<string,unknown>:{};
 return <main className="fixed-runtime-detail"><header className="f3-detail-heading"><div><span className="resource-type-mark"><NavigationIcon name="runtime"/><span>运行环境</span></span><h1>{data?.name??'运行环境固定版本'}</h1><p>查看本能力绑定的运行环境声明。</p>{data?.revision&&<span className="resource-version-state" data-state={data.revision.state}>{text(data.revision.state)}</span>}</div></header>
  {loading&&<p role="status">正在核对运行环境版本…</p>}
  {error&&<section className="f3-detail-card" role="alert"><p>{error}</p><button onClick={()=>setRetry(value=>value+1)}>重新读取原版本</button></section>}
  {content&&<><section className="f3-detail-card"><h2>运行方式与资源</h2><dl><div><dt>运行引擎</dt><dd>{text(content.provider)}</dd></div><div><dt>隔离方式</dt><dd>{text(content.isolation)}</dd></div><div><dt>CPU 申请 / 上限</dt><dd>{text(resources.cpuRequest)} / {text(resources.cpuLimit)}</dd></div><div><dt>内存申请 / 上限</dt><dd>{text(resources.memoryRequest)} / {text(resources.memoryLimit)}</dd></div><div><dt>状态管理</dt><dd>{text(content.stateMode)}</dd></div><div><dt>会话保持</dt><dd>{text(content.sessionAffinity)}</dd></div></dl><p>已发布的是配置声明，实际运行状态以对应任务与实例记录为准。</p></section><section className="f3-detail-card"><h2>本次引用</h2><p>能力保留此固定版本；已有新版本不会自动替换本次引用。</p><details><summary>查看版本与配置依据</summary><dl><div><dt>资源</dt><dd>{id}</dd></div><div><dt>版本</dt><dd>{revision}</dd></div><div><dt>内容标识</dt><dd>{digest}</dd></div></dl><pre>{JSON.stringify(content,null,2)}</pre></details></section></>}
 </main>;
}
