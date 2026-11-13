import {ConversationList} from "../problems/ConversationList";
import { Link, NavLink, useLocation } from "react-router-dom";
import {resourceNavigationUrl} from "../resources/resourceNavigationContext";
import { NavigationIcon, type NavigationIconName } from "./NavigationIcon";

type Entry = { to: string; label: string; icon: NavigationIconName };
const resources: Entry[] = [
  {to:"/skills",label:"技能",icon:"skill"},
  {to:"/mcp",label:"MCP 服务",icon:"mcp"},
  {to:"/knowledge",label:"知识",icon:"knowledge"},
  {to:"/tools",label:"工具",icon:"tool"},
  {to:"/workflow-definitions",label:"工作流",icon:"flow"},
];
const advanced: Entry[] = [
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
export function BusinessNavigation({mobile=false,sessionIdentity}:{mobile?:boolean;sessionIdentity:string|null}) {
  const {pathname}=useLocation();
  const workActive=pathname==="/work"||pathname.startsWith("/work/")||pathname==="/tasks";
  const resourceActive=resources.some(x=>x.to===pathname||pathname.startsWith(x.to+"/"));
  const advancedActive=advanced.some(x=>x.to===pathname);
  return <nav className="px-business-nav" aria-label={mobile?"移动端全部产品导航":"P1 核心产品导航"}>
    <section><h2>工作与协同</h2>
      <EntryLink entry={{to:"/dashboard",label:"首页 · 我的工作台",icon:"home"}}/>
      <details key={`work-${workActive}`} open={workActive}>
        <summary className={workActive?"active":""}><NavigationIcon name="problem"/><span>我的会话</span></summary>
        {sessionIdentity?<ConversationList key={sessionIdentity}/>:<p className="conversation-source-note">登录后读取当前账号的会话记录。</p>}</details><NavLink to="/tasks"><NavigationIcon name="outcome"/>我的任务</NavLink><NavLink to="/attention"><NavigationIcon name="attention"/>待我处理</NavLink><NavLink to="/outcomes"><NavigationIcon name="record"/>成果与记录</NavLink>

    </section>
    <section><h2>业务与团队</h2>{import.meta.env.VITE_BUSINESS_PROCESS_DEFINITIONS_ENABLED === "true"?<EntryLink entry={{to:"/business-processes",label:"业务流程",icon:"relationships"}}/>:<div className="px-navigation-unavailable" aria-disabled="true" title="企业架构、业务流程与活动管理尚未接入"><NavigationIcon name="relationships"/><span>业务流程<small>待接入</small></span></div>}{import.meta.env.VITE_BUSINESS_CAPABILITIES_ENABLED === "true"&&<EntryLink entry={{to:"/capabilities",label:"业务能力",icon:"agent"}}/>}<EntryLink entry={{to:import.meta.env.VITE_TEAM_DEFINITIONS_ENABLED==="true"?"/teams":"/digital-employees",label:import.meta.env.VITE_TEAM_DEFINITIONS_ENABLED==="true"?"数字人团队":"数字员工",icon:"employee"}}/>
    </section><section><h2>资源与平台</h2>
      <details key={`resources-${resourceActive}`} open={resourceActive}>
        <summary className={resourceActive?"active":""}><NavigationIcon name="resource"/><span>资源管理</span></summary>
        {resources.map(entry=><EntryLink key={entry.to} entry={entry}/>)}
      </details>
    </section>
    <section><h2>运营与治理</h2>
      <EntryLink entry={{to:"/operations",label:"执行与观测",icon:"operations"}}/>
      <EntryLink entry={{to:"/usage",label:"成本与预算",icon:"usage"}}/>
      <details key={`advanced-${advancedActive}`} open={advancedActive}>
        <summary><NavigationIcon name="manage"/><span>管理与技术</span></summary>
        <nav aria-label="管理与技术导航">{advanced.map(entry=><EntryLink key={entry.to} entry={entry}/>)}</nav>
      </details>
    </section>
    <div className="px-navigation-settings"><EntryLink entry={{to:"/settings",label:"设置",icon:"manage"}}/></div>
  </nav>;
}
export function ResourceNavigation() {
  const {search}=useLocation();
  return <nav className="px-resource-navigation" aria-label="能力资源分类">{resources.map(entry=><NavLink key={entry.to} to={resourceNavigationUrl(entry.to,search)}>{entry.label}</NavLink>)}</nav>;
}
