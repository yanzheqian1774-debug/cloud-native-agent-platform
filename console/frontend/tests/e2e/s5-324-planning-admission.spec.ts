import {expect,test} from '@playwright/test';

test('324 precise planning preparation survives refresh and explicit continuation only',async({page},info)=>{
 let ready=false,calls=0;const writes:string[]=[];
 const value=()=>({invocation:{target:{invocation_id:'staged:324'},request:{answers:['只使用合成供应商样本，不推断企业事实。']},submitted_at:'2026-09-22T00:00:00Z'},result:{technical_status:'AUTHORIZATION_PENDING',kind:null},admission:{context_id:'planning:324',ready,maximum_new_calls:1,cumulative_call_cap:20}});
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(route.request().method()==='POST')writes.push(path);
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:demo323-requester',tenantId:'s5-323-demo',securityDomain:'isolated-real-demo'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(path.includes('/planning-input/'))return route.fulfill({json:{result:{target:{},title:'合成供应商问题',description:'核查交付与质量数据范围；缺失证据单列，不能虚构企业结论。'.repeat(6)}}});
  if(path.endsWith('/continue')){calls++;return route.fulfill({json:{result:{...value(),admission:undefined,result:{technical_status:'SUCCEEDED',kind:'NEEDS_CLARIFICATION',questions:['样本的统计日期是什么？']}}}})}
  if(path.includes('/planning-v2/requests/')||path.endsWith('/planning-v2/invocations'))return route.fulfill({json:{result:value()}});
  return route.fulfill({json:{result:{}}});
 });
 await page.setViewportSize({width:1536,height:1024});
 await page.goto('/work/plan?problem=synthetic:324&request=existing:324');
 await expect(page.getByRole('heading',{name:'等待独立规划准入',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'继续本次规划调用',exact:true})).toBeDisabled();
 const user=await page.locator('.px-user-message>div:last-child').boundingBox();
 const stream=await page.locator('.px-message-stream').boundingBox();
 expect(user!.x+user!.width/2).toBeGreaterThan(stream!.x+stream!.width/2);
 await page.screenshot({path:info.outputPath('planning-pending-1536.png')});
 await page.reload();expect(writes).toEqual([]);
 ready=true;await page.getByRole('button',{name:'查看授权状态',exact:true}).click();
 await expect(page.getByRole('heading',{name:'等待继续',exact:true})).toBeVisible();
 expect(writes).toEqual([]);
 await page.setViewportSize({width:1229,height:819});
 const proceed=page.getByRole('button',{name:'继续本次规划调用',exact:true});
 await proceed.scrollIntoViewIfNeeded();await expect(proceed).toBeInViewport();
 await page.screenshot({path:info.outputPath('planning-ready-125-equivalent.png')});
 await proceed.click();await expect(page.getByText('样本的统计日期是什么？',{exact:true})).toBeVisible();
 expect(calls).toBe(1);expect(writes).toEqual(['/api/workbench/v1/planning-v2/requests/existing%3A324/continue']);
});

test('324 planning approval shows exact scope without business-list reads or signing',async({page},info)=>{
 const writes:string[]=[];
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(route.request().method()!=='GET')writes.push(path);
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:demo323-approver',tenantId:'s5-323-demo',securityDomain:'isolated-real-demo'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(path.includes('/context-admissions/'))return route.fulfill({json:{status:'NOT_ADMITTED',request:{context_id:'planning:324',subject_id:'human:demo323-requester',tenant_id:'s5-323-demo',security_domain:'isolated-real-demo',account_revision:1,digest:'a'.repeat(64),record:{phase:'planning',cumulative_call_cap:20,target:{problem:'synthetic:324'},configuration:{profile_revision_id:'original:planning',profile_digest:'b'.repeat(64),configuration_digest:'c'.repeat(64),ledger_id:'original:planning',calls:8,cost_microusd:10000000,input_tokens:65536,output_tokens:8192}}},budgetSummary:{calls:19,charged_or_reserved_microusd:4816896},decision:null,reasonCode:'CONTEXT_ADMISSION_REQUIRED'}});
  expect(path).not.toContain('/problems');
  return route.fulfill({json:{result:{}}});
 });
 await page.setViewportSize({width:1536,height:1024});
 await page.goto('/authorization-admin?context=planning%3A324');
 await page.getByRole('button',{name:'核对调用对象',exact:true}).click();
 await expect(page.getByText('同案规划 · 有界一次',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'本人独立签发此 context',exact:true})).toBeEnabled();
 await page.screenshot({path:info.outputPath('approval-planning-1536.png')});
 await page.setViewportSize({width:1229,height:819});
 await page.getByRole('button',{name:'本人独立签发此 context',exact:true}).scrollIntoViewIfNeeded();
 await page.screenshot({path:info.outputPath('approval-planning-125-equivalent.png')});
 expect(writes).toEqual([]);
});
