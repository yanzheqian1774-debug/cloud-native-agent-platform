import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {capabilitySession,listCapabilities,type CapabilityItem} from '../api/businessCapabilities';
import {workbenchPrincipalKey} from '../api/digitalEmployees';

export function CapabilityFavorites(){
 const [items,setItems]=useState<CapabilityItem[]>([]),[loading,setLoading]=useState(true),[error,setError]=useState(''),[more,setMore]=useState(false),[refresh,setRefresh]=useState(0);
 useEffect(()=>{
  let active=true;const controller=new AbortController();
  const load=async()=>{
   setLoading(true);setError('');setItems([]);setMore(false);
   try{
    const session=await capabilitySession(controller.signal);
    const result=await listCapabilities(workbenchPrincipalKey(session),null,controller.signal,{query:'',domain:'',favoritesOnly:true});
    if(active){setItems(result.items.slice(0,3));setMore(result.items.length>3||!!result.nextCursor)}
   }catch{if(active)setError('收藏能力暂未读取成功，请重新读取。')}
   finally{if(active)setLoading(false)}
  };
  const withdraw=()=>{active=false;controller.abort();setItems([]);setMore(false);setLoading(false);setError('登录已失效，请重新登录后查看收藏。')};
  const focus=()=>setRefresh(value=>value+1);
  window.addEventListener('workbench-session-expired',withdraw);window.addEventListener('focus',focus);void load();
  return()=>{active=false;controller.abort();window.removeEventListener('workbench-session-expired',withdraw);window.removeEventListener('focus',focus)};
 },[refresh]);
 return <section className="f3-home-card" aria-label="我的收藏能力"><header><h2>我的收藏能力</h2><Link to="/capabilities">查看能力目录</Link></header>
  {loading&&<p role="status">正在读取收藏能力…</p>}
  {error&&<p role="alert">{error}</p>}
  {items.map(item=><article key={item.capabilityId}><div><h3>{item.title}</h3><p>{item.intent}</p><p>{item.currentPublished?'已发布':'草稿'} · {item.businessDomain??'未设置领域'}</p></div><Link to={'/capabilities?'+new URLSearchParams({capability:item.capabilityId,revision:item.revisionId,digest:item.digest,returnHome:'1'})}>查看与使用</Link></article>)}
  {!loading&&!error&&!items.length&&<p>暂无可读取的收藏能力。可到能力目录收藏常用能力。</p>}
  {more&&<p>此处展示前三项收藏，其余请到能力目录查看。</p>}
  <button disabled={loading} onClick={()=>setRefresh(value=>value+1)}>刷新收藏</button><p>收藏不授予额外访问或执行权限。</p>
 </section>;
}
