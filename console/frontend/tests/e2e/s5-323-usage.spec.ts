import {expect,test} from '@playwright/test';

for(const state of ['SUCCEEDED','CANCELLATION_REQUESTED']){
 test(`323 controlled UI: ${state} does not conceal fee or cancellation uncertainty`,async({page})=>{
  let calls=0;
  await page.route('**/api/workbench/v1/**',async route=>{
   const path=new URL(route.request().url()).pathname;
   if(path.endsWith('/session')){await route.fulfill({json:{principal:{principalId:'controlled-323',tenantId:'synthetic-323',securityDomain:'test'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'controlled'}});return;}
   if(path.endsWith('/draft-assistance/invocations')){calls++;await route.fulfill({json:{result:{contextId:'context:323',turnId:'turn:1',turnVersion:1,invocationId:'inv:323',state,resultKind:state==='SUCCEEDED'?'DRAFT_READY':null,transport:'SYNTHETIC',draft:state==='SUCCEEDED'?{title:'合成采购',description:'只规划，不执行'}:null,contentDisposition:'CONTENT_NOT_RETAINED',settlementStatus:'SETTLEMENT_WRITE_PENDING',reasonCode:'PROVIDER_BUDGET_SETTLEMENT_PENDING',localWorkerState:'NOT_OBSERVED'}}});return;}
   await route.fulfill({json:{result:{problems:[]}}});
  });
  await page.goto('/work');await page.locator('#problem-composer').fill('合成采购问题，仅受控UI验证');await page.locator('#problem-composer').press('Enter');
  await expect(page.getByText('费用核对：',{exact:false})).toBeVisible();
  await expect(page.getByText('费用核对：',{exact:false})).toContainText('结算写入待恢复');
  if(state==='CANCELLATION_REQUESTED'){
   await expect(page.getByText('取消请求不等于底层工作已停止。',{exact:false})).toBeVisible();
   await expect(page.getByText('取消请求不等于底层工作已停止。',{exact:false})).toContainText('远端停止和停止计费均未证实');
  }
  expect(calls).toBe(1);
 });
}
