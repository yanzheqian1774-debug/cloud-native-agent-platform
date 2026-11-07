import {expect,test,type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
import type {ExecutionView} from '../../src/api/preparedExecution';
const plan=JSON.parse(readFileSync(new URL('./fixtures/delivery-plan.json',import.meta.url),'utf8'));
const content=readFileSync(new URL('./fixtures/sales-report.json',import.meta.url),'utf8'),source=JSON.parse(content).sourceSnapshot;
const conversation='jx01-original',problem='jx01-problem',digest='c'.repeat(64),ref={resource_id:'skill-definition:jx01',revision_id:'skill-revision:historical',digest:'a'.repeat(64)};
const principal={principalId:'human:jx01-fixture',tenantId:'jx01-fixture',securityDomain:'isolated'},scope={tenantId:principal.tenantId,securityDomain:principal.securityDomain};
const item={kind:'skill',identity:ref.resource_id,revisionId:ref.revision_id,digest:ref.digest,name:'JX01隔离校验技能',state:'PUBLISHED',enabled:true,isCurrentPublished:false,isCurrentDraft:false,createdAt:null,executionReady:false,policyReviewed:false};
function view():ExecutionView{const tasks=plan.semantics.tasks;return {digest,executionStarted:true,preparation:{plan_id:'jx01-plan',plan_version:4,plan_digest:'d'.repeat(64),approval_id:'fixture-approval',source_snapshot:source,semantics:{...plan.semantics,title:'已有合成销售成果',target:{problem:{resource_id:problem,revision_id:'1',digest:'b'.repeat(64)}}},participants:tasks.map((t:{task_id:string;operation:string})=>({task_id:t.task_id,instance_id:'fixture-instance',assignment_id:'fixture-assignment',definition:ref,skill:{reference:ref,operation:t.operation},profile:ref}))},progress:{state:'SUCCEEDED',version:10,cancellation_request_id:null,tasks:tasks.map((t:{task_id:string})=>({task_id:t.task_id,state:'SUCCEEDED',attempt_ordinal:1,reason:null}))},admission:{state:'ADMITTED',reason:null},resourceUses:[],artifacts:[{artifact_id:'jx01-report',task_id:tasks.at(-1).task_id,digest:'e'.repeat(64),bytes:content.length,created_at:'2026-11-07T00:00:00Z',contentAccess:'AUTHORIZED',content}],events:[],outcome:null}}
async function setup(page:Page,mode='normal'){
 let detailReads=0;const writes:string[]=[];
 await page.route('**/api/workbench/v1/**',async route=>{
  const r=route.request(),path=new URL(r.url()).pathname;
  if(r.method()!=='GET'){writes.push(r.method()+' '+path);return route.abort()}
  if(path.endsWith('/session'))return route.fulfill({json:{principal,session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(path.endsWith('/conversations/capabilities'))return route.fulfill({json:{result:{enabled:true}}});
  if(path.endsWith('/conversations'))return route.fulfill({json:{result:{items:[{conversation_id:conversation,title:'JX01隔离原会话',created_at:'2026-11-07'}]}}});
  if(path.endsWith('/conversations/'+conversation))return route.fulfill({json:{result:{conversation:{conversation_id:conversation,title:'JX01隔离原会话',version:2,created_at:'2026-11-07'},messages:Array.from({length:15},(_,i)=>({message_id:'m'+i,sequence:i+1,content:'保留的会话消息与原始状态。'.repeat(10),disposition:'FOLLOWUP_RECORDED',created_at:'2026-11-07'})),links:[{link_id:'original-work',title:'已有合成销售成果',readable:true,target:{problemId:problem,revisionId:'1',problemDigest:'b'.repeat(64),executionDigest:digest}}]}}});
  if(path.endsWith('/business-problems'))return route.fulfill({json:{problems:[]}});
  if(path.includes('/prepared-executions/'))return route.fulfill({json:{result:view()}});
  if(path.endsWith('/resource-directory'))return route.fulfill({json:{result:{subject:principal.principalId,scope,items:[item,{...item,identity:'skill-definition:other',name:'另一个隔离技能',digest:'b'.repeat(64)}],nextCursor:null,executionAuthority:'NONE'}}});
  if(path.includes('/resource-directory/')){
   detailReads++;if(mode==='denied')return route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
   const other=path.includes(encodeURIComponent('skill-definition:other')),selected=other?{...item,identity:'skill-definition:other',name:'另一个隔离技能',digest:'b'.repeat(64)}:item;
   return route.fulfill({json:{result:{...selected,subject:principal.principalId,scope,revision:{revisionId:selected.revisionId,digest:selected.digest,state:'PUBLISHED',content:{description:'仅隔离界面校验',instructions:'已有只读规则。'.repeat(300)}},usage:mode==='no-usage'||other?[]:[{digest,title:'已有合成销售成果',planVersion:4,state:'SUCCEEDED',problemId:problem}]}}});
  }
  return route.fulfill({status:404,json:{reasonCode:'FIXTURE_NOT_FOUND'}});
 });return()=>({detailReads,writes});
}
const url=(expected=ref.digest)=>'/skills?'+new URLSearchParams({selected:ref.resource_id,resourceRevision:ref.revision_id,resourceDigest:expected,fromExecution:digest,returnConversation:conversation});

test('JX01 original conversation to inline report to exact Skill and back preserves nonzero draft and position',async({page})=>{
 const counts=await setup(page);await page.setViewportSize({width:1280,height:720});await page.goto('/work?conversation='+conversation);
 await page.locator('#private-input').fill('尚未发送的原会话草稿：核对后继续。');
 await page.getByRole('button',{name:'已有合成销售成果',exact:true}).click();await page.getByRole('button',{name:'当前工作',exact:true}).click();
 await expect(page.getByRole('region',{name:'销售诊断关键数据'})).toBeVisible();const bindings=page.getByRole('region',{name:'本次方案绑定的技能'}),link=bindings.getByRole('link',{name:'查看准确版本',exact:true});await expect(link).toHaveCount(1);await expect(link).toHaveAttribute('href',url());
 await link.scrollIntoViewIfNeeded();const before=await page.locator('.px-message-stream').evaluate(n=>n.scrollTop);expect(before).toBeGreaterThan(0);await link.click();
 await expect(page.getByRole('heading',{name:item.name,exact:true})).toBeVisible();await expect(page.getByRole('region',{name:'原执行的版本引用'})).toContainText('已从当前可读使用记录核对');await page.reload();await expect(page.getByRole('heading',{name:item.name,exact:true})).toBeVisible();await page.getByRole('link',{name:'返回原会话',exact:true}).click();
 await expect(page.locator('#private-input')).toHaveValue('尚未发送的原会话草稿：核对后继续。');await expect(page.getByRole('button',{name:'当前工作',exact:true})).toHaveAttribute('aria-pressed','true');await expect(page.getByRole('region',{name:'销售诊断关键数据'})).toBeVisible();await expect.poll(()=>page.locator('.px-message-stream').evaluate(n=>n.scrollTop)).toBeGreaterThan(0);expect(Math.abs(await page.locator('.px-message-stream').evaluate(n=>n.scrollTop)-before)).toBeLessThan(4);expect(counts().writes).toEqual([]);
});

test('JX01 expected digest mismatch stops exact detail rather than choosing current head',async({page})=>{const counts=await setup(page);await page.goto(url('0'.repeat(64)));await expect(page.getByRole('alert')).toContainText('准确版本未能核对');await expect(page.locator('.resource-readonly-detail')).toHaveCount(0);expect(counts().detailReads).toBe(0);expect(counts().writes).toEqual([])});
for(const mode of ['denied','no-usage'])test('JX01 '+mode+' cannot claim a verified original execution reference',async({page})=>{const counts=await setup(page,mode);await page.goto(url());if(mode==='denied'){await expect(page.getByRole('alert')).toContainText('当前版本详情未读回');await expect(page.locator('.resource-readonly-detail')).toHaveCount(0)}else await expect(page.getByRole('region',{name:'原执行的版本引用'})).toContainText('尚未证实');await expect(page.getByText('已从当前可读使用记录核对原执行的准确版本引用。',{exact:true})).toHaveCount(0);expect(counts().writes).toEqual([])});
test('JX01 choosing another resource clears source binding but keeps the original conversation return',async({page})=>{const counts=await setup(page);await page.goto(url());await expect(page.getByRole('heading',{name:item.name,exact:true})).toBeVisible();await page.getByRole('navigation',{name:'本页可读资源'}).getByRole('link').filter({hasText:'另一个隔离技能'}).click();await expect(page.getByRole('heading',{name:'另一个隔离技能',exact:true})).toBeVisible();expect(new URL(page.url()).searchParams.has('resourceDigest')).toBe(false);expect(new URL(page.url()).searchParams.has('fromExecution')).toBe(false);await expect(page.getByRole('link',{name:'返回原会话',exact:true})).toHaveAttribute('href','/work?conversation='+conversation);expect(counts().writes).toEqual([])});
