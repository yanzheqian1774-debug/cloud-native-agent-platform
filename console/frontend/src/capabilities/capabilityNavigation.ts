import type {CapabilityBinding,CapabilityDetail} from '../api/businessCapabilities';
const identity=(value:string|null):value is string=>!!value&&value.length<=200;
export function safeCapabilityReturn(raw:string|null):string|null{
 if(!raw||raw.length>1800)return null;
 try{
  const url=new URL(raw,window.location.origin),p=url.searchParams;
  if(url.origin!==window.location.origin||url.pathname!=='/capabilities'||url.hash)return null;
  if([...p.keys()].some(key=>!['capability','revision','digest','returnConversation'].includes(key)||p.getAll(key).length!==1))return null;
  if(!identity(p.get('capability'))||!identity(p.get('revision'))||!/^[a-f0-9]{64}$/.test(p.get('digest')??'')||(p.has('returnConversation')&&!identity(p.get('returnConversation'))))return null;
  return url.pathname+'?'+p;
 }catch{return null}
}
export function capabilityMemberHref(binding:CapabilityBinding,detail:CapabilityDetail,conversation:string|null):string|null{
 const backParams=new URLSearchParams({capability:detail.revision.capability_id,revision:detail.revision.revision_id,digest:detail.digest});if(conversation)backParams.set('returnConversation',conversation);
 const back='/capabilities?'+backParams,ref=binding.reference;
 if(binding.kind==='EMPLOYEE')return '/employees?'+new URLSearchParams({employeeDefinitionId:ref.resource_id,employeeDefinitionRevisionId:ref.revision_id,employeeDefinitionDigest:ref.digest,section:'capabilities',detail:'1',capabilityReturn:back});
 const routes:Partial<Record<CapabilityBinding['kind'],[string,string]>>={SKILL:['/skills','skill'],MCP:['/mcp','mcp'],KNOWLEDGE:['/knowledge','knowledge']};
 const target=routes[binding.kind];if(!target)return null;
 return target[0]+'?'+new URLSearchParams({kind:target[1],query:ref.resource_id,selected:ref.resource_id,resourceRevision:ref.revision_id,resourceDigest:ref.digest,capabilityReturn:back,...(conversation?{returnConversation:conversation}:{})});
}
