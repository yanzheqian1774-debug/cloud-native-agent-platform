import {test, expect} from '@playwright/test';

test('interrupted preparation keeps original request and does not claim success',async({page})=>{
  const keys:string[]=[];
  await page.route('**/api/workbench/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:tester',tenantId:'test',securityDomain:'isolated'},session:{expiresAt:'2099-01-01T00:00:00Z',idleExpiresAt:'2099-01-01T00:00:00Z'},csrfToken:'test-token'}});
    if(path.endsWith('/test-resource-access/status'))return route.fulfill({json:{result:{available:true,policyDigest:'a'.repeat(64)}}});
    if(path.endsWith('/test-resource-access/prepare')){
      keys.push(route.request().postDataJSON().idempotencyKey);
      if(keys.length===1)return route.fulfill({status:503,json:{reasonCode:'UNAVAILABLE'}});
      return route.fulfill({json:{result:{policyDigest:'a'.repeat(64),items:[{state:'APPROVED'}]}}});
    }
    return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
  });
  await page.goto('/help');
  await expect(page.getByText('测试资源准备结果尚未核实。可以核对原请求，或继续使用已有权限。')).toBeVisible();
  await page.getByRole('button',{name:'核对原请求'}).click();
  await expect(page.getByRole('button',{name:'核对原请求'})).toHaveCount(0);
  await expect.poll(()=>keys.length).toBe(2);
  expect(keys[0]).toBe(keys[1]);
});

test('unconfigured policy performs no preparation',async({page})=>{
  let writes=0;
  await page.route('**/api/workbench/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:tester',tenantId:'test',securityDomain:'isolated'},session:{expiresAt:'2099-01-01T00:00:00Z',idleExpiresAt:'2099-01-01T00:00:00Z'},csrfToken:'test-token'}});
    if(route.request().method()!=='GET')writes++;
    return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
  });
  await page.goto('/help');
  await expect(page.getByText('正在准备可用的测试资源…')).toHaveCount(0);
  await expect(page.getByRole('heading',{name:'帮助中心',exact:true})).toBeVisible();
  expect(writes).toBe(0);
});

test('confirmed expiry renews only after user action',async({page})=>{
  const keys:string[]=[];
  await page.route('**/api/workbench/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:tester',tenantId:'test',securityDomain:'isolated'},session:{expiresAt:'2099-01-01T00:00:00Z',idleExpiresAt:'2099-01-01T00:00:00Z'},csrfToken:'test-token'}});
    if(path.endsWith('/test-resource-access/status'))return route.fulfill({json:{result:{available:true,policyDigest:'a'.repeat(64)}}});
    if(path.endsWith('/test-resource-access/prepare')){
      keys.push(route.request().postDataJSON().idempotencyKey);
      return route.fulfill({json:{result:{policyDigest:'a'.repeat(64),items:[{state:keys.length===1?'EXPIRED':'APPROVED'},{state:'REVOKED'}]}}});
    }
    return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
  });
  await page.goto('/help');
  await expect(page.getByRole('button',{name:'重新准备已过期资源'})).toBeVisible();
  expect(keys).toHaveLength(1);
  await page.getByRole('button',{name:'重新准备已过期资源'}).click();
  await expect.poll(()=>keys.length).toBe(2);
  expect(keys[0]).not.toBe(keys[1]);
  await expect(page.getByText('有 1 项测试资源暂不可读取，其他页面可继续使用。')).toBeVisible();
  await expect(page.getByRole('button',{name:'重新准备已过期资源'})).toHaveCount(0);
});

test('identity change before prepare prevents submission under old context',async({page})=>{
  let switched=false,writes=0;
  await page.route('**/api/workbench/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:switched?'human:other':'human:tester',tenantId:'test',securityDomain:'isolated'},session:{expiresAt:'2099-01-01T00:00:00Z',idleExpiresAt:'2099-01-01T00:00:00Z'},csrfToken:'test-token'}});
    if(path.endsWith('/test-resource-access/status')){switched=true;return route.fulfill({json:{result:{available:true,policyDigest:'a'.repeat(64)}}});}
    if(route.request().method()!=='GET')writes++;
    return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
  });
  await page.goto('/help');
  await expect(page.getByText('测试资源准备结果尚未核实。可以核对原请求，或继续使用已有权限。')).toBeVisible();
  expect(writes).toBe(0);
});
