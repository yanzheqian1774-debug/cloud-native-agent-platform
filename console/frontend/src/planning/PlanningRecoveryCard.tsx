import {Link} from "react-router-dom";
import {continuationQuery} from "../api/conversationActions";
import {ExactReadRequest} from "./ExactReadRequest";
import {PlanningCallEvidence} from "./PlanningCallEvidence";
import {StatusBadge} from "../components/WorkspacePrimitives";

type Props={invocationId?:string|null;requestKey:string|null;status:string;reason?:string;busy:boolean;onRead:()=>void;sourceProblem:string;remoteRecoveryUnavailable?:boolean;diagnostic?:{locations?:{path:(string|number)[];rule?:string;contractFacts?:{subcondition?:string}}[]}};
export function PlanningRecoveryCard({invocationId,requestKey,status,reason,busy,onRead,sourceProblem,remoteRecoveryUnavailable=false,diagnostic}:Props){
 const missing=reason==="NO_DURABLE_TERMINAL_RESULT_DO_NOT_REDISPATCH";
 const invalid=status==="INVALID";
 const unknown=status==="OUTCOME_UNKNOWN";
 const title=status==="MISMATCH"?"原调用与当前问题不一致":unknown?(missing?"原调用尚无持久终态":"本次规划调用结果未知"):invalid?"原方案未通过契约校验":status==="FAILED"?"原调用已知失败":"正在核对原调用记录";
 return <section className="planning-card planning-recovery-card" aria-label="原规划调用只读恢复">
  <header><h2>{title}</h2><StatusBadge tone={unknown||invalid?"warning":"neutral"}>{status==="MISMATCH"?"上下文待核对":unknown?"UNKNOWN":invalid?"校验未通过":status==="FAILED"?"FAILED":"待读回"}</StatusBadge></header>
  <p>{status==="MISMATCH"?"读回记录属于另一个问题，当前生成和继续入口已停用。请核对原链接后再操作。":unknown?(missing?"已有原调用记录，但尚未取得持久终态。缺少终态或供应商回执不能证明未派发、未处理或零费用。":"原调用可能已到达供应商。超时或本地进程结束不能证明远端未处理，也不能据此认定零费用。") :invalid?"模型响应已记录，但方案声明未通过契约校验。没有创建可确认方案或启动执行；读取原记录不会自动修改或重发。":status==="FAILED"?"保留原失败记录。读取状态不会创建替代调用或自动重试。":"当前先读取原记录；未读回前，生成和继续入口保持停用。"}</p>
  <dl><dt>原调用编号</dt><dd><code>{invocationId??"尚未读回"}</code></dd>{requestKey&&<><dt>原请求标识</dt><dd><code>{requestKey}</code></dd></>}</dl>
  {unknown&&<p>保留原调用与预算预留；先核实可归属的供应商结果或用量，以及正式恢复依据。读取状态不会重试、追加额度或释放预留。</p>}
  {remoteRecoveryUnavailable&&<p>当前Kimi接入不提供远端观察或取消；重新读取不会取回远端输出，也不会取消远端调用。</p>}
  {invalid&&<details><summary>查看原校验定位</summary>{diagnostic?.locations?.length?diagnostic.locations.slice(0,16).map((item,index)=><p key={index}>{item.path[0]==='semantics'&&item.path[1]==='tasks'&&typeof item.path[2]==='number'?`第 ${item.path[2]+1} 项任务：`:'方案声明：'}{item.rule==='PLANNING_OPERATION_INPUT_CONFLICT'?'输入依赖契约未通过':'原契约校验未通过'}。{({EMPTY_PRODUCER_SET:'尚无实际输入生产者。',DECLARED_PRODUCER_SET_MISMATCH:'声明的输入类型集合与全部直接依赖输出集合不相等。',NO_COMPATIBLE_INPUT_KIND:'实际输入中没有该操作可消费的类型。',READ_ROOT_MISMATCH:'读取任务的根依赖或输入类型不符。'} as Record<string,string>)[item.contractFacts?.subcondition??'']??'具体子条件未记录，不能从原文摘要补造。'}</p>):<p>原记录未提供更细定位，不能补造无效输出原文。</p>}</details>}
  {invocationId&&status!=='MISMATCH'&&<PlanningCallEvidence key={invocationId} invocationId={invocationId}/>}
  {requestKey&&status!=='MISMATCH'&&<ExactReadRequest key={requestKey+'|'+sourceProblem} requestKey={requestKey} problemId={sourceProblem} invocationId={invocationId}/>}
  <div className="planning-recovery-actions"><button type="button" disabled={busy} onClick={onRead}>{busy?"正在读取原记录…":"读取原调用状态（不重试）"}</button><Link to={`/work?problem=${encodeURIComponent(sourceProblem)}${continuationQuery()}`}>返回原问题与标准</Link></div>
 </section>;
}
