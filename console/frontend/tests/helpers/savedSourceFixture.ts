import {expect,type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
const plan=JSON.parse(readFileSync(new URL('../e2e/fixtures/delivery-plan.json',import.meta.url),'utf8'));
export const principal={principalId:'human:source-return-fixture',tenantId:'source-return-fixture',securityDomain:'isolated'},scope={tenantId:principal.tenantId,securityDomain:principal.securityDomain};
export const conversation='original-source-return',execution='c'.repeat(64);
export async function fixture(page:Page,kind='sales',invalid=false){
 const file=kind==='supplier'?'delivery-report324.json':kind==='v2'?'sales-gross-profit-v2-isolated.json':'sales-report.json';
 const report=JSON.parse(readFileSync(new URL('../e2e/fixtures/'+file,import.meta.url),'utf8')),source=report.sourceSnapshot;
 const state={writes:[] as string[],oldKnowledgeCalls:[] as string[],sourceCalls:[] as string[],denied:false};
 const item={kind:'knowledge',identity:source.resource_id,revisionId:source.revision_id,digest:source.digest,name:'原执行保存的知识来源',state:'PUBLISHED',enabled:true,isCurrentPublished:false,isCurrentDraft:false,createdAt:null,executionReady:false,policyReviewed:false};
 await page.route('**/api/**',async route=>{
  const req=route.request(),u=new URL(req.url()),path=decodeURIComponent(u.pathname);
  if(req.method()!=='GET'){state.writes.push(req.method()+' '+path);return route.abort()}
  if(path.startsWith('/api/internal/')){state.oldKnowledgeCalls.push(path);return route.fulfill({status:404,json:{reasonCode:'LEGACY_NOT_CONNECTED'}})}
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal,session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture-only'}});
  if(path.endsWith('/conversations/capabilities'))return route.fulfill({json:{result:{enabled:true}}});
  if(path.endsWith('/conversations'))return route.fulfill({json:{result:{items:[{conversation_id:conversation,title:'原会话来源返回核对',created_at:'2026-11-08'}]}}});
  if(path.endsWith('/conversations/'+conversation))return route.fulfill({json:{result:{conversation:{conversation_id:conversation,title:'原会话来源返回核对',version:2,created_at:'2026-11-08'},messages:[],links:[{link_id:'saved-work',title:'原执行保存结果',readable:true,target:{problemId:'source-problem',revisionId:'1',problemDigest:'b'.repeat(64),executionDigest:execution}}]}}});
  if(path.endsWith('/problems'))return route.fulfill({json:{result:{problems:[]}}});
  if(path.includes('/prepared-executions/'))return route.fulfill({json:{result:{digest:execution,executionStarted:true,preparation:{plan_id:'saved-source-plan',plan_version:4,plan_digest:'d'.repeat(64),approval_id:'fixture-only',source_snapshot:invalid?{...source,digest:'bad'}:source,semantics:{...plan.semantics,title:'原执行保存结果',target:{problem:{resource_id:'source-problem',revision_id:'1',digest:'b'.repeat(64)}}},participants:plan.semantics.tasks.map((t:{task_id:string;operation:string})=>({task_id:t.task_id,instance_id:'fixture',assignment_id:'fixture',definition:source,skill:{reference:source,operation:t.operation},profile:source}))},progress:{state:'SUCCEEDED',version:10,tasks:plan.semantics.tasks.map((t:{task_id:string})=>({task_id:t.task_id,state:'SUCCEEDED',attempt_ordinal:1,reason:null}))},admission:{state:'NOT_ADMITTED',reason:'SAVED_FIXTURE'},resourceUses:[],artifacts:[{artifact_id:'source-report',task_id:plan.semantics.tasks.at(-1).task_id,digest:'e'.repeat(64),bytes:1000,created_at:'2026-11-08',contentAccess:'AUTHORIZED',content:JSON.stringify(report)}],events:[],outcome:null}}});
  if(path.endsWith('/resource-directory'))return route.fulfill({json:{result:{subject:principal.principalId,scope,items:[item,{...item,revisionId:'later-revision',digest:'f'.repeat(64),isCurrentPublished:true}],nextCursor:null,executionAuthority:'NONE'}}});
  if(path.includes('/resource-directory/')){
   state.sourceCalls.push(path);if(state.denied)return route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
   if(path.endsWith('/references'))return route.fulfill({json:{result:{kind:'knowledge',identity:item.identity,revision:item.revisionId,digest:item.digest,subject:principal.principalId,scope,dependencies:{incoming:[],outgoing:[],limitations:['CURRENT_READABLE_SCOPE_ONLY']}}}});
   return route.fulfill({json:{result:{...item,subject:principal.principalId,scope,revision:{revisionId:item.revisionId,digest:item.digest,state:'PUBLISHED',content:{name:item.name,source:{sourceId:'original-source',documentId:'original-document',content:'只读核对的原始来源正文',provenance:'fixture-only'},documents:[{documentId:'original-document',chunks:[{content:'只读核对的原始来源正文'}]}]},createdAt:'2026-11-08'},usage:[{digest:execution,title:'原执行保存结果',planVersion:4,state:'SUCCEEDED',problemId:'source-problem'}]}}});
  }
  return route.fulfill({status:404,json:{reasonCode:'FIXTURE_NOT_FOUND'}});
 });return {state,source};
}
export async function open(page:Page){await page.goto('/work?conversation='+conversation);await expect(page.locator('#private-input')).toBeVisible();await page.locator('#private-input').fill('保留原会话未发送草稿');await page.getByRole('button',{name:'原执行保存结果',exact:true}).click();await page.getByRole('button',{name:'当前工作',exact:true}).click();await expect(page.locator('.px-delivery-summary')).toBeVisible()}
