import type {SkillMcpResource} from '../api/skillMcpResources';

const identity = (v: string | null): v is string => !!v && v.length <= 200;
const digest = (v: string) => /^(sha256:)?[a-f0-9]{64}$/.test(v);
const tabs = new Set(['业务规则','输入输出','依赖','执行设置','测试','发布检查','版本','使用追溯','管理']);

/** Finite navigation only: no generic return URL, mutation, or authority. */
export function safeResourceReturn(raw: string | null): string | null {
  if (!raw || raw.length > 3000) return null;
  try {
    const url = new URL(raw, window.location.origin);
    if (url.origin !== window.location.origin || url.hash || !['/skills','/mcp'].includes(url.pathname)) return null;
    const p = url.searchParams;
    if ([...p.keys()].some(k => !['managedResource','resourceTab','query','status','kind'].includes(k) || p.getAll(k).length !== 1)
      || (p.has('kind') && p.get('kind') !== (url.pathname === '/skills' ? 'skill' : 'mcp'))
      || !identity(p.get('managedResource')) || (p.has('resourceTab') && !tabs.has(p.get('resourceTab')!))
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
  return revision ? exactSkillMcpHref(resource.kind,resource.resourceId,revision.revisionId,revision.digest) : null;
}

export function employeeReferenceHref(employee: {identity: string;revision: string}, resource: SkillMcpResource): string {
  const p = new URLSearchParams({employeeDefinitionId:employee.identity,employeeDefinitionRevisionId:employee.revision,detail:'1',section:'capabilities'});
  const back = safeResourceReturn(window.location.pathname + window.location.search);
  if (back && new URL(back,window.location.origin).searchParams.get('managedResource') === resource.resourceId) p.set('resourceBack',back);
  return '/employees?' + p;
}
