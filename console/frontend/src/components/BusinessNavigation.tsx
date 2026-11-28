import {useState,type ReactNode} from "react";
import {ConversationList} from "../problems/ConversationList";
import { Link, NavLink, useLocation } from "react-router-dom";
import {resourceNavigationUrl} from "../resources/resourceNavigationContext";
import { NavigationIcon, type NavigationIconName } from "./NavigationIcon";

type Entry = { to: string; label: string; icon: NavigationIconName };
const resources: Entry[] = [
  {to:"/skills",label:"技能",icon:"skill"},
  {to:"/mcp",label:"MCP 服务",icon:"mcp"},
  {to:"/ontology",label:"本体",icon:"network"},
  {to:"/knowledge",label:"知识",icon:"knowledge"},
  {to:"/tools",label:"工具",icon:"tool"},
];
const advanced: Entry[] = [
  {to:"/workflow-definitions",label:"工作流",icon:"flow"},
  {to:"/runtime-profiles",label:"运行环境",icon:"runtime"},
  {to:"/evidence",label:"证据记录",icon:"record"},
  {to:"/authorization-admin",label:"独立授权审批",icon:"shield"},
  {to:"/problems",label:"问题审核与修订",icon:"problem"},
  {to:"/agents",label:"智能体定义",icon:"agent"},
  {to:"/catalog",label:"资源统一目录",icon:"resource"},
  {to:"/relationships",label:"对象关系",icon:"relationships"},
  {to:"/applications",label:"应用市场",icon:"applications"},
  {to:"/agent-center",label:"Agent Center",icon:"agent"},
  {to:"/permissions",label:"权限中心",icon:"shield"},
  {to:"/security",label:"安全中心",icon:"shield"},
  {to:"/models",label:"模型中心",icon:"model"},
  {to:"/help",label:"帮助中心",icon:"help"},
];
function EntryLink({entry}:{entry:Entry}) {
  const {search,pathname}=useLocation();
  const employeeAlias=entry.to==="/digital-employees"&&pathname==="/employees",teamAlias=entry.to==="/teams"&&["/employees","/digital-employees"].includes(pathname);
  if(teamAlias)return <Link className="active" aria-current="page" to="/teams"><NavigationIcon name={entry.icon}/><span>{entry.label}</span></Link>;
  return <NavLink className={({isActive})=>isActive||employeeAlias||teamAlias?"active":undefined} aria-current={employeeAlias||teamAlias?"page":undefined} to={resourceNavigationUrl(employeeAlias?"/employees":entry.to,search)} data-resource-kind={entry.icon==="skill"||entry.icon==="mcp"?entry.icon:undefined} aria-label={entry.to==="/attention"?"Attention":undefined}>
    <NavigationIcon name={entry.icon}/><span>{entry.label}</span>
  </NavLink>;
}
function NavigationGroup({name,scope,initial,label,icon,children}:{name:string;scope:string|null;initial:boolean;label:string;icon:NavigationIconName;children:ReactNode}) {
 const key='f3-nav-group:'+scope+':'+name;
 const [open,setOpen]=useState(()=>{try{const saved=sessionStorage.getItem(key);return saved===null?initial:saved==='true'}catch{return initial}});
 return <details open={open} data-navigation-group={name} onToggle={event=>{if(event.target!==event.currentTarget)return;const value=event.currentTarget.open;setOpen(value);try{sessionStorage.setItem(key,String(value))}catch{/* Optional view state only. */}}}><summary><NavigationIcon name={icon}/><span>{label}</span></summary>{children}</details>;
}
export function BusinessNavigation({mobile=false,sessionIdentity}:{mobile?:boolean;sessionIdentity:string|null}) {
  const {pathname}=useLocation();
  const workActive=pathname==="/work"||pathname.startsWith("/work/");
  const resourceActive=resources.some(x=>x.to===pathname||pathname.startsWith(x.to+"/"));
  const advancedActive=advanced.some(x=>x.to===pathname);
  return <nav className="px-business-nav" aria-label={mobile?"移动端全部产品导航":"P1 核心产品导航"}>
    <section><h2>工作与协同</h2>
      <EntryLink entry={{to:"/dashboard",label:"首页 · 我的工作台",icon:"home"}}/>
      <NavigationGroup key={`work-${sessionIdentity}`} name="conversations" scope={sessionIdentity} initial={workActive} label="我的会话" icon="problem">
        {sessionIdentity?<ConversationList key={sessionIdentity}/>:<p className="conversation-source-note">登录后读取当前账号的会话记录。</p>}</NavigationGroup><EntryLink entry={{to:"/tasks",label:"我的任务",icon:"outcome"}}/><EntryLink entry={{to:"/attention",label:"待我处理",icon:"attention"}}/><EntryLink entry={{to:"/outcomes",label:"成果与记录",icon:"record"}}/>

    </section>
    <section><h2>业务与团队</h2>{import.meta.env.VITE_BUSINESS_PROCESS_DEFINITIONS_ENABLED === "true"?<EntryLink entry={{to:"/business-processes",label:"业务流程",icon:"relationships"}}/>:<div className="px-navigation-unavailable" aria-disabled="true" title="企业架构、业务流程与活动管理尚未接入"><NavigationIcon name="relationships"/><span>业务流程<small>待接入</small></span></div>}{import.meta.env.VITE_BUSINESS_CAPABILITIES_ENABLED === "true"&&<EntryLink entry={{to:"/capabilities",label:"业务能力",icon:"agent"}}/>}<EntryLink entry={{to:import.meta.env.VITE_TEAM_DEFINITIONS_ENABLED==="true"?"/teams":"/digital-employees",label:import.meta.env.VITE_TEAM_DEFINITIONS_ENABLED==="true"?"数字人团队":"数字员工",icon:"employee"}}/>
    </section><section><h2>资源与平台</h2>
      <NavigationGroup key={`resources-${sessionIdentity}`} name="resources" scope={sessionIdentity} initial={resourceActive} label="资源管理" icon="resource">
        {resources.map(entry=><EntryLink key={entry.to} entry={entry}/>)}
      </NavigationGroup>
    </section>
    <section><h2>运营与治理</h2>
      <EntryLink entry={{to:"/operations",label:"执行与观测",icon:"operations"}}/>
      <EntryLink entry={{to:"/usage",label:"成本与预算",icon:"usage"}}/>
      <NavigationGroup key={`advanced-${sessionIdentity}`} name="advanced" scope={sessionIdentity} initial={advancedActive} label="管理与技术" icon="manage">
        <nav aria-label="管理与技术导航">{advanced.map(entry=><EntryLink key={entry.to} entry={entry}/>)}</nav>
      </NavigationGroup>
    </section>
    <div className="px-navigation-settings"><EntryLink entry={{to:"/settings",label:"设置",icon:"manage"}}/></div>
  </nav>;
}
export function ResourceNavigation() {
  const {search}=useLocation();
  return <nav className="px-resource-navigation" aria-label="能力资源分类">{resources.map(entry=><NavLink key={entry.to} to={resourceNavigationUrl(entry.to,search)}>{entry.label}</NavLink>)}</nav>;
}
