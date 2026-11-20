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

test('published selection is encoded in exact key and unknown never retargets after refresh',async({page},info)=>{
  let selection='b'.repeat(64),fail=true;
  const writes:{idempotencyKey:string;expectedSelectionDigest:string}[]=[];
  await page.route('**/api/workbench/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:tester',tenantId:'test',securityDomain:'isolated'},session:{},csrfToken:'test-token'}});
    if(path.endsWith('/test-resource-access/status'))return route.fulfill({json:{result:{available:true,policyDigest:'a'.repeat(64),selectionDigest:selection}}});
    if(path.endsWith('/test-resource-access/prepare')){
      writes.push(route.request().postDataJSON());
      if(fail)return route.abort('failed');
      return route.fulfill({json:{result:{policyDigest:'a'.repeat(64),selectionDigest:selection,items:[{state:'APPROVED'}]}}});
    }
    return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
  });
  await page.goto('/help');
  await expect(page.getByRole('button',{name:'核对原请求'})).toBeVisible();
  expect(writes).toHaveLength(1);
  const first=writes[0];
  expect(first.idempotencyKey).toMatch(new RegExp('^published:'+first.expectedSelectionDigest+':'));
  await page.getByRole('button',{name:'核对原请求'}).click();
  await expect.poll(()=>writes.length).toBe(2);
  expect(writes[1]).toEqual(first);
  selection='c'.repeat(64);fail=false;
  await page.reload();
  await expect(page.getByText(/资料版本已更新。上次读取结果尚未核实/)).toBeVisible();
  expect(writes).toHaveLength(2);
  await page.setViewportSize({width:1440,height:1000});
  await page.screenshot({path:info.outputPath('updated-material-unknown-1440.png'),fullPage:true});
  await page.getByRole('button',{name:'读取新版资料'}).click();
  await expect.poll(()=>writes.length).toBe(3);
  expect(writes[2].expectedSelectionDigest).toBe(selection);
  expect(writes[2].idempotencyKey).not.toBe(first.idempotencyKey);
  await expect(page.getByRole('button',{name:'读取新版资料'})).toHaveCount(0);
  const saved=await page.evaluate(()=>Object.entries(sessionStorage));
  expect(saved.some(([key,value])=>key.endsWith(':unresolved')&&value.includes(first.idempotencyKey))).toBe(true);
});

test('known completed publication can prepare new selection without changing prior key',async({page})=>{
  let selection='b'.repeat(64);
  const writes:{idempotencyKey:string;expectedSelectionDigest:string}[]=[];
  await page.route('**/api/workbench/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:tester',tenantId:'test',securityDomain:'isolated'},session:{},csrfToken:'test-token'}});
    if(path.endsWith('/test-resource-access/status'))return route.fulfill({json:{result:{available:true,policyDigest:'a'.repeat(64),selectionDigest:selection}}});
    if(path.endsWith('/test-resource-access/prepare')){writes.push(route.request().postDataJSON());return route.fulfill({json:{result:{policyDigest:'a'.repeat(64),selectionDigest:selection,items:[{state:'APPROVED'}]}}})}
    return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
  });
  await page.goto('/help');await expect(page.getByRole('heading',{name:'帮助中心',exact:true})).toBeVisible();
  const first=writes[0];await page.reload();await expect.poll(()=>writes.length).toBe(2);expect(writes[1]).toEqual(first);
  selection='c'.repeat(64);await page.reload();await expect.poll(()=>writes.length).toBe(3);
  expect(writes[2].idempotencyKey).not.toBe(first.idempotencyKey);expect(writes[2].expectedSelectionDigest).toBe(selection);
});

for(const outcome of ['success','second-expired','lost','revoked','denied','unknown','selection-changed'])test(`automatic exact expired READ renewal: ${outcome}`,async({page})=>{
 const keys:string[]=[],business:string[]=[];let selection='b'.repeat(64),statusReads=0;
 await page.route('**/api/**',async route=>{
  const p=new URL(route.request().url()).pathname;
  if(p.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:tester',tenantId:'test',securityDomain:'isolated'},session:{},csrfToken:'test-token'}});
  if(p.endsWith('/test-resource-access/status')){statusReads++;if(outcome==='selection-changed'&&statusReads>1)selection='c'.repeat(64);return route.fulfill({json:{result:{available:true,policyDigest:'a'.repeat(64),selectionDigest:selection}}})}
  if(p.endsWith('/test-resource-access/prepare')){
   keys.push(route.request().postDataJSON().idempotencyKey);
   if(outcome==='lost'&&keys.length===2)return route.abort('failed');
   let state=keys.length===1?'EXPIRED':'APPROVED';
   if(outcome==='second-expired')state='EXPIRED';
   if(outcome==='revoked')state='REVOKED';if(outcome==='denied')state='DENIED';if(outcome==='unknown')state='UNKNOWN';
   return route.fulfill({json:{result:{policyDigest:'a'.repeat(64),selectionDigest:selection,items:[{state}]}}});
  }
  if(route.request().method()!=='GET')business.push(p);
  return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
 });
 await page.goto('/help');
 if(['success','second-expired','lost'].includes(outcome)){
  await expect.poll(()=>keys.length).toBe(2);expect(keys[0]).not.toBe(keys[1]);
  expect(keys[1]).toMatch(/^published:[a-f0-9]{64}:[a-f0-9]{64}$/);
  if(outcome==='lost')await expect(page.getByRole('button',{name:'核对原请求'})).toBeVisible();
  else if(outcome==='second-expired')await expect(page.getByRole('button',{name:'重新准备已过期资源'})).toBeVisible();
  else await expect(page.getByRole('heading',{name:'帮助中心',exact:true})).toBeVisible();
  const renewed=keys[1];await page.reload();await expect.poll(()=>keys.length).toBe(3);expect(keys[2]).toBe(renewed);
  await expect(page.getByRole('heading',{name:'帮助中心',exact:true})).toBeVisible();expect(new Set(keys).size).toBe(2);
 }else{
  if(outcome==='selection-changed')await expect(page.getByRole('button',{name:'核对原请求'})).toBeVisible();
  else await expect(page.getByText(/有 1 项测试资源暂不可读取/)).toBeVisible();
  expect(keys).toHaveLength(1);
 }
 expect(business).toEqual([]);
});

test('unknown original policy does not become a new automatic request after policy changes',async({page})=>{
 let policy='a'.repeat(64);const keys:string[]=[];
 await page.route('**/api/**',route=>{
  const p=new URL(route.request().url()).pathname;
  if(p.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:tester',tenantId:'test',securityDomain:'isolated'},session:{},csrfToken:'test-token'}});
  if(p.endsWith('/test-resource-access/status'))return route.fulfill({json:{result:{available:true,policyDigest:policy}}});
  if(p.endsWith('/test-resource-access/prepare')){keys.push(route.request().postDataJSON().idempotencyKey);return route.abort('failed')}
  return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
 });
 await page.goto('/help');await expect(page.getByRole('button',{name:'核对原请求'})).toBeVisible();expect(keys).toHaveLength(1);
 policy='b'.repeat(64);await page.reload();await expect(page.getByRole('button',{name:'核对原请求'})).toBeVisible();expect(keys).toHaveLength(1);
});

for(const unresolved of [false,true])test(`publication refresh observes new selection without retargeting unresolved=${unresolved}`,async({page})=>{
 let selection='b'.repeat(64);const writes:{idempotencyKey:string;expectedSelectionDigest:string}[]=[];
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:tester',tenantId:'test',securityDomain:'isolated'},session:{expiresAt:'2099-01-01T00:00:00Z',idleExpiresAt:'2099-01-01T00:00:00Z'},csrfToken:'test-token'}});
  if(path.endsWith('/test-resource-access/status'))return route.fulfill({json:{result:{available:true,policyDigest:'a'.repeat(64),selectionDigest:selection}}});
  if(path.endsWith('/test-resource-access/prepare')){const body=route.request().postDataJSON();writes.push(body);if(unresolved)return route.abort('failed');return route.fulfill({json:{result:{policyDigest:'a'.repeat(64),selectionDigest:body.expectedSelectionDigest,items:[{state:'APPROVED'}]}}});}
  return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
 });
 await page.goto('/help');await expect.poll(()=>writes.length).toBe(1);
 if(unresolved)await expect(page.getByRole('button',{name:'核对原请求'})).toBeVisible();
 else await expect(page.getByRole('heading',{name:'帮助中心',exact:true})).toBeVisible();
 selection='c'.repeat(64);await page.evaluate(()=>window.dispatchEvent(new Event('published-test-resources-changed')));
 if(unresolved){await expect(page.getByRole('button',{name:'读取新版资料'})).toBeVisible();expect(writes).toHaveLength(1);}
 else{await expect.poll(()=>writes.length).toBe(2);expect(writes[1].idempotencyKey).toContain('published:'+selection+':');expect(writes[1].idempotencyKey).not.toBe(writes[0].idempotencyKey);}
 await page.reload();await expect(page.getByRole('heading',{name:'帮助中心',exact:true})).toBeVisible();
 if(unresolved){await expect(page.getByRole('button',{name:'读取新版资料'})).toBeVisible();expect(writes).toHaveLength(1);}
 else{await expect.poll(()=>writes.length).toBe(3);expect(writes[2].idempotencyKey).toBe(writes[1].idempotencyKey);}
});
