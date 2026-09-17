import {expect,test,type Page} from '@playwright/test';
import {writeFileSync,readFileSync} from 'node:fs';
import type {DraftAssistanceResult,UnderstandingItem} from '../../src/api/draftAssistanceTypes';

type Body={content:string;idempotencyKey:string;[key:string]:unknown};
type State={requests:Body[];writes:Body[];outputs:string[];hold?:Promise<void>;unknown?:boolean;created?:Record<string,unknown>;principal:string;criteriaStatus:number;denyRead?:boolean;denyCreate?:boolean;readApproved?:boolean;links:number};
function understanding(text:string):UnderstandingItem[]{return ['goal','scope','time','constraints','successCriteria'].map(field=>({field:field as UnderstandingItem['field'],value:field==='goal'?text:'尚不清楚',source:field==='goal'?'USER_STATEMENT':'UNKNOWN',sourceRefs:field==='goal'?['user:fixture']:[]}))}
async function setup(page:Page,outputs=['A供应商，缺陷率低于2%，不能更换供应商。']){
  const state:State={requests:[],writes:[],outputs,principal:'human:321',criteriaStatus:403,links:0};
  await page.route('**/api/workbench/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname,method=route.request().method();
    if(path.endsWith('/session')){await route.fulfill({json:{principal:{principalId:state.principal,tenantId:'tenant-321',securityDomain:'quality'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'synthetic-321'}});return;}
    if(path.endsWith('/draft-assistance/invocations')){
      const body=route.request().postDataJSON() as Body;state.requests.push(body);await state.hold;
      const index=state.requests.length,text=state.outputs[Math.min(index-1,state.outputs.length-1)];
      const result:Partial<DraftAssistanceResult>={contextId:'context:321',turnId:`turn:${index}`,turnVersion:index,invocationId:`inv:${index}`,state:'SUCCEEDED',resultKind:'DRAFT_READY',transport:'SYNTHETIC',draft:{title:'来料改善',description:text},contentDisposition:'CONTENT_NOT_RETAINED',understanding:understanding(text)};
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

test('B01 direct confirmation has one business action and matching payload',async({page},info)=>{
  const state=await setup(page);await send(page,state.outputs[0]);await ready(page);
  await expect(page.getByLabel('当前问题理解')).toContainText('不能更换供应商');await page.screenshot({path:info.outputPath('understanding.png')});
  await confirm(page).click();await expect(page.getByRole('heading',{name:'业务问题已创建',exact:true})).toBeVisible();
  expect(state.writes).toHaveLength(1);expect(state.writes[0].description).toBe(state.outputs[0]);
  writeFileSync(info.outputPath('operations.json'),JSON.stringify({kind:'MOCK_INTERACTION',modelQuality:'NOT_MEASURED',inputCount:1,confirmClicks:1,forcedEditVisits:0,problemCommands:state.writes.length}));
});

test('B02 natural correction and local edit submit only the displayed revision',async({page},info)=>{
  const state=await setup(page,['A供应商，缺陷率低于2%，不能更换供应商。','B供应商，缺陷率低于1%，不能更换供应商。']);
  await send(page,state.outputs[0]);await ready(page);const card=page.getByLabel('问题草稿卡片');
  await card.getByRole('button',{name:'修改',exact:true}).click();await card.getByRole('textbox',{name:'完整描述',exact:true}).fill('B供应商，缺陷率低于2%，不能更换供应商。');await card.getByRole('button',{name:'采用字段修改',exact:true}).click();
  await send(page,'只把阈值改成低于1%，其他保持。');await expect(card).toContainText(state.outputs[1]);await ready(page);
  const context=JSON.parse(state.requests[1].content);expect(context.currentDraft.description).toContain('B供应商');expect(context.messages.map((m:{text:string})=>m.text).join('\n')).toContain('用户采用字段修改');expect(state.requests[1].expectedParentVersion).toBe(1);
  await page.screenshot({path:info.outputPath('correction.png')});await confirm(page).click();await expect.poll(()=>state.writes.length).toBe(1);expect(state.writes[0].description).toBe(state.outputs[1]);
});

test('B03 late result does not clear new input, steal focus or enable stale create',async({page})=>{
  const state=await setup(page);let release!:()=>void;state.hold=new Promise(resolve=>{release=resolve});
  await send(page,'A供应商改善');await expect.poll(()=>state.requests.length).toBe(1);
  const input=page.locator('#problem-composer');await input.fill('纠正：只看B');release();await expect(input).toHaveValue('纠正：只看B');await expect(input).toBeFocused();
  await expect(confirm(page)).toHaveCount(0);expect(state.writes).toHaveLength(0);
  const assistance=page.getByLabel('AI 问题理解与草稿辅助');await assistance.getByRole('button',{name:'切换为手工草稿',exact:true}).click();await expect(input).toHaveValue('纠正：只看B');await expect(confirm(page)).toHaveCount(0);
  state.hold=undefined;await input.press('Enter');await ready(page);expect(state.requests).toHaveLength(2);
});

test('B04 IME, repeated Enter, sending key and explicit confirm focus',async({page})=>{
  const state=await setup(page);const input=page.locator('#problem-composer');await input.fill('A供应商改善');
  await input.dispatchEvent('keydown',{key:'Enter',isComposing:true});await input.dispatchEvent('keydown',{key:'Enter',keyCode:229});expect(state.requests).toHaveLength(0);
  await input.press('Shift+Enter');expect(state.requests).toHaveLength(0);await input.press('Enter');await ready(page);expect(state.writes).toHaveLength(0);await expect(input).toBeFocused();
  const card=page.getByLabel('问题草稿卡片');await card.getByRole('button',{name:'修改',exact:true}).click();await card.getByRole('button',{name:'采用字段修改',exact:true}).click();await expect(confirm(page)).toBeFocused();
  await confirm(page).dispatchEvent('keydown',{key:'Enter',repeat:true});await confirm(page).dispatchEvent('keydown',{key:'Enter',keyCode:229});await confirm(page).dispatchEvent('compositionstart');await confirm(page).press('Enter');expect(state.writes).toHaveLength(0);await confirm(page).dispatchEvent('compositionend');await card.getByRole('button',{name:'修改',exact:true}).focus();await page.keyboard.press('Tab');await expect(confirm(page)).toBeFocused();await confirm(page).press('Enter');await expect.poll(()=>state.writes.length).toBe(1);
});

test('B05 double action and unknown recover the original key and payload',async({page})=>{
  const state=await setup(page);state.unknown=true;await send(page,'A供应商改善');await ready(page);await confirm(page).dblclick();
  await expect(page.getByLabel('问题草稿卡片')).toContainText('结果不确定');await expect(page.getByRole('button',{name:'修改',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'恢复原创建结果',exact:true}).click();await expect(page.getByRole('heading',{name:'业务问题已创建',exact:true})).toBeVisible();expect(state.writes).toHaveLength(2);expect(state.writes[0]).toEqual(state.writes[1]);
  await page.reload();await expect(page.getByRole('heading',{name:'问题详情已读取',exact:true})).toHaveCount(0);
  await authorizeRead(page,state);await page.reload();await expect(page.getByRole('heading',{name:'问题详情已读取',exact:true})).toBeVisible();expect(state.writes).toHaveLength(2);
});

test('B06 criteria and provenance failures preserve creation with independent disclosure',async({page},info)=>{
  const state=await setup(page);await send(page,'A供应商改善');await ready(page);await confirm(page).click();
  await expect(page.getByRole('heading',{name:'业务问题已创建',exact:true})).toBeVisible();expect(state.writes).toHaveLength(1);
  await expect.poll(()=>state.links).toBe(1);await page.getByRole('button',{name:'仅重试来源补记',exact:true}).click();await expect.poll(()=>state.links).toBe(2);expect(state.writes).toHaveLength(1);
  await authorizeRead(page,state);await expect(page.getByText('读取成功标准',{exact:false}).first()).toBeVisible();
  state.criteriaStatus=500;await page.reload();await expect(page.getByRole('heading',{name:'问题详情已读取',exact:true})).toBeVisible();await expect(page.getByText('读取成功标准',{exact:false}).first()).toBeVisible();await page.screenshot({path:info.outputPath('created-criteria-unavailable.png')});
  state.denyRead=true;await page.reload();await expect(page.getByRole('heading',{name:'问题详情已读取',exact:true})).toHaveCount(0);expect(state.writes).toHaveLength(1);
});

test('B07 scope change fences input and pending model content; no raw storage',async({page})=>{
  const state=await setup(page);await send(page,'321-sensitive-synthetic');await ready(page);
  const storage=await page.evaluate(()=>JSON.stringify({local:{...localStorage},session:{...sessionStorage}}));expect(storage).not.toContain('321-sensitive-synthetic');
  state.principal='human:other-321';await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect(page.getByLabel('问题草稿卡片')).toHaveCount(0);await expect(page.getByLabel('AI 问题理解与草稿辅助')).toHaveCount(0);await expect(page.locator('#problem-composer')).toHaveValue('');expect(state.writes).toHaveLength(0);
});

test('B08 explicit failure, compact cards and narrow-screen keyboard reachability',async({page},info)=>{
  const state=await setup(page);state.denyCreate=true;await page.setViewportSize({width:390,height:844});await send(page,'A供应商改善');await ready(page);
  await expect(page.getByLabel('AI 问题理解与草稿辅助')).not.toHaveAttribute('open','');await confirm(page).click();await expect(page.getByLabel('问题草稿卡片')).toContainText('创建失败');await expect(page.getByRole('heading',{name:'业务问题已创建',exact:true})).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:info.outputPath('failure-390.png')});
});

const cases=JSON.parse(readFileSync(new URL('../../../backend/tests/fixtures/s5_321_quality_cases.json',import.meta.url),'utf8')).cases as {id:string;turns:string[];oracle:string}[];
for(const fixture of cases)test(`${fixture.id} synthetic input/correction contract (quality NOT_MEASURED)`,async({page})=>{
  const state=await setup(page,['明确标识的mock草稿；不作为模型质量结果。']);
  for(const turn of fixture.turns){await send(page,turn);await ready(page);}
  const context=JSON.parse(state.requests.at(-1)!.content);expect(context.messages.map((m:{text:string})=>m.text)).toEqual(fixture.turns);expect(state.writes).toHaveLength(0);expect(fixture.oracle).toBeTruthy();
});

test('B03 stale card stays unsubmitable after a second edit and late correction',async({page})=>{
 const state=await setup(page,['旧版','新版']);await send(page,'旧版');await ready(page);
 let release!:()=>void;state.hold=new Promise(resolve=>{release=resolve});await send(page,'修正为新版');await expect.poll(()=>state.requests.length).toBe(2);
 await page.locator('#problem-composer').fill('又有新约束');release();await expect(page.locator('#problem-composer')).toHaveValue('又有新约束');await expect(confirm(page)).toHaveCount(0);expect(state.writes).toHaveLength(0);
});

test('B07 late rejected invocation cannot restore a card after identity change',async({page})=>{
 const state=await setup(page);await send(page,'old-sensitive');await ready(page);let release!:()=>void;const hold=new Promise<void>(resolve=>{release=resolve});let requested=false;
 await page.route('**/draft-assistance/invocations/*/reject',async route=>{requested=true;await hold;await route.fulfill({json:{result:{contextId:'context:321',turnId:'turn:1',turnVersion:1,invocationId:'inv:1',state:'REJECTED_BY_USER',transport:'SYNTHETIC',contentDisposition:'CONTENT_NOT_RETAINED'}}});});
 await page.getByLabel('问题草稿卡片').getByRole('button',{name:'取消草稿',exact:true}).click();await expect.poll(()=>requested).toBe(true);
 state.principal='human:new-321';await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect(page.getByLabel('问题草稿卡片')).toHaveCount(0);release();await expect(page.getByLabel('AI 问题理解与草稿辅助')).toHaveCount(0);expect(state.writes).toHaveLength(0);
});

test('Q14 bounded context deduplicates exactly and refuses overflow without truncation',async()=>{
 const {appendUserMessage,understandingContent}=await import('../../src/problems/problemUnderstandingModel');
 let messages=appendUserMessage([],'X产线停机低于每月2小时，预算8万，禁止换设备');
 for(let i=0;i<40;i++)messages=appendUserMessage(messages,'本条重复背景，无新增约束');
 messages=appendUserMessage(messages,'预算纠正为6万');
 const packed=understandingContent(messages,3,null,null,null);expect(JSON.parse(packed).messages).toHaveLength(3);expect(packed).toContain('禁止换设备');expect(packed).toContain('预算纠正为6万');
 const overflow=[...messages,...Array.from({length:9},(_,i)=>({id:`user:large-${i}`,text:'长'.repeat(2000)}))];expect(()=>understandingContent(overflow,4,null,null,null)).toThrow('未被截断');expect(overflow[0].text).toContain('禁止换设备');
});


test('B03 manual fallback cannot silently discard an unsent correction',async({page})=>{
 const state=await setup(page);await send(page,'A供应商');await ready(page);await page.locator('#problem-composer').fill('只看B供应商');
 const assistance=page.getByLabel('AI 问题理解与草稿辅助');await assistance.locator(':scope > summary').click();await assistance.getByRole('button',{name:'切换为手工草稿',exact:true}).click();
 await expect(page.locator('#problem-composer')).toHaveValue('只看B供应商');await expect(confirm(page)).toBeDisabled();await expect(page.getByText('当前输入尚未采用；请先发送修改，或清空输入后明确选择手工草稿并编辑。',{exact:true})).toBeVisible();expect(state.writes).toHaveLength(0);
});

for(const transport of ['SYNTHETIC','REAL_PROVIDER'])test(`clarification is not labelled as a generated draft (${transport})`,async({page})=>{
 await setup(page);
 await page.route('**/draft-assistance/invocations',async route=>{await route.fulfill({json:{result:{contextId:'context:321',turnId:'turn:1',turnVersion:1,invocationId:'inv:1',state:'SUCCEEDED',resultKind:'NEEDS_CLARIFICATION',transport,draft:null,clarificationQuestion:'希望达到什么目标？',contentDisposition:'CONTENT_NOT_RETAINED'}}});});
 await send(page,'供应商质量不好');
 const card=page.getByLabel('AI 问题理解与草稿辅助');
 await expect(card.getByRole('heading',{name:'需要补充信息',exact:true})).toBeVisible();
 await expect(card.locator('.px-status')).toHaveText('等待补充信息');
 await expect(card).not.toContainText('草稿已生成');
 await expect(card).not.toContainText('本次草稿来自');
 await expect(card.getByRole('button',{name:'拒绝本次辅助',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'确认创建',exact:true})).toHaveCount(0);
 if(transport==='REAL_PROVIDER')await expect(card).toContainText('尚未生成可确认草稿');
});
