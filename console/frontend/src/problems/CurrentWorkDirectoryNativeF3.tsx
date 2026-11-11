import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {SelectedWork} from './CurrentWorkDirectoryF3';
import {directoryTimeoutMessage,readDirectoryPage,type DirectoryItem} from './currentWorkDirectoryApi';
import {readViewString,saveViewString} from './workViewState';
import {pageScrollTop,scrollPageTo} from './pageScroll';
import {formatTime} from '../journey/formatTime';
import './CurrentWorkDirectory.css';

const stateLabels:Record<string,string>={SUCCEEDED:'执行完成',RUNNING:'正在推进',PENDING:'准备执行',CANCEL_REQUESTED:'正在取消',FAILED:'需要核查',CANCELLED:'已取消',RECOVERY_REQUIRED:'结果待核实'};
export function CurrentWorkDirectoryNative(){
 const [params,setParams]=useSearchParams(),selected=params.get('work')??'',origin=params.get('origin')??'',scope=params.get('scope')??'',query=params.get('q')??'',filter=params.get('filter')??'all',cursor=params.get('cursor')??'';
 const pageNumber=Math.max(1,Number(params.get('page'))||1),requestKey=JSON.stringify([scope,query,filter,cursor]);
 const [read,setRead]=useState<(Awaited<ReturnType<typeof readDirectoryPage>>&{requestKey:string})|null>(null),[error,setError]=useState(''),[version,setVersion]=useState(0),[clock,setClock]=useState(Date.now);
 const main=useRef<HTMLElement>(null),data=read?.requestKey===requestKey?read:null;
 const page=data?.page,viewKey=data?data.viewKey+':'+page?.scopeFilter+':'+filter+':'+query:undefined,positionKey=viewKey+':'+cursor;
 function choose(patch:Record<string,string>,replace=false){setRead(null);setError('');const next=new URLSearchParams(params);for(const[k,v]of Object.entries(patch)){if(v)next.set(k,v);else next.delete(k)}setParams(next,{replace})}
 function refresh(){setRead(null);setError('');setVersion(v=>v+1)}
 useEffect(()=>{
  if(selected)return;
  const controller=new AbortController();let live=true,poll:ReturnType<typeof setTimeout>|undefined;
  const expired=()=>{live=false;controller.abort();setRead(null);setError('登录已失效，请重新登录。')};
  window.addEventListener('workbench-session-expired',expired);
  const debounce=setTimeout(()=>{setRead(null);setError('');void readDirectoryPage({scope,query,state:filter,cursor},controller.signal).then(value=>{
   if(!live)return;setRead({...value,requestKey});setError('');
   if(value.page.items.some(i=>['PENDING','RUNNING','CANCEL_REQUESTED'].includes(i.executionState)))poll=setTimeout(()=>{if(live&&document.visibilityState==='visible')setVersion(v=>v+1)},10000);
  }).catch(e=>{if(live){setRead(null);setError(e instanceof Error?e.message:'读取失败')}})},200);
  return()=>{live=false;controller.abort();clearTimeout(debounce);if(poll)clearTimeout(poll);window.removeEventListener('workbench-session-expired',expired)};
 },[scope,query,filter,cursor,selected,version,requestKey]);
 useEffect(()=>{const focus=()=>{setRead(null);setError('');setVersion(v=>v+1)};window.addEventListener('focus',focus);const timer=setInterval(()=>setClock(Date.now()),1000);return()=>{window.removeEventListener('focus',focus);clearInterval(timer)}},[]);
 useLayoutEffect(()=>{
  if(selected||!data||!viewKey)return;
  saveViewString(viewKey,'cursor-'+pageNumber,cursor);
  const node=main.current?.closest<HTMLElement>('.skill-frame-content');if(!node)return;
  let ready=false;
  const frame=requestAnimationFrame(()=>{const table=main.current?.querySelector<HTMLElement>('.f3-work-table-wrap');if(table)table.scrollLeft=Number(readViewString(positionKey,'table-scroll','0'))||0;const top=Number(readViewString(positionKey,'scroll','0'));if(Number.isFinite(top))scrollPageTo(top);const digest=readViewString(positionKey,'focus');if(digest)main.current?.querySelector<HTMLElement>(`[data-open-work="${CSS.escape(digest)}"]`)?.focus({preventScroll:true});ready=true});
  const save=()=>{if(ready)saveViewString(positionKey,'scroll',String(pageScrollTop()))};node.addEventListener('scroll',save);
  return()=>{cancelAnimationFrame(frame);node.removeEventListener('scroll',save)};
 },[selected,data,viewKey,positionKey,cursor,pageNumber]);
 function open(item:DirectoryItem){saveViewString(positionKey,'table-scroll',String(main.current?.querySelector<HTMLElement>('.f3-work-table-wrap')?.scrollLeft??0));saveViewString(positionKey,'scroll',String(pageScrollTop()));saveViewString(positionKey,'focus',item.preparationDigest);choose({work:item.preparationDigest,origin:item.originConversationId??''});scrollPageTo(0)}
 const scopeLabel=page?.scopeFilter==='initiated'?'我发起的':page?.scopeFilter==='visible'?'当前可见':'正在核对范围';
 const previous=readViewString(viewKey,'cursor-'+(pageNumber-1),'__missing__');
 return <main className="f3-work-page f3-native-directory" ref={main}>
  <header className="f3-work-heading"><div><small>MY WORK</small><h1>{selected?'任务详情':'我的任务'}</h1><p>看清正在推进的工作，及时处理阻塞。</p></div>{selected?<button onClick={()=>choose({work:'',origin:'',workView:''})}>返回我的任务</button>:<Link className="f3-work-primary" to="/work">发起新工作</Link>}</header>

  {selected?<SelectedWork key={selected+':'+origin+':'+version} digest={selected} origin={origin} version={version} now={clock}/>:<>
   {page&&<section className="f3-work-metrics" aria-label="任务记录概览">{[['筛选内任务',page.total,scopeLabel],['待补充任务',page.questionStatusComplete===true?page.counts.waiting:'待核实',page.questionStatusComplete===true?'当前筛选内的必要追问':'部分任务的追问状态暂不可读取'],['执行完成',page.counts.completed,'业务结论另行核验'],['固定工作','—','尚未汇入本列表']].map(([label,count,hint])=><article key={label}><span>{label}</span><strong>{count}</strong><small>{hint}</small></article>)}</section>}
   <div className="f3-work-toolbar"><nav aria-label="我的任务分组">{[['all','全部任务'],['waiting','待补充任务'],['completed','执行完成']].map(([id,label])=><button key={id} aria-pressed={filter===id} onClick={()=>choose({filter:id,cursor:'',page:''})}>{label}</button>)}</nav><label>搜索工作<input value={query} onChange={e=>choose({q:e.target.value,cursor:'',page:''},true)} placeholder="按目标或任务名称搜索"/></label><div className="f3-native-scope"><label>查看范围 <select aria-label="查看范围" value={scope||page?.scopeFilter||''} onChange={e=>{saveViewString(data?.viewKey,'scope',e.target.value);choose({scope:e.target.value,cursor:'',page:''})}}><option value="" disabled>正在核对</option><option value="visible">当前可见</option><option value="initiated">我发起的</option></select></label><p>{scopeLabel} · 按当前权限读取执行记录。固定工作尚未汇入。</p><button onClick={refresh}>重新读取</button></div></div>
   {error?<section className="f3-work-empty" role="alert"><h2>当前工作暂不可读</h2><p>{error===directoryTimeoutMessage?directoryTimeoutMessage:"本次未取得完整记录，请重新核对。"}</p><details><summary>查看诊断信息</summary><p>{error}</p></details><button onClick={()=>{choose({cursor:'',page:''});refresh()}}>重新核对</button></section>:!page?<p role="status">正在读取任务、当前权限和保存结果…</p>:<>

    {filter!=='completed'&&page.questionStatusComplete!==true&&<p role="status">部分任务的追问状态暂不可读取，待补充列表可能不完整；可在全部任务中查看已保存进度。</p>}
    {page.items.length?<div className="f3-work-table-wrap"><table className="f3-work-table"><colgroup><col style={{width:'38%'}}/><col style={{width:'21%'}}/><col style={{width:'14%'}}/><col style={{width:'18%'}}/><col style={{width:'9%'}}/></colgroup><thead><tr><th>任务与下一步</th><th>承担者 / 固定版本</th><th>阶段 / 状态</th><th>来源 / 更新</th><th>查看</th></tr></thead><tbody>{page.items.map(item=><tr key={item.workflowRunId}><td><strong>{item.title}</strong><p>{item.artifactCount?`已有 ${item.artifactCount} 份保存产物；查看任务后核对内容与来源。`:'尚未形成可交付产物。'}</p><small>下一步：{item.pendingQuestionCount?'在原会话回答必要信息':item.executionState==='SUCCEEDED'?'阅读成果并追溯依据':'查看已保存进度与阻塞原因'}</small></td><td><span>{item.participantCount==null?'查看实际参与实例':`${item.participantCount} 个本次参与实例`}</span><small>{item.planVersion==null?'固定资源快照':`计划 v${item.planVersion} · 固定资源快照`}</small><small>发起人：{item.initiatorId??'原记录待核实'}</small></td><td><span className="f3-work-badge">{item.pendingQuestionCount?'待你补充':stateLabels[item.executionState]??'结果待核实'}</span><small>{item.completedTaskCount??'—'} / {item.taskCount??'—'} 项任务执行完成</small></td><td><span>{item.originConversationId?(item.originVerified?'原会话':'关联会话')+' · '+item.originConversationId.slice(0,8):'原会话未核实'}</span><small>{formatTime(item.updatedAt??item.createdAt)}</small></td><td><button data-open-work={item.preparationDigest} onClick={()=>open(item)}>查看任务</button></td></tr>)}</tbody></table></div>:<section className="f3-work-empty"><p>{filter==='waiting'&&page.questionStatusComplete!==true?'暂未发现可确认的待补充任务，尚不能判断是否全部无需补充。':'当前筛选下没有可读取的执行记录。'}</p></section>}
    <nav className="f3-work-toolbar" aria-label="任务分页"><span>{scopeLabel} · 共 {page.total} 条 · 第 {pageNumber} 页</span><div><button disabled={pageNumber<=1||previous==='__missing__'} onClick={()=>choose({cursor:previous,page:String(pageNumber-1)})}>上一页</button><button disabled={!page.nextCursor} onClick={()=>choose({cursor:page.nextCursor??'',page:String(pageNumber+1)})}>下一页</button></div></nav>
   </>}
  </>}
 </main>;
}
