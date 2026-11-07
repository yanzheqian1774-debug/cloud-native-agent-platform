import {useId} from 'react';
import {useViewString} from './workViewState';
import {csvCell,downloadArtifact} from './artifactDownloads';

import {parseGrossProfit} from './salesGrossProfitReport';
import type {Change,Group,Dim} from './salesGrossProfitReport';
const names={region:'区域',channel:'渠道',product:'产品'};
const dims=Object.keys(names) as Dim[];
const rate=(m:Change)=>m.rate.status==='BASELINE_ZERO'?'基期为零，变化率不适用':m.rate.value;
export function SalesGrossProfitArtifactView({content,query='',inline=false,viewKey}:{content:string;query?:string;inline?:boolean;viewKey?:string}){
 const report=parseGrossProfit(content),[saved,setDimension]=useViewString(viewKey,'gp-dimension','region'),[expanded,setExpanded]=useViewString(viewKey,'gp-expanded'),detailId=useId();
 const dimension:Dim=saved==='channel'||saved==='product'?saved:'region';
 if(!report)return <><p role="alert">毛利 v2 合同或数据格式不匹配，请核对原始产物。</p><pre>{content}</pre></>;
 const groups=report.dimensions[dimension].filter(r=>!query||[r.value,r.currency].some(v=>v.toLocaleLowerCase().includes(query.toLocaleLowerCase())));
 const key=(r:Group)=>JSON.stringify([r.currency,r.valueStatus,r.value]);
 const active=groups.find(r=>key(r)===expanded),ids=active?.sourceRows.flatMap(r=>r.rowIds)??[];
 const rows=report.rowContributions.filter(r=>ids.includes(r.rowId)&&r.currency===active?.currency);
 const label=(r:Group)=>r.valueStatus==='UNRESOLVED'?'未解析维度':r.value;
 function csv(){if(!report)return;const cells=[['固定合成快照；三维分解不能相加，不证明因果或业务改善'],['维度','项目','状态','币种','基期净销售额','本期净销售额','净销售变化','基期成本','本期成本','成本变化','基期毛利','本期毛利','毛利变化','毛利变化率','来源记录'],...dims.flatMap(d=>report.dimensions[d].map(r=>[names[d],label(r),r.valueStatus,r.currency,r.netSales.baseline,r.netSales.current,r.netSales.delta,r.cost.baseline,r.cost.current,r.cost.delta,r.grossProfit.baseline,r.grossProfit.current,r.grossProfit.delta,rate(r.grossProfit),r.sourceRows.flatMap(s=>s.rowIds).join('|')]))];downloadArtifact('sales-gross-profit-v2.csv','\ufeff'+cells.map(row=>row.map(csvCell).join(',')).join('\r\n'),'text/csv;charset=utf-8')}
 return <section className="delivery-artifact" aria-label={inline?'销售毛利关键数据':'销售毛利 v2 报告'}>
  <h4>两期销售、成本与毛利</h4><p>{report.periods.join(' → ')} · 固定合成资料 · 各币种分别核算 · 仍需人工核对</p>
  {!inline&&<div className="delivery-file-actions"><button type="button" onClick={csv}>下载分维度毛利 CSV</button><button type="button" onClick={()=>downloadArtifact('sales-gross-profit-v2.json',content,'application/json;charset=utf-8')}>下载原始产物 JSON</button></div>}
  <div className="delivery-report-table"><table><caption>逐币种两期毛利</caption><thead><tr><th>币种</th><th>基期毛利</th><th>本期毛利</th><th>毛利变化额</th><th>毛利变化率（比值）</th><th>净销售变化</th><th>成本变化</th></tr></thead><tbody>{report.currencyComparisons.map(r=><tr key={r.currency}><th scope="row">{r.currency}</th><td>{r.grossProfit.baseline}</td><td>{r.grossProfit.current}</td><td>{r.grossProfit.delta}</td><td>{rate(r.grossProfit)}</td><td>{r.netSales.delta}</td><td>{r.cost.delta}</td></tr>)}</tbody></table></div>
  <h4>分维度毛利变化贡献</h4><div className="delivery-file-actions">{dims.map(d=><button type="button" key={d} aria-pressed={d===dimension} onClick={()=>{setDimension(d);setExpanded('')}}>{names[d]}</button>)}</div>
  <p role="status">{names[dimension]}匹配 {groups.length} 项。区域、渠道、产品各自对账，三维分解不能相加。标签尚未规范核实。</p>
  <div className="delivery-report-table"><table><thead><tr><th>{names[dimension]}</th><th>币种</th><th>基期毛利</th><th>本期毛利</th><th>毛利变化额</th></tr></thead><tbody>{groups.map(r=><tr key={key(r)}><th scope="row"><button type="button" aria-expanded={key(r)===expanded} aria-controls={detailId} onClick={()=>setExpanded(key(r)===expanded?'':key(r))}>{label(r)}</button></th><td>{r.currency}</td><td>{r.grossProfit.baseline}</td><td>{r.grossProfit.current}</td><td>{r.grossProfit.delta}</td></tr>)}</tbody></table></div>
  {active&&<section id={detailId} aria-label="毛利贡献来源明细"><h4>{label(active)} · {active.currency} · 来源明细</h4><p>基期贡献取反，本期保留符号；退货保留负销售额与负成本。</p><div className="delivery-report-table"><table><thead><tr><th>记录</th><th>期间</th><th>类型</th><th>净销售额</th><th>成本</th><th>毛利</th><th>对变化额贡献</th><th>来源</th></tr></thead><tbody>{rows.map(r=><tr key={r.rowId}><th scope="row">{r.rowId}</th><td>{r.period}</td><td>{r.kind==='RETURN'?'退货':'销售'}</td><td>{r.netSales}</td><td>{r.cost}</td><td>{r.grossProfit}</td><td>{r.deltaContributions.grossProfit}</td><td>CSV 第 {r.sourceLine} 行</td></tr>)}</tbody></table></div><button type="button" onClick={()=>setExpanded('')}>收起来源明细</button></section>}
  <p>当前{names[dimension]}逐币种毛利对账：{report.reconciliations[dimension].map(r=>`${r.currency} ${r.grossProfit.sumGroupDelta} = ${r.grossProfit.currencyDelta}`).join('；')}</p>
  <h4>排除与口径</h4><ul>{report.excludedRows.map(r=><li key={r.rowId}>{r.rowId} · CSV 第 {r.sourceLine} 行 · 取消记录已排除</li>)}</ul><p>毛利＝带符号净销售额－带符号成本。取消金额未作财务校验；不跨币种汇总、不换汇。未知维度保留未解析组。本结果不证明因果、真实销售改善或验收完成。</p>
  <details><summary>来源版本与原始产物</summary><p>{report.sourceSnapshot.resource_id} / {report.sourceSnapshot.revision_id}</p><pre>{content}</pre></details>
 </section>;
}
