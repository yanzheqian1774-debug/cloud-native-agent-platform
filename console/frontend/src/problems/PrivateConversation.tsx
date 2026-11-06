import {useCallback,useEffect,useRef,useState} from 'react';
import {Link,useLocation,useNavigate} from 'react-router-dom';
import {conversationRequest,type PrivateConversation as RecordView,type WorkLink} from '../api/privateConversation';
import {readWorkbenchSession,readBusinessProblem,listBusinessProblems,type WorkbenchSession,type BusinessProblemRevision} from '../api/businessWorkspace';
import {conversationScope} from './conversationViewState';
import {readViewString,saveViewString,useViewString} from './workViewState';
import {ConversationFrame} from './ProblemConversation';
import {PreparedExecutionPanel} from './PreparedExecutionPanel';
import {ProblemWorkspacePage} from './ProblemWorkspacePage';
import {formatTime} from '../journey/formatTime';
import './PrivateConversation.css';

export function ConversationEntry(){
 const loc=useLocation(),params=new URLSearchParams(loc.search),[enabled,setEnabled]=useState<boolean|null>(null),[error,setError]=useState('');
 useEffect(()=>{let live=true;conversationRequest<{enabled:boolean}>('/capabilities').then(r=>{if(live)setEnabled(r.enabled)}).catch(e=>{if(live)setError(String(e))});return()=>{live=false}},[]);
 if(params.has('problem')||params.has('legacy'))return <ProblemWorkspacePage/>;
 if(error)return <main><p role="alert">会话入口读取失败，请重新登录后重试。{error}</p></main>;
 if(enabled===null)return <p role="status">正在读取会话入口…</p>;
 if(enabled===false&&params.has("conversation"))return <main><p>会话功能当前关闭，已保存记录仍保留。</p><Link to="/work?legacy=1">原业务入口</Link></main>;
 return enabled?<PrivateConversationLoader key={params.get('conversation')??params.get('draft')??'new'}/>:<ProblemWorkspacePage/>;
}
function PrivateConversationLoader(){
 const [session,setSession]=useState<WorkbenchSession|null>(null),[error,setError]=useState('');
 useEffect(()=>{let live=true;readWorkbenchSession().then(s=>{if(live)setSession(s)}).catch(e=>{if(live)setError(String(e))});return()=>{live=false}},[]);
 return session?<PrivateConversationPage session={session}/>:<p role={error?'alert':'status'}>{error||'正在确认私有会话身份…'}</p>;
}
const hints:Record<string,string>={NEW_GOAL_REVIEW:'已记录新的目标意图。业务问题尚未创建；需要确认目标与原有授权后才能办理。',CLARIFY_WORK:'这条要求指向哪项工作？请选择下方关联工作后补充，原消息会保留。',FOLLOWUP_RECORDED:'已保存到当前会话，并关联所关注的工作。可继续查看原结果或在原工作中处理；没有启动新的执行。',GOAL_RECORDED:'目标已记录在本会话，尚未创建业务问题或调用模型。'};
function workUrl(link:WorkLink,conversation:string){return '/work?'+new URLSearchParams({problem:link.target!.problemId,...(link.target!.executionDigest?{execution:link.target!.executionDigest}:{}),returnConversation:conversation})}
function PrivateConversationPage({session}:{session:WorkbenchSession}){
 const location=useLocation(),navigate=useNavigate(),params=new URLSearchParams(location.search),id=params.get('conversation'),scope=conversationScope(session),key=scope+':private:'+(id??params.get('draft')??'new');
 const [data,setData]=useState<RecordView|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[draft,setDraft]=useViewString(key,'draft'),[focused,setFocused]=useViewString(key,'focus'),[tab,setTab]=useViewString(key,'view','messages');
 const [problems,setProblems]=useState<BusinessProblemRevision[]>([]),[attach,setAttach]=useState(params.get('attachProblem')??'');
 const alive=useRef(true),flight=useRef(false);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[]);
 const verifySession=useCallback(async()=>{const actual=await readWorkbenchSession();if(conversationScope(actual)!==scope)throw new Error('CONVERSATION_IDENTITY_CHANGED')},[scope]);
 const load=useCallback(async()=>{if(!id)return;await verifySession();const r=await conversationRequest<RecordView>('/'+id);await verifySession();if(alive.current)setData(r)},[id,verifySession,setData]);
 useEffect(()=>{void load().catch(e=>{if(alive.current)setError(String(e))});listBusinessProblems().then(async r=>{await verifySession();if(alive.current)setProblems(r.problems)}).catch(()=>{});},[load,verifySession]);
 function pending(name:string,body:Record<string,unknown>){
  const stored=readViewString(key,name);if(stored){const old=JSON.parse(stored) as {key:string;body:Record<string,unknown>};const comparable=(v:Record<string,unknown>)=>Object.fromEntries(Object.entries(v).filter(([k])=>k!=="expectedVersion"));if(JSON.stringify(comparable(old.body))===JSON.stringify(comparable(body)))return {...old.body,idempotencyKey:old.key}}
  const value=crypto.randomUUID();saveViewString(key,name,JSON.stringify({key:value,body}));return {...body,idempotencyKey:value};
 }

 async function ensureConversation(){if(id)return id;const body={title:draft.trim().slice(0,80)||'已有工作接续'};const r=await conversationRequest<{conversation_id:string}>('',session.csrfToken,pending('create',body));saveViewString(scope+':private:'+r.conversation_id,'draft',draft);return r.conversation_id}
 async function act(action:()=>Promise<void>){if(flight.current)return;flight.current=true;setBusy(true);setError('');try{await verifySession();await action()}catch(e){if(String(e).includes('CONVERSATION_VERSION_CONFLICT')){saveViewString(key,'send','');saveViewString(key,'link','')}if(alive.current)setError(String(e)+'。原记录保留；请读取当前状态后再决定。')}finally{flight.current=false;if(alive.current)setBusy(false)}}
 async function send(){const value=draft.trim();if(!value)return;await act(async()=>{const current=await ensureConversation();const body={expectedVersion:data?.conversation.version??0,content:value,focusLinkId:focused||null};await conversationRequest('/'+current+'/messages',session.csrfToken,pending('send',body));saveViewString(key,'send','');saveViewString(scope+':private:'+current,'draft','');setDraft('');window.dispatchEvent(new Event('private-conversations-changed'));if(!alive.current)return;if(!id)navigate('/work?conversation='+current,{replace:true});else await load()})}
 async function linkWork(){if(!attach)return;await act(async()=>{const detail=await readBusinessProblem(attach);const revision=detail.revisions.find(r=>r.revision_id===detail.problem.current_revision_id)!;const execution=params.get('attachExecution');const target={problemId:attach,revisionId:revision.revision_id,problemDigest:revision.digest,...(execution&&attach===params.get('attachProblem')?{executionDigest:execution}:{})};const current=await ensureConversation();const body={expectedVersion:data?.conversation.version??0,target};const result=await conversationRequest<{identity:string}>('/'+current+'/links',session.csrfToken,pending('link',body));saveViewString(key,'link','');saveViewString(scope+':private:'+current,'focus',result.identity);window.dispatchEvent(new Event('private-conversations-changed'));if(!alive.current)return;if(!id)navigate('/work?conversation='+current,{replace:true});else{setFocused(result.identity);await load()}})}
 const link=data?.links.find(l=>l.link_id===focused&&l.readable),showWork=tab==='work'&&link?.target;
 return <main className="px-page px-workspace private-conversation" aria-busy={busy}><header className="private-heading"><p>我的会话 · 仅本人可见</p><h1>{data?.conversation.title??(id?'读取会话':'新建会话')}</h1><p>消息保存在本会话；关联工作仍按原权限读取和办理。</p></header>{error&&<div role="alert">{error}<button type="button" onClick={()=>void act(load)}>读取当前状态</button></div>}{id&&!data?<p role="status">{error?'未取得会话读取权限。':'正在读取已保存消息…'}</p>:<div className="px-workspace-body"><ConversationFrame key={key+':'+tab} viewScope={scope} viewId={'private:'+id+':'+tab} newMessageKey={String(data?.messages.length??0)} composer={<form className="private-composer" onSubmit={e=>{e.preventDefault();void send()}}><label htmlFor="private-input">{link?'继续当前工作：'+link.title:'继续这段会话'}</label><textarea id="private-input" value={draft} maxLength={2048} onChange={e=>setDraft(e.target.value)} placeholder="描述目标、补充要求或说明要继续哪项工作"/><button disabled={busy||!draft.trim()}>发送</button><small>发送只保存消息，不创建问题、调用模型或启动执行。</small></form>}>
 <nav className="work-view-tabs"><button type="button" aria-pressed={tab!=='work'} onClick={()=>setTab('messages')}>会话消息</button><button type="button" aria-pressed={tab==='work'} disabled={!link} onClick={()=>setTab('work')}>当前工作</button></nav>
 {showWork?<section className="private-work"><button onClick={()=>setTab('messages')}>返回会话原处</button><h2>{link.title}</h2>{link.target!.executionDigest?<PreparedExecutionPanel key={key+focused} contextKey={key+focused} digest={link.target!.executionDigest} problemId={link.target!.problemId} csrfToken={session.csrfToken} blocked={true} onBusy={()=>{}}/>:<p>已关联问题，尚未关联精确执行。可在原工作入口查看已有计划与成果。</p>}<Link to={workUrl(link,id!)}>在原工作中继续处理</Link></section>:<div className="private-messages">{!data?.messages.length&&<p>这是一段新的会话。发送首条消息后保存，不会自动创建业务问题。</p>}{data?.messages.map(m=><article className="private-message" key={m.message_id} data-message-id={m.message_id}><div className="private-user"><time>{formatTime(m.created_at)}</time><p>{m.content}</p></div><div className="private-receipt"><p>{hints[m.disposition]}</p>{m.focus_link_id&&<button disabled={!data.links.some(l=>l.link_id===m.focus_link_id&&l.readable)} onClick={()=>{setFocused(m.focus_link_id!);setTab('work')}}>查看所关联工作</button>}{m.disposition==='NEW_GOAL_REVIEW'&&<Link to={'/work?legacy=1&returnConversation='+id}>核对新的业务目标</Link>}</div></article>)}</div>}
 </ConversationFrame><aside className="private-rail"><h2>关联工作</h2><p>选择只改变关注对象，不执行或重试。</p>{data?.links.map(l=><button className="private-work-link" key={l.link_id} aria-pressed={focused===l.link_id} disabled={!l.readable} onClick={()=>setFocused(l.link_id)}>{l.readable?l.title:'当前无权读取关联工作'}</button>)}<button onClick={()=>setFocused('')}>暂不指定工作</button><label>关联已有问题<select value={attach} onChange={e=>setAttach(e.target.value)}><option value="">请选择可读问题</option>{problems.map(p=><option key={p.business_problem_id} value={p.business_problem_id}>{p.title}</option>)}</select></label><button disabled={busy||!attach} onClick={()=>void linkWork()}>关联到本会话</button><p>旧记录不会被改写为聊天历史。关联不授予额外权限。</p><Link to="/work?legacy=1">查看原业务办理入口</Link></aside></div>}</main>
}
