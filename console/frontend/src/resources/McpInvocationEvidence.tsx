import type {SkillMcpResource} from '../api/skillMcpResources';
import {mcpInvocationOutcome} from './mcpInvocationOutcome';
import {formatTime} from '../journey/formatTime';

type Invocation=SkillMcpResource['invocations'][number];
export function McpInvocationEvidence({item}:{item:Invocation}){
 const outcome=mcpInvocationOutcome(item);
 return <section aria-label="管理调用结果"><strong>{outcome.label}</strong>{item.toolName&&<> · {item.toolName}</>}{item.invokedAt&&<> · {formatTime(item.invokedAt)}</>}{outcome.note&&<p>{outcome.note}</p>}<p>管理调用记录不代表任务执行成功或业务问题已解决。</p><details><summary>查看调用技术记录</summary><dl><dt>调用记录</dt><dd>{item.invocationId}</dd><dt>技术状态</dt><dd>{item.status}</dd><dt>请求阶段</dt><dd>{item.dispatchState??'未记录'}</dd><dt>原因</dt><dd>{item.reasonCode??'未提供'}</dd><dt>来源版本</dt><dd>{item.revisionId??'未记录'}</dd><dt>来源摘要</dt><dd>{item.revisionDigest??'未记录'}</dd><dt>发现快照</dt><dd>{item.snapshotId??'未记录'}</dd><dt>快照摘要</dt><dd>{item.snapshotDigest??'未记录'}</dd></dl><pre>{JSON.stringify({input:item.input,result:item.result},null,2)}</pre></details></section>;
}
