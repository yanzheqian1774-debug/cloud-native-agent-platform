import {WorkTeamContext} from '../teams/WorkTeamContext';
import {pageScrollTop,scrollPageTo} from './pageScroll';
import {ExecutionRuntimeSection} from '../digital-employees/EmployeeExecutionTrace';
import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {readCurrentWork,readSelectedWork,pendingQuestions,terminalWork,type CurrentWork} from './currentWorkReadback';
import {PreparedDeliverySummary} from './PreparedDeliverySummary';
import {ExecutionWorkView} from './ExecutionWorkView';
import {readViewString,saveViewString,useViewString} from './workViewState';
import {artifactMatchesSource} from './artifactProvenance';
import {formatTime} from '../journey/formatTime';
import './CurrentWorkDirectory.css';

const states:Record<string,string>={SUCCEEDED:'执行完成',RUNNING:'正在推进',QUEUED:'已排队',PENDING:'尚未启动',FAILED:'需要核查',RECOVERY_REQUIRED:'结果待核实',UNKNOWN:'结果未知',OUTCOME_UNKNOWN:'结果未知',CANCELLED:'已取消',CANCELED:'已取消'};
const labels:Record<string,string>={CONFIRMED_SOLVED:'业务已确认解决',UNDETERMINED:'业务结论尚未判定',NOT_SOLVED:'业务问题尚未解决'};
const conversationHref=(w:CurrentWork)=>'/work?'+new URLSearchParams({conversation:w.conversation});
function questionLabel(question:string){
 if(/(?:还是|或者|或).{0,40}(?:规范|口径|范围)|(?:规范|口径|范围).{0,40}(?:还是|或者|或)/.test(question))return '需确认口径';
 if(/(?:请|需要).{0,12}(?:上传|提供|补充).{0,20}(?:资料|文件|文档|数据)/.test(question))return '需补充资料';
 return '需确认信息';
}
function workState(w:CurrentWork,now:number){return pendingQuestions(w,now).length?'待你补充':states[w.execution.progress?.state??'']??'状态待读取'}
function summary(w:CurrentWork){
 const readable=w.execution.artifacts.filter(a=>a.contentAccess==='AUTHORIZED'&&artifactMatchesSource(a.content??'',w.execution.preparation.source_snapshot));
 for(const a of readable){try{const r=JSON.parse(a.content??'');if(r.operation==='RENDER_REPORT'&&r.documentReview&&Array.isArray(r.documentReview.missingSections)&&Array.isArray(r.documentReview.incompleteSections))return `文档检查发现 ${r.documentReview.missingSections.length} 项缺失、${r.documentReview.incompleteSections.length} 项待补充；可阅读报告与原文依据。`}catch{/* Malformed content never becomes a result. */}}
 return w.execution.artifacts.length?`已有 ${w.execution.artifacts.length} 份保存产物，其中 ${readable.length} 份已核对读取权限与来源；可查看记录和适用范围。`:'尚未形成可交付产物，当前进度与输入记录可追溯。';
}
const updated=(w:CurrentWork)=>[...w.execution.events.map(e=>e.created_at),...w.execution.artifacts.map(a=>a.created_at)].filter(v=>Number.isFinite(Date.parse(v))).sort().at(-1)??'';
function Badge({children}:{children:string}){return <span className="f3-work-badge">{children}</span>}
function Empty({text}:{text:string}){return <section className="f3-work-empty"><p>{text}</p></section>}

export function CurrentWorkDirectory({outcomes=false,attention=false}:{outcomes?:boolean;attention?:boolean}){
 const [params,setParams]=useSearchParams(),selected=params.get('work')??'',originHint=params.get('origin')??'',query=params.get('q')??'',filter=params.get('filter')??(outcomes?'accepted':'all');
 const [data,setData]=useState<Awaited<ReturnType<typeof readCurrentWork>>|null>(null),[error,setError]=useState(''),[version,setVersion]=useState(0),[clock,setClock]=useState(()=>Date.now());
 const returnKey=data?data.scope+':directory:'+(attention?'attention':outcomes?'outcomes':'tasks')+':'+filter+':'+query:undefined;
 const restore=useRef<{top:number;digest:string}|null>(null),main=useRef<HTMLElement>(null);
 useEffect(()=>{if(selected)return;const controller=new AbortController();let live=true,timer:ReturnType<typeof setTimeout>|undefined;const expired=()=>{live=false;setData(null);setError('登录已失效，请重新登录后读取。')};window.addEventListener('workbench-session-expired',expired);
  void readCurrentWork(value=>{if(live)setData(previous=>previous&&!previous.loading?previous:value)},controller.signal,{includeCompletedQuestions:attention}).then(value=>{if(live){setData(value);setError('');if(value.works.some(w=>!terminalWork.has(w.execution.progress?.state??'')))timer=setTimeout(()=>{if(live&&document.visibilityState==='visible')setVersion(v=>v+1)},10000)}}).catch(e=>{if(live){setData(null);setError(e instanceof Error?e.message:'当前工作读取失败')}});
  return()=>{live=false;controller.abort();if(timer)clearTimeout(timer);window.removeEventListener('workbench-session-expired',expired)};
 },[version,attention,outcomes,selected]);
 useEffect(()=>{const refresh=()=>{setData(null);setVersion(v=>v+1)};window.addEventListener('focus',refresh);const timer=setInterval(()=>setClock(Date.now()),1000);return()=>{window.removeEventListener('focus',refresh);clearInterval(timer)}},[]);
 useLayoutEffect(()=>{if(!selected&&data&&!data.loading){let previous=restore.current;try{previous=previous??JSON.parse(readViewString(returnKey,'return','null'))}catch{/* Damaged view state cannot choose a work record. */}if(!previous||!Number.isFinite(previous.top)||typeof previous.digest!=='string')return;restore.current=null;saveViewString(returnKey,'return','');const target=previous;const frame=requestAnimationFrame(()=>{saveViewString(returnKey,'page-scroll',String(target.top));saveViewString(returnKey,'page-focus',target.digest);scrollPageTo(target.top);main.current?.querySelector<HTMLElement>(`[data-open-work="${CSS.escape(target.digest)}"]`)?.focus({preventScroll:true})});return()=>cancelAnimationFrame(frame)}},[selected,data,returnKey]);
 const listReady=!selected&&!!data&&!data.loading;
 useLayoutEffect(()=>{
  if(!listReady||!returnKey)return;
  const node=main.current?.closest<HTMLElement>('.skill-frame-content');if(!node)return;
  let ready=false;
  const frame=requestAnimationFrame(()=>{const saved=Number(readViewString(returnKey,'page-scroll','0'));if(Number.isFinite(saved))node.scrollTop=saved;const focused=readViewString(returnKey,'page-focus','');if(focused)main.current?.querySelector<HTMLElement>(`[data-open-work="${CSS.escape(focused)}"]`)?.focus({preventScroll:true});ready=true});
  const save=()=>{if(ready&&!restore.current)saveViewString(returnKey,'page-scroll',String(node.scrollTop))};
  const focus=(event:FocusEvent)=>{const target=event.target;if(target instanceof HTMLElement&&target.dataset.openWork)saveViewString(returnKey,'page-focus',target.dataset.openWork)};
  node.addEventListener('scroll',save);node.addEventListener('focusin',focus);
  return()=>{cancelAnimationFrame(frame);node.removeEventListener('scroll',save);node.removeEventListener('focusin',focus)};
 },[listReady,returnKey]);
 const works=data?.works??[],waiting=works.filter(w=>pendingQuestions(w,clock).length),completed=works.filter(w=>w.execution.progress?.state==='SUCCEEDED');
 const matches=works.filter(w=>(w.problem.title+' '+w.execution.preparation.semantics.title).toLocaleLowerCase().includes(query.toLocaleLowerCase()));
 const questions=matches.flatMap(w=>w.questions.filter(q=>filter==='done'?q.answer!==null:pendingQuestions(w,clock).some(p=>p.questionKey===q.questionKey)).map(q=>({w,q})));
 const visible=outcomes?(filter==='stage'?matches:[]):matches.filter(w=>filter==='waiting'?pendingQuestions(w,clock).length:filter==='completed'?w.execution.progress?.state==='SUCCEEDED':true);
 function choose(patch:Record<string,string>){const next=new URLSearchParams(params);for(const [k,v] of Object.entries(patch)){if(v)next.set(k,v);else next.delete(k)}setParams(next,{replace:patch.q!==undefined})}
 function open(w:CurrentWork){restore.current={top:pageScrollTop(),digest:w.execution.digest};saveViewString(returnKey,'return',JSON.stringify(restore.current));choose({work:w.execution.digest,origin:w.conversation});scrollPageTo(0)}
 function refresh(){setData(null);setError('');setVersion(v=>v+1)}
 const title=attention?'待我处理':outcomes?'成果与记录':'我的任务';
 const tabs=outcomes?[['accepted','已确认成果'],['stage','阶段与执行记录']]:attention?[['all','待你处理'],['done','已处理']]:[['all','全部任务'],['waiting','等待处理'],['completed','已完成']];
 return <main className="f3-work-page" ref={main} data-observed-at={clock}>
  <header className="f3-work-heading"><div><small>{attention?'MY INBOX':outcomes?'DELIVERABLES':'MY WORK'}</small><h1>{selected?(outcomes?'成果预览':'任务详情'):title}</h1><p>{attention?'只呈现当前需要你回答的问题，回答后继续原任务。':outcomes?'先查看可交付内容；业务确认与阶段记录分别呈现。':'看清正在推进的工作，及时处理阻塞。'}</p></div>{selected?<button onClick={()=>choose({work:'',origin:'',workView:''})}>返回{title}</button>:<Link className="f3-work-primary" to="/work">发起新工作</Link>}</header>
  <div className="f3-work-scope"><span>当前可读范围</span><p>按当前身份读取已关联会话的真实执行记录。固定工作及其他领域审批尚未汇入本列表。</p><button onClick={refresh}>重新读取</button></div>
  {!selected&&data?.loading&&<p role="status">已读记录先行展示，正在继续核对其余会话；数量尚未完整。</p>}
  {!selected&&data?.limited&&<p role="status" className="f3-work-notice">部分关联记录当前未能读取。本页只展示已核实记录，不能据此认定全部工作均已处理。</p>}
  {selected?<SelectedWork key={selected+':'+originHint+':'+version} digest={selected} origin={originHint} version={version} now={clock}/>:error?<section className="f3-work-empty" role="alert"><h2>当前工作暂不可读</h2><p>{error}</p><button onClick={refresh}>重新核对</button></section>:!data?<p role="status">正在读取已保存工作与当前权限…</p>:<>
   {!attention&&!outcomes&&<section className="f3-work-metrics" aria-label="任务记录概览">{[['全部任务',works.length,'当前已读执行记录'],['等待处理',waiting.length,'仍有效的必要追问'],['执行完成',completed.length,'业务结论另行核验'],['固定工作','—','尚未汇入本列表']].map(([label,note,hint])=><article key={label}><span>{label}</span><strong>{note}</strong><small>{hint}</small></article>)}</section>}
   <div className="f3-work-toolbar"><nav aria-label={title+'分组'}>{tabs.map(([id,label])=><button key={id} aria-pressed={filter===id} onClick={()=>choose({filter:id})}>{label}</button>)}</nav><label>搜索工作<input value={query} onChange={e=>choose({q:e.target.value})} placeholder="按目标或任务名称搜索"/></label></div>
   {attention?<div className="f3-work-inbox"><section>{questions.length?questions.map(({w,q})=><article className="f3-work-decision" key={w.execution.digest+q.questionKey}><header><Badge>{q.answer!==null?'已回答':questionLabel(q.question)}</Badge><small>{q.answer===null?'回答期限：'+formatTime(q.expiresAt):'已由原执行记录确认接收'}</small></header><h2>{w.problem.title}</h2><p>{q.question}</p><dl><dt>处理事项</dt><dd>{q.answer!==null?'已回答：'+q.answer:'请确认以上必要信息'}</dd><dt>判断依据</dt><dd>来自本次执行保存的原问题，未自动替你作选择。</dd><dt>影响范围</dt><dd>回答交回目标会话，由原执行核验问题版本和授权；本列表不提交回答。</dd></dl><footer><button data-open-work={w.execution.digest} onClick={()=>open(w)}>查看任务依据</button><Link className="f3-work-primary" to={conversationHref(w)}>{q.answer!==null?(w.originVerified?'查看原处理记录':'查看关联记录'):w.originVerified?'在原会话回答':'到关联会话核对'}</Link></footer></article>):<Empty text={filter==='done'?'当前已读记录中没有已回答事项。':'当前已读记录中没有仍有效的未回答追问。'}/>}</section><aside className="f3-work-card"><h2>处理之后会怎样</h2><p>确认必要信息后，在原会话继续原任务。</p><p>已回答或已过期的问题不会继续列为待处理。排队、模型等待和系统格式失败不会生成用户待办。</p><p>返回本页后重新读取，以后台接收结果为准。</p></aside></div>:outcomes?<div className="f3-work-results">{visible.length?visible.map(w=><article className="f3-work-result" key={w.execution.digest}><div className="f3-work-report-preview"><small>已保存产物 · 按原输入快照</small><h2>{w.problem.title}</h2><p>{summary(w)}</p></div><Badge>{'阶段与执行记录'}</Badge><h2>{w.problem.title}</h2><p>{labels[w.execution.outcome?.businessResolution??'']??'业务评价待读取'}</p><dl><dt>来源</dt><dd>{w.originVerified?'原会话':'关联会话'} · {w.conversation.slice(0,8)}</dd><dt>更新</dt><dd>{formatTime(updated(w))}</dd><dt>版本</dt><dd>本次计划 v{w.execution.preparation.plan_version} · 输入和资源引用已保存</dd></dl><footer><small>报告可读不等于业务已批准</small><button className="f3-work-primary" data-open-work={w.execution.digest} onClick={()=>open(w)}>阅读成果与依据</button></footer></article>):<Empty text={filter==='stage'?'当前分组没有可读取的阶段记录。':'成果验收状态尚未接通。已生成的报告请在“阶段与执行记录”中阅读。'}/>}</div>:visible.length?<div className="f3-work-table-wrap"><table className="f3-work-table"><thead><tr><th>任务与下一步</th><th>承担者 / 固定版本</th><th>阶段 / 状态</th><th>来源 / 更新</th><th>查看</th></tr></thead><tbody>{visible.map(w=><tr key={w.execution.digest}><td><strong>{w.problem.title}</strong><p>{summary(w)}</p><small>下一步：{pendingQuestions(w,clock).length?'在原会话回答必要信息':w.execution.progress?.state==='SUCCEEDED'?'阅读成果并追溯依据':'查看已保存进度与阻塞原因'}</small></td><td><span>{new Set(w.execution.preparation.participants.map(p=>p.instance_id)).size} 个本次参与实例</span><small>计划 v{w.execution.preparation.plan_version} · 固定资源快照</small></td><td><Badge>{workState(w,clock)}</Badge><small>{w.execution.progress?.tasks.filter(t=>t.state==='SUCCEEDED').length??'—'} / {w.execution.preparation.semantics.tasks.length} 项任务执行完成</small></td><td><span>会话 · {w.conversation.slice(0,8)}</span><small>{formatTime(updated(w))}</small></td><td><button data-open-work={w.execution.digest} onClick={()=>open(w)}>查看任务</button></td></tr>)}</tbody></table></div>:<Empty text="当前筛选下没有可读取的执行记录。"/>}
   {!attention&&!outcomes&&data.unlinkedProblems>0&&<p className="f3-work-footnote">另有 {data.unlinkedProblems} 个可读问题尚未取得关联执行记录，未计为任务。可从原会话继续核对。</p>}
  </>}
 </main>;
}
export function SelectedWork({digest,origin,version,now}:{digest:string;origin:string;version:number;now:number}){
 const [value,setValue]=useState<Awaited<ReturnType<typeof readSelectedWork>>|null>(null),[error,setError]=useState('');
 useEffect(()=>{let live=true,timer:ReturnType<typeof setTimeout>|undefined;const controller=new AbortController();const expired=()=>{live=false;controller.abort();setValue(null);setError('登录已失效，请重新登录后读取。')};window.addEventListener('workbench-session-expired',expired);
  const read=()=>readSelectedWork(digest,origin,controller.signal).then(v=>{if(live){setValue(v);setError('');if(!terminalWork.has(v.work.execution.progress?.state??''))timer=setTimeout(()=>{if(live&&document.visibilityState==='visible')void read()},10000)}}).catch(e=>{if(live){setValue(null);setError(e instanceof Error?e.message:'当前任务读取失败')}});void read();
  return()=>{live=false;controller.abort();if(timer)clearTimeout(timer);window.removeEventListener('workbench-session-expired',expired)};
 },[digest,origin,version]);
 return error?<section className="f3-work-empty" role="alert"><h2>当前无法读取这项工作</h2><p>{error}</p><p>未替换为其他任务或最新版本，可重新读取后核对。</p></section>:value?<WorkDetail work={value.work} scope={value.scope} now={now}/>:<p role="status">正在读取本次任务与固定版本；无需遍历其他会话。</p>;
}
function WorkDetail({work:w,scope,now}:{work:CurrentWork;scope:string;now:number}){
 const view=w.execution,key=scope+':work-directory:'+view.digest;
 const [params,setParams]=useSearchParams(),requestedResult=params.get('workView')==='result';
 const [storedTab,setStoredTab]=useViewString(key,'tab',view.progress?.state==='SUCCEEDED'&&view.artifacts.length?'result':'process'),[artifact,setArtifact]=useViewString(key,'artifact'),[origin,setOrigin]=useViewString(key,'artifactReturn','result');
 const tab=requestedResult?'result':storedTab;
 function setTab(value:string){setStoredTab(value);if(requestedResult)setParams(previous=>{const next=new URLSearchParams(previous);next.delete('workView');return next},{replace:true})}
 function inspect(id:string,from='result'){saveViewString(key,'artifactScroll',String(pageScrollTop()));setOrigin(from);setArtifact(id);setTab('result')}
 function closeArtifact(){const id=artifact;setArtifact('');setTab(origin==='process'?'process':'result');requestAnimationFrame(()=>{scrollPageTo(Number(readViewString(key,'artifactScroll','0')));document.querySelector<HTMLElement>(`${origin==='process'?'.work-artifact-open':'.artifact-file-open'}[data-artifact-id="${CSS.escape(id)}"]`)?.focus({preventScroll:true})})}
 const active=pendingQuestions(w,now);
 return <section className="f3-work-detail"><WorkTeamContext work={w}/><header><Badge>{workState(w,now)}</Badge><h2>{w.problem.title}</h2><p>{summary(w)}</p>{w.conversation?<Link className="f3-work-primary" to={conversationHref(w)+(['teamRef','teamRevision','teamDigest'].every(k=>params.has(k))?'&'+new URLSearchParams(Object.fromEntries(['teamRef','teamRevision','teamDigest'].map(k=>[k,params.get(k)!]))):'')}>{w.originVerified?(active.length?'在原会话回答并继续':'回到原会话'):'回到关联会话'}</Link>:<p className="f3-work-notice">原会话关联尚未核实，未提供替代跳转；本次任务与报告仍可按当前权限查看。</p>}</header>
  {active.map(q=><aside className="f3-work-notice" key={q.questionKey}><strong>需要补充的必要信息</strong><p>{q.question}</p><small>请在 {formatTime(q.expiresAt)} 前回原会话回答。</small></aside>)}
  <nav className="f3-work-tabs" aria-label="工作详情页签">{[['result','成果与记录'],['process','办理过程'],['basis','输入与版本依据']].map(([id,label])=><button key={id} aria-pressed={tab===id} onClick={()=>setTab(id)}>{label}</button>)}</nav>
  {tab==='result'?(view.progress?.state==='SUCCEEDED'&&view.artifacts.length?<PreparedDeliverySummary view={view} viewKey={key} selectedArtifact={artifact} onArtifact={id=>inspect(id)} onCloseArtifact={closeArtifact} query="" onReview={()=>setTab('basis')}/>:<Empty text={view.artifacts.length?`执行尚未完成，已有 ${view.artifacts.length} 份阶段产物记录；请查看办理过程与原会话中的实际返回。`:"尚未保存可交付产物，可查看办理过程。"}/>):tab==='process'?<><ExecutionWorkView view={view} viewKey={key} onArtifact={id=>inspect(id,'process')}/><ExecutionRuntimeSection digest={view.digest} conversationId={w.conversation} bindings={view.preparation.participants.map(t=>({taskId:t.task_id,instanceId:t.instance_id,assignmentId:t.assignment_id,runtimeInstanceId:t.runtime_instance_id??'',runtimeGeneration:t.runtime_generation??0}))}/></>:<section className="f3-work-card"><h3>本次输入与固定版本</h3><dl><dt>输入资料</dt><dd>{view.preparation.source_snapshot.resource_id} · {view.preparation.source_snapshot.revision_id}</dd><dt>计划版本</dt><dd>v{view.preparation.plan_version}</dd><dt>业务评价</dt><dd>{labels[view.outcome?.businessResolution??'']??'尚未取得评价记录'}</dd><dt>人工决定</dt><dd>{view.outcome?.confirmationId?'已有决定记录；不据此推断业务批准':'尚无已读的人工决定记录'}</dd></dl><h3>本次实际绑定</h3>{view.preparation.participants.map(p=><details key={p.task_id}><summary>{view.preparation.semantics.tasks.find(t=>t.task_id===p.task_id)?.title??'原任务'}</summary><dl><dt>参与实例</dt><dd>{p.instance_id}</dd><dt>数字人定义</dt><dd>{p.definition.resource_id} · {p.definition.revision_id}</dd><dt>技能版本</dt><dd>{p.skill.reference.resource_id} · {p.skill.reference.revision_id}</dd><dt>运行环境快照</dt><dd>{p.runtime_instance_id?`${p.runtime_instance_id} · ${p.runtime_generation??'版本未记录'}`:'原记录未提供运行实例快照，不追补当前配置。'}</dd></dl></details>)}</section>}
 </section>;
}
