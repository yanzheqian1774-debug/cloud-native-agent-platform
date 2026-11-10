import {AllFunctionsMenu} from './AllFunctionsMenu';
import {WorkspaceFrame} from './SkillWorkspaceFrame';
import {clearConversationViewState} from "../problems/conversationViewState";
import "../journey/journey.css";
import {DevelopmentAdministratorNotice} from "./DevelopmentAdministratorNotice";
import {flushSync} from "react-dom";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

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
export function ConsoleShell({children}:ConsoleShellProps){const location=useLocation(),focusParams=new URLSearchParams(location.search),focusKey=`${location.pathname}:${focusParams.get("journey")??""}:${focusParams.get("stage")??""}`;const[sessionState,setSessionState]=useState<{path:string;identity:string|null;scope?:string;expired?:boolean}>({path:"",identity:null});const [logoutError,setLogoutError]=useState("");const [loggingOut,setLoggingOut]=useState(false);const logoutConfirmed=useRef(false);const keyboardNavigation=useRef(false);useEffect(()=>{const keyboard=()=>{keyboardNavigation.current=true;document.querySelectorAll('.f3-route-autofocus').forEach(n=>n.classList.remove('f3-route-autofocus'))};const pointer=()=>{keyboardNavigation.current=false};document.addEventListener('keydown',keyboard,true);document.addEventListener('pointerdown',pointer,true);return()=>{document.removeEventListener('keydown',keyboard,true);document.removeEventListener('pointerdown',pointer,true)}},[]);const [loggedOut,setLoggedOut]=useState(false);const logout=async()=>{setLoggingOut(true);setLogoutError("");try{await logoutWorkbenchSession();flushSync(()=>{logoutConfirmed.current=true;setLoggedOut(true);setSessionState({path:location.pathname,identity:null,expired:true});setLoggingOut(false);window.dispatchEvent(new Event("workbench-session-expired"))})}catch{setLogoutError("退出尚未核实，当前登录可能仍有效。请重新核查后退出");setLoggingOut(false)}};const sessionIdentity=!loggedOut?sessionState.identity:null;useEffect(()=>{
  let active=true,request:AbortController|null=null;
  const refreshSession=()=>{if(logoutConfirmed.current)return;request?.abort();const controller=new AbortController();request=controller;readWorkbenchSession(controller.signal).then(session=>{if(active&&request===controller&&!logoutConfirmed.current)setSessionState({path:location.pathname,identity:session.principal.principalId,scope:`${session.principal.tenantId} / ${session.principal.securityDomain}`})}).catch(error=>{if(active&&request===controller&&!logoutConfirmed.current&&error?.name!=="AbortError"){if(error?.status===401)window.dispatchEvent(new Event("workbench-session-expired"));else setSessionState({path:location.pathname,identity:null})}})};
  const refreshVisibleSession=()=>{if(document.visibilityState==="visible")refreshSession()};
  const refreshFocusedSession=()=>refreshSession();
  const expired=()=>{logoutConfirmed.current=true;request?.abort();request=null;clearConversationViewState();setSessionState({path:location.pathname,identity:null,expired:true})};
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
    // A child layout may restore its task button before this route effect runs.
    // Treat that existing focus as transferred, just like a later focusin event.
    if(active instanceof HTMLElement&&active.matches('[data-open-work]')&&active.closest('main')){focusTransferred=true;return;}
    const heading=document.querySelector<HTMLElement>("main h1");
    if(!heading||heading===ownedHeading||ownedHeading?.isConnected)return;
    if(ownedHeading&&active!==document.body&&active!==document.documentElement&&active!==ownedHeading)return;
    ownedHeading=heading;
    heading.tabIndex=-1;
    heading.classList.toggle("f3-route-autofocus",!keyboardNavigation.current);
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
},[focusKey,location.state]);const inProblemJourney=location.pathname==="/work"||location.pathname.startsWith("/work/");return <WorkspaceFrame journey={inProblemJourney} brand={<Link to="/dashboard"><NavigationIcon name="network"/>企业数字员工</Link>} home={<Link to="/dashboard" aria-label="返回首页"><NavigationIcon name="home"/></Link>} workspace={<details><summary>当前工作空间<small>企业工作空间 · 查看范围</small></summary><small>{sessionState.scope??'登录后查看当前范围'}</small><DevelopmentAdministratorNotice identity={sessionIdentity} path={location.pathname}/></details>} navigation={<BusinessNavigation sessionIdentity={sessionIdentity}/>} identity={<details className="px-identity-menu"><summary aria-label={sessionIdentity?`当前可信身份 ${sessionIdentity}`:undefined}>{sessionIdentity?<><span className="px-user" aria-hidden="true">{sessionIdentity.slice(0,1).toUpperCase()}</span><span className="px-header-identity">当前账号<small>查看身份与范围</small></span><span aria-hidden="true">⌄</span></>:<a href={`/api/workbench/v1/login?returnTo=${encodeURIComponent(location.pathname+location.search+location.hash)}`}>核对登录状态</a>}</summary><div>{sessionIdentity?<><strong>当前可信身份</strong><p>{sessionIdentity}</p><small>{sessionState.scope}{sessionState.scope==="s5-323-demo / isolated-real-demo"&&" · 本地隔离测试"}</small><button type="button" onClick={logout} disabled={loggingOut}>{loggingOut?"正在退出":"退出登录"}</button></>:<a href={`/api/workbench/v1/login?returnTo=${encodeURIComponent(location.pathname+location.search+location.hash)}`}>核对登录状态</a>}<Link to="/help">帮助中心</Link><details className="px-demo-menu"><summary>演示路径</summary><nav className="px-demo-links" aria-label="可重复演示路径"><Link to="/work">可信问题工作台</Link><Link to={journeys.assembly.steps[0].to}>数字员工装配</Link><Link to={journeys.governance.steps[0].to}>平台治理</Link></nav></details>{logoutError&&<span role="alert">{logoutError}</span>}</div></details>} menu={<AllFunctionsMenu key={JSON.stringify([location.pathname,location.search,sessionIdentity,sessionState.scope])} sessionIdentity={sessionIdentity}/>} breadcrumb={location.pathname==='/skills'?<><Link to="/catalog">资源管理</Link> › 技能</>:<RouteBreadcrumb/>} actions={<><Link className="skill-frame-primary" to={'/work?draft='+crypto.randomUUID()}>＋ 发起会话</Link><Link to="/attention">待办</Link><time>{new Date().toLocaleDateString('zh-CN',{month:'long',day:'numeric',weekday:'short'})}</time></>}>{inProblemJourney&&import.meta.env.VITE_ACCEPTANCE_LABEL&&<p className="journey-test-source" role="note">测试来源：{import.meta.env.VITE_ACCEPTANCE_LABEL}</p>}<JourneyRail/>{import.meta.env.VITE_RESOURCE_DIRECTORY_ENABLED!=="true"&&["/skills","/mcp","/knowledge","/workflow-definitions"].includes(location.pathname)&&!focusParams.has("managedResource")&&<ResourceNavigation/>}{sessionState.expired ? <main className="px-session-expired" role="alert"><h1>{loggedOut?"已退出登录":"当前登录已失效"}</h1><p>请重新登录并核对当前身份、组织和原请求。不会自动重发、确认方案或执行任务。</p><p>已提交记录保留；未发送内容仅在当前页面，离开可能丢失。</p><a className="px-primary-button" href={`/api/workbench/v1/login?returnTo=${encodeURIComponent(location.pathname+location.search+location.hash)}`}>重新登录并读回</a></main> : children}</WorkspaceFrame>;}
