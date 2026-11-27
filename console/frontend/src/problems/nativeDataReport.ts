import type {NativeLoopResult} from './NativeLoopTrace';
const object=(v:unknown):v is Record<string,unknown>=>Boolean(v)&&typeof v==='object'&&!Array.isArray(v);
const adapters:Record<string,string>={"native-declarative-tabular-readonly":"7fef0e1a6e01c0252344b711c09632e37374b14cb61133ffbcd33d2c1c03d8be","native-synthetic-delivery-readonly":"3186a76b272c860f038cf7e328e6b41ccf3101e99cb87860c9ef696546f7ba3d"};
const digest=(v:unknown):v is string=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const ref=(a:unknown,b:unknown)=>object(a)&&object(b)&&['resource_id','revision_id','digest'].every(k=>typeof a[k]==='string'&&a[k]===b[k]);
// Only the server-verified report field is a business view. Raw TOOL_RESULT
// observations remain execution evidence and never substitute for this receipt.
export function nativeDataReport(content:string){
 try{
  const v:unknown=JSON.parse(content);
  if(!object(v)||v.schemaVersion!=='native-data-output.v1'||v.operation!=='RENDER_REPORT'||v.synthetic!==true||v.externalWrites!==false||v.businessConclusion!=='UNDETERMINED')return null;
  const a=v.adapter,r=v.nativeReport,c=v.nativeReportVerification,l=v.nativeLoop;
  if(!object(a)||!object(r)||!object(c)||!object(l)||a.effectPolicy!=='READ_ONLY'||a.externalWrites!==false||a.adapterRevision!=='1'||typeof a.adapterId!=='string'||adapters[a.adapterId]!==a.configurationDigest)return null;
  const schema=a.adapterId==='native-synthetic-delivery-readonly'?'synthetic-delivery-output.v1':a.adapterId==='native-declarative-tabular-readonly'?'tabular-diagnostic-output.v1':null;
  if(!schema||r.schemaVersion!==schema||r.operation!=='RENDER_REPORT'||r.synthetic!==true||!ref(r.sourceSnapshot,v.sourceSnapshot))return null;
  if(c.schemaVersion!=='native-data-report-verification.v1'||c.businessAcceptance!==false||!digest(c.digest)||c.adapterDigest!==a.configurationDigest||c.sourceDigest!==v.sourceDigest||!digest(c.sourceDigest)||!ref(c.sourceSnapshot,v.sourceSnapshot)||!digest(c.reportDigest)||c.reportDigest!==r.reportDigest)return null;
  if(l.status!=='SUCCEEDED'||!object(l.answer)||l.answer.reportDigest!==c.reportDigest||!Array.isArray(l.trace)||!l.trace.length)return null;
  const last=l.trace.at(-1);if(!object(last)||!object(last.decision)||last.decision.action!=='FINISH'||!object(last.verification)||last.verification.passed!==true)return null;
  if(schema==='synthetic-delivery-output.v1'&&(r.adapterDigest!==a.configurationDigest||r.sourceDigest!==c.sourceDigest||l.answer.businessAcceptance!==false))return null;
  return {report:r,content:JSON.stringify(r),loop:l as unknown as NativeLoopResult,kind:schema};
 }catch{return null}
}

const executors:Record<string,string>={"native-declarative-tabular-readonly":"2f4d59a6e618f00908d7bc4263505d18121ad5d54c028a2997ce52dbea23a9d4","native-synthetic-delivery-readonly":"fe92bb7e92bfce39838c361d22e8ea850c3d76fad3eb8f38e34eee770c13098e"};
export function nativeDataExecutorMatches(content:string,participant:unknown){
 try{const v:unknown=JSON.parse(content);if(!object(v)||v.schemaVersion!=='native-data-output.v1')return true;
  if(!object(v.adapter)||!object(participant)||typeof v.adapter.adapterId!=='string')return false;
  return participant.executor_id===v.adapter.adapterId&&participant.executor_revision==='1'&&participant.executor_digest===executors[v.adapter.adapterId]&&Boolean(executors[v.adapter.adapterId]);
 }catch{return true}
}
