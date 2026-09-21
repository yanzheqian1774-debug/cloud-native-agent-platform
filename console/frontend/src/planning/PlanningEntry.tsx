import {useEffect, useState} from "react";
import {Link, useSearchParams} from "react-router-dom";
import {JourneySteps} from "../journey/JourneySteps";
import {PlanningDialogue} from "./PlanningDialogue";
import {planningRequest, type PlanningInput} from "./planningRequests";
import "./planning.css";
export function PlanningEntry() {
  const [params] = useSearchParams(), problem = params.get("problem") ?? "";
  const [stage, setStage] = useState("等待显式生成");
  const [input, setInput] = useState<PlanningInput | null>(null), [error, setError] = useState("");
  useEffect(()=>{let active=true;planningRequest<PlanningInput>(`planning-input/${encodeURIComponent(problem)}`).then(value=>{if(active)setInput(value)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[problem]);
  return <section className="planning-page"><header className="planning-heading"><div><p>问题工作台 / 制定方案</p><h1>{input?.title ?? "读取已确认目标"}</h1></div><Link to={`/work?problem=${encodeURIComponent(problem)}`}>修订目标或标准</Link></header><div className="planning-layout"><main><JourneySteps current={3}/><PlanningDialogue key={problem} problem={problem} disabled={!input} onStatus={setStage}><section className="planning-card"><h2>已确认目标</h2><p>{(input?.description ?? error) || "正在读取…"}</p><p>没有账单或来源数据时，只能规划数据准备和后续分析，不能声称已完成分析。</p></section></PlanningDialogue></main><aside><section className="planning-card"><h2>当前阶段</h2><p>制定方案 · {stage}</p><p>问题和标准的正式修订在目标页面保存后生效。</p></section><section className="planning-card"><h2>执行边界</h2><p>确认只保存计划，不启动执行。资源缺口保留，不自动发布或变更业务数据。</p></section></aside></div></section>;
}
