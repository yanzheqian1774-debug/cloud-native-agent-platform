import {test,expect,type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
const report=JSON.parse(readFileSync(new URL('../e2e/fixtures/delivery-report324.json',import.meta.url),'utf8'));
const plan=JSON.parse(readFileSync(new URL('../e2e/fixtures/delivery-plan.json',import.meta.url),'utf8'));
async function fixture(page:Page,count=1){
 const state={reads:[] as string[],writes:[] as string[],denied:false,nativeDenied:false,mismatch:false,running:false,answer:null as string|null,expired:false,question:'确认使用生产环境还是测试环境规范？'};
 const ids=Array.from({length:count},(_,i)=>String(i+1));
 await page.route('**/api/**',async route=>{
  const request=route.request(),p=decodeURIComponent(new URL(request.url()).pathname);if(request.method()!=='GET'){state.writes.push(p);return route.abort()}
  state.reads.push(p);const ok=(result:unknown)=>route.fulfill({json:{result}});
  if(p.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:directory',tenantId:'fixture',securityDomain:'isolated'},session:{expiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(p.endsWith('/conversations/capabilities'))return ok({enabled:true});
  if(p.endsWith('/problems'))return ok({problems:ids.map(id=>({business_problem_id:'p'+id,title:'交付检查 '+id,description:'合成资料范围',created_at:'2026-11-10T00:00:00Z'}))});
  if(p.endsWith('/conversations'))return ok({items:ids.map(id=>({conversation_id:'c'+id,title:'交付检查 '+id,created_at:'2026-11-10T00:00:00Z'}))});
  const detail=p.match(/\/problems\/p(\d+)$/);if(detail){const id=detail[1];return ok({problem:{business_problem_id:'p'+id},revisions:[{business_problem_id:'p'+id,revision_id:'p'+id+':1',digest:'a'.repeat(64),title:'交付检查 '+id,description:'固定问题范围'}]})}
  const journey=p.match(/\/conversations\/c(\d+)\/journey$/);if(journey)return ok({state:{execution:'e'+journey[1]}});
  const conversation=p.match(/\/conversations\/c(\d+)\/work-links$/);if(conversation){const id=conversation[1];return ok({conversation:{conversation_id:'c'+id,title:'交付检查 '+id,version:1},messages:[],links:[{link_id:'l'+id,readable:true,target:{problemId:'p'+id,executionDigest:'e'+id}}]})}
  const native=p.match(/\/prepared-executions\/e(\d+)\/native-progress$/);if(native){if(state.nativeDenied)return route.fulfill({status:403,json:{reasonCode:'NOT_AUTHORIZED'}});return ok({questions:[{questionKey:'q'+native[1],questionDigest:'a'.repeat(64),question:state.question,expiresAt:state.expired?'2020-01-01':'2099-01-01',expired:state.expired,answer:state.answer}],steps:[],modelInFlight:false})}
  const execution=p.match(/\/prepared-executions\/e(\d+)$/);if(execution){if(state.denied)return route.fulfill({status:403,json:{reasonCode:'NOT_AUTHORIZED'}});const id=execution[1],source=report.sourceSnapshot;return ok({digest:state.mismatch?'wrong':'e'+id,executionStarted:true,preparation:{plan_id:'plan'+id,plan_version:4,source_snapshot:source,semantics:{...plan.semantics,title:'交付分析 '+id,target:{problem:{resource_id:'p'+id,revision_id:'p'+id+':1',digest:'a'.repeat(64)}}},participants:plan.semantics.tasks.map((t:{task_id:string;operation:string})=>({task_id:t.task_id,instance_id:'worker',assignment_id:'assignment',definition:source,skill:{reference:source,operation:t.operation},profile:source}))},progress:{state:state.running?'RUNNING':'SUCCEEDED',version:1,tasks:plan.semantics.tasks.map((t:{task_id:string})=>({task_id:t.task_id,state:state.running?'RUNNING':'SUCCEEDED',attempt_ordinal:1}))},admission:{state:'ADMITTED'},resourceUses:[],artifacts:[{artifact_id:'artifact'+id,task_id:plan.semantics.tasks.at(-1).task_id,digest:'f'.repeat(64),bytes:1000,created_at:'2026-11-10T00:00:00Z',contentAccess:'AUTHORIZED',content:JSON.stringify(report)}],events:[],outcome:{businessResolution:'UNDETERMINED',confirmationId:null,evaluation:{results:[]}}})}
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
 const s=await fixture(page,16);await page.goto('/tasks?q=交付检查&filter=completed');await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(16);await expect(page.getByText('已读记录先行展示，正在继续核对其余会话；数量尚未完整。',{exact:true})).toHaveCount(0);const open=page.getByRole('button',{name:'查看任务',exact:true}).last();await open.scrollIntoViewIfNeeded();await open.focus();const top=await page.evaluate(()=>document.querySelector('.skill-frame-content')?.scrollTop??scrollY);expect(top).toBeGreaterThan(100);await open.click();await expect(page.getByRole('heading',{name:'任务详情',exact:true})).toBeVisible();await page.reload();await expect(page.getByRole('heading',{name:'任务详情',exact:true})).toBeVisible();await page.getByRole('button',{name:'返回我的任务',exact:true}).click();await expect(page.getByLabel('搜索工作',{exact:false})).toHaveValue('交付检查');await expect.poll(()=>page.evaluate(()=>document.querySelector('.skill-frame-content')?.scrollTop??scrollY)).toBeGreaterThan(100);expect(Math.abs(await page.evaluate(()=>document.querySelector('.skill-frame-content')?.scrollTop??scrollY)-top)).toBeLessThan(3);await expect(page.getByRole('button',{name:'查看任务',exact:true}).last()).toBeFocused();expect(s.writes).toEqual([]);
});
test('denied exact record withdraws detail and partial reads never become a complete empty claim',async({page})=>{
 const s=await fixture(page);await page.goto('/tasks?work=e1');await expect(page.locator('.px-delivery-summary')).toBeVisible();s.denied=true;await page.getByRole('button',{name:'重新读取',exact:true}).click();await expect(page.getByRole('heading',{name:'当前无法读取这项工作',exact:true})).toBeVisible();await expect(page.locator('.px-delivery-summary')).toHaveCount(0);await expect(page.getByText('未替换为其他任务或最新版本，可重新读取后核对。',{exact:true})).toBeVisible();expect(s.writes).toEqual([]);
});
test('narrow task page contains table scrolling and mismatched owner cannot supply a task',async({page})=>{
 const s=await fixture(page,2);await page.setViewportSize({width:390,height:844});await page.goto('/tasks');await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(2);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);s.mismatch=true;await page.getByRole('button',{name:'重新读取',exact:true}).click();await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(0);await expect(page.getByText('部分关联记录当前未能读取。',{exact:false})).toBeVisible();expect(s.writes).toEqual([]);
});
test('a verified original journey wins over another readable link to the same execution',async({page})=>{
 const s=await fixture(page);s.running=true;
 await page.route('**/api/workbench/v1/conversations',r=>r.fulfill({json:{result:{items:[{conversation_id:'alias'},{conversation_id:'c1'}]}}}));
 await page.route('**/api/workbench/v1/conversations/alias/work-links',r=>r.fulfill({json:{result:{conversation:{conversation_id:'alias',title:'关联历史'},messages:[],links:[{readable:true,target:{problemId:'p1',executionDigest:'e1'}}]}}}));
 await page.route('**/api/workbench/v1/conversations/alias/journey',r=>r.fulfill({json:{result:{state:null}}}));
 await page.goto('/attention');await expect(page.getByRole('link',{name:'在原会话回答',exact:true})).toHaveAttribute('href','/work?conversation=c1');await expect(page.getByRole('link',{name:'在原会话回答',exact:true})).toHaveCount(1);await expect(page.getByText('已读记录先行展示，正在继续核对其余会话；数量尚未完整。',{exact:true})).toHaveCount(0);expect(s.reads.filter(p=>p==='/api/workbench/v1/prepared-executions/e1')).toHaveLength(1);expect(s.reads.filter(p=>p==='/api/workbench/v1/prepared-executions/e1/native-progress')).toHaveLength(1);expect(s.writes).toEqual([]);
});
test('persisted partial artifacts never make a running task appear completed',async({page})=>{
 const s=await fixture(page);s.running=true;await page.goto('/tasks?work=e1');await expect(page.getByRole('region',{name:'当前作业过程',exact:true})).toBeVisible();await page.getByRole('navigation',{name:'工作详情页签'}).getByRole('button',{name:'成果与记录',exact:true}).click();await expect(page.getByText('执行尚未完成，已有 1 份阶段产物记录；',{exact:false})).toBeVisible();await expect(page.locator('.px-delivery-summary')).toHaveCount(0);expect(s.writes).toEqual([]);
});

test('real conversation problem-only link resolves only its matching original journal execution',async({page})=>{
 const s=await fixture(page);await page.route('**/api/workbench/v1/conversations/c1/work-links',r=>r.fulfill({json:{result:{conversation:{conversation_id:'c1',title:'交付检查 1'},messages:[],links:[{readable:true,target:{problemId:'p1',revisionId:'p1:1',problemDigest:'a'.repeat(64)}}]}}}));await page.route('**/api/workbench/v1/conversations/c1/journey',r=>r.fulfill({json:{result:{state:{execution:'e1',problem:{business_problem_id:'p1'}}}}}));await page.goto('/tasks?work=e1&origin=c1');await expect(page.locator('.px-delivery-summary')).toBeVisible();await expect(page.getByRole('link',{name:'回到原会话',exact:true})).toHaveAttribute('href','/work?conversation=c1');expect(s.writes).toEqual([]);
});
test('journal execution never attaches to a different linked problem',async({page})=>{
 const s=await fixture(page);await page.route('**/api/workbench/v1/conversations/c1/work-links',r=>r.fulfill({json:{result:{conversation:{conversation_id:'c1'},messages:[],links:[{readable:true,target:{problemId:'p1'}}]}}}));await page.route('**/api/workbench/v1/conversations/c1/journey',r=>r.fulfill({json:{result:{state:{execution:'e1',problem:{business_problem_id:'different'}}}}}));await page.goto('/tasks');await expect(page.getByText('当前筛选下没有可读取的执行记录。',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(0);expect(s.writes).toEqual([]);
});
test('verified work appears while another historical conversation is still reading',async({page})=>{
 const s=await fixture(page,2);let release=()=>{};const held=new Promise<void>(r=>{release=r});await page.route('**/api/workbench/v1/conversations/c2/work-links',async r=>{await held;await r.fulfill({status:403,json:{reasonCode:'NOT_AUTHORIZED'}})});await page.goto('/tasks');await expect(page.locator('[data-open-work="e1"]')).toBeVisible();await expect(page.getByText('已读记录先行展示，正在继续核对其余会话；数量尚未完整。',{exact:true})).toBeVisible();release();await expect(page.getByText('已读记录先行展示，正在继续核对其余会话；数量尚未完整。',{exact:true})).toHaveCount(0);await expect(page.getByText('部分关联记录当前未能读取。',{exact:false})).toBeVisible();expect(s.writes).toEqual([]);
});

test('selected detail reads only exact owners and survives reload without scanning history',async({page})=>{
 const s=await fixture(page,30);await page.goto('/tasks?work=e24&origin=c24');await expect(page.locator('.px-delivery-summary')).toBeVisible();await expect(page.getByRole('link',{name:'回到原会话',exact:true})).toHaveAttribute('href','/work?conversation=c24');await page.reload();await expect(page.locator('.px-delivery-summary')).toBeVisible();expect(s.reads.filter(p=>p.includes('/prepared-executions/')&&!p.includes('/e24'))).toEqual([]);expect(s.reads.filter(p=>/\/problems$/.test(p))).toEqual([]);expect(s.reads.filter(p=>/\/conversations\/c(?!24(?:$|\/))\d+/.test(p))).toEqual([]);expect(s.writes).toEqual([]);
});
test('an old direct URL shows its exact report without inventing a conversation',async({page})=>{
 const s=await fixture(page);await page.goto('/tasks?work=e1');await expect(page.locator('.px-delivery-summary')).toBeVisible();await expect(page.getByText('原会话关联尚未核实，未提供替代跳转；',{exact:false})).toBeVisible();await expect(page.getByRole('link',{name:'回到原会话',exact:true})).toHaveCount(0);expect(s.reads.filter(p=>/\/problems$/.test(p))).toEqual([]);expect(s.writes).toEqual([]);
});
test('a foreign origin hint cannot redirect an authorized exact report',async({page})=>{
 const s=await fixture(page,2);await page.goto('/tasks?work=e1&origin=c2');await expect(page.locator('.px-delivery-summary')).toBeVisible();await expect(page.getByText('原会话关联尚未核实，未提供替代跳转；',{exact:false})).toBeVisible();await expect(page.getByRole('link',{name:'回到关联会话',exact:true})).toHaveCount(0);expect(s.writes).toEqual([]);
});
test('different problem revision never substitutes the selected execution snapshot',async({page})=>{
 const s=await fixture(page);await page.route('**/api/workbench/v1/problems/p1',r=>r.fulfill({json:{result:{problem:{business_problem_id:'p1'},revisions:[{business_problem_id:'p1',revision_id:'p1:2',digest:'b'.repeat(64),title:'最新问题'}]}}}));await page.goto('/tasks?work=e1&origin=c1');await expect(page.getByText('本次执行引用的问题版本当前不可读，未替换为最新版本。',{exact:true})).toBeVisible();await expect(page.locator('.px-delivery-summary')).toHaveCount(0);expect(s.writes).toEqual([]);
});

test('switching exact detail discards a delayed previous execution read',async({page})=>{
 const s=await fixture(page,2);let release=()=>{};const held=new Promise<void>(r=>{release=r});await page.route('**/api/workbench/v1/prepared-executions/e1',async r=>{await held;await r.fallback().catch(()=>{})});await page.goto('/tasks?work=e1&origin=c1');await expect.poll(()=>s.reads.filter(p=>p.endsWith('/session')).length).toBeGreaterThan(0);await page.evaluate(()=>{history.pushState({},'', '/tasks?work=e2&origin=c2');dispatchEvent(new PopStateEvent('popstate'))});await expect(page.locator('.f3-work-detail>header h2')).toHaveText('交付检查 2');release();await expect(page.locator('.f3-work-detail>header h2')).toHaveText('交付检查 2');await expect(page.getByRole('link',{name:'回到原会话',exact:true})).toHaveAttribute('href','/work?conversation=c2');expect(s.writes).toEqual([]);
});


test('directory uses work links without reading unrelated conversation messages',async({page})=>{
 const s=await fixture(page,3);await page.goto('/tasks');await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(3);
 expect(s.reads.filter(p=>/\/conversations\/c\d+$/.test(p))).toEqual([]);
 expect(s.reads.filter(p=>p.endsWith('/work-links'))).toHaveLength(3);expect(s.writes).toEqual([]);
});
for(const [question,label] of [['确认使用生产环境还是测试环境规范？','需确认口径'],['请提供交接资料。','需补充资料'],['请确认负责人姓名。','需确认信息']])test('pending label reflects literal question: '+label,async({page})=>{
 const s=await fixture(page);s.running=true;s.question=question;await page.goto('/attention');await expect(page.locator('.f3-work-decision .f3-work-badge')).toHaveText(label);expect(s.writes).toEqual([]);
});


test('all revoked conversation links retain an explicit incomplete-directory warning',async({page})=>{
 const s=await fixture(page);await page.route('**/api/workbench/v1/conversations/c1/work-links',r=>r.fulfill({json:{result:{conversation:{conversation_id:'c1'},links:[{link_id:'revoked',readable:false}]}}}));await page.goto('/attention');await expect(page.getByText('部分关联记录当前未能读取。',{exact:false})).toBeVisible();await expect(page.getByText('当前已读记录中没有仍有效的未回答追问。',{exact:true})).toBeVisible();expect(s.reads.some(p=>p.includes('/prepared-executions/'))).toBe(false);expect(s.writes).toEqual([]);
});

for(const mode of ['historical','exact-listed','denied-history'] as const)test('task list preserves execution problem revision: '+mode,async({page})=>{
 const s=await fixture(page);
 await page.route('**/api/workbench/v1/problems',r=>r.fulfill({json:{result:{problems:[{business_problem_id:'p1',revision_id:mode==='exact-listed'?'p1:1':'p1:2',digest:(mode==='exact-listed'?'a':'b').repeat(64),title:mode==='exact-listed'?'交付检查 1':'后来修改的新问题标题'}]}}}));
 if(mode==='denied-history')await page.route('**/api/workbench/v1/problems/p1',r=>r.fulfill({status:403,json:{reasonCode:'NOT_AUTHORIZED'}}));
 await page.goto('/tasks');
 if(mode==='denied-history'){await expect(page.getByText('部分关联记录当前未能读取。',{exact:false})).toBeVisible();await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(0)}
 else{await expect(page.locator('.f3-work-table strong')).toHaveText('交付检查 1');if(mode==='exact-listed')expect(s.reads.filter(p=>p.endsWith('/problems/p1'))).toHaveLength(0);else expect(s.reads.filter(p=>p.endsWith('/problems/p1'))).toHaveLength(1)}
 await expect(page.getByText('后来修改的新问题标题',{exact:true})).toHaveCount(0);expect(s.writes).toEqual([]);
});

for(const mode of ['matched','wrong-binding','foreign-origin'] as const)test('task process reuses lazy exact runtime binding: '+mode,async({page})=>{
 const s=await fixture(page,2);let runtimeReads=0;
 await page.route('**/api/workbench/v1/prepared-executions/e1/runtime-review',r=>{runtimeReads++;return r.fulfill({json:{result:{schemaVersion:'execution-runtime-review.v1',executionDigest:'e1',subject:'human:directory',scope:{tenantId:'fixture',securityDomain:'isolated'},executionStarted:false,tasks:plan.semantics.tasks.map((t:{task_id:string;title:string})=>({taskId:t.task_id,title:t.title,state:'SUCCEEDED',attemptId:null,instanceId:mode==='wrong-binding'?'foreign':'worker',assignmentId:'assignment',employee:{resource_id:'employee:fixed',revision_id:'1',digest:'a'.repeat(64)},agentInstanceId:'agent:fixed',runtimeInstanceId:'',runtimeGeneration:0,profile:report.sourceSnapshot,providerHealth:'NOT_OBSERVED'}))}}})});
 await page.goto('/tasks?work=e1&origin='+(mode==='foreign-origin'?'c2':'c1'));await expect(page.locator('.px-delivery-summary')).toBeVisible();expect(runtimeReads).toBe(0);
 await page.getByRole('navigation',{name:'工作详情页签'}).getByRole('button',{name:'办理过程',exact:true}).click();await expect(page.getByText('查看任务运行绑定',{exact:true})).toBeVisible();expect(runtimeReads).toBe(0);await page.getByText('查看任务运行绑定',{exact:true}).click();const region=page.getByRole('region',{name:'本次任务运行绑定',exact:true});
 if(mode==='wrong-binding'){await expect(region.getByRole('alert')).toBeVisible();await expect(region.getByRole('link',{name:'查看此员工分工'})).toHaveCount(0)}else{const link=region.getByRole('link',{name:'查看此员工分工'}).first();await expect(link).toBeVisible();const url=new URL((await link.getAttribute('href'))!, 'http://local');expect(url.searchParams.get('workExecution')).toBe('e1');expect(url.searchParams.get('returnConversation')).toBe(mode==='foreign-origin'?null:'c1')}
 expect(runtimeReads).toBe(1);expect(s.writes).toEqual([]);
});

test('explicit task result destination overrides remembered process but leaves tabs usable',async({page})=>{
 const s=await fixture(page);await page.goto('/tasks?work=e1&origin=c1');await expect(page.locator('.px-delivery-summary')).toBeVisible();const tabs=page.getByRole('navigation',{name:'工作详情页签'});await tabs.getByRole('button',{name:'办理过程',exact:true}).click();await expect(page.getByRole('region',{name:'当前作业过程',exact:true})).toBeVisible();await page.goto('/tasks?work=e1&workView=result&origin=c1');await expect(page.locator('.px-delivery-summary')).toBeVisible();await page.reload();await expect(page.locator('.px-delivery-summary')).toBeVisible();await tabs.getByRole('button',{name:'办理过程',exact:true}).click();await expect(page.getByRole('region',{name:'当前作业过程',exact:true})).toBeVisible();expect(new URL(page.url()).searchParams.has('workView')).toBe(false);expect(s.writes).toEqual([]);
});

test('filtered task list restores nonzero content scroll and focus after another page and refresh',async({page})=>{
 const s=await fixture(page,16);await page.goto('/tasks?q=交付检查&filter=completed');const last=page.getByRole('button',{name:'查看任务',exact:true}).last();await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(16);await expect(page.getByText('已读记录先行展示，正在继续核对其余会话；数量尚未完整。',{exact:true})).toHaveCount(0);await last.scrollIntoViewIfNeeded();await last.focus();const top=await page.locator('.skill-frame-content').evaluate(n=>n.scrollTop);expect(top).toBeGreaterThan(100);await page.locator('.skill-frame-actions').getByRole('link',{name:'＋ 发起会话',exact:true}).click();await expect(page).toHaveURL(/work\?draft=/);await page.goBack();await expect(page.getByLabel('搜索工作',{exact:false})).toHaveValue('交付检查');await expect.poll(()=>page.locator('.skill-frame-content').evaluate(n=>n.scrollTop)).toBe(top);await expect(last).toBeFocused();await page.reload();await expect.poll(()=>page.locator('.skill-frame-content').evaluate(n=>n.scrollTop)).toBe(top);await expect(last).toBeFocused();expect(s.writes).toEqual([]);
});

test('task list omits terminal question history but handled attention retains it and refresh reauthorizes',async({page})=>{
 const s=await fixture(page);s.answer='测试环境';await page.goto('/tasks');await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(1);await expect(page.getByText('已读记录先行展示，正在继续核对其余会话；数量尚未完整。',{exact:true})).toHaveCount(0);expect(s.reads.filter(p=>p.endsWith('/native-progress'))).toHaveLength(0);await page.goto('/attention');await page.getByRole('button',{name:'已处理',exact:true}).click();await expect(page.getByText('已回答：测试环境',{exact:true})).toBeVisible();expect(s.reads.filter(p=>p==='/api/workbench/v1/prepared-executions/e1')).toHaveLength(2);expect(s.reads.filter(p=>p.endsWith('/native-progress'))).toHaveLength(1);s.nativeDenied=true;await page.getByRole('button',{name:'重新读取',exact:true}).click();await expect(page.getByText('已回答：测试环境',{exact:true})).toHaveCount(0);await expect(page.getByText('部分关联记录当前未能读取。',{exact:false})).toBeVisible();expect(s.writes).toEqual([]);
});

test('directory does not increase read fanout while the original journey is pending',async({page})=>{
 const s=await fixture(page);let entered=false;let release!:()=>void;const gate=new Promise<void>(r=>release=r);await page.route('**/conversations/c1/journey',async route=>{entered=true;await gate;await route.fulfill({json:{result:{state:{execution:'e1'}}}})});await page.goto('/tasks');try{await expect.poll(()=>entered).toBe(true);expect(s.reads.filter(p=>p==='/api/workbench/v1/prepared-executions/e1')).toHaveLength(0)}finally{release()}await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(1);expect(s.writes).toEqual([]);
});

test('running detail keeps unavailable questions distinct from no questions',async({page},testInfo)=>{
 const s=await fixture(page);s.running=true;
 await page.route('**/api/workbench/v1/prepared-executions/e1/native-progress',r=>r.fulfill({status:403,json:{reasonCode:'NOT_AUTHORIZED'}}));
 await page.goto('/tasks?work=e1&origin=c1');
 await expect(page.locator('.f3-work-detail > header .f3-work-badge')).toHaveText('进展待核实');
 await expect(page.getByText('必要追问状态暂不可读取，不能判断是否需要补充。请重新读取或回到原会话核对。',{exact:true})).toBeVisible();
 await expect(page.getByRole('link',{name:'回到原会话',exact:true})).toHaveAttribute('href','/work?conversation=c1');expect(s.writes).toEqual([]);
 await page.screenshot({path:testInfo.outputPath('unknown-clarification-detail.png'),fullPage:true});
});

for(const destination of ['detail','inbox'] as const)test(`stalled question read releases saved ${destination} and recovers on reread`,async({page},testInfo)=>{
 const s=await fixture(page);s.running=true;let reads=0;let release!:()=>void;
 const held=new Promise<void>(resolve=>{release=resolve});
 await page.route('**/api/workbench/v1/prepared-executions/e1/native-progress',async route=>{
  reads++;if(reads===1)await held;await route.fallback();
 });
 try{
  await page.goto(destination==='detail'?'/tasks?work=e1&origin=c1':'/attention');
  await expect.poll(()=>reads).toBe(1);
  if(destination==='detail'){
   await expect(page.locator('.f3-work-detail > header .f3-work-badge')).toHaveText('进展待核实',{timeout:20000});
   await expect(page.getByRole('link',{name:'回到原会话',exact:true})).toHaveAttribute('href','/work?conversation=c1');
   await expect(page.locator('.f3-work-detail > header')).toContainText('已有 1 份保存产物');
  }else{
   await expect(page.getByText('部分关联记录当前未能读取。',{exact:false})).toBeVisible({timeout:20000});
   await expect(page.getByText('已读记录先行展示，正在继续核对其余会话；数量尚未完整。',{exact:true})).toHaveCount(0);
   await expect(page.getByRole('link',{name:'在原会话回答',exact:true})).toHaveCount(0);
  }
  expect(reads).toBe(1);expect(s.writes).toEqual([]);
  await page.screenshot({path:testInfo.outputPath(`stalled-${destination}-read.png`),fullPage:true});
  await page.getByRole('button',{name:'重新读取',exact:true}).click();
  await expect(page.getByText(s.question,{exact:true})).toBeVisible();
  await expect(page.getByRole('link',{name:destination==='detail'?'在原会话回答并继续':'在原会话回答',exact:true})).toHaveAttribute('href','/work?conversation=c1');
  expect(reads).toBe(2);release();
  await expect(page.getByText(s.question,{exact:true})).toBeVisible();expect(s.writes).toEqual([]);
 }finally{release()}
});

test('independent detail reads proceed while fixed problem verification is pending without exposing a result',async({page})=>{
 const s=await fixture(page);s.running=true;let entered=false,release!:()=>void;const held=new Promise<void>(resolve=>{release=resolve});
 await page.route('**/api/workbench/v1/problems/p1',async route=>{entered=true;await held;return route.fallback()});
 try{await page.goto('/tasks?work=e1&origin=c1');await expect.poll(()=>entered).toBe(true);await expect.poll(()=>s.reads.filter(p=>p.endsWith('/native-progress')).length).toBe(1);await expect.poll(()=>s.reads.filter(p=>p.endsWith('/journey')).length).toBe(1);await expect(page.locator('.f3-work-detail')).toHaveCount(0);release();await expect(page.getByText(s.question,{exact:true})).toBeVisible();await expect(page.getByRole('link',{name:'在原会话回答并继续',exact:true})).toHaveAttribute('href','/work?conversation=c1');expect(s.writes).toEqual([])}finally{release()}
});
