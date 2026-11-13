import {conversationRequest} from '../api/privateConversation';
import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {Link,useLocation} from 'react-router-dom';
import {listBusinessProblems,readWorkbenchSession,type BusinessProblemRevision} from '../api/businessWorkspace';
import {conversationScope,conversationUrl} from './conversationViewState';
import {formatTime} from '../journey/formatTime';

function useHistoryScroll(key:string,version:unknown){
 const list=useRef<HTMLDivElement>(null);
 useLayoutEffect(()=>{
  const node=list.current;if(!node||!key)return;
  const restore=()=>{if(node.clientHeight)try{node.scrollTop=Number(sessionStorage.getItem(key)??0)}catch{/* Optional coordinates. */}};
  restore();const group=node.closest('details');group?.addEventListener('toggle',restore);
  return()=>group?.removeEventListener('toggle',restore);
 },[key,version]);
 return {ref:list,onScroll:(event:React.UIEvent<HTMLDivElement>)=>{if(key&&event.currentTarget.clientHeight)try{sessionStorage.setItem(key,String(event.currentTarget.scrollTop))}catch{/* Optional coordinates. */}}};
}
function ProblemProjectionList(){
 const location=useLocation(),selected=new URLSearchParams(location.search).get('problem');
 const [data,setData]=useState<{scope:string;items:BusinessProblemRevision[]}|null>(null),[failed,setFailed]=useState(false);
 const scroll=useHistoryScroll(data?'conversation-list.scroll:'+data.scope:'',data);
 useEffect(()=>{let active=true;const load=async()=>{try{const session=await readWorkbenchSession(),items=await listBusinessProblems(),verified=await readWorkbenchSession();if(conversationScope(session)!==conversationScope(verified))throw Error('CONVERSATION_IDENTITY_CHANGED');if(active){setData({scope:conversationScope(session),items:items.problems});setFailed(false)}}catch{if(active){setData(null);setFailed(true)}}};void load();window.addEventListener('focus',load);return()=>{active=false;window.removeEventListener('focus',load)}},[location.pathname]);
 return <div className="conversation-navigation"><Link className="conversation-new" to={'/work?draft='+crypto.randomUUID()}>＋ 新建会话</Link><div className="conversation-list" {...scroll} aria-label="业务问题记录列表">{data?.items.slice().reverse().map(item=><Link key={item.business_problem_id} onClick={event=>{if(document.querySelector('.px-workspace[aria-busy=true]'))event.preventDefault()}} to={conversationUrl(data.scope,item.business_problem_id)} className={selected===item.business_problem_id&&location.pathname==='/work'?'selected':''} aria-current={selected===item.business_problem_id&&location.pathname==='/work'?'page':undefined}><strong>{item.title}</strong><span>{item.description}</span><time>{formatTime(item.created_at)}</time></Link>)}</div><p className="conversation-source-note">{failed?'问题记录暂不可读，请登录后重试。':data?.items.length?'按已保存问题分组；完整会话历史待接入。':'暂无可读问题记录。'}</p></div>;
}
export function ConversationList(){
 const location=useLocation(),[enabled,setEnabled]=useState<boolean|null>(null),[items,setItems]=useState<Array<{conversation_id:string;title:string;created_at:string}>>([]),[error,setError]=useState(false),[scope,setScope]=useState('');
 const scroll=useHistoryScroll(scope?'private-list-scroll:'+scope:'',items);
 useEffect(()=>{let active=true;const load=async()=>{try{const before=await readWorkbenchSession(),capability=await conversationRequest<{enabled:boolean}>('/capabilities'),result=capability.enabled?await conversationRequest<{items:Array<{conversation_id:string;title:string;created_at:string}>}>():{items:[]},after=await readWorkbenchSession();if(conversationScope(before)!==conversationScope(after))throw Error('IDENTITY_CHANGED');if(active){setEnabled(capability.enabled);setItems(result.items);setScope(conversationScope(after));setError(false)}}catch{if(active){setError(true);setItems([])}}};void load();window.addEventListener('private-conversations-changed',load);window.addEventListener('focus',load);return()=>{active=false;window.removeEventListener('private-conversations-changed',load);window.removeEventListener('focus',load)}},[location.search]);
 if(enabled===false)return <ProblemProjectionList/>;
 const selected=new URLSearchParams(location.search).get('conversation');
 return <div className="conversation-navigation"><Link className="conversation-new" to={'/work?draft='+crypto.randomUUID()}>＋ 新建会话</Link><div className="conversation-list" {...scroll} aria-label="可访问的会话">{items.map(item=><Link className={selected===item.conversation_id?'selected':''} aria-current={selected===item.conversation_id?'page':undefined} key={item.conversation_id} to={'/work?conversation='+item.conversation_id}><strong>{item.title}</strong><time>{formatTime(item.created_at)}</time></Link>)}</div><p className="conversation-source-note">{error?'会话读取失败，请重新登录后重试。':enabled===null?'正在读取会话…':items.length?'按当前权限可见 · 已保存会话':'暂无已保存会话'}</p><Link className="conversation-legacy" to="/work?legacy=1&panel=existing">历史业务问题</Link></div>;
}
