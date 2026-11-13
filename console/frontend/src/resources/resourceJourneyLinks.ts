import {safeCapabilityReturn} from '../capabilities/capabilityNavigation';
import type {SkillMcpResource} from '../api/skillMcpResources';

const identity = (v: string | null): v is string => !!v && v.length <= 200;
const digest = (v: string) => /^(sha256:)?[a-f0-9]{64}$/.test(v);
const tabs = new Set(['业务规则','输入输出','依赖','执行设置','测试','发布检查','版本','使用追溯','管理']);

/** Finite navigation only: no generic return URL, mutation, or authority. */
export function safeResourceReturn(raw: string | null): string | null {
  if (!raw || raw.length > 3000) return null;
  try {
    const url = new URL(raw, window.location.origin);
    if (url.origin !== window.location.origin || url.hash || !['/skills','/mcp','/agents','/knowledge'].includes(url.pathname)) return null;
    const p = url.searchParams;
    if(p.has('selected')){
      const expected={'/agents':'agent','/knowledge':'knowledge','/skills':'skill','/mcp':'mcp'}[url.pathname];
      if([...p.keys()].some(k=>!['selected','resourceRevision','resourceDigest','kind','query','status','resourceView','resourceSection'].includes(k)||p.getAll(k).length!==1)||p.get('kind')!==expected||!identity(p.get('selected'))||!identity(p.get('resourceRevision'))||!digest(p.get('resourceDigest')??'')||(p.get('query')?.length??0)>200||(p.get('status')?.length??0)>32)return null;
      if((p.has('resourceView')&&p.get('resourceView')!=='professional')||(p.has('resourceSection')&&!['overview','content','impact'].includes(p.get('resourceSection')!)))return null;
      p.sort();return url.pathname+'?'+p;
    }
    if ([...p.keys()].some(k => !['managedResource','resourceTab','resourceView','resourceSection','viewRevision','query','status','kind','returnConversation','fromExecution'].includes(k) || p.getAll(k).length !== 1)
      || (p.has('kind') && p.get('kind') !== ({'/skills':'skill','/mcp':'mcp','/agents':'agent','/knowledge':'knowledge'}[url.pathname]))
      || !identity(p.get('managedResource')) || (p.has('resourceTab') && !tabs.has(p.get('resourceTab')!))
      || (p.has('resourceView')&&p.get('resourceView')!=='professional')
      || (p.has('resourceSection')&&!['overview','content','impact','history'].includes(p.get('resourceSection')!))
      || (p.has('viewRevision')&&!identity(p.get('viewRevision')))
      || (p.has('returnConversation')&&!identity(p.get('returnConversation'))) || (p.has('fromExecution')&&!/^[a-f0-9]{64}$/.test(p.get('fromExecution')!))
      || (p.get('query')?.length ?? 0) > 200 || (p.get('status')?.length ?? 0) > 32) return null;
    p.sort();
    return url.pathname + '?' + p;
  } catch { return null; }
}

export function exactSkillMcpHref(kind: 'skill' | 'mcp', id: string, revision: string, contentDigest: string): string {
  if (!identity(id) || !identity(revision) || !digest(contentDigest)) throw Error('RESOURCE_REFERENCE_INVALID');
  return (kind === 'skill' ? '/skills?' : '/mcp?') + new URLSearchParams({kind,query:id,selected:id,resourceRevision:revision,resourceDigest:contentDigest});
}

export function publishedResourceHref(resource: SkillMcpResource): string | null {
  const revision = resource.revisions.find(r => r.revisionId === resource.publishedRevisionId && r.state === 'PUBLISHED');
  if(!revision)return null;const href=new URL(exactSkillMcpHref(resource.kind,resource.resourceId,revision.revisionId,revision.digest),window.location.origin),current=new URLSearchParams(window.location.search),conversation=current.get('returnConversation'),execution=current.get('fromExecution');if(identity(conversation))href.searchParams.set('returnConversation',conversation);if(execution&&/^[a-f0-9]{64}$/.test(execution))href.searchParams.set('fromExecution',execution);return href.pathname+href.search;
}

export function employeeReferenceHref(employee: {identity: string;revision: string}, resource: SkillMcpResource): string {
  const p = new URLSearchParams({employeeDefinitionId:employee.identity,employeeDefinitionRevisionId:employee.revision,detail:'1',section:'capabilities'});
  const back = safeResourceReturn(window.location.pathname + window.location.search);
  if (back && new URL(back,window.location.origin).searchParams.get('managedResource') === resource.resourceId) p.set('resourceBack',back);
  return '/employees?' + p;
}

const employeeTeamKeys=['teamRef','teamRevision','teamDigest','teamDirectoryQuery'];
function employeeTeamContext(params:URLSearchParams){
 if(!employeeTeamKeys.some(k=>params.has(k)))return null;
 if(employeeTeamKeys.some(k=>params.getAll(k).length>1)||!identity(params.get('teamRef'))||!identity(params.get('teamRevision'))||!/^[a-f0-9]{64}$/.test(params.get('teamDigest')??'')||(params.get('teamDirectoryQuery')?.length??0)>200)return null;
 return {teamRef:params.get('teamRef')!,teamRevision:params.get('teamRevision')!,teamDigest:params.get('teamDigest')!,...(params.has('teamDirectoryQuery')?{teamDirectoryQuery:params.get('teamDirectoryQuery')!}:{})};
}
export const employeeReturnKeys=['employeeRef','employeeRev','employeeDigest','employeeResourceBack','employeeSection','employeeViewReturn',...employeeTeamKeys];
export function employeeReturnContext(params:URLSearchParams){
 if(!employeeReturnKeys.some(k=>params.has(k)))return null;
 if(employeeReturnKeys.some(k=>params.getAll(k).length>1)||!identity(params.get('employeeRef'))||!identity(params.get('employeeRev'))||!/^[a-f0-9]{64}$/.test(params.get('employeeDigest')??''))throw Error('EMPLOYEE_RETURN_UNSAFE');
 const capabilityRaw=params.get('capabilityReturn'),capabilityBack=capabilityRaw?safeCapabilityReturn(capabilityRaw):null;
 if(params.getAll('capabilityReturn').length>1||(capabilityRaw&&!capabilityBack))throw Error('EMPLOYEE_RETURN_UNSAFE');
 const raw=params.get('employeeResourceBack'),back=raw?safeResourceReturn(raw):null;if(raw&&!back)throw Error('EMPLOYEE_RETURN_UNSAFE');
 const section=params.get('employeeSection')??'capabilities',view=params.get('employeeViewReturn');
 if(!['overview','capabilities','instances','assignments'].includes(section)||(view!==null&&view!=='professional'))throw Error('EMPLOYEE_RETURN_UNSAFE');
 const team=employeeTeamContext(params);if(employeeTeamKeys.some(k=>params.has(k))&&!team)throw Error('EMPLOYEE_RETURN_UNSAFE');
 return {section,view,id:params.get('employeeRef')!,revision:params.get('employeeRev')!,digest:params.get('employeeDigest')!,back,capabilityBack,team};
}
export function employeeMemberHref(href:string,item:{employeeDefinitionId:string;employeeDefinitionRevisionId:string;employeeDefinitionDigest:string}){
 const u=new URL(href,window.location.origin);if(u.origin!==window.location.origin||!['/skills','/mcp','/knowledge','/agents'].includes(u.pathname))return href;
 u.searchParams.set('employeeRef',item.employeeDefinitionId);u.searchParams.set('employeeRev',item.employeeDefinitionRevisionId);u.searchParams.set('employeeDigest',item.employeeDefinitionDigest);
 const current=new URLSearchParams(window.location.search),section=current.get('section')??'overview';
 if(['overview','capabilities','instances','assignments'].includes(section))u.searchParams.set('employeeSection',section);
 if(current.get('employeeView')==='professional')u.searchParams.set('employeeViewReturn','professional');
 const capabilityBack=safeCapabilityReturn(current.get('capabilityReturn'));if(current.getAll('capabilityReturn').length===1&&capabilityBack)u.searchParams.set('capabilityReturn',capabilityBack);
 const team=employeeTeamContext(current);if(team)for(const [key,value] of Object.entries(team))u.searchParams.set(key,value);
 const back=safeResourceReturn(current.get('resourceBack'));if(back)u.searchParams.set('employeeResourceBack',back);
 employeeReturnContext(u.searchParams);return u.pathname+'?'+u.searchParams;
}
