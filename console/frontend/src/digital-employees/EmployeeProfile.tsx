import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { getAgentDefinition, type AgentRevision } from "../api/agentDefinitions";
import type { EmployeeDefinition, EmployeeMember } from "../api/digitalEmployees";

export type ExactAgentProfile = {
  name: string;
  definitionId: string;
  revision: AgentRevision;
};

export function EmployeeProfileLoader({ item }: { item: EmployeeDefinition }) {
  const primary = item.members.find(member => member.kind === "AGENT");
  const [agent, setAgent] = useState<ExactAgentProfile | null>(null);
  const [state, setState] = useState<"LOADING" | "READY" | "UNAVAILABLE">("LOADING");
  const generation = useRef(0);
  useEffect(() => {
    const turn = ++generation.current;
    if (!primary) return;
    getAgentDefinition(primary.resourceId).then(value => {
      if (turn !== generation.current) return;
      const revision = value.definition.revisions.find(candidate => candidate.revisionId === primary.revisionId && candidate.digest === primary.digest.replace(/^sha256:/, ""));
      setAgent(revision ? { name: value.definition.name, definitionId: value.definition.definitionId, revision } : null);
      setState("READY");
    }).catch(() => {
      if (turn !== generation.current) return;
      setState("UNAVAILABLE");
    });
    return () => { generation.current += 1; };
  }, [item, primary]);
  return <EmployeeProfile item={item} agent={agent} agentState={primary ? state : "READY"} />;
}

const kindLabel: Record<EmployeeMember["kind"], string> = {
  AGENT: "Agent 定义",
  WORKFLOW: "工作流定义",
  SKILL: "技能",
  MCP: "MCP 资源",
  KNOWLEDGE: "知识资源",
  RUNTIME_PROFILE: "Runtime Profile",
};

function exactCatalogLink(member: EmployeeMember) {
  return `/catalog?${new URLSearchParams({ kind: member.kind, query: member.resourceId })}`;
}

export function EmployeeProfile({ item, agent, agentState }: { item: EmployeeDefinition; agent: ExactAgentProfile | null; agentState: "LOADING" | "READY" | "UNAVAILABLE" }) {
  const primary = item.members.find(member => member.kind === "AGENT");
  const agentExact = Boolean(primary && agent && agent.definitionId === primary.resourceId && agent.revision.revisionId === primary.revisionId && agent.revision.digest === primary.digest.replace(/^sha256:/, ""));
  return <>
    <section className="employee-profile" aria-labelledby="employee-profile-title">
      <header><div><p className="eyebrow">数字员工档案 · Definition</p><h2 id="employee-profile-title">{item.role}</h2><p>这是 Digital Employee Definition 自身的角色描述，不代表企业 HR 岗位身份。</p></div><span className="px-status info">{item.published ? "已发布" : "未发布"}</span></header>
      <dl className="employee-profile-grid">
        <div><dt>档案名称</dt><dd>未提供 <small>当前正式契约没有 display name 字段</small></dd></div>
        <div><dt>职责角色</dt><dd>{item.role} <small>来源：Digital Employee Definition</small></dd></div>
        <div><dt>Definition</dt><dd><code>{item.employeeDefinitionId}</code></dd></div>
        <div><dt>发布修订</dt><dd><code>{item.employeeDefinitionRevisionId}</code></dd></div>
        <div className="wide"><dt>精确摘要</dt><dd><code>{item.employeeDefinitionDigest}</code></dd></div>
        <div><dt>Definition 状态</dt><dd>{item.published ? "已发布" : "尚未发布"}</dd></div>
        <div><dt>独立匹配授权</dt><dd>{item.matchable ? "已授权" : "未授权"}</dd></div>
      </dl>
      <h3>Definition 自身职责</h3>
      <ul>{item.responsibilities.map(value => <li key={value}>{value}</li>)}</ul>
    </section>

    <section className="employee-agent-profile" aria-labelledby="employee-agent-title">
      <header><div><p className="eyebrow">来源：Agent Definition</p><h3 id="employee-agent-title">Agent 的角色、目的与能力</h3></div>{agentExact && <span className="binding-status">精确修订已核对</span>}</header>
      {agentState === "LOADING" && <p role="status">正在读取 Agent Definition……</p>}
      {agentState === "UNAVAILABLE" && <p role="status">尚未接通或当前无权读取 Agent 详情；不会用 Employee 字段补写。</p>}
      {agentState === "READY" && !agentExact && <p role="status">未找到与成员 ID、revision、digest 全部一致的 Agent 修订。</p>}
      {agentExact && agent && <dl className="employee-profile-grid">
        <div><dt>Agent 名称</dt><dd>{agent.name}</dd></div>
        <div><dt>Agent 角色标题</dt><dd>{agent.revision.content.title || "未提供"}</dd></div>
        <div className="wide"><dt>业务目的</dt><dd>{agent.revision.content.businessPurpose || "未提供"}</dd></div>
        <div className="wide"><dt>职责</dt><dd><ul>{agent.revision.content.duties.map(value => <li key={value}>{value}</li>)}</ul></dd></div>
        <div className="wide"><dt>能力</dt><dd><ul className="employee-capabilities">{agent.revision.content.capabilities.map(value => <li key={value}>{value}</li>)}</ul></dd></div>
      </dl>}
      <p className="employee-disclosure">以上文字仍归 Agent Definition 所有，仅用于说明该员工装配的 Agent，不复制为新的员工或岗位权威事实。</p>
    </section>

    <section aria-labelledby="employee-bindings-title">
      <h3 id="employee-bindings-title">精确能力与资源绑定</h3>
      <p>绑定表示 configured / bound，不表示已经分配、运行或成功。</p>
      <ul className="px-binding-list">{item.members.map(member => <li key={`${member.kind}:${member.resourceId}`}><span>{kindLabel[member.kind]}</span><strong>{member.resourceId}</strong><small>{member.revisionId}</small><small>{member.digest}</small><Link to={exactCatalogLink(member)}>在资源目录核对</Link></li>)}</ul>
    </section>
  </>;
}
