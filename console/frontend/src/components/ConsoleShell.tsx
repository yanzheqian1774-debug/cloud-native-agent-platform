import "../journey/journey.css";
import {flushSync} from "react-dom";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";

import { BusinessNavigation, ResourceNavigation } from "./BusinessNavigation";
import { NavigationIcon } from "./NavigationIcon";
import { RouteBreadcrumb } from "./RouteBreadcrumb";

import { logoutWorkbenchSession, readWorkbenchSession } from "../api/businessWorkspace";

interface ConsoleShellProps { children: ReactNode }
type JourneyStep={to:string;label:string};
const journeys:Record<string,{title:string;steps:JourneyStep[]}>= {
  assembly:{title:"数字员工装配",steps:[{to:"/digital-employees?journey=assembly",label:"数字员工"},{to:"/agent-center?journey=assembly",label:"Agent Definition"},{to:"/skills?journey=assembly",label:"Skill 绑定"},{to:"/mcp?journey=assembly",label:"MCP 端点边界"},{to:"/knowledge?journey=assembly",label:"Knowledge 绑定"},{to:"/workflow-definitions?journey=assembly",label:"Workflow 定义"},{to:"/runtime-profiles?journey=assembly",label:"Runtime 配置"},{to:"/evidence?journey=assembly",label:"Evidence 入口"}]},
  governance:{title:"平台治理与运营",steps:[{to:"/dashboard?journey=governance",label:"首页"},{to:"/permissions?journey=governance",label:"权限中心"},{to:"/security?journey=governance",label:"安全中心"},{to:"/operations?journey=governance",label:"运维监控"},{to:"/models?journey=governance",label:"模型中心"},{to:"/usage?journey=governance",label:"费用与使用量"},{to:"/settings?journey=governance",label:"系统设置"},{to:"/help?journey=governance",label:"帮助中心"}]}
};
function JourneyRail(){const location=useLocation(),params=new URLSearchParams(location.search),id=params.get("journey")??"",journey=journeys[id];if(!journey)return null;const current=`${location.pathname}${location.search}`,exact=journey.steps.findIndex(step=>step.to===current),index=Math.max(0,exact>=0?exact:journey.steps.findIndex(step=>new URL(step.to,"http://local").pathname===location.pathname));return <nav className="px-journey-rail" aria-label={`${journey.title}演示路径`}><div><strong>{journey.title}</strong><span>第 {index+1} / {journey.steps.length} 步 · {journey.steps[index].label}</span></div><ol>{journey.steps.map((step,stepIndex)=><li key={step.to}><Link aria-current={stepIndex===index?"step":undefined} to={step.to}>{step.label}</Link></li>)}</ol><div className="px-journey-actions">{index>0&&<Link to={journey.steps[index-1].to}>上一步</Link>}{index<journey.steps.length-1&&<Link to={journey.steps[index+1].to}>下一步</Link>}<Link to={location.pathname}>退出演示</Link></div></nav>}
export function ConsoleShell({children}:ConsoleShellProps){const location=useLocation(),focusParams=new URLSearchParams(location.search),focusKey=`${location.pathname}:${focusParams.get("journey")??""}:${focusParams.get("stage")??""}`;const[sessionState,setSessionState]=useState<{path:string;identity:string|null;scope?:string;expired?:boolean}>({path:"",identity:null});const [logoutError,setLogoutError]=useState("");const [loggingOut,setLoggingOut]=useState(false);const logoutConfirmed=useRef(false);const [loggedOut,setLoggedOut]=useState(false);const logout=async()=>{setLoggingOut(true);setLogoutError("");try{await logoutWorkbenchSession();flushSync(()=>{logoutConfirmed.current=true;setLoggedOut(true);setSessionState({path:location.pathname,identity:null,expired:true});setLoggingOut(false);window.dispatchEvent(new Event("workbench-session-expired"))})}catch{setLogoutError("退出尚未核实，当前登录可能仍有效。请重新核查后退出");setLoggingOut(false)}};const sessionIdentity=!loggedOut&&sessionState.path===location.pathname?sessionState.identity:null;useEffect(()=>{
  let active=true,request:AbortController|null=null;
  const refreshSession=()=>{request?.abort();const controller=new AbortController();request=controller;readWorkbenchSession(controller.signal).then(session=>{if(active&&request===controller&&!logoutConfirmed.current)setSessionState({path:location.pathname,identity:session.principal.principalId,scope:`${session.principal.tenantId} / ${session.principal.securityDomain}`})}).catch(error=>{if(active&&request===controller&&!logoutConfirmed.current&&error?.name!=="AbortError")setSessionState({path:location.pathname,identity:null,expired:error?.status===401})})};
  const refreshVisibleSession=()=>{if(document.visibilityState==="visible")refreshSession()};
  const refreshFocusedSession=()=>refreshSession();
  const expired=()=>setSessionState({path:location.pathname,identity:null,expired:true});
  window.addEventListener("workbench-session-expired",expired);
  refreshSession();document.addEventListener("visibilitychange",refreshVisibleSession);window.addEventListener("focus",refreshFocusedSession);
  return()=>{active=false;request?.abort();window.removeEventListener("workbench-session-expired",expired);document.removeEventListener("visibilitychange",refreshVisibleSession);window.removeEventListener("focus",refreshFocusedSession)};
},[location.pathname]);useEffect(()=>{
  // Evidence owns return focus, including cancellation after a user Tab.
  // Do not let a later route commit or projection load steal that focus.
  if(location.state?.evidenceFocusReturn===true)return;
  let ownedHeading:HTMLElement|null=null;
  let focusTransferred=false;
  const focusHeading=()=>{
    if(focusTransferred||document.querySelector('[role="dialog"]:not([hidden]),dialog[open],[aria-modal="true"]'))return;
    const active=document.activeElement;
    if(active instanceof HTMLElement&&active.matches('input,textarea,select,[contenteditable="true"]'))return;
    const heading=document.querySelector<HTMLElement>("main h1");
    if(!heading||heading===ownedHeading||ownedHeading?.isConnected)return;
    if(ownedHeading&&active!==document.body&&active!==document.documentElement&&active!==ownedHeading)return;
    ownedHeading=heading;
    heading.tabIndex=-1;
    heading.focus();
  };
  const transferred=(event:FocusEvent)=>{
    if(event.target!==ownedHeading&&event.target!==document.body)focusTransferred=true;
  };
  focusHeading();
  document.addEventListener("focusin",transferred);
  const observer=new MutationObserver(focusHeading);
  observer.observe(document.body,{childList:true,subtree:true});
  return()=>{observer.disconnect();document.removeEventListener("focusin",transferred)};
},[focusKey,location.state]);const inProblemJourney=location.pathname==="/work"||location.pathname.startsWith("/work/");return <div className={`px-shell${inProblemJourney ? " journey-shell" : ""}`}><aside className="px-sidebar"><span className="demo-primary-nav px-nav-compat" aria-hidden="true"/><BusinessNavigation/><a className="px-sidebar-foot" href="/dashboard#planned"><span className="px-plan-dot"/>查看规划能力</a></aside><header className="px-topbar"><NavLink className="px-brand" to="/dashboard"><span className="px-brand-mark"><svg viewBox="0 0 28 28" aria-hidden="true"><rect x="3" y="3" width="15" height="15" rx="2"/><rect x="10" y="10" width="15" height="15" rx="2"/></svg></span><span>企业数字员工平台</span></NavLink><div className="px-header-path"><Link to="/dashboard" aria-label="返回首页"><NavigationIcon name="home"/></Link><RouteBreadcrumb/></div><div className="px-header-actions"><time className="px-current-date" dateTime={new Date().toISOString().slice(0,10)}>{new Date().toLocaleDateString("zh-CN",{year:"numeric",month:"long",day:"numeric",weekday:"long"})}</time><Link className="px-new-conversation" to={"/work?draft="+crypto.randomUUID()}><span aria-hidden="true">⊞</span> 新会话</Link><NavLink className="px-header-tool" to="/attention"><NavigationIcon name="outcome"/><span>待办</span></NavLink><NavLink className="px-header-tool px-header-notices" to="/attention" aria-label="待处理事项"><NavigationIcon name="attention"/></NavLink><details className="px-identity-menu"><summary aria-label={sessionIdentity?`当前可信身份 ${sessionIdentity}`:undefined}>{sessionIdentity?<><span className="px-user" aria-hidden="true">{sessionIdentity.slice(0,1).toUpperCase()}</span><span className="px-header-identity">{sessionIdentity}</span><span aria-hidden="true">⌄</span></>:<a href={`/api/workbench/v1/login?returnTo=${encodeURIComponent(location.pathname+location.search+location.hash)}`}>登录工作台</a>}</summary><div>{sessionIdentity?<><strong>当前可信身份</strong><p>{sessionIdentity}</p><small>{sessionState.scope}{sessionState.scope==="s5-323-demo / isolated-real-demo"&&" · 本地隔离测试"}</small><button type="button" onClick={logout} disabled={loggingOut}>{loggingOut?"正在退出":"退出登录"}</button></>:<a href={`/api/workbench/v1/login?returnTo=${encodeURIComponent(location.pathname+location.search+location.hash)}`}>登录工作台</a>}<Link to="/help">帮助中心</Link><details className="px-demo-menu"><summary>演示路径</summary><nav className="px-demo-links" aria-label="可重复演示路径"><Link to="/work">可信问题工作台</Link><Link to={journeys.assembly.steps[0].to}>数字员工装配</Link><Link to={journeys.governance.steps[0].to}>平台治理</Link></nav></details>{logoutError&&<span role="alert">{logoutError}</span>}</div></details></div></header><details className="px-mobile-menu" key={location.pathname}><summary>全部导航</summary><BusinessNavigation mobile/></details><div className="px-content">{inProblemJourney&&import.meta.env.VITE_ACCEPTANCE_LABEL&&<p className="journey-test-source" role="note">测试来源：{import.meta.env.VITE_ACCEPTANCE_LABEL}</p>}<JourneyRail/>{["/skills","/mcp","/knowledge","/workflow-definitions"].includes(location.pathname)&&!focusParams.has("managedResource")&&<ResourceNavigation/>}{(inProblemJourney || ["/authorization-admin","/tasks","/outcomes","/attention"].includes(location.pathname)) && sessionState.path===location.pathname && sessionState.expired ? <main className="px-session-expired" role="alert"><h1>{loggedOut?"已退出登录":"当前登录已失效"}</h1><p>请重新登录并核对当前身份、组织和原请求。不会自动重发、确认方案或执行任务。</p><p>已提交记录保留；未发送内容仅在当前页面，离开可能丢失。</p><a className="px-primary-button" href={`/api/workbench/v1/login?returnTo=${encodeURIComponent(location.pathname+location.search+location.hash)}`}>重新登录并读回</a></main> : children}</div><footer className="px-platform-footer"><span>企业数字员工平台</span><nav><Link to="/help">帮助与反馈</Link><Link to="/security">隐私与安全</Link></nav></footer></div>}
