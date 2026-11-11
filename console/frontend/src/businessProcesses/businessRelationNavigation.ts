import type {FixedBusinessReference} from '../api/businessProcesses';
export function businessProcessHref(reference:FixedBusinessReference,activity?:string,handoff?:string){return '/business-processes?'+new URLSearchParams({process:reference.resource_id,revision:reference.revision_id,digest:reference.digest,...(handoff?{handoff}:activity?{activity}:{})})}
export function safeBusinessProcessReturn(raw:string|null){
 if(!raw||raw.length>1600)return null;
 try{const url=new URL(raw,window.location.origin),p=url.searchParams;if(url.origin!==window.location.origin||url.pathname!=='/business-processes'||url.hash||[...p.keys()].some(key=>!['process','revision','digest','activity','handoff','edit','draft'].includes(key)||p.getAll(key).length!==1))return null;
  if(p.has('draft'))return p.size===2&&p.get('edit')==='process'&&/^business-process:[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(p.get('draft')??'')?url.pathname+'?'+p:null;
  if(p.has('edit')&&p.get('edit')!=='process')return null;
  if(!['process','revision'].every(key=>{const value=p.get(key);return value&&value.trim()&&value.length<=200})||!/^[a-f0-9]{64}$/.test(p.get('digest')??''))return null;
  if(p.has('handoff')&&(!p.get('handoff')?.trim()||p.get('handoff')!.length>1000||p.has('activity')))return null;
  if(p.has('activity')&&(!p.get('activity')?.trim()||p.get('activity')!.length>200))return null;return url.pathname+'?'+p;
 }catch{return null}
}

export function businessReferenceHref(kind:'knowledge'|'employee',reference:FixedBusinessReference,returnTo:string){
 const back=safeBusinessProcessReturn(returnTo);if(!back)return null;
 if(kind==='employee')return '/employees?'+new URLSearchParams({employeeDefinitionId:reference.resource_id,employeeDefinitionRevisionId:reference.revision_id,employeeDefinitionDigest:reference.digest,section:'capabilities',detail:'1',businessProcessReturn:back});
 return '/knowledge?'+new URLSearchParams({kind:'knowledge',query:reference.resource_id,selected:reference.resource_id,resourceRevision:reference.revision_id,resourceDigest:reference.digest,businessProcessReturn:back});
}
