import {expect,test} from '@playwright/test';

for(const scenario of [
 {status:503,reason:'DRAFT_ASSISTANCE_NOT_CONFIGURED',title:'AI 草稿辅助当前不可用',detail:'本次没有进入模型派发'},
 {status:403,reason:'AUTHORIZATION_NOT_FOUND',title:'AI 草稿辅助权限尚未就绪',detail:'精确准入'},
 {status:503,reason:'TRANSPORT_AMBIGUOUS',title:'AI 调用结果需要核验',detail:'不能作为普通失败再次发送'},
 {status:422,reason:'OUTPUT_SCHEMA_INVALID',title:'AI 生成内容未通过契约校验',detail:'不能作为成功草稿'},
])test(`324 new conversation displays actionable ${scenario.reason} without replay`,async({page},info)=>{
 let calls=0;
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:"workbench-session.v1",principal:{principalId:'human:fixture',tenantId:'fixture-324',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(path.endsWith('/draft-assistance/invocations')){calls++;return route.fulfill({status:scenario.status,json:{reasonCode:scenario.reason,requestId:'workbench-request-fixture-324'}})}
  return route.fulfill({json:{result:{problems:[]}}});
 });
 await page.setViewportSize({width:1536,height:1024});
 await page.goto('/work');
 const input=page.locator('#problem-composer');
 const content='合成供应商管理问题：缺少交付与质量数据，请先澄清分析范围，不虚构企业结论。'.repeat(5);
 await input.fill(content);await page.getByRole('button',{name:'发送',exact:true}).click();
 const error=page.getByRole('alert');await expect(error).toContainText(scenario.title);await expect(error).toContainText(scenario.detail);
 await expect(error.getByText('workbench-request-fixture-324',{exact:true}).first()).toBeVisible();
 await expect(input).toHaveValue(content);expect(calls).toBe(1);
 if(scenario.reason==='TRANSPORT_AMBIGUOUS')await expect(page.getByRole('button',{name:'发送',exact:true})).toBeDisabled();
 for(const scale of [1,1.25]){
  await page.setViewportSize({width:Math.floor(1536/scale),height:Math.floor(1024/scale)});
  await expect(page.getByRole('button',{name:'发送',exact:true})).toBeInViewport();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  if(scenario.reason==='DRAFT_ASSISTANCE_NOT_CONFIGURED')await page.screenshot({path:info.outputPath(`new-conversation-error-${scale}.png`)});
 }
 await page.reload();await expect(input).toHaveValue('');expect(calls).toBe(1);
});

test('324 context signature requires explicit independent operation and refresh never replays',async({page},info)=>{
 let writes=0;let approved=false;
 const context='draft-context:fixture-324';
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:"workbench-session.v1",principal:{principalId:'human:independent-fixture',tenantId:'fixture-324',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(path.includes('/context-admissions/')){
   if(route.request().method()==='POST'){writes++;expect(route.request().headers()['x-csrf-token']).toBe('fixture');expect(route.request().postDataJSON().request_digest).toBe('a'.repeat(64));approved=true;return route.fulfill({json:{admission_id:'fixture-admission'}})}
   return route.fulfill({json:{request:{context_id:context,subject_id:'human:requester-fixture',tenant_id:'fixture-324',security_domain:'isolated',account_revision:1,digest:'a'.repeat(64),record:{configuration:{profile_revision_id:'fixture-model:1',profile_digest:'b'.repeat(64),configuration_digest:'c'.repeat(64),ledger_id:'original-fixture',calls:12,cost_microusd:10000000,input_tokens:65536,output_tokens:8192}}},decision:approved?{admission_id:'fixture-admission',issuer_id:'human:independent-fixture',expires_at:'2099-01-01'}:null,status:approved?'ACTIVE':'NOT_ADMITTED',reasonCode:null}});
  }
  return route.fulfill({json:{result:{}}});
 });
 await page.setViewportSize({width:1536,height:1024});
 await page.goto(`/authorization-admin?context=${encodeURIComponent(context)}`);
 await page.getByRole('button',{name:'核对调用对象',exact:true}).click();
 const panel=page.getByRole('region',{name:'合成问题独立调用准入'});
 await expect(panel).toContainText('不是剩余额度');expect(writes).toBe(0);
 await panel.getByRole('button',{name:'本人独立签发此 context'}).click();
 await expect(panel).toContainText('当前准入有效');expect(writes).toBe(1);
 await page.screenshot({path:info.outputPath('context-admission-fixture.png')});
 await page.reload();expect(writes).toBe(1);
});
