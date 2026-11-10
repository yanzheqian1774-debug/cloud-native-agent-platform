import {expect,test,type Page} from '@playwright/test';
import {readFileSync,mkdirSync} from 'node:fs';
import type {ExecutionView} from '../../src/api/preparedExecution';
const plan=JSON.parse(readFileSync(new URL('./fixtures/delivery-plan.json',import.meta.url),'utf8'));
const content=readFileSync(new URL('./fixtures/sales-report.json',import.meta.url),'utf8'),source=JSON.parse(content).sourceSnapshot;
const conversation='jx02-original',problem='jx02-problem',digest='c'.repeat(64),ref={resource_id:'skill-definition:jx02',revision_id:'skill-revision:historical',digest:'a'.repeat(64)};
const principal={principalId:'human:jx02-fixture',tenantId:'jx02-fixture',securityDomain:'isolated'},scope={tenantId:principal.tenantId,securityDomain:principal.securityDomain};
const item={kind:'skill',identity:ref.resource_id,revisionId:ref.revision_id,digest:ref.digest,name:'JX02隔离历史技能',state:'PUBLISHED',enabled:true,isCurrentPublished:false,isCurrentDraft:false,createdAt:null,executionReady:false,policyReviewed:false};
function view():ExecutionView{const tasks=plan.semantics.tasks;return {digest,executionStarted:true,preparation:{plan_id:'jx02-plan',plan_version:4,plan_digest:'d'.repeat(64),approval_id:'fixture-approval',source_snapshot:source,semantics:{...plan.semantics,title:'JX02已有隔离销售成果',target:{problem:{resource_id:problem,revision_id:'1',digest:'b'.repeat(64)}}},participants:tasks.map((t:{task_id:string;operation:string})=>({task_id:t.task_id,instance_id:'fixture-instance',assignment_id:'fixture-assignment',definition:ref,skill:{reference:ref,operation:t.operation},profile:ref}))},progress:{state:'SUCCEEDED',version:10,cancellation_request_id:null,tasks:tasks.map((t:{task_id:string})=>({task_id:t.task_id,state:'SUCCEEDED',attempt_ordinal:1,reason:null}))},admission:{state:'NOT_ADMITTED',reason:'READ_ONLY_FIXTURE'},resourceUses:[{resourceUseId:'fixture-restricted',state:'READ_RESTRICTED'}],artifacts:[{artifact_id:'jx02-report',task_id:tasks.at(-1).task_id,digest:'e'.repeat(64),bytes:content.length,created_at:'2026-11-07T00:00:00Z',contentAccess:'AUTHORIZED',content}],events:[],outcome:null}}
async function setup(page:Page,declaration='empty'){
 const state={writes:[] as string[],detailReads:[] as string[],executionReads:0,denied:false,mismatch:false,flipIdentity:false,otherIdentity:false,hold:false,release:()=>{}};
 await page.route('**/api/workbench/v1/**',async route=>{
  const r=route.request(),u=new URL(r.url()),path=u.pathname;
  if(r.method()!=='GET'){state.writes.push(r.method()+' '+path);return route.abort()}
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{...principal,...(state.otherIdentity?{principalId:'human:other'}:{})},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture-secret-not-to-store'}});
  if(path.endsWith('/conversations/capabilities'))return route.fulfill({json:{result:{enabled:true}}});
  if(path.endsWith('/conversations'))return route.fulfill({json:{result:{items:[{conversation_id:conversation,title:'JX02隔离原会话',created_at:'2026-11-07'}]}}});
  if(path.endsWith('/conversations/'+conversation))return route.fulfill({json:{result:{conversation:{conversation_id:conversation,title:'JX02隔离原会话',version:2,created_at:'2026-11-07'},messages:Array.from({length:12},(_,i)=>({message_id:'m'+i,sequence:i+1,content:'原会话消息。'.repeat(80),disposition:'FOLLOWUP_RECORDED',created_at:'2026-11-07'})),links:[{link_id:'original-work',title:'JX02已有隔离销售成果',readable:true,target:{problemId:problem,revisionId:'1',problemDigest:'b'.repeat(64),executionDigest:digest}}]}}});
  if(path.endsWith('/problems'))return route.fulfill({json:{result:{problems:[]}}});
  if(path.includes('/prepared-executions/')){
   state.executionReads++;if(state.hold)await new Promise<void>(resolve=>{state.release=resolve});
   if(state.denied)return route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
   const value=view();if(state.mismatch)value.preparation.participants=value.preparation.participants.map(p=>({...p,skill:{...p.skill,reference:{...ref,digest:'f'.repeat(64)}}}));
   if(state.flipIdentity)state.otherIdentity=true;
   return route.fulfill({json:{result:value}});
  }
  if(path.endsWith('/resource-directory'))return route.fulfill({json:{result:{subject:principal.principalId,scope,items:[...Array.from({length:8},(_,i)=>({...item,identity:'other:'+i,name:'其他当前可读版本 '+i})),item,{...item,revisionId:'skill-revision:latest',digest:'b'.repeat(64),isCurrentPublished:true}],nextCursor:null,executionAuthority:'NONE'}}});
  if(path.includes('/resource-directory/')){
   state.detailReads.push(path);
   const config:Record<string,unknown>={description:'隔离界面校验，非真实业务接受。',instructions:'此为准确历史版本的只读规则。\n'.repeat(75),inputSchema:{type:'object'},outputSchema:{type:'object'},permissions:[],operations:[{name:'READ_DATA',inputSchema:{type:'object',required:['source']},outputSchema:{type:'object'}}]};
   if(declaration!=='absent')config.dependencies=declaration==='null'?null:declaration==='malformed'?{name:'not-an-array'}:[];
   const id=decodeURIComponent(path.split('/').at(-2)!),selected=id===ref.resource_id?item:{...item,identity:id,name:'其他当前可读版本 '+id.split(':').at(-1)};
   return route.fulfill({json:{result:{...selected,subject:principal.principalId,scope,revision:{revisionId:selected.revisionId,digest:selected.digest,state:'PUBLISHED',content:config},usage:id===ref.resource_id?[{digest,title:'JX02已有隔离销售成果',planVersion:4,state:'SUCCEEDED',problemId:problem}]:[]}}});
  }
  return route.fulfill({status:404,json:{reasonCode:'FIXTURE_NOT_FOUND'}});
 });return state;
}
const root=()=>'/skills?'+new URLSearchParams({resourceView:'professional',selected:ref.resource_id,resourceRevision:ref.revision_id,resourceDigest:ref.digest,fromExecution:digest,returnConversation:conversation,query:'隔离',status:'PUBLISHED'});
async function openUse(page:Page){await page.goto(root());await page.getByRole('button',{name:'JX02已有隔离销售成果',exact:true}).click();await expect(page.getByRole('heading',{name:'已有执行的只读核对',exact:true})).toBeVisible()}
async function capture(page:Page,name:string){const dir=process.env.JX02_SCREENSHOT_DIR;if(dir){mkdirSync(dir,{recursive:true});await page.screenshot({path:dir+'/'+name+'-1280x720.png'})}}

test('JX02 old exact Skill to saved execution and back preserves filter, open sections, focus, positions and original conversation draft',async({page})=>{
 const state=await setup(page);await page.setViewportSize({width:1280,height:720});await page.goto('/work?conversation='+conversation);await page.locator('#private-input').fill('JX02原会话未发送草稿，不进入资源返回存储。');await page.getByRole('button',{name:'JX02已有隔离销售成果',exact:true}).click();await page.getByRole('button',{name:'当前工作',exact:true}).click();
 const link=page.getByRole('region',{name:'本次方案绑定的技能'}).getByRole('link',{name:'查看准确版本',exact:true});await link.scrollIntoViewIfNeeded();const workScroll=await page.locator('.px-message-stream').evaluate(n=>n.scrollTop);expect(workScroll).toBeGreaterThan(0);await link.click();await page.goto(root());
 await expect(page.getByRole('region',{name:'固定版本',exact:true})).toContainText(ref.revision_id);await page.getByText('查看保存的依赖与权限声明',{exact:true}).click();await page.getByText('查看准确操作的输入与输出声明',{exact:true}).click();await expect(page.getByRole('region',{name:'本版本声明信息'})).toContainText('无法确认是否明确声明无依赖');
 const region=page.getByRole('region',{name:'资源详情滚动区'}),use=page.getByRole('button',{name:'JX02已有隔离销售成果',exact:true});await use.scrollIntoViewIfNeeded();await page.locator('.resource-detail-list').evaluate(n=>n.scrollTop=160);const position=await region.evaluate(n=>n.scrollTop),list=await page.locator('.resource-detail-list').evaluate(n=>n.scrollTop);expect(position).toBeGreaterThan(0);expect(list).toBeGreaterThan(0);await capture(page,'candidate-skill-declarations-and-use');await use.click();
 await expect(page.getByRole('region',{name:'销售诊断关键数据'})).toBeVisible();await expect(page.getByRole('region',{name:'原执行保存绑定'})).toContainText('读取受限');expect(new URL(page.url()).searchParams.has('resourceRead')).toBe(true);await capture(page,'candidate-saved-execution');await page.reload();await expect(page.getByRole('region',{name:'销售诊断关键数据'})).toBeVisible();
 await page.goBack();await expect(page.getByRole('heading',{name:item.name,exact:true})).toBeVisible();await expect.poll(()=>region.evaluate(n=>n.scrollTop)).toBeGreaterThan(0);expect(Math.abs(await region.evaluate(n=>n.scrollTop)-position)).toBeLessThan(4);await page.goForward();await expect(page.getByRole('region',{name:'销售诊断关键数据'})).toBeVisible();await page.getByRole('link',{name:'返回同一准确资源',exact:true}).click();
 await expect(page.getByRole('heading',{name:item.name,exact:true})).toBeVisible();await expect.poll(()=>region.evaluate(n=>n.scrollTop)).toBeGreaterThan(0);expect(Math.abs(await region.evaluate(n=>n.scrollTop)-position)).toBeLessThan(4);expect(await page.locator('.resource-detail-list').evaluate(n=>n.scrollTop)).toBe(list);await expect(use).toBeFocused();
 await expect(page.locator('details[data-resource-section=declarations]')).toHaveAttribute('open','');await expect(page.locator('details[data-resource-section=operations]')).toHaveAttribute('open','');const u=new URL(page.url());expect(u.searchParams.get('query')).toBe('隔离');expect(u.searchParams.get('resourceRevision')).toBe(ref.revision_id);expect(u.searchParams.get('resourceDigest')).toBe(ref.digest);expect(u.searchParams.get('status')).toBe('PUBLISHED');await capture(page,'candidate-exact-resource-return');
 const saved=await page.evaluate(()=>Object.keys(sessionStorage).filter(k=>k.startsWith('resource-read.v1:')).map(k=>sessionStorage.getItem(k)).join(''));expect(saved).not.toContain('fixture-secret-not-to-store');expect(saved).not.toContain('JX02原会话未发送草稿');
 await page.getByRole('link',{name:'返回原会话',exact:true}).click();await expect(page.locator('#private-input')).toHaveValue('JX02原会话未发送草稿，不进入资源返回存储。');await expect(page.getByRole('button',{name:'当前工作',exact:true})).toHaveAttribute('aria-pressed','true');await expect.poll(()=>page.locator('.px-message-stream').evaluate(n=>n.scrollTop)).toBeGreaterThan(0);expect(Math.abs(await page.locator('.px-message-stream').evaluate(n=>n.scrollTop)-workScroll)).toBeLessThan(4);expect(state.writes).toEqual([]);expect(state.detailReads.every(p=>!p.includes('latest'))).toBe(true);
});

for(const [mode,message] of [['absent','未返回依赖声明字段'],['null','不能解释为明确无依赖'],['malformed','依赖声明格式尚未核对']])test('JX02 declaration '+mode+' is not silently converted to a verified empty relation',async({page})=>{const state=await setup(page,mode);await page.goto(root());await page.getByText('查看保存的依赖与权限声明',{exact:true}).click();await expect(page.getByRole('region',{name:'本版本声明信息'})).toContainText(message);await expect(page.getByText('没有完整性或分页标记',{exact:false})).toBeVisible();expect(state.writes).toEqual([])});

for(const mode of ['denied','mismatch','identity'])test('JX02 '+mode+' saved execution cannot expose old results',async({page})=>{
 const state=await setup(page);await openUse(page);await expect(page.getByRole('region',{name:'销售诊断关键数据'})).toBeVisible();if(mode==='denied')state.denied=true;else if(mode==='mismatch')state.mismatch=true;else state.flipIdentity=true;
 await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect(page.getByRole('alert')).toContainText('原执行暂未读回');await expect(page.getByRole('region',{name:'销售诊断关键数据'})).toHaveCount(0);await expect(page.getByRole('link',{name:'返回同一准确资源',exact:true})).toHaveCount(0);expect(state.writes).toEqual([]);
});

test('JX02 delayed old response cannot restore data after session expiry',async({page})=>{
 const state=await setup(page);await openUse(page);await expect(page.getByRole('region',{name:'销售诊断关键数据'})).toBeVisible();const before=state.executionReads;state.hold=true;await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect.poll(()=>state.executionReads).toBeGreaterThan(before);await page.evaluate(()=>window.dispatchEvent(new Event('workbench-session-expired')));state.release();await expect(page.getByRole('alert')).toContainText('当前登录已失效');await page.waitForTimeout(150);await expect(page.getByRole('region',{name:'销售诊断关键数据'})).toHaveCount(0);expect(state.writes).toEqual([]);
});

for(const tamper of ['external','different-version'])test('JX02 rejects '+tamper+' return context before execution read',async({page})=>{
 const state=await setup(page);await openUse(page);await expect(page.getByRole('region',{name:'销售诊断关键数据'})).toBeVisible();const count=state.executionReads,origin=new URL(page.url()).origin;await page.evaluate(mode=>{const key=Object.keys(sessionStorage).find(k=>k.startsWith('resource-read.v1:'))!;const value=JSON.parse(sessionStorage.getItem(key)!);value.href=mode==='external'?'https://example.invalid/skills?selected=x':value.href.replace('historical','latest');sessionStorage.setItem(key,JSON.stringify(value))},tamper);await page.reload();await expect(page.getByRole('alert')).toContainText('原执行暂未读回');expect(state.executionReads).toBe(count);await expect(page.getByRole('region',{name:'销售诊断关键数据'})).toHaveCount(0);expect(new URL(page.url()).origin).toBe(origin);expect(state.writes).toEqual([]);
});
test('JX02 missing context never guesses a source or latest resource',async({page})=>{const state=await setup(page);await page.goto('/work?resourceRead=aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa');await expect(page.getByRole('alert')).toContainText('原执行暂未读回');expect(state.executionReads).toBe(0);expect(state.writes).toEqual([])});
test('JX02 unavailable local view storage prevents untracked navigation without business writes',async({page})=>{const state=await setup(page);await page.addInitScript(()=>{const original=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k.startsWith('resource-read.'))throw Error('fixture storage unavailable');original.call(this,k,v)}});await page.goto(root());await page.getByRole('button',{name:'JX02已有隔离销售成果',exact:true}).click();await expect(page.getByRole('alert')).toContainText('RESOURCE_RETURN_STORAGE_UNAVAILABLE');expect(state.executionReads).toBe(0);expect(new URL(page.url()).pathname).toBe('/skills');expect(state.writes).toEqual([])});


test('JX02 explicit different-resource and directory navigation discard the old return context',async({page})=>{
 const state=await setup(page);await openUse(page);await expect(page.getByRole('region',{name:'销售诊断关键数据'})).toBeVisible();await page.getByRole('link',{name:'返回同一准确资源',exact:true}).click();await expect(page.getByRole('heading',{name:item.name,exact:true})).toBeVisible();expect(new URL(page.url()).searchParams.has('resourceContext')).toBe(true);await expect(page.getByRole('link',{name:'返回资源目录',exact:true})).not.toHaveAttribute('href',/resourceContext/);
 await page.getByRole('navigation',{name:'本页可读资源'}).getByRole('link').filter({hasText:'其他当前可读版本 0'}).click();await expect(page.getByRole('heading',{name:'其他当前可读版本 0',exact:true})).toBeVisible();const u=new URL(page.url());for(const key of ['resourceContext','resourceDigest','fromExecution'])expect(u.searchParams.has(key)).toBe(false);expect(u.searchParams.get('returnConversation')).toBe(conversation);await expect(page.getByRole('region',{name:'原执行的版本引用'})).toHaveCount(0);expect(state.writes).toEqual([]);
});


test('F3 business impact returns from saved execution to same tab, exact version and focus',async({page})=>{
 const state=await setup(page);const href=new URL(root(),'http://localhost');href.searchParams.delete('resourceView');href.searchParams.set('resourceSection','impact');
 await page.goto(href.pathname+href.search);
 await expect(page.getByRole('tab',{name:'引用与影响',exact:true})).toHaveAttribute('aria-selected','true');
 const use=page.getByRole('button',{name:'JX02已有隔离销售成果',exact:true});await use.click();
 await expect(page.getByRole('region',{name:'销售诊断关键数据'})).toBeVisible();
 await page.getByRole('link',{name:'返回同一准确资源',exact:true}).click();
 await expect(page.getByRole('tab',{name:'引用与影响',exact:true})).toHaveAttribute('aria-selected','true');await expect(use).toBeFocused();
 expect(new URL(page.url()).searchParams.get('resourceRevision')).toBe(ref.revision_id);expect(new URL(page.url()).searchParams.get('query')).toBe('隔离');
 expect(state.writes).toEqual([]);expect(state.detailReads.every(p=>!p.includes('latest'))).toBe(true);
});
