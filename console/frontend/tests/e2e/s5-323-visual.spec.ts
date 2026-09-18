import {expect,test,type Page} from '@playwright/test';
import {writeFileSync} from 'node:fs';
import type {DraftAssistanceResult,UnderstandingItem} from '../../src/api/draftAssistanceTypes';

type Body={content:string;idempotencyKey:string;[key:string]:unknown};
type State={requests:Body[];writes:Body[];outputs:string[];hold?:Promise<void>;unknown?:boolean;created?:Record<string,unknown>;principal:string;criteriaStatus:number;denyRead?:boolean;denyCreate?:boolean;readApproved?:boolean;links:number};
function understanding(text:string):UnderstandingItem[]{return ['goal','scope','time','constraints','successCriteria'].map(field=>({field:field as UnderstandingItem['field'],value:field==='goal'?text:'尚不清楚',source:field==='goal'?'USER_STATEMENT':'UNKNOWN',sourceRefs:field==='goal'?['user:fixture']:[]}))}
async function setup(page:Page,outputs=['A供应商，缺陷率低于2%，不能更换供应商。']){
  const state:State={requests:[],writes:[],outputs,principal:'human:323-visual',criteriaStatus:403,links:0};
  await page.route('**/api/workbench/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname,method=route.request().method();
    if(path.endsWith('/session')){await route.fulfill({json:{principal:{principalId:state.principal,tenantId:'tenant-321',securityDomain:'quality'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'synthetic-321'}});return;}
    if(path.endsWith('/draft-assistance/invocations')){
      const body=route.request().postDataJSON() as Body;state.requests.push(body);await state.hold;
      const index=state.requests.length,text=state.outputs[Math.min(index-1,state.outputs.length-1)];
      const result:Partial<DraftAssistanceResult>={contextId:'context:321',turnId:`turn:${index}`,turnVersion:index,invocationId:`inv:${index}`,state:'SUCCEEDED',resultKind:'DRAFT_READY',transport:'SYNTHETIC',draft:{title:'整理延期采购订单清单',description:text},contentDisposition:'CONTENT_NOT_RETAINED',understanding:understanding(text)};
      await route.fulfill({json:{result}});return;
    }
    if(path.includes('/authorization/grant-requests')){await route.fulfill({json:{requestId:'request:321',state:state.readApproved?'APPROVED':'PENDING',aggregateVersion:1,submittedAt:'2026-09-17T00:00:00Z',purpose:'CONTINUE_PROBLEM_READ',requestedActions:['READ']}});return;}
    if(path.endsWith('/problem-link')){state.links++;await route.fulfill({status:503,json:{reasonCode:'EVIDENCE_STORAGE_UNAVAILABLE'}});return;}
    if(path.endsWith('/problems')&&method==='POST'){
      const body=route.request().postDataJSON() as Body;state.writes.push(body);
      if(state.denyCreate){await route.fulfill({status:403,json:{reasonCode:'AUTHORIZATION_DENIED'}});return}
      state.created??={scope:{namespace:'tenant-321',security_domain:'quality'},business_problem_id:'problem:321',revision_id:'revision:321',revision:1,predecessor_revision_id:null,title:body.title,description:body.description,owner_id:body.ownerId,created_by:body.ownerId,created_at:'2026-09-17T00:00:00Z',digest:'a'.repeat(64)};
      if(state.unknown){state.unknown=false;await route.fulfill({status:503,json:{reasonCode:'BUSINESS_PROBLEM_STORAGE_UNAVAILABLE'}});return}
      await route.fulfill({status:201,json:{result:{revision:state.created,creatorContinuation:{state:'AVAILABLE',continuationId:'continuation:321',expiresAt:'2099-01-01T00:00:00Z'}}}});return;
    }
    if(path.endsWith('/problems')){await route.fulfill({json:{result:{problems:state.created?[state.created]:[]}}});return}
    if(path.includes('/criteria')){await route.fulfill({status:state.criteriaStatus,json:state.criteriaStatus===200?{result:{revisions:[]}}:{reasonCode:'AUTHORIZATION_DENIED'}});return}
    if(path.endsWith('/problems/problem%3A321')){
      if(state.denyRead||!state.readApproved){await route.fulfill({status:403,json:{reasonCode:'AUTHORIZATION_DENIED'}});return}
      await route.fulfill({json:{result:{problem:{business_problem_id:'problem:321',current_revision_id:'revision:321',aggregate_version:1,current_state:'DRAFT'},revisions:[state.created],lifecycle:[]}}});return;
    }
    await route.fulfill({json:{result:{}}});
  });
  await page.goto('/work');await expect(page.locator('#problem-composer')).toBeVisible();return state;
}
async function send(page:Page,text:string){const input=page.locator('#problem-composer');await input.fill(text);await input.press('Enter');}
async function authorizeRead(page:Page,state:State){await page.getByRole('button',{name:'申请查看权限',exact:true}).click();state.readApproved=true;await page.getByRole('button',{name:'刷新授权状态',exact:true}).click();await expect(page.getByRole('heading',{name:'问题详情已读取',exact:true})).toBeVisible();}
async function ready(page:Page){await expect(page.getByLabel('问题草稿卡片').getByRole('button',{name:'确认创建',exact:true})).toBeEnabled()}
const confirm=(page:Page)=>page.getByLabel('问题草稿卡片').getByRole('button',{name:'确认创建',exact:true});


import {procurement} from "./fixtures/planning323";

// Identical case and actions can be captured against the retained pre-visual build.
test('V323 same-case problem clarification correction create and readback',async({page},info)=>{
 await page.setViewportSize({width:1500,height:1050});
 const initial='请整理截至今天仍未交付的延期采购订单，给我清单和供应商摘要。';
 const supplement='2026年9月17日10:00，323五行合成采购样本；只看A供应商，不修改订单、不发送通知。';
 const corrected='2026年9月17日10:00，323五行合成采购样本；所有供应商，缺失日期和来源冲突单列，不修改订单、不发送通知。';
 const state=await setup(page,['',supplement,corrected]);state.criteriaStatus=200;
 let first=true;
 await page.route('**/draft-assistance/invocations',async route=>{
  if(!first){await route.fallback();return;}first=false;state.requests.push(route.request().postDataJSON());
  await route.fulfill({json:{result:{contextId:'context:321',turnId:'turn:1',turnVersion:1,aggregateVersion:1,invocationId:'inv:1',state:'SUCCEEDED',resultKind:'NEEDS_CLARIFICATION',transport:'SYNTHETIC',clarificationQuestion:'请确认快照时间、供应商范围，以及是否需要发送通知。',contentDisposition:'CONTENT_NOT_RETAINED'}}});
 });
 await page.route('**/problem-link',route=>route.fulfill({json:{result:{contextId:'context:321',turnId:'turn:3',turnVersion:3,invocationId:'inv:3',state:'SUCCEEDED',resultKind:'DRAFT_READY',transport:'SYNTHETIC',contentDisposition:'CONTENT_NOT_RETAINED'}}}));
 async function shot(name:string,target?:string){if(target)await page.locator(target).evaluate(node=>{(node.closest('.px-message')??node).scrollIntoView({block:'start',behavior:'instant'});window.scrollTo(0,0)});await page.screenshot({path:info.outputPath(name+'.png')});}
 await shot('01-problem-input');await send(page,initial);await expect(page.getByLabel('AI 问题理解与草稿辅助')).toContainText('等待补充信息');await shot('02-ai-clarification','#draft-assistance-message');
 await page.getByRole('button',{name:'回答补问',exact:true}).click();await expect(page.locator('#problem-composer')).toBeFocused();
 await send(page,supplement);await ready(page);await send(page,'纠正：改为所有供应商；缺失日期和来源冲突单列，其余保持。');await ready(page);
 const card=page.getByLabel('问题草稿卡片');await expect(card).toContainText(corrected);await shot('03-corrected-confirm','#draft-problem-message');
 await confirm(page).click();await expect(page.getByRole('heading',{name:'业务问题已创建',exact:true})).toBeVisible();await shot('04-created','#created-problem-message');
 await authorizeRead(page,state);await shot('05-readback','#formal-problem-message');await page.reload();await expect(page.getByRole('heading',{name:'问题详情已读取',exact:true})).toBeVisible();await shot('06-refreshed','#formal-problem-message');
 expect(state.writes).toHaveLength(1);expect(state.writes[0].description).toBe(corrected);
 writeFileSync(info.outputPath('receipt.json'),JSON.stringify({kind:'UI_API_FIXTURE',providerCalls:0,databaseWrites:0,fixtureCreates:state.writes.length,fixtureAssistanceRequests:state.requests.length,initial,supplement,corrected},null,2));
});

async function planning(page:Page){
 const proposal={proposal_id:'proposal:323-visual',revision:1,semantics:procurement};
 const history:{proposals:typeof proposal[];plans:unknown[]}={proposals:[proposal],plans:[]};
 const commands:{path:string;body:Record<string,unknown>}[]=[];
 const snapshot={checked_at:"2026-09-17T02:00:00Z",observations:[{requirement_id:"employee",status:"MATCHED",reason:"EXACT_TEST_OWNER"}]};
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:323-visual',tenantId:'tenant-a',securityDomain:'quality'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(route.request().method()==='POST')commands.push({path,body:route.request().postDataJSON()});
  if(path.endsWith('/confirm'))history.plans=[{plan:{plan_id:'plan:323-visual',version:1,source_proposal_revision:1,semantics:procurement},digest:'a'.repeat(64),approval:{approval_decision_id:'approval:323-visual',decided_at:'2026-09-17T02:00:00Z'},execution_status:'NOT_STARTED'}];
  const result=path.endsWith('/history')?history:path.endsWith('/confirm')?history.plans[0]:path.endsWith('/resources')?{snapshot}:{proposal:history.proposals.find(p=>p.revision===Number(new URL(route.request().url()).searchParams.get("version")))??proposal,digest:'b'.repeat(64),snapshot};
  await route.fulfill({json:{result}});
 });
 await page.goto('/work/planning/proposal%3A323-visual?revision=1');await expect(page.locator('.planning-task')).toHaveCount(5);return {commands,history,snapshot};
}

for(const width of [1500,1366])test(`V323 planning layout and interactions ${width}`,async({page},info)=>{
 await page.setViewportSize({width,height:width===1500?1050:768});const state=await planning(page);
 await expect(page.locator('.planning-stage')).toHaveCount(3);
 for(const task of await page.locator('.planning-task').all()){await expect(task.locator(':scope > summary')).toContainText('职责：');await expect(task.locator(':scope > summary')).toContainText('数字员工：');}
 if(width===1500){await expect(page.locator('.planning-goal')).toBeInViewport({ratio:1});await expect(page.locator('.planning-task').last()).toBeInViewport({ratio:1});await expect(page.getByRole('button',{name:'确认计划',exact:true})).toBeInViewport({ratio:1});}
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:info.outputPath('07-goal-and-plan.png')});
 const task=page.locator('.planning-task').nth(1);await task.locator(':scope > summary').click();await expect(task).toContainText('读取快照结果');await expect(task).toContainText('检查缺失日期与来源冲突');
 await task.scrollIntoViewIfNeeded();await page.screenshot({path:info.outputPath('08-task-purpose.png')});
 await task.locator(':scope > summary').click();await page.getByRole('button',{name:'确认计划',exact:true}).click();await expect(page.locator('.planning-confirm')).toContainText('尚未开始执行');
 expect(state.commands.filter(c=>c.path.endsWith('/confirm'))).toHaveLength(1);
 await page.getByRole('button',{name:'刷新资源状态',exact:true}).click();await expect(page.locator('.planning-counts')).toContainText('1已匹配');await expect(page.locator('.planning-count-explanation')).toContainText('1 项可选未匹配');
 await page.getByRole('link',{name:'查看资源用途与缺口 →'}).click();await page.locator('#requirement-employee > summary').click();await expect(page.locator('#requirement-employee')).toContainText('非企业生产目录');
 await expect(page.locator('#requirement-employee code')).not.toBeVisible();await page.locator('#requirement-employee').getByText('准确版本与技术引用',{exact:true}).click();await expect(page.locator('#requirement-employee code')).toBeVisible();
 await page.screenshot({path:info.outputPath('09-resource-gaps.png')});await page.reload();await expect(page.locator('.planning-confirm')).toContainText('计划已确认');
 await page.getByLabel('查看历史建议').selectOption('1');await expect(page.locator('.planning-confirm')).toContainText('2026-09-17 10:00（北京时间）');
 await page.locator('.planning-confirm summary').click();await page.locator('.planning-confirm').scrollIntoViewIfNeeded();await page.screenshot({path:info.outputPath('10-confirmation-history.png')});
 expect(state.commands).toHaveLength(2);expect(state.history.plans).toHaveLength(1);
 writeFileSync(info.outputPath('receipt.json'),JSON.stringify({kind:'UI_API_FIXTURE',width,providerCalls:0,databaseWrites:0,commands:state.commands},null,2));
});

test('V323 history and unknown resources never imply readiness or silently confirm',async({page})=>{
 const state=await planning(page);
 state.snapshot.observations=[{requirement_id:'employee',status:'UNKNOWN',reason:'READER_UNAVAILABLE'},{requirement_id:'snapshot',status:'VERSION_MISMATCH',reason:'REVISION_CHANGED'}];
 state.history.proposals.push({...state.history.proposals[0],revision:2});await page.reload();
 await expect(page.getByRole('button',{name:'确认计划',exact:true})).toBeDisabled();
 await page.locator('.planning-task').first().locator(':scope > summary').click();
 await expect(page.locator('.planning-task').first()).toContainText('待核实');await expect(page.locator('.planning-task').first()).toContainText('版本不符');
 await page.getByLabel('查看历史建议').selectOption('2');await expect(page.getByRole('button',{name:'确认计划',exact:true})).toBeEnabled();
 expect(state.commands).toHaveLength(0);expect(state.history.plans).toHaveLength(0);
});

test('V323 grouped navigation keeps destinations and stays outside workflow pages',async({page})=>{
 await planning(page);await page.locator('.px-sidebar').getByText('管理与技术',{exact:true}).click();
 await expect(page.locator('.px-sidebar').getByRole('link',{name:'问题审核与修订',exact:true})).toHaveAttribute('href','/problems');
 await page.locator('.px-sidebar').getByText('平台支撑',{exact:true}).click();await expect(page.locator('.px-sidebar').getByRole('link',{name:'系统设置',exact:true})).toHaveAttribute('href','/settings');
 await page.locator('.px-primary-nav').getByRole('link',{name:'Workflow',exact:false}).click();await expect(page.locator('.journey-shell')).toHaveCount(0);
});

test('V323 formal planning errors are visible and do not create or execute',async({page})=>{
  let calls=0;
  await page.route('**/api/workbench/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:323',tenantId:'isolated-323',securityDomain:'test'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'test'}});
    if(path.includes('/planning-input/'))return route.fulfill({json:{result:{target:{},title:'受控规划',description:'仅测试接线'}}});
    if(path.endsWith('/planning-v2/invocations')){calls++;return route.fulfill({json:{result:{invocation:{target:{invocation_id:'failed:323'}},result:{technical_status:'FAILED',kind:null,reason:'PLANNING_PROVIDER_HTTP_REJECTED'},facts_status:'RECORDED'}}});}
    if(path.endsWith('/invocations/failed:323'))return route.fulfill({json:{result:{invocation:{target:{invocation_id:'failed:323'}},result:{technical_status:'FAILED',kind:null,reason:'PLANNING_PROVIDER_HTTP_REJECTED'},facts_status:'RECORDED'}}});
    return route.fulfill({json:{result:{}}});
  });
  await page.goto('/work/plan?problem=test:323');
  await page.getByRole('button',{name:'生成建议计划',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('没有创建建议、批准或执行');
  await expect(page.getByRole('button',{name:'生成建议计划',exact:true})).toBeDisabled();
  expect(calls).toBe(1);
});

test('V323 missing planning configuration is explicit and clarification retains answers',async({page})=>{
  const requests:Record<string,unknown>[]=[];let missing=true;
  const value=(id:string)=>({invocation:{target:{invocation_id:id}},result:{technical_status:'SUCCEEDED',kind:'NEEDS_CLARIFICATION',questions:['请补充统计日期或口径']},facts_status:'RECORDED'});
  await page.route('**/api/workbench/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:323',tenantId:'isolated-323',securityDomain:'test'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'test'}});
    if(path.includes('/planning-input/'))return route.fulfill({json:{result:{target:{},title:'受控规划',description:'仅测试接线'}}});
    if(path.endsWith('/planning-v2/invocations')){
      if(missing)return route.fulfill({status:503,json:{reasonCode:'PLANNING_NOT_CONFIGURED'}});
      requests.push(route.request().postDataJSON());return route.fulfill({json:{result:value(`clarification:${requests.length}`)}});
    }
    if(path.includes('/planning-v2/invocations/'))return route.fulfill({json:{result:value(path.split('/').at(-1)!)}});
    return route.fulfill({json:{result:{}}});
  });
  await page.goto('/work/plan?problem=test:323');
  await page.getByRole('button',{name:'生成建议计划',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('PLANNING_NOT_CONFIGURED');
  expect(requests).toHaveLength(0);missing=false;
  await page.getByRole('button',{name:'生成建议计划',exact:true}).click();
  await page.getByLabel('补充回答').fill('2026-09-18');
  await page.getByRole('button',{name:'提交补充并生成建议'}).click();
  await expect(page.getByLabel('补充回答')).toHaveValue('');
  await page.getByLabel('补充回答').fill('纠正：仅公司A，不含已取消订单');
  await page.getByRole('button',{name:'提交补充并生成建议'}).click();
  await expect.poll(()=>requests.length).toBe(3);
  expect(requests[2].answers).toEqual(['2026-09-18','纠正：仅公司A，不含已取消订单']);
  expect(page.url()).not.toContain('公司A');
});
