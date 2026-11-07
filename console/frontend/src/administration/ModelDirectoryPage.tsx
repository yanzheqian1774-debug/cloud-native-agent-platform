import {useEffect,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {PageHeader,StatusBadge} from '../components/WorkspacePrimitives';
import {modelLink,readModelDirectory,type ModelDirectoryPage as ModelPage,type ModelIdentity} from '../api/modelDirectory';
import '../resources/TrustedResourceDirectory.css';
import '../resources/ResourceDetailWorkspace.css';
const labels:Record<string,string>={DRAFT:'草稿',VALIDATED:'验证通过',HUMAN_REVIEWED:'审核通过',PUBLISHED_ENABLED:'已发布并启用',PUBLISHED_DISABLED:'已发布并停用',DEPRECATED:'已弃用',REVOKED:'已撤销',NOT_RECORDED:'尚无生命周期记录'};
export function ModelDirectoryPage(){
 const [params,setParams]=useSearchParams(),[saved,setSaved]=useState<{key:string;value:ModelPage}|null>(null),[error,setError]=useState(''),[reload,setReload]=useState(0);
 const key=params.toString(),data=saved?.key===key?saved.value:null,selected=params.has('model')||params.has('revision')||params.has('digest');
 useEffect(()=>{
  let live=true,generation=0,timer:ReturnType<typeof setTimeout>|undefined;
  const abort=new AbortController(),withdraw=()=>{generation++;setSaved(null);setError('当前读取依据已失效，请重新核对。')};
  const focus=()=>{withdraw();setReload(n=>n+1)};
  const turn=generation;
  void readModelDirectory(new URLSearchParams(key),abort.signal).then(({value,until})=>{if(live&&generation===turn){setSaved({key,value});setError('');timer=setTimeout(withdraw,Math.min(until-Date.now(),2147483647))}}).catch(e=>{if(live&&!abort.signal.aborted){setSaved(null);setError(e instanceof Error?e.message:'MODEL_DIRECTORY_UNAVAILABLE')}});
  window.addEventListener('focus',focus);window.addEventListener('workbench-session-expired',withdraw);
  return()=>{live=false;generation++;abort.abort();clearTimeout(timer);window.removeEventListener('focus',focus);window.removeEventListener('workbench-session-expired',withdraw)};
 },[key,reload]);
 const back=new URLSearchParams(params);for(const name of ['model','revision','digest'])back.delete(name);
 const item=data?.item;
 function refresh(){setSaved(null);setError('');setReload(n=>n+1)}
 return <main className="trusted-resources"><PageHeader eyebrow="平台管理 / 模型" title="模型中心" description="查看当前账号可读的模型版本、声明与生命周期记录。" actions={<button className="trusted-resource-action" onClick={refresh}>重新核对</button>}/>
 <section className="trusted-resource-list"><p>来源：模型管理中的已保存记录。发布与启用只表示管理状态；当前页面未接入实时可用性、测量价格或费用。</p>
 {selected?<Link to={'/models'+(back.size?'?'+back:'')}>返回原筛选列表</Link>:<form className="trusted-resource-filters" onSubmit={e=>e.preventDefault()}><label>搜索模型<input aria-label="搜索模型" placeholder="输入模型名称" value={params.get('query')??''} onChange={e=>{const next=new URLSearchParams();if(e.target.value)next.set('query',e.target.value);setSaved(null);setError('');setParams(next)}}/></label><p>仅显示当前账号获准读取的版本，列表不代表企业全部模型。</p></form>}
 {error?<div role="alert" className="trusted-resource-empty"><h2>模型记录暂未读回</h2><p>当前读取条件未满足，不能据此判断没有记录。原版本仍保留。</p><details><summary>查看核查依据</summary><code>{error}</code></details></div>:!data?<p className="trusted-resource-empty" role="status">正在核对模型记录…</p>:selected&&item?<section aria-label="模型准确版本" className="trusted-resource-detail"><section><h2>{item.name}</h2><StatusBadge>{labels[item.state]??'状态待核对'}</StatusBadge><p>版本 {item.revision} · {item.isCurrentRevision?'当前修订':'历史修订'}</p><h3>声明的能力与兼容性</h3><p>{item.capabilities.join('、')||'尚未声明'}</p><p>{item.compatibility.join('、')||'尚未声明兼容性'}</p><p>声明不替代实际调用或评估结论。</p><h3>声明的调用限制</h3>{item.invocationLimits.length?<ul>{item.invocationLimits.map(v=><li key={v.name}>{v.name}：{v.value} {v.unit}</li>)}</ul>:<p>尚未声明</p>}</section><section><h3>准确版本依据</h3><dl><dt>模型</dt><dd>{item.modelId}</dd><dt>修订</dt><dd>{item.revisionId}</dd><dt>内容摘要</dt><dd>{item.digest}</dd><dt>保存时间</dt><dd>{item.createdAt}</dd><dt>生命周期记录</dt><dd>{item.lifecycleHighWater?'已记录至第 '+item.lifecycleHighWater.ordinal+' 条':'尚无记录'}</dd></dl><details><summary>查看绑定的配置版本</summary><Identity label="Provider" value={item.provider}/><Identity label="Endpoint" value={item.endpoint}/><Identity label="Profile" value={item.connectionProfile}/></details><p>实际可用性：不可度量；价格：不可度量。</p></section></section>:!data.items?.length?<div className="trusted-resource-empty"><h2>当前筛选下暂无可读模型版本</h2><p>可调整名称筛选，或重新核对当前账号的读取范围。</p></div>:<><div className="trusted-resource-table"><table><caption>当前可读的模型版本</caption><thead><tr><th>模型</th><th>版本</th><th>生命周期</th><th>声明</th><th>详情</th></tr></thead><tbody>{data.items.map(v=><tr key={v.modelId+'|'+v.revisionId+'|'+v.digest}><td><strong>{v.name}</strong></td><td>{v.revision} · {v.isCurrentRevision?'当前修订':'历史修订'}</td><td>{labels[v.state]??'待核对'}</td><td>{v.capabilities.join('、')||'尚未声明'}</td><td><Link to={modelLink(v,params)}>查看准确版本</Link></td></tr>)}</tbody></table></div>{data.nextCursor&&<button className="trusted-resource-more" onClick={()=>{const next=new URLSearchParams(params);next.set('cursor',data.nextCursor!);setSaved(null);setError('');setParams(next)}}>下一页可读版本</button>}</>}
 </section></main>;
}
function Identity({label,value}:{label:string;value:ModelIdentity}){return <dl><dt>{label}</dt><dd>{value.provider_id??value.endpoint_id??value.profile_id}</dd><dt>版本</dt><dd>{value.revision_id}</dd><dt>内容摘要</dt><dd>{value.digest}</dd></dl>}
