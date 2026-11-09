import {test,expect} from '@playwright/test';

test('administrator label follows verified server role and clears on revocation',async({page})=>{
 let enabled=true;
 await page.route('**/api/workbench/v1/**',async route=>{
  const p=new URL(route.request().url()).pathname;
  const principal={principalId:'human:development-admin',tenantId:'s5-323-demo',securityDomain:'isolated-real-demo'};
  const body=p.endsWith('/session')?{schemaVersion:'workbench-session.v1',principal,session:{expiresAt:'2099-01-01T00:00:00Z',idleExpiresAt:'2099-01-01T00:00:00Z'},csrfToken:'test-csrf'}:
   p.endsWith('/development-administrator')?{result:{subject:principal.principalId,enabled}}:
   {result:{subject:principal.principalId,scope:{tenantId:principal.tenantId,securityDomain:principal.securityDomain},items:[],nextCursor:null,basis:'EXACT_CURRENT_READ_GRANTS',executionAuthority:'NONE'}};
  await route.fulfill({json:body});
 });
 await page.goto('/catalog');
 await expect(page.getByRole('note',{name:'开发超级管理员'})).toBeVisible();
 enabled=false;await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
 await expect(page.getByRole('note',{name:'开发超级管理员'})).toHaveCount(0);
});

test('ordinary account cannot claim administrator through page parameters',async({page})=>{
 let roleReads=0;
 await page.route('**/api/workbench/v1/**',async route=>{
  const p=new URL(route.request().url()).pathname;
  if(p.endsWith('/development-administrator'))roleReads++;
  const principal={principalId:'human:demo323-requester',tenantId:'s5-323-demo',securityDomain:'isolated-real-demo'};
  await route.fulfill({json:p.endsWith('/session')?{schemaVersion:'workbench-session.v1',principal,session:{expiresAt:'2099-01-01T00:00:00Z',idleExpiresAt:'2099-01-01T00:00:00Z'},csrfToken:'test-csrf'}:{result:{subject:principal.principalId,scope:{tenantId:principal.tenantId,securityDomain:principal.securityDomain},items:[],nextCursor:null}}});
 });
 await page.goto('/catalog?role=DEVELOPMENT_ADMINISTRATOR');
 await expect(page.getByRole('heading',{name:'能力资源目录'})).toBeVisible();
 await expect(page.getByRole('note',{name:'开发超级管理员'})).toHaveCount(0);
 expect(roleReads).toBe(0);
});
