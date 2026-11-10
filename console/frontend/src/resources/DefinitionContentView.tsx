import {KnowledgeDocumentContent} from './KnowledgeDocumentContent';
import {Link} from 'react-router-dom';
import type {DirectoryItem} from '../api/resourceDirectory';
import {readDirectoryResource} from '../api/resourceDirectory';
import {readWorkbenchSession} from '../api/businessWorkspace';
import {useEffect,useState} from 'react';
import {exactDefinitionHref} from './definitionJourney';
import {exactSkillMcpHref,safeResourceReturn} from './resourceJourneyLinks';

export function DefinitionContentView({kind,content}:{kind:'agent'|'knowledge';content:Record<string,unknown>}){
 if(kind==='knowledge'){const source=content.source as Record<string,unknown>|undefined,docs=content.documents as {documentId:string;chunks:{content:string}[]}[]|undefined;return <section aria-label="知识正文与来源"><h2>知识正文与来源</h2><p>出处：{String(source?.provenance??'未提供')}</p><p>来源：{String(source?.sourceId??'未提供')}</p>{docs?.map(d=><article key={d.documentId}>{d.chunks.map((c,i)=><KnowledgeDocumentContent key={i} text={c.content}/>)}</article>)}<p>这里核对保存的正文版本；发布不代表索引已建立、已检索或已被业务采用。</p></section>}
 const bindings=content.bindings as Record<string,unknown>|undefined;
 return <section aria-label="Agent职责与准确绑定"><h2>{String(content.title??'Agent职责')}</h2><p>{String(content.businessPurpose??'未提供业务用途')}</p><ul>{Array.isArray(content.duties)&&content.duties.map((x,i)=><li key={i}>{String(x)}</li>)}</ul><h3>准确资源绑定</h3>{(['skills','knowledge','mcpTools'] as const).map(group=>{const values=bindings?.[group];return Array.isArray(values)&&values.map((r:{resourceId:string;revisionId:string;digest:string;toolName?:string},i)=><p key={group+i}><Link to={group==='knowledge'?exactDefinitionHref('knowledge',r.resourceId,r.revisionId,r.digest):exactSkillMcpHref(group==='skills'?'skill':'mcp',r.resourceId,r.revisionId,r.digest)}>{group==='knowledge'?'查看绑定知识':group==='skills'?'查看绑定技能':'查看绑定MCP'}{r.toolName?' · '+r.toolName:''}</Link></p>)})}<p>职责与保存绑定不代表已运行；既有员工与工作维持原版本。</p></section>;
}

type References={kind:string;identity:string;revision:string;digest:string;subject:string;scope:{tenantId:string;securityDomain:string};dependencies:{incoming:{kind:string;identity:string;revision:string;name:string;versionRelation:string}[];outgoing:{kind:string;identity:string;revision:string;digest?:string;name?:string;readable?:boolean}[];limitations:string[]}};
export function DefinitionReferenceView({item}:{item:DirectoryItem}){
 const [data,setData]=useState<References|null>(null),[error,setError]=useState(false);
 useEffect(()=>{let live=true,generation=0;const abort=new AbortController();const withdraw=()=>{generation++;setData(null);setError(true)};const load=async()=>{const turn=generation;const before=await readWorkbenchSession(abort.signal);const response=await fetch('/api/workbench/v1/resource-directory/'+[item.kind,item.identity,item.revisionId].map(encodeURIComponent).join('/')+'/references',{credentials:'same-origin',signal:abort.signal});if(!response.ok)throw Error();const d=(await response.json()).result as References;const exact=await readDirectoryResource(item,abort.signal),after=await readWorkbenchSession(abort.signal);if(JSON.stringify(before.principal)!==JSON.stringify(after.principal)||d.subject!==after.principal.principalId||d.scope.tenantId!==after.principal.tenantId||d.scope.securityDomain!==after.principal.securityDomain||d.kind!==item.kind||d.identity!==item.identity||d.revision!==item.revisionId||d.digest!==item.digest||exact.revision?.digest!==item.digest||!Array.isArray(d.dependencies?.incoming))throw Error();if(live&&generation===turn){setData(d);setError(false)}};void load().catch(()=>{if(live)withdraw()});window.addEventListener('workbench-session-expired',withdraw);return()=>{live=false;abort.abort();window.removeEventListener('workbench-session-expired',withdraw)}},[item]);
 if(error)return <section role="status"><h2>引用记录暂不可读</h2><p>不据此认定没有影响，原引用保留。</p></section>;
 if(!data)return <p role="status">正在核对准确版本引用…</p>;
 const current=new URL(window.location.href);current.searchParams.set('resourceDigest',item.digest);current.searchParams.set('kind',item.kind);
 const exact=current.searchParams.get('selected')===item.identity&&current.searchParams.get('resourceRevision')===item.revisionId;
 const back=(exact?safeResourceReturn(current.pathname+current.search):null)??safeResourceReturn(exactDefinitionHref(item.kind as 'agent'|'knowledge',item.identity,item.revisionId,item.digest));
 return <section aria-label="准确版本引用"><h2>当前可读的版本引用</h2><p>仅依据保存的准确版本关系，空列表不能证明未被引用。</p><ul>{data.dependencies.incoming.filter(r=>r.kind==='EMPLOYEE').map(r=><li key={r.identity+r.revision}><Link to={'/employees?'+new URLSearchParams({employeeDefinitionId:r.identity,employeeDefinitionRevisionId:r.revision,section:'capabilities',detail:'1',...(back?{resourceBack:back}:{})})}>{r.name}</Link><span>{r.versionRelation==='DIGEST_MISMATCH'?' · 内容摘要不符，不能当成已核对引用':' · 保存引用，不自动升级'}</span></li>)}</ul><details><summary>本次读取范围</summary><ul>{data.dependencies.limitations.map(x=><li key={x}>{x}</li>)}</ul></details></section>;
}
