import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  DigitalEmployeeRequestError,
  getAgentDefinitionRevision,
  type AgentDefinitionRevision,
  type EmployeeDefinition,
  type EmployeeLifecycleState,
  type EmployeeMember,
} from "../api/digitalEmployees";

type AgentReadState = "LOADING" | "READY" | "AUTHENTICATION_REQUIRED" | "DENIED" | "UNAVAILABLE";
type ProfileSection = "overview" | "capabilities";

export function EmployeeProfileLoader({ item, section }: { item: EmployeeDefinition; section: ProfileSection }) {
  const primary = item.members.find(member => member.kind === "AGENT");
  const shouldReadAgent = section === "capabilities" && Boolean(primary);
  const [agent, setAgent] = useState<AgentDefinitionRevision | null>(null);
  const [state, setState] = useState<AgentReadState>(shouldReadAgent ? "LOADING" : "READY");
  const generation = useRef(0);

  useEffect(() => {
    const turn = ++generation.current;
    const controller = new AbortController();
    queueMicrotask(() => {
      if (turn !== generation.current) return;
      setAgent(null);
      setState(shouldReadAgent ? "LOADING" : "READY");
    });
    if (!primary || !shouldReadAgent) return () => controller.abort();
    getAgentDefinitionRevision(primary.resourceId, primary.revisionId, controller.signal)
      .then(value => {
        if (turn !== generation.current) return;
        const exact = value.definitionId === primary.resourceId
          && value.revisionId === primary.revisionId
          && value.digest === primary.digest.replace(/^sha256:/, "");
        setAgent(exact ? value : null);
        setState(exact ? "READY" : "UNAVAILABLE");
      })
      .catch(reason => {
        if (turn !== generation.current || (reason instanceof DOMException && reason.name === "AbortError")) return;
        setAgent(null);
        if (reason instanceof DigitalEmployeeRequestError && reason.status === 401) setState("AUTHENTICATION_REQUIRED");
        else if (reason instanceof DigitalEmployeeRequestError && (reason.status === 403 || reason.status === 404)) setState("DENIED");
        else setState("UNAVAILABLE");
      });
    return () => {
      controller.abort();
      generation.current += 1;
    };
  }, [item, primary, shouldReadAgent]);

  return <EmployeeProfile item={item} agent={agent} agentState={state} section={section} />;
}

const kindLabel: Record<EmployeeMember["kind"], string> = {
  AGENT: "Agent 定义",
  WORKFLOW: "工作流定义",
  SKILL: "技能",
  MCP: "MCP 资源",
  KNOWLEDGE: "知识资源",
  RUNTIME_PROFILE: "Runtime Profile",
};

const lifecycleLabel: Record<EmployeeLifecycleState, string> = {
  DRAFT: "草稿",
  VALIDATED: "已校验",
  APPROVED: "已批准",
  PUBLISHED: "已发布",
  REJECTED: "已拒绝",
  DEPRECATED: "已弃用",
};

function exactCatalogLink(member: EmployeeMember) {
  return `/catalog?${new URLSearchParams({ kind: member.kind, query: member.resourceId })}`;
}

function CopyValue({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  return <span className="employee-copy-value"><code>{value}</code><button type="button" aria-label={`复制${label}`} onClick={() => { void navigator.clipboard.writeText(value).then(() => { setCopied(true); window.setTimeout(() => setCopied(false), 1200); }); }}>{copied ? "已复制" : "复制"}</button></span>;
}

export function EmployeeProfile({ item, agent, agentState, section }: { item: EmployeeDefinition; agent: AgentDefinitionRevision | null; agentState: AgentReadState; section: ProfileSection }) {
  const primary = item.members.find(member => member.kind === "AGENT");
  const agentExact = Boolean(primary && agent
    && agent.definitionId === primary.resourceId
    && agent.revisionId === primary.revisionId
    && agent.digest === primary.digest.replace(/^sha256:/, ""));

  if (section === "overview") return <section className="employee-profile" aria-labelledby="employee-profile-title">
    <h3 id="employee-profile-title">职责与成员</h3>
    <section className="employee-responsibilities"><h4>职责</h4><ul>{item.responsibilities.map((value, index) => <li key={`${index}:${value}`}>{value}</li>)}</ul></section>
    <section className="employee-overview-members"><h4>已装配成员</h4><ul>{item.members.map(member => <li key={`${member.kind}:${member.resourceId}:${member.revisionId}`}><span>{kindLabel[member.kind]}</span><strong title={member.resourceId}>{member.resourceId}</strong></li>)}</ul><small>来源：Digital Employee Definition 所选修订；装配不表示已运行。</small></section>
    <dl className="employee-status-facts"><div><dt>发布状态</dt><dd>{item.publicationState === "PUBLISHED" ? "已发布" : "未发布"}</dd></div><div><dt>生命周期</dt><dd>{item.lifecycleState ? lifecycleLabel[item.lifecycleState] : "正式详情接口未提供"}</dd></div></dl>
    <p className="employee-disclosure">运行状态未接通；发布不等于已运行。</p>
    <details className="employee-technical-details"><summary>技术身份与版本</summary><dl><dt>Employee Definition ID</dt><dd><CopyValue label="Employee Definition ID" value={item.employeeDefinitionId} /></dd><dt>Revision ID</dt><dd><CopyValue label="Revision ID" value={item.employeeDefinitionRevisionId} /></dd><dt>Digest</dt><dd><CopyValue label="Digest" value={item.employeeDefinitionDigest} /></dd></dl></details>
  </section>;

  return <section className="employee-capability-profile" aria-labelledby="employee-capability-title">
    <header><div><p className="eyebrow">已绑定成员 · 不是候选发现</p><h3 id="employee-capability-title">职责与能力装配</h3></div>{agentExact && <span className="binding-status">Agent 精确修订已核对</span>}</header>
    <p>成员来自当前所选修订；Agent 候选只在创建流程中出现。绑定表示已装配，不表示已分配、已放置或已运行。</p>
    {agentState === "LOADING" && <p role="status">正在独立读取已绑定 Agent 修订……</p>}
    {agentState === "AUTHENTICATION_REQUIRED" && <p role="status">尚无可信 Workbench session，Agent 详情不可用。</p>}
    {agentState === "DENIED" && <p role="status">已绑定 Agent 修订不存在或当前访问未获授权。</p>}
    {agentState === "UNAVAILABLE" && <p role="status">已绑定 Agent 身份无法核对或读取暂不可用；不会用员工字段补写。</p>}
    {agentExact && agent && <section className="employee-bound-agent"><div className="employee-bound-agent-title"><span className="employee-avatar" aria-hidden="true">A</span><div><strong>{agent.name}</strong><small>来源：Agent Definition 所选修订</small></div></div><dl className="employee-profile-grid"><div><dt>Agent 角色标题</dt><dd>{agent.role.title || "未提供"}</dd></div><div className="wide"><dt>业务目的</dt><dd>{agent.role.businessPurpose || "未提供"}</dd></div><div className="wide"><dt>Agent 职责</dt><dd><ul>{agent.role.duties.map((value, index) => <li key={`${index}:${value}`}>{value}</li>)}</ul></dd></div><div className="wide"><dt>能力</dt><dd><ul className="employee-capabilities">{agent.role.capabilities.map(value => <li key={value}>{value}</li>)}</ul></dd></div></dl></section>}
    <details className="employee-technical-details"><summary>当前员工修订身份</summary><p>以下身份限定本页职责与成员的来源，不授予运行资格。</p><dl><dt>Employee Definition ID</dt><dd><CopyValue label="Employee Definition ID" value={item.employeeDefinitionId} /></dd><dt>Revision ID</dt><dd><CopyValue label="Revision ID" value={item.employeeDefinitionRevisionId} /></dd><dt>Digest</dt><dd><CopyValue label="Digest" value={item.employeeDefinitionDigest} /></dd></dl></details>
    <ul className="px-binding-list employee-member-list">{item.members.map(member => <li key={`${member.kind}:${member.resourceId}:${member.revisionId}`}><span><code>{member.kind}</code> · {kindLabel[member.kind]}</span><strong>{member.resourceId}</strong><small>{member.revisionId}</small><details><summary>摘要与目录</summary><CopyValue label={`${kindLabel[member.kind]}摘要`} value={member.digest} /><Link to={exactCatalogLink(member)}>在资源目录核对</Link></details></li>)}</ul>
    <p className="employee-disclosure">查看员工列表的权限不包含已绑定 Agent 的详情权限。Agent 名称与目的仍归 Agent Definition 所有，不成为员工名称或职责权威。</p>
  </section>;
}
