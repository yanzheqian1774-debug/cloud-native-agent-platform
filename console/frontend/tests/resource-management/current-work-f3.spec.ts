import {test,expect,type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
const report=JSON.parse(readFileSync(new URL('../e2e/fixtures/delivery-report324.json',import.meta.url),'utf8'));
const plan=JSON.parse(readFileSync(new URL('../e2e/fixtures/delivery-plan.json',import.meta.url),'utf8'));
async function fixture(page:Page,count=1){
 const state={writes:[] as string[],denied:false,nativeDenied:false,mismatch:false,running:false,answer:null as string|null,expired:false};
 const ids=Array.from({length:count},(_,i)=>String(i+1));
 await page.route('**/api/**',async route=>{
  const request=route.request(),p=decodeURIComponent(new URL(request.url()).pathname);if(request.method()!=='GET'){state.writes.push(p);return route.abort()}
  const ok=(result:unknown)=>route.fulfill({json:{result}});
  if(p.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:directory',tenantId:'fixture',securityDomain:'isolated'},session:{expiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(p.endsWith('/conversations/capabilities'))return ok({enabled:true});
  if(p.endsWith('/problems'))return ok({problems:ids.map(id=>({business_problem_id:'p'+id,title:'交付检查 '+id,description:'合成资料范围',created_at:'2026-11-10T00:00:00Z'}))});
  if(p.endsWith('/conversations'))return ok({items:ids.map(id=>({conversation_id:'c'+id,title:'交付检查 '+id,created_at:'2026-11-10T00:00:00Z'}))});
  const journey=p.match(/\/conversations\/c(\d+)\/journey$/);if(journey)return ok({state:{execution:'e'+journey[1]}});
  const conversation=p.match(/\/conversations\/c(\d+)$/);if(conversation){const id=conversation[1];return ok({conversation:{conversation_id:'c'+id,title:'交付检查 '+id,version:1},messages:[],links:[{link_id:'l'+id,readable:true,target:{problemId:'p'+id,executionDigest:'e'+id}}]})}
  const native=p.match(/\/prepared-executions\/e(\d+)\/native-progress$/);if(native){if(state.nativeDenied)return route.fulfill({status:403,json:{reasonCode:'NOT_AUTHORIZED'}});return ok({questions:[{questionKey:'q'+native[1],questionDigest:'a'.repeat(64),question:'确认使用生产环境还是测试环境规范？',expiresAt:state.expired?'2020-01-01':'2099-01-01',expired:state.expired,answer:state.answer}],steps:[],modelInFlight:false})}
  const execution=p.match(/\/prepared-executions\/e(\d+)$/);if(execution){if(state.denied)return route.fulfill({status:403,json:{reasonCode:'NOT_AUTHORIZED'}});const id=execution[1],source=report.sourceSnapshot;return ok({digest:state.mismatch?'wrong':'e'+id,executionStarted:true,preparation:{plan_id:'plan'+id,plan_version:4,source_snapshot:source,semantics:{...plan.semantics,title:'交付分析 '+id,target:{problem:{resource_id:'p'+id}}},participants:plan.semantics.tasks.map((t:{task_id:string;operation:string})=>({task_id:t.task_id,instance_id:'worker',assignment_id:'assignment',definition:source,skill:{reference:source,operation:t.operation},profile:source}))},progress:{state:state.running?'RUNNING':'SUCCEEDED',version:1,tasks:plan.semantics.tasks.map((t:{task_id:string})=>({task_id:t.task_id,state:state.running?'RUNNING':'SUCCEEDED',attempt_ordinal:1}))},admission:{state:'ADMITTED'},resourceUses:[],artifacts:[{artifact_id:'artifact'+id,task_id:plan.semantics.tasks.at(-1).task_id,digest:'f'.repeat(64),bytes:1000,created_at:'2026-11-10T00:00:00Z',contentAccess:'AUTHORIZED',content:JSON.stringify(report)}],events:[],outcome:{businessResolution:'UNDETERMINED',confirmationId:null,evaluation:{results:[]}}})}
  return ok({items:[],enabled:false});
 });return state;
}
test('stage result stays readable without falsely becoming confirmed business success',async({page})=>{
 const s=await fixture(page);await page.goto('/outcomes');await expect(page.getByText('成果验收状态尚未接通。',{exact:false})).toBeVisible();
 await page.getByRole('button',{name:'阶段与执行记录',exact:true}).click();await expect(page.getByText('业务结论尚未判定',{exact:true})).toBeVisible();await page.getByLabel('搜索工作',{exact:false}).fill('交付检查');
 await page.getByRole('button',{name:'阅读成果与依据',exact:true}).click();await expect(page.getByRole('heading',{name:'成果预览',exact:true})).toBeVisible();await expect(page.locator('.px-delivery-summary')).toBeVisible();await expect(page.getByRole('link',{name:'回到原会话',exact:true})).toHaveAttribute('href','/work?conversation=c1');
 await page.getByRole('button',{name:'返回成果与记录',exact:true}).click();await expect(page.getByLabel('搜索工作',{exact:false})).toHaveValue('交付检查');await expect(page.getByRole('button',{name:'阶段与执行记录',exact:true})).toHaveAttribute('aria-pressed','true');expect(s.writes).toEqual([]);
});
test('only live unanswered questions enter attention and accepted answers move to handled',async({page})=>{
 const s=await fixture(page);s.running=true;await page.goto('/attention');await expect(page.getByText('确认使用生产环境还是测试环境规范？',{exact:true})).toBeVisible();await expect(page.getByRole('link',{name:'在原会话回答',exact:true})).toHaveAttribute('href','/work?conversation=c1');
 s.answer='生产环境';await page.getByRole('button',{name:'重新读取',exact:true}).click();await expect(page.getByText('当前已读记录中没有仍有效的未回答追问。',{exact:true})).toBeVisible();await page.getByRole('button',{name:'已处理',exact:true}).click();await expect(page.getByText('已回答：生产环境',{exact:true})).toBeVisible();expect(s.writes).toEqual([]);
});
for(const terminal of [false,true])test('expired or terminal questions are not fabricated user work '+terminal,async({page})=>{
 const s=await fixture(page);s.running=!terminal;s.expired=!terminal;await page.goto('/attention');await expect(page.getByText('当前已读记录中没有仍有效的未回答追问。',{exact:true})).toBeVisible();await expect(page.getByRole('link',{name:'在原会话回答',exact:true})).toHaveCount(0);expect(s.writes).toEqual([]);
});
test('task detail returns to the filtered long list with position and focus',async({page})=>{
 const s=await fixture(page,16);await page.goto('/tasks?q=交付检查&filter=completed');const open=page.getByRole('button',{name:'查看任务',exact:true}).last();await open.scrollIntoViewIfNeeded();await open.focus();const top=await page.evaluate(()=>scrollY);expect(top).toBeGreaterThan(100);await open.click();await expect(page.getByRole('heading',{name:'任务详情',exact:true})).toBeVisible();await page.reload();await expect(page.getByRole('heading',{name:'任务详情',exact:true})).toBeVisible();await page.getByRole('button',{name:'返回我的任务',exact:true}).click();await expect(page.getByLabel('搜索工作',{exact:false})).toHaveValue('交付检查');await expect.poll(()=>page.evaluate(()=>scrollY)).toBeGreaterThan(100);expect(Math.abs(await page.evaluate(()=>scrollY)-top)).toBeLessThan(3);await expect(page.getByRole('button',{name:'查看任务',exact:true}).last()).toBeFocused();expect(s.writes).toEqual([]);
});
test('denied exact record withdraws detail and partial reads never become a complete empty claim',async({page})=>{
 const s=await fixture(page);await page.goto('/tasks?work=e1');await expect(page.locator('.px-delivery-summary')).toBeVisible();s.denied=true;await page.getByRole('button',{name:'重新读取',exact:true}).click();await expect(page.getByRole('heading',{name:'当前无法读取这项工作',exact:true})).toBeVisible();await expect(page.locator('.px-delivery-summary')).toHaveCount(0);await expect(page.getByText('部分关联记录当前未能读取。',{exact:false})).toBeVisible();expect(s.writes).toEqual([]);
});
test('narrow task page contains table scrolling and mismatched owner cannot supply a task',async({page})=>{
 const s=await fixture(page,2);await page.setViewportSize({width:390,height:844});await page.goto('/tasks');await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(2);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);s.mismatch=true;await page.getByRole('button',{name:'重新读取',exact:true}).click();await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(0);await expect(page.getByText('部分关联记录当前未能读取。',{exact:false})).toBeVisible();expect(s.writes).toEqual([]);
});
test('a verified original journey wins over another readable link to the same execution',async({page})=>{
 const s=await fixture(page);s.running=true;
 await page.route('**/api/workbench/v1/conversations',r=>r.fulfill({json:{result:{items:[{conversation_id:'alias'},{conversation_id:'c1'}]}}}));
 await page.route('**/api/workbench/v1/conversations/alias',r=>r.fulfill({json:{result:{conversation:{conversation_id:'alias',title:'关联历史'},messages:[],links:[{readable:true,target:{problemId:'p1',executionDigest:'e1'}}]}}}));
 await page.route('**/api/workbench/v1/conversations/alias/journey',r=>r.fulfill({json:{result:{state:null}}}));
 await page.goto('/attention');await expect(page.getByRole('link',{name:'在原会话回答',exact:true})).toHaveAttribute('href','/work?conversation=c1');await expect(page.getByRole('link',{name:'在原会话回答',exact:true})).toHaveCount(1);expect(s.writes).toEqual([]);
});
test('persisted partial artifacts never make a running task appear completed',async({page})=>{
 const s=await fixture(page);s.running=true;await page.goto('/tasks?work=e1');await expect(page.getByRole('region',{name:'当前作业过程',exact:true})).toBeVisible();await page.getByRole('navigation',{name:'工作详情页签'}).getByRole('button',{name:'成果与记录',exact:true}).click();await expect(page.getByText('执行尚未完成，已有 1 份阶段产物记录；',{exact:false})).toBeVisible();await expect(page.locator('.px-delivery-summary')).toHaveCount(0);expect(s.writes).toEqual([]);
});
