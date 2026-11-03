import {Link} from "react-router-dom";
import {StatusBadge} from "../components/WorkspacePrimitives";

type Props={invocationId?:string|null;requestKey:string|null;status:string;reason?:string;busy:boolean;onRead:()=>void;sourceProblem:string};
export function PlanningRecoveryCard({invocationId,requestKey,status,reason,busy,onRead,sourceProblem}:Props){
 const missing=reason==="NO_DURABLE_TERMINAL_RESULT_DO_NOT_REDISPATCH";
 const unknown=status==="OUTCOME_UNKNOWN";
 const title=status==="MISMATCH"?"原调用与当前问题不一致":unknown?(missing?"原调用尚无持久终态":"供应商处理结果未知"):status==="FAILED"?"原调用已知失败":"正在核对原调用记录";
 return <section className="planning-card planning-recovery-card" aria-label="原规划调用只读恢复">
  <header><h2>{title}</h2><StatusBadge tone={unknown?"warning":"neutral"}>{status==="MISMATCH"?"上下文待核对":unknown?"UNKNOWN":status==="FAILED"?"FAILED":"待读回"}</StatusBadge></header>
  <p>{status==="MISMATCH"?"读回记录属于另一个问题，当前生成和继续入口已停用。请核对原链接后再操作。":unknown?(missing?"已有原调用记录，但尚未取得持久终态。缺少终态或供应商回执不能证明未派发、未处理或零费用。":"原调用可能已到达供应商。超时或本地进程结束不能证明远端未处理，也不能据此认定零费用。") :status==="FAILED"?"保留原失败记录。读取状态不会创建替代调用或自动重试。":"当前先读取原记录；未读回前，生成和继续入口保持停用。"}</p>
  <dl><dt>原调用编号</dt><dd><code>{invocationId??"尚未读回"}</code></dd>{requestKey&&<><dt>原请求标识</dt><dd><code>{requestKey}</code></dd></>}</dl>
  {unknown&&<p>保留原调用与预算预留；先核实可归属的供应商结果或用量，以及正式恢复依据。读取状态不会重试、追加额度或释放预留。</p>}
  <div className="planning-recovery-actions"><button type="button" disabled={busy} onClick={onRead}>{busy?"正在读取原记录…":"读取原调用状态（不重试）"}</button><Link to={`/work?problem=${encodeURIComponent(sourceProblem)}`}>返回原问题与标准</Link></div>
 </section>;
}
