import type {Ref} from '../api/preparedExecution';

// Known analytical reports must describe the exact source selected for this run.
// Plain-text and other artifacts retain raw viewing; they do not become reports.
export function artifactMatchesSource(content:string,expected:Ref){
 try{
  const value:unknown=JSON.parse(content);
  if(!value||typeof value!=='object'||!('schemaVersion' in value))return true;
  const document=value as Record<string,unknown>;
  if(!['sales-diagnostic-output.v1','sales-diagnostic-output.v2','synthetic-delivery-output.v1'].includes(String(document.schemaVersion)))return true;
  const ref=document.sourceSnapshot;
  return Boolean(ref)&&typeof ref==='object'&&(['resource_id','revision_id','digest'] as const).every(k=>(ref as Record<string,unknown>)[k]===expected[k]);
 }catch{return true}
}
