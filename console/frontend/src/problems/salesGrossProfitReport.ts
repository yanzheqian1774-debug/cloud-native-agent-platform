type Rate={status:'BASELINE_ZERO';value?:never}|{status:'DEFINED';value:string};
export type Change={baseline:string;current:string;delta:string;rate:Rate};
export type Dim='region'|'channel'|'product';
type Row={rowId:string;sourceLine:number;period:string;currency:string;kind:string;netSales:string;cost:string;grossProfit:string;changeSign:number;deltaContributions:Record<'netSales'|'cost'|'grossProfit',string>;dimensions:Record<Dim,{value:string;valueStatus:string;rawValue:string;sourceValueState:string}>};
type Total={currency:string;netSales:Change;cost:Change;grossProfit:Change;sourceRows:{period:string;rowIds:string[]}[]};
export type Group=Total&{value:string;valueStatus:'UNRESOLVED'|'PROVIDED_UNVERIFIED'};
type Report={schemaVersion:'sales-diagnostic-output.v2';contractDigest:string;synthetic:true;operation:string;businessConclusion:'UNDETERMINED';periods:[string,string];currencyComparisons:Total[];dimensions:Record<Dim,Group[]>;rowContributions:Row[];excludedRows:{rowId:string;sourceLine:number;reason:string}[];inputIssues:unknown[];reconciliations:Record<Dim,{currency:string;groupCount:number;grossProfit:{sumGroupDelta:string;currencyDelta:string;matches:true}}[]>;sourceSnapshot:{resource_id:string;revision_id:string;digest:string}};
const names={region:'区域',channel:'渠道',product:'产品'};
const dims=Object.keys(names) as Dim[];
const obj=(v:unknown):v is Record<string,unknown>=>Boolean(v)&&typeof v==='object'&&!Array.isArray(v);
const money=(v:unknown):v is string=>typeof v==='string'&&/^-?\d{1,17}\.\d{2}$/.test(v);
const text=(v:unknown):v is string=>typeof v==='string';
function change(v:unknown):boolean{return obj(v)&&['baseline','current','delta'].every(k=>money(v[k]))&&obj(v.rate)&&(v.rate.status==='BASELINE_ZERO'?v.baseline==='0.00'&&!('value' in v.rate):v.rate.status==='DEFINED'&&v.baseline!=='0.00'&&text(v.rate.value)&&/^-?\d+(?:\.\d+)?(?:E[+-]?\d+)?$/.test(v.rate.value))}
function total(v:unknown):boolean{return obj(v)&&text(v.currency)&&/^[A-Z]{3}$/.test(v.currency)&&['netSales','cost','grossProfit'].every(k=>change(v[k]))&&Array.isArray(v.sourceRows)&&v.sourceRows.length===2&&v.sourceRows.every(r=>obj(r)&&text(r.period)&&Array.isArray(r.rowIds)&&r.rowIds.every(text))}
const every=(v:unknown,predicate:(row:unknown)=>boolean):boolean=>Array.isArray(v)&&v.every(predicate);
function group(v:unknown):boolean{return obj(v)&&total(v)&&text(v.value)&&['UNRESOLVED','PROVIDED_UNVERIFIED'].includes(String(v.valueStatus))&&(v.valueStatus==='UNRESOLVED'?v.value==='':v.value!=='')}
function dimensionGroups(v:unknown):boolean{return obj(v)&&dims.every(d=>every(v[d],group))}
function reconciliation(v:unknown):boolean{return obj(v)&&text(v.currency)&&Number.isSafeInteger(v.groupCount)&&obj(v.grossProfit)&&money(v.grossProfit.sumGroupDelta)&&v.grossProfit.sumGroupDelta===v.grossProfit.currencyDelta&&v.grossProfit.matches===true}
function reconciliations(v:unknown):boolean{return obj(v)&&dims.every(d=>every(v[d],reconciliation))}
function metrics(v:unknown):boolean{return obj(v)&&['netSales','cost','grossProfit'].every(k=>money(v[k]))}
function rowDimensions(v:unknown):boolean{return obj(v)&&dims.every(d=>{const label=v[d];return obj(label)&&text(label.value)&&text(label.valueStatus)&&text(label.rawValue)&&text(label.sourceValueState)})}
function row(v:unknown):boolean{return obj(v)&&text(v.rowId)&&Number.isSafeInteger(v.sourceLine)&&text(v.period)&&text(v.currency)&&text(v.kind)&&metrics(v)&&[-1,1].includes(Number(v.changeSign))&&metrics(v.deltaContributions)&&rowDimensions(v.dimensions)}
function reference(v:unknown):boolean{return obj(v)&&['resource_id','revision_id','digest'].every(k=>text(v[k]))}
export function parseGrossProfit(content:string):Report|null{
 try{
  if(new TextEncoder().encode(content).length>262144)return null;
  const v:unknown=JSON.parse(content);
  if(!obj(v)||v.schemaVersion!=='sales-diagnostic-output.v2'||v.contractDigest!=='b65eba5a15f1024efd3b80f3875e89a9dbfa39c659064f9825b276d4a0724eb2'||v.sourceDigest!=='8e3dfeabb34cdcee26d523e8a94b46e93c5c4338c43f33ce81e2b1f1ce925391'||v.synthetic!==true||v.businessConclusion!=='UNDETERMINED'||v.grossProfitDefinition!=='NET_SALES_MINUS_SIGNED_COST')return null;
  if(!['READ_DATA','VALIDATE_DATA','SUMMARIZE','ANALYZE_DATA','RENDER_REPORT'].includes(String(v.operation))||!Array.isArray(v.periods)||v.periods.length!==2||!v.periods.every(text)||v.periods[0]===v.periods[1])return null;
  if(!Array.isArray(v.currencyComparisons)||!v.currencyComparisons.length||!v.currencyComparisons.every(total)||!dimensionGroups(v.dimensions)||!reconciliations(v.reconciliations)||!every(v.rowContributions,row)||!every(v.excludedRows,r=>obj(r)&&text(r.rowId)&&Number.isSafeInteger(r.sourceLine)&&r.reason==='CANCELLED')||!Array.isArray(v.inputIssues)||!reference(v.sourceSnapshot))return null;
  return v as Report;
 }catch{return null}
}
