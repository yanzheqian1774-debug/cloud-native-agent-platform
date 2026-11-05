import {useEffect,useLayoutEffect,useRef,useState} from "react";
import {Link,useLocation} from "react-router-dom";
import {listBusinessProblems,readWorkbenchSession,type BusinessProblemRevision} from "../api/businessWorkspace";
import {NavigationIcon} from "../components/NavigationIcon";
import {conversationScope,conversationUrl} from "./conversationViewState";
import {formatTime} from "../journey/formatTime";
export function ConversationList(){
 const location=useLocation(),selected=new URLSearchParams(location.search).get("problem");
 const [data,setData]=useState<{scope:string;items:BusinessProblemRevision[]}|null>(null),[failed,setFailed]=useState(false);
 const [open,setOpen]=useState(()=>sessionStorage.getItem("conversation-list.open")!=="false");
 const list=useRef<HTMLDivElement>(null);
 useEffect(()=>{let active=true;const load=async()=>{try{const session=await readWorkbenchSession(),items=await listBusinessProblems(),verified=await readWorkbenchSession();if(conversationScope(session)!==conversationScope(verified))throw new Error("CONVERSATION_IDENTITY_CHANGED");if(active){setData({scope:conversationScope(session),items:items.problems});setFailed(false)}}catch{if(active){setData(null);setFailed(true)}}};void load();window.addEventListener("focus",load);return()=>{active=false;window.removeEventListener("focus",load)}},[location.pathname]);
 useLayoutEffect(()=>{if(list.current&&data)list.current.scrollTop=Number(sessionStorage.getItem(`conversation-list.scroll:${data.scope}`)??0)},[data,open]);
 return <div className="conversation-navigation"><button className={`conversation-list-toggle${location.pathname==="/work"?" active":""}`} type="button" aria-expanded={open} onClick={()=>setOpen(value=>{sessionStorage.setItem("conversation-list.open",String(!value));return !value})}><NavigationIcon name="conversation"/><span>我的会话</span><span aria-hidden="true">{open?"⌄":"›"}</span></button>{open&&<><Link className="conversation-new" to={"/work?draft="+crypto.randomUUID()}>＋ 新建会话</Link><div className="conversation-list" ref={list} onScroll={event=>{if(data)sessionStorage.setItem(`conversation-list.scroll:${data.scope}`,String(event.currentTarget.scrollTop))}} aria-label="我的会话列表">{data?.items.slice().reverse().map(item=><Link key={item.business_problem_id} onClick={event=>{if(document.querySelector(".px-workspace[aria-busy=true]"))event.preventDefault()}} to={conversationUrl(data.scope,item.business_problem_id)} className={selected===item.business_problem_id&&location.pathname==="/work"?"selected":""} aria-current={selected===item.business_problem_id&&location.pathname==="/work"?"page":undefined}><strong>{item.title}</strong><span>{item.description}</span><time dateTime={item.created_at} title="问题记录时间">记录于 {formatTime(item.created_at)}</time></Link>)}</div><p className="conversation-source-note">{failed?"会话记录暂不可读，请登录后重试。":data?.items.length?"按已保存问题分组；完整会话历史待接入。":"暂无可读问题记录。"}</p></>}</div>
}
