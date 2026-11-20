import type {ExecutionView} from '../api/preparedExecution';
import {formatTime} from '../journey/formatTime';

export function HumanDecisionSummary({view}:{view:ExecutionView}){
 const review=view.humanReview;
 if(review?.status!=='READABLE')return <section className="f3-work-card" aria-label="人工核阅记录"><h3>人工核阅记录</h3><p>尚未取得可核对的人工决定记录；不能据此判断是否已有人核阅。</p></section>;
 const value=review.decision;
 if(!view.outcome||value.confirmationId!==view.outcome.confirmationId||!['ACKNOWLEDGE_UNDETERMINED','DISAGREE'].includes(value.decision))return <section className="f3-work-card" aria-label="人工核阅记录"><h3>人工核阅记录</h3><p>人工决定与当前成果的关联待核实。</p></section>;
 return <section className="f3-work-card" aria-label="人工核阅记录"><h3>{value.decision==='DISAGREE'?'对结果有异议':'已核阅，仍待处理'}</h3><p>{value.reason}</p><p>这是对本次记录的核阅决定，不代表交付物已接受，也不代表业务问题已解决。</p><details><summary>查看核阅来源与准确记录</summary><dl><dt>核阅人</dt><dd>{value.actorId}</dd><dt>记录时间</dt><dd>{formatTime(review.createdAt)}</dd><dt>决定记录</dt><dd>{value.confirmationId}</dd><dt>评价记录</dt><dd>{value.evaluationId}</dd><dt>评价摘要</dt><dd>{value.evaluationDigest}</dd><dt>核阅快照</dt><dd>{value.reviewedSnapshotId}</dd><dt>快照摘要</dt><dd>{value.reviewedSnapshotDigest}</dd><dt>授权依据</dt><dd>{value.authorityBasis}</dd><dt>决定摘要</dt><dd>{review.digest}</dd></dl></details></section>;
}
