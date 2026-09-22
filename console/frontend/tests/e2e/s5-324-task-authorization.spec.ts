import {expect,test} from '@playwright/test';

test('task scope decision is explicit; refresh never re-signs and long details remain reachable',async({page})=>{
 const ref={resource_id:'fixture-root',revision_id:'fixture-revision',digest:'a'.repeat(64)};
 const value={request:{request_id:'fixture-task',subject_id:'human:business-fixture',tenant_id:'fixture',security_domain:'isolated',digest:'b'.repeat(64),record:{purpose:'SAME_CASE_DELIVERY',root:ref,source_snapshot:ref,determination_date:'2026-09-22',permissions:[{owner:'PLAN',action:'READ',exact_resource:'plan:v2:fixture'}],derived_permissions:[],configuration:null,recovery_invocation_id:null}},status:'NOT_ADMITTED',reasonCode:'TASK_AUTHORIZATION_REQUIRED',decision:null as null|{decision_id:string;issuer_id:string;expires_at:string}};
 let writes=0;
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:reviewer-fixture',tenantId:'fixture',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(route.request().method()==='POST'){
   writes++;expect(path).toContain('/fixture-task/approve');const body=route.request().postDataJSON();expect(body.request_digest).toBe(value.request.digest);
   value.status='ACTIVE';value.decision={decision_id:'fixture-decision',issuer_id:'human:reviewer-fixture',expires_at:'2099-01-01T00:00:00Z'};
  }
  return route.fulfill({json:value});
 });
 await page.setViewportSize({width:1536,height:1024});await page.goto('/authorization-admin?task=fixture-task');
 const panel=page.getByRole('region',{name:'有界任务审核'});await expect(panel.getByText('原供应商交付及时性案例')).toBeVisible();
 const sign=panel.getByRole('button',{name:'本人独立签发任务范围'});await expect(sign).toBeDisabled();expect(writes).toBe(0);
 await panel.getByRole('checkbox').check();await sign.click();await expect(panel.getByText('当前任务授权有效')).toBeVisible();expect(writes).toBe(1);
 await page.reload();await expect(panel.getByText('当前任务授权有效')).toBeVisible();expect(writes).toBe(1);
 for(const width of [1536,1228]){await page.setViewportSize({width,height:819});await panel.getByText('完整精确修订与摘要').click();await panel.locator('pre').scrollIntoViewIfNeeded();await expect(panel.locator('pre')).toBeInViewport();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await panel.getByText('完整精确修订与摘要').click();}
 expect(writes).toBe(1);
});
