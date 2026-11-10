import {DocumentArtifactView} from './DocumentArtifactView';
import {TabularArtifactView} from './TabularArtifactView';
import {useWorkScroll} from "./workViewState";
import {useEffect,useRef} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {exactDefinitionHref} from '../resources/definitionJourney';
import type {ExecutionView} from '../api/preparedExecution';
import {DeliveryArtifactView} from './DeliveryArtifactView';
import {SalesGrossProfitArtifactView} from './SalesGrossProfitArtifactView';
import {parseGrossProfit} from './salesGrossProfitReport';
import {SalesArtifactView} from './SalesArtifactView';
import {downloadArtifact} from './artifactDownloads';
import {artifactMatchesSource} from './artifactProvenance';
import {formatTime} from '../journey/formatTime';

type Artifact=ExecutionView['artifacts'][number];
function body(a?:Artifact):Record<string,unknown>|null{if(a?.contentAccess!=='AUTHORIZED'||!a.content)return null;try{const v:unknown=JSON.parse(a.content);return v&&typeof v==='object'&&!Array.isArray(v)?v as Record<string,unknown>:null}catch{return null}}
export function PreparedDeliverySummary({view,viewKey,selectedArtifact,onArtifact,onCloseArtifact,query,onReview}:{view:ExecutionView;viewKey:string;selectedArtifact:string;onArtifact:(id:string)=>void;onCloseArtifact:()=>void;query:string;onReview:()=>void}){
 const selected=selectedArtifact;const dialog=useRef<HTMLDialogElement>(null),returnFocus=useRef<HTMLElement|null>(null);
 const mismatched=view.artifacts.filter(a=>a.contentAccess==='AUTHORIZED'&&!artifactMatchesSource(a.content??'',view.preparation.source_snapshot));
 const report=view.artifacts.find(a=>body(a)?.operation==='RENDER_REPORT'&&!mismatched.includes(a)),value=body(report);
 const artifact=view.artifacts.find(a=>a.artifact_id===selected&&!mismatched.includes(a));
 const activeId=artifact?.artifact_id;
 useEffect(()=>{const node=dialog.current;if(activeId&&!node?.open)node?.showModal();if(!activeId&&node?.open)node.close()},[activeId]);
 function close(){dialog.current?.close();onCloseArtifact();returnFocus.current?.focus({preventScroll:true})}
 function open(a:Artifact,target:HTMLElement){if(mismatched.includes(a))return;returnFocus.current=target;onArtifact(a.artifact_id)}
 useWorkScroll(dialog,viewKey+":artifact:"+(activeId??"none"),Boolean(activeId));
 const salesV2=value?.schemaVersion==='sales-diagnostic-output.v2'&&Boolean(parseGrossProfit(report?.content??''));
 const sales=value?.schemaVersion==='sales-diagnostic-output.v1'||salesV2;
 const malformedV2=value?.schemaVersion==='sales-diagnostic-output.v2'&&!salesV2;
 const document=value?.schemaVersion==='document-review-output.v1';
 const tabular=value?.schemaVersion==='tabular-diagnostic-output.v1';
 const delivery=value?.schemaVersion==='synthetic-delivery-output.v1';
 const orders=Array.isArray(value?.orderDetails)?value.orderDetails:[];
 const suppliers=Array.isArray(value?.suppliers)?value.suppliers:[];
 const anomalies=Array.isArray(value?.anomalies)?value.anomalies:[];
 const stats=delivery?[{number:orders.filter(r=>r&&typeof r==='object'&&r.overdue===true).length,label:'确定延期'},{number:suppliers.length,label:'涉及供应商'},{number:anomalies.length,label:'异常单列'}]:sales?[{number:Array.isArray(value?.currencyComparisons)?value.currencyComparisons.length:0,label:'币种分别核对'},{number:2,label:'对比期间'},{number:Array.isArray(value?.excludedRows)?value.excludedRows.length:0,label:'取消记录排除'}]:[{number:view.progress?.tasks.filter(t=>t.state==='SUCCEEDED').length??0,label:'任务完成'},{number:view.artifacts.length,label:'持久化产物'},{number:view.outcome?view.outcome.evaluation.results.filter(r=>r.result==='SATISFIED').length:'—',label:'业务标准已满足'}];
 const source=view.preparation.source_snapshot;
 const [params]=useSearchParams();
 let sourceHref:string|null=`/knowledge?resourceId=${encodeURIComponent(source.resource_id)}&revisionId=${encodeURIComponent(source.revision_id)}`;
 if(import.meta.env.VITE_RESOURCE_DIRECTORY_ENABLED==='true'){
  sourceHref=null;
  if([source.resource_id,source.revision_id].every(v=>typeof v==='string'&&v.length>0&&v.length<=200)&&/^[a-f0-9]{64}$/.test(source.digest)&&/^[a-f0-9]{64}$/.test(view.digest)){
   const exact=exactDefinitionHref('knowledge',source.resource_id,source.revision_id,source.digest),query=new URLSearchParams(exact.split('?')[1]);
   query.set('fromExecution',view.digest);
   const conversation=params.get('conversation')??params.get('returnConversation');
   if(conversation&&conversation.length<=200)query.set('returnConversation',conversation);
   sourceHref='/knowledge?'+query;
  }
 }
 return <div className="px-delivery-summary">{mismatched.length>0&&<p role="alert" className="prepared-gap">报告来源版本与本次执行不一致，已停止展示其中的数据。原产物记录保留，请核对来源后再查看。</p>}{malformedV2&&<p role="alert">毛利 v2 合同或数据格式不匹配，摘要暂不可用。</p>}<div className="px-delivery-feedback"><p>{delivery?`分析已完成：${stats[0].number} 条确定延期，涉及 ${stats[1].number} 家供应商；${stats[2].number} 条异常单列。`:salesV2?'分维度毛利结果已生成，各币种分别列示；仍需核对标准与适用范围。':sales?'销售变化诊断已完成，已分别核对各币种的净销售额、毛利与维度变化贡献。':'本次只读执行已完成，交付产物和执行依据已保存。'}<br/>明细、汇总和报告已备好。可以直接查看结果，再核对标准与适用范围。</p></div><section className="px-result-card"><h3><span aria-hidden="true">▥</span> 结果摘要</h3><div className="px-result-metrics" aria-label="交付结果摘要">{stats.map((s,i)=><div key={s.label} className={`metric-${i}`}><strong>{s.number}</strong><span>{s.label}</span></div>)}</div>{!delivery&&!sales&&<p className="px-business-evaluation-note">执行完成表示任务已运行并保存产物；业务标准是否满足另行评价。{view.outcome?<>当前已确认满足 {view.outcome.evaluation.results.filter(r=>r.result==='SATISFIED').length} 项，未确认不代表已经通过。</>:<>业务标准评价尚未读回，不将其记为零或通过。</>}检查结论与具体依据见下方。</p>}</section>{report&&document&&<section className="px-result-card"><DocumentArtifactView content={report.content??''}/></section>}{report&&tabular&&<section className="px-result-card"><TabularArtifactView content={report.content??''}/></section>}{report&&(delivery||sales)&&<section className="px-result-card px-inline-business-result"><h3>{sales?"销售变化概览":"供应商交付概览"}</h3>{salesV2?<SalesGrossProfitArtifactView viewKey={viewKey+":inline:"+report.digest} content={report.content??''} query={query} inline/>:sales?<SalesArtifactView viewKey={viewKey+":inline:"+report.digest} content={report.content??''} query={query} inline/>:<DeliveryArtifactView viewKey={viewKey+":inline:"+report.digest} content={report.content??''} query={query} inline/>}</section>}<section className="px-result-card"><h3><svg aria-hidden="true" viewBox="0 0 24 24"><path fill="currentColor" d="M4 2h10l6 6v14H4z"/><path fill="none" stroke="#fff" d="M8 11h8M8 15h8M8 19h5"/></svg>成果文件 · 可直接查看</h3><div className="px-result-files">{view.artifacts.map((a,i)=>{const op=view.preparation.participants.find(p=>p.task_id===a.task_id)?.skill.operation;const title=op==='RENDER_REPORT'?(document?'文档检查报告':sales?'销售变化诊断报告':tabular?'指标诊断报告':'交付分析报告'):op==='READ_DATA'?'来源快照与明细':'分析汇总';return <article key={a.artifact_id}><span className={`px-file-icon ${op==='RENDER_REPORT'?'is-report':''}`} aria-hidden="true">JSON</span><div><strong>{title}.json</strong><p>{mismatched.includes(a)?'来源版本不一致，需重新核对':a.contentAccess==='AUTHORIZED'?`${formatTime(a.created_at)} · 已保存 ${a.bytes.toLocaleString()} 字节`:'内容读取权限尚未取得'}</p></div><button disabled={a.contentAccess!=='AUTHORIZED'||mismatched.includes(a)} type="button" className="artifact-file-open" data-artifact-id={a.artifact_id} onClick={e=>open(a,e.currentTarget)} aria-label={`查看${title}`}>查看</button><button disabled={a.contentAccess!=='AUTHORIZED'||mismatched.includes(a)} type="button" className="px-file-download" onClick={()=>downloadArtifact(`delivery-${i+1}.json`,a.content??'','application/json;charset=utf-8')} aria-label={`下载${title}`}>↓</button></article>})}</div></section><section className="px-result-card px-delivery-next"><h3><span aria-hidden="true">◎</span> 交付依据与下一步</h3><p>方案 v{view.preparation.plan_version} · 隔离合成资料 · 只读分析 · {view.outcome?.confirmationId?'结果决定与限制已留存':'仍需人工核对'}</p><div>{sourceHref?<Link to={sourceHref}>查看来源版本</Link>:<span role="status">来源版本依据尚未完整读回</span>}<button type="button" className="px-primary-button" onClick={onReview}>查看验收摘要</button></div></section><dialog ref={dialog} className="px-artifact-dialog" aria-label="成果文件详情" onCancel={e=>{e.preventDefault();close()}}><header><div><span>本次交付 · 只读查看</span><h2>{view.preparation.semantics.tasks.find(t=>t.task_id===artifact?.task_id)?.title??'成果文件'}</h2></div><button type="button" onClick={close}>返回成果</button></header>{artifact&&<><details className="px-artifact-lineage"><summary>任务、产物与来源依据</summary><dl><dt>产物</dt><dd>{artifact.artifact_id}</dd><dt>任务</dt><dd>{artifact.task_id}</dd><dt>摘要</dt><dd>{artifact.digest}</dd><dt>来源版本</dt><dd>{source.resource_id} / {source.revision_id}</dd></dl>{sourceHref?<Link to={sourceHref}>查看精确来源</Link>:<span role="status">来源版本依据尚未完整读回</span>}</details>{body(artifact)?.schemaVersion==='document-review-output.v1'?<DocumentArtifactView content={artifact.content??''}/>:body(artifact)?.schemaVersion==='tabular-diagnostic-output.v1'?<TabularArtifactView content={artifact.content??''}/>:body(artifact)?.schemaVersion==='sales-diagnostic-output.v2'?<SalesGrossProfitArtifactView key={artifact.digest} viewKey={viewKey+":dialog:"+artifact.digest} content={artifact.content??''} query={query}/>:body(artifact)?.schemaVersion==='sales-diagnostic-output.v1'?<SalesArtifactView key={artifact.digest} viewKey={viewKey+":dialog:"+artifact.digest} content={artifact.content??''} query={query}/>:<DeliveryArtifactView key={artifact.digest} viewKey={viewKey+":dialog:"+artifact.digest} content={artifact.content??''} query={query}/>}</>}</dialog></div>;
}
