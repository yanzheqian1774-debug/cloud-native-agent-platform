import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { listDigitalEmployeeTemplates, type DigitalEmployeeTemplate } from "../api/productAssembly";

export function DigitalEmployeesPage() {
  const [items, setItems] = useState<DigitalEmployeeTemplate[] | null>(null);
  const [error, setError] = useState("");
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const view = params.get("view") === "technical" ? "technical" : "product";
  const selected = params.get("selected");
  useEffect(() => {
    let active = true;
    listDigitalEmployeeTemplates().then((value) => active && setItems(value)).catch((reason) => active && setError(reason.reasonCode ?? "DIGITAL_EMPLOYEE_PROJECTION_UNAVAILABLE"));
    return () => { active = false; };
  }, []);
  const visible = useMemo(() => items?.filter((item) => `${item.name}${item.purpose}${item.templateId}`.toLowerCase().includes(query.toLowerCase())) ?? [], [items, query]);
  const current = visible.find((item) => item.templateId === selected) ?? visible[0];
  function update(values: Record<string, string>) {
    const next = new URLSearchParams(params);
    Object.entries(values).forEach(([key, value]) => next.set(key, value));
    setParams(next);
  }
  return <main className="px-page px-center-page">
    <header className="px-page-title"><div><p>数字员工 <small>Digital Employee</small></p><h1>数字员工定义与装配</h1><span>数字员工是面向业务责任的可复用组合模板，不等于 Agent Definition、Agent Instance、Runtime Instance 或 Application。</span></div><button className="px-primary-button" disabled title="当前 API 只提供只读模板投影">创建入口不可用</button></header>
    <section className="px-truth-banner" role="status"><span className="px-status success">REAL</span><strong>模板来自持久化产品投影</strong><p>当前页面不具备执行权威；执行权限固定为 NONE；模板不代表正在运行的实例。</p></section>
    <div className="px-view-tabs" role="tablist" aria-label="数字员工视图"><button role="tab" aria-selected={view === "product"} className={view === "product" ? "active" : ""} onClick={() => update({ view: "product" })}>产品视图</button><button role="tab" aria-selected={view === "technical"} className={view === "technical" ? "active" : ""} onClick={() => update({ view: "technical" })}>技术视图</button></div>
    {error ? <div className="px-state danger" role="alert"><strong>数字员工投影暂不可用</strong><p>{error}</p><button onClick={() => location.reload()}>重试</button></div> : items === null ? <div className="px-state" role="status"><strong>正在读取数字员工定义</strong></div> : <div className="px-master-detail" role="region" aria-label="数字员工模板与定义集合"><aside><label className="px-center-search">搜索数字员工<input value={query} onChange={(event) => update({ q: event.target.value })} placeholder="按名称、职责或 ID 搜索" /></label>{visible.length ? <nav aria-label="数字员工定义列表"><ul className="agent-list">{visible.map((item) => <li key={item.templateId}><button className={current?.templateId === item.templateId ? "selected" : ""} aria-pressed={current?.templateId === item.templateId} onClick={() => update({ selected: item.templateId })}><strong>{item.name}</strong><small>{item.readiness} · {item.composition.length} 项绑定</small></button></li>)}</ul></nav> : <div className="px-empty"><strong>没有匹配的数字员工</strong><p>系统不会用虚构人员填充列表。</p></div>}</aside><section>{current ? <EmployeeDetail item={current} technical={view === "technical"} /> : <div className="px-empty large"><strong>尚无数字员工定义</strong><p>等待权威产品投影提供已发布组合模板。</p></div>}</section></div>}
    <section className="px-unavailable-grid"><article><span className="px-status neutral">NOT_CONNECTED</span><h2>Agent Instance</h2><p>当前模板投影没有实例创建或运行 authority。</p></article><article><span className="px-status neutral">UNAVAILABLE</span><h2>Assignment 与 Placement</h2><p>需要真实执行上下文；本页不生成分配、放置或健康状态。</p></article></section>
  </main>;
}

function EmployeeDetail({ item, technical }: { item: DigitalEmployeeTemplate; technical: boolean }) {
  return <article className="px-object-detail">
    <header><div><span className="px-status info">定义模板</span><h2>{item.name}</h2><p>{item.purpose}</p></div><Link to={item.deepLink}>查看 Agent Definition</Link></header>
    <section aria-label="Agent Definition 精确依据"><h3>Agent Definition 精确依据</h3><dl><dt>Agent Definition</dt><dd><code>{item.agentDefinition.identity}</code></dd><dt>Revision</dt><dd><code>{item.agentDefinition.revisionId ?? "NO_REVISION"}</code></dd><dt>Digest</dt><dd><code>{item.agentDefinition.digest ?? "NO_DIGEST"}</code></dd></dl></section>
    {technical ? <dl><dt>Template ID</dt><dd><code>{item.templateId}</code></dd><dt>Execution authority</dt><dd><code>{item.executionAuthority}</code></dd></dl> : <dl><dt>业务责任</dt><dd>{item.purpose}</dd><dt>装配就绪度</dt><dd>{item.readiness}</dd><dt>组合资源</dt><dd>{item.composition.length} 项精确绑定</dd><dt>执行状态</dt><dd>未执行</dd><dt>业务结果贡献</dt><dd>尚未采集</dd></dl>}
    <section><h3>能力与资源装配</h3>{item.composition.length ? <ul className="px-binding-list">{item.composition.map((binding, index) => <li key={`${binding.targetKind}:${binding.targetIdentity}:${index}`}><span>{binding.targetKind.replaceAll("_", " ")}</span><strong>{binding.targetIdentity}</strong><small>{binding.targetRevisionId ?? "NO_REVISION"}</small><small>{binding.targetDigest ?? "NO_DIGEST_DECLARED"}</small></li>)}</ul> : <div className="px-empty"><strong>未绑定资源</strong><p>没有可展示的组合关系。</p></div>}</section>
    <section><h3>限制与恢复建议</h3>{item.limitations.length ? <ul>{item.limitations.map((value) => <li key={value}>{value.replaceAll("_", " ")}</li>)}</ul> : <p>权威投影未声明额外限制。</p>}<p>如资源不可用，请进入对应 Agent、Skill、MCP、Knowledge 或 Runtime 页面检查精确修订。</p></section>
  </article>;
}
