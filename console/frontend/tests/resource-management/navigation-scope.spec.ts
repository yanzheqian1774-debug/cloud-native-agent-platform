import {test,expect} from '@playwright/test';
test('business process is not falsely linked or highlighted as execution workflow',async({page})=>{
 const writes:string[]=[];
 await page.route('**/api/**',route=>{
  const p=new URL(route.request().url()).pathname;
  if(route.request().method()==='POST')writes.push(p);
  if(p==='/api/internal/v0.2.2/workflow-definitions')return route.fulfill({json:[]});
  if(p.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:test',tenantId:'tenant',securityDomain:'domain'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'csrf'}});
  return route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:[],entries:[],rejectedResources:0}}});
 });
 await page.goto('/workflow-definitions');
 const nav=page.getByRole('navigation',{name:'P1 核心产品导航',exact:true});
 await expect(nav.getByRole('link',{name:'工作流',exact:true})).toHaveAttribute('aria-current','page');
 await expect(nav.getByRole('link',{name:'业务流程',exact:true})).toHaveCount(0);
 const unavailable=nav.locator('.px-navigation-unavailable');await expect(unavailable).toContainText('业务流程');await expect(unavailable).toContainText('待接入');await expect(unavailable).toHaveAttribute('aria-disabled','true');
 await expect(nav.locator('a[aria-current="page"]')).toHaveCount(1);expect(writes).toEqual([]);
});
