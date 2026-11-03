import {useEffect, useState} from "react";
import {Link, useSearchParams} from "react-router-dom";
import {JourneySteps} from "../journey/JourneySteps";
import {PageHeader,StatusBadge} from "../components/WorkspacePrimitives";
import {ControlledState} from "../shared/ControlledState";
import {PlanningDialogue} from "./PlanningDialogue";
import {planningRequest, type PlanningInput} from "./planningRequests";
import "./planning.css";

type TargetRead={problem:string;input:PlanningInput|null;error:string};
export function PlanningEntry() {
  const [params] = useSearchParams(), problem = params.get("problem") ?? "";
  const [stage, setStage] = useState("等待显式生成"),[readVersion,setReadVersion]=useState(0);
  const [read,setRead]=useState<TargetRead>({problem:"",input:null,error:""});
  // A URL change immediately withdraws the old target, even before this effect
  // runs. A late or failed GET can never enable generation for another problem.
  const current=read.problem===problem?read:null;
  const input=current?.input??null,error=current?.error??"";
  useEffect(()=>{
    let active=true;
    if(problem)planningRequest<PlanningInput>(`planning-input/${encodeURIComponent(problem)}`)
      .then(value=>{if(active)setRead({problem,input:value,error:""})})
      .catch(e=>{if(active)setRead({problem,input:null,error:e instanceof Error?e.message:"暂时无法读取已确认目标"})});
    return()=>{active=false};
  },[problem,readVersion]);
  const retry=()=>{setRead({problem:"",input:null,error:""});setReadVersion(value=>value+1)};
  return <main className="planning-page px-planning-entry">
    <PageHeader eyebrow="问题工作台 / 制定方案" title={input?.title??"读取已确认目标"} actions={<Link className="px-secondary-button" to={problem?`/work?problem=${encodeURIComponent(problem)}`:"/work"}>{problem?"修订目标或标准":"返回问题工作台"}</Link>}/>
    <div className="planning-layout"><section><JourneySteps current={3}/>
      {!problem?<ControlledState kind="not-found" title="请先选择业务问题" detail="从问题工作台打开已确认的问题与标准，不需要手填内部编号。"/>:
       error?<ControlledState kind="unavailable" title="已确认目标暂时无法读取" detail={error} action={<button type="button" onClick={retry}>重新读取已确认目标</button>}/>:
       !input?<ControlledState kind="loading" title="正在读取已确认目标与标准…" detail="读取完成前不能生成建议，不显示上一个问题的目标。"/>:null}
      <PlanningDialogue key={problem} problem={problem} disabled={!input} onStatus={setStage}>
        {input&&<section className="planning-card" aria-label="当前已确认目标"><header><h2>已确认目标</h2><StatusBadge tone="info">正式读取</StatusBadge></header><p>{input.description}</p><Link to={`/work?problem=${encodeURIComponent(problem)}`}>查看原问题与成功标准</Link><details><summary>本次目标的精确来源</summary><pre>{JSON.stringify(input.target,null,2)}</pre></details><p>没有账单或来源数据时，只能规划数据准备和后续分析，不能声称已完成分析。</p></section>}
      </PlanningDialogue>
    </section><aside><section className="planning-card"><h2>当前阶段</h2><p>制定方案 · {input?stage:"等待读取目标"}</p><p>问题和标准的正式修订在目标页面保存后生效。</p></section><section className="planning-card"><h2>执行边界</h2><p>确认只保存计划，不启动执行。资源缺口保留，不自动发布或变更业务数据。</p></section></aside></div>
  </main>;
}
