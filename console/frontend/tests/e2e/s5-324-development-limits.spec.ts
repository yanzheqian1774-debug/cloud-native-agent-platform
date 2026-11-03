import {expect,test} from '@playwright/test';

test('development task shows100 andUSD50 as cumulative limits with GET-only reload',async({page})=>{
 const ref={resource_id:'fixture-root',revision_id:'fixture-revision',digest:'a'.repeat(64)};let writes=0;
 const value={request:{request_id:'fixture-development-task',subject_id:'human:business-fixture',tenant_id:'fixture',security_domain:'isolated',digest:'b'.repeat(64),record:{purpose:'SAME_CASE_DELIVERY',root:ref,source_snapshot:ref,determination_date:'2026-11-03',permissions:[],derived_permissions:[],configuration:{revision_id:'config55',configuration_digest:'c'.repeat(64),read_seconds:55,total_seconds:60,cleanup_seconds:2,cumulative_call_cap:21},recovery_invocation_id:'original21',development_revision:{revision_id:'dev100-usd50',cumulative_call_cap:100,total_cost_cap_microusd:50000000,recovery_observation_ids:['observation20','observation21']}}},status:'NOT_ADMITTED',reasonCode:'TASK_AUTHORIZATION_REQUIRED',decision:null};
 await page.route('**/api/workbench/v1/**',async route=>{
  if(route.request().method()!=='GET')writes++;
  if(new URL(route.request().url()).pathname.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:reviewer-fixture',tenantId:'fixture',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  return route.fulfill({json:value});
 });
 await page.goto('/authorization-admin?task=fixture-development-task');const panel=page.getByRole('region',{name:'有界任务审核'});
 await expect(panel).toContainText('本对象研发修订：累计上限100次，总额USD50');await expect(panel).toContainText('原规则保留');await page.reload();await expect(panel).toContainText('总额USD50');expect(writes).toBe(0);
});
