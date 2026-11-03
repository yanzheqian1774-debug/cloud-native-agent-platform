import {useState} from "react";

type Supplier={supplierId:string;rank:number;maxOverdueDays:number;overdueOrderCount:number;remainingByUnit:Record<string,string>;rankingReason:string};
type Report={schemaVersion:string;synthetic:true;operation:"RENDER_REPORT";title:string;assessmentDate:string;suppliers:Supplier[];anomalies:{orderId:string;rowIndex:number;reasons:string[]}[];gaps:string[];suggestedChecks:string[];sourceSnapshot:{resource_id:string;revision_id:string;digest:string}};
const record=(value:unknown):value is Record<string,unknown>=>Boolean(value)&&typeof value==="object"&&!Array.isArray(value);
const strings=(value:unknown):value is string[]=>Array.isArray(value)&&value.every(v=>typeof v==="string");
function report(content:string):Report|null{
 try{
  const v:unknown=JSON.parse(content);if(!record(v)||v.schemaVersion!=="synthetic-delivery-output.v1"||v.synthetic!==true||v.operation!=="RENDER_REPORT"||typeof v.title!=="string"||typeof v.assessmentDate!=="string")return null;
  if(!Array.isArray(v.suppliers)||!v.suppliers.every(s=>record(s)&&typeof s.supplierId==="string"&&Number.isSafeInteger(s.rank)&&Number.isSafeInteger(s.maxOverdueDays)&&Number.isSafeInteger(s.overdueOrderCount)&&record(s.remainingByUnit)&&Object.values(s.remainingByUnit).every(q=>typeof q==="string")&&typeof s.rankingReason==="string"))return null;
  if(!Array.isArray(v.anomalies)||!v.anomalies.every(a=>record(a)&&typeof a.orderId==="string"&&Number.isSafeInteger(a.rowIndex)&&strings(a.reasons))||!strings(v.gaps)||!strings(v.suggestedChecks))return null;
  if(!record(v.sourceSnapshot)||![v.sourceSnapshot.resource_id,v.sourceSnapshot.revision_id,v.sourceSnapshot.digest].every(x=>typeof x==="string"))return null;
  return v as Report;
 }catch{return null}
}
const reasons:Record<string,string>={PROMISED_DATE_MISSING_OR_INVALID:"承诺日期缺失或无效",QUANTITY_CONTRADICTION_OR_MISSING:"数量缺失或相互矛盾",DUPLICATE_ORDER_ID:"订单编号重复",MISSING_ORDER_ID_OR_INVALID_ROW:"订单编号缺失或记录无效"};
export function DeliveryArtifactView({content}:{content:string}){
 const value=report(content);const [selected,setSelected]=useState<string|null>(null);
 if(!value)return <pre>{content}</pre>;
 const supplier=value.suppliers.find(s=>s.supplierId===selected);
 return <section className="delivery-artifact" aria-label="供应商交付报告"><header><span className="prepared-state">合成订单验证</span><h4>{value.title}</h4><p>判定日期：{value.assessmentDate} · {value.suppliers.length} 家供应商 · {value.anomalies.length} 条异常</p></header><p>排名按最长逾期天数、逾期订单数及供应商编号确定；不同单位的数量分别展示。</p><div className="delivery-report-table"><table><caption>供应商交付优先级</caption><thead><tr><th scope="col">排名</th><th scope="col">供应商</th><th scope="col">最长逾期</th><th scope="col">逾期订单</th><th scope="col">未交数量</th></tr></thead><tbody>{value.suppliers.map(s=><tr key={s.supplierId}><td>{s.rank}</td><td><button type="button" onClick={()=>setSelected(selected===s.supplierId?null:s.supplierId)} aria-expanded={selected===s.supplierId}>{s.supplierId}</button></td><td>{s.maxOverdueDays} 天</td><td>{s.overdueOrderCount} 笔</td><td>{Object.entries(s.remainingByUnit).map(([unit,q])=><span className="delivery-quantity" key={unit}>{q} {unit}</span>)}</td></tr>)}</tbody></table></div>{supplier&&<p role="status">{supplier.supplierId} 排名依据：{supplier.rankingReason}</p>}<h4>异常与待补资料</h4>{value.anomalies.length?<ul>{value.anomalies.map(a=><li key={`${a.rowIndex}:${a.orderId}`}>{a.orderId}：{a.reasons.map(r=>reasons[r]??r).join("；")}</li>)}</ul>:<p>该产物未列出异常。</p>}<h4>后续核查</h4><ul>{value.suggestedChecks.map((s,i)=><li key={i}>{s}</li>)}</ul><div className="prepared-gap">{value.gaps.map((g,i)=><p key={i}>{g}</p>)}<p>本报告验证固定合成快照，不代表真实企业问题已解决；标准评价与人工决定分别记录。</p></div><details><summary>来源版本与原始产物</summary><p>{value.sourceSnapshot.resource_id} / {value.sourceSnapshot.revision_id}</p><code>{value.sourceSnapshot.digest}</code><pre>{content}</pre></details></section>;
}
