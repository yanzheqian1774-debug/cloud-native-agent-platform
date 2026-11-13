import {test,expect,type Page} from '@playwright/test';

async function fixture(page:Page){
 const state={status:200,principal:'human:old',writes:[] as string[]};
 await page.route('**/api/**',route=>{
  const path=new URL(route.request().url()).pathname;
  if(route.request().method()!=='GET')state.writes.push(route.request().method()+' '+path);
  if(path.endsWith('/session'))return route.fulfill(state.status===200?{json:{principal:{principalId:state.principal,tenantId:'tenant',securityDomain:'domain'},csrfToken:'csrf',session:{expiresAt:'2099-01-01T00:00:00Z'}}}:{status:state.status,json:{reasonCode:state.status===401?'AUTHENTICATION_REQUIRED':'UNAVAILABLE'}});
  if(path.endsWith('/test-resource-access/status'))return route.fulfill({json:{result:{available:false}}});
  return route.fulfill({json:{result:{items:[],enabled:false}}});
 });
 return state;
}

test('session 401 remains expired and cannot be resumed by temporary-failure retry',async({page})=>{
 const state=await fixture(page);state.status=401;
 await page.addInitScript(()=>sessionStorage.setItem('324.command.original','retained-unknown'));
 await page.goto('/help');
 await expect(page.getByRole('heading',{name:'当前登录已失效',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'重新核对登录状态',exact:true})).toHaveCount(0);
 state.status=200;await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
 await expect(page.getByRole('heading',{name:'当前登录已失效',exact:true})).toBeVisible();
 expect(await page.evaluate(()=>sessionStorage.getItem('324.command.original'))).toBe('retained-unknown');
 expect(state.writes).toEqual([]);
});

test('temporary session failure removes old identity and explicit GET recovers new identity',async({page})=>{
 const state=await fixture(page);await page.goto('/help');
 await expect(page.getByLabel('当前可信身份 human:old',{exact:true})).toBeVisible();
 state.status=503;await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
 await expect(page.getByRole('heading',{name:'暂时无法核对登录状态',exact:true})).toBeVisible();
 await expect(page.getByLabel('当前可信身份 human:old',{exact:true})).toHaveCount(0);
 await expect(page.getByText('正在核对登录状态，请稍候或使用右上角登录入口。',{exact:true})).toHaveCount(0);
 state.principal='human:new';state.status=200;
 await page.getByRole('button',{name:'重新核对登录状态',exact:true}).click();
 await expect(page.getByLabel('当前可信身份 human:new',{exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'暂时无法核对登录状态',exact:true})).toHaveCount(0);
 await expect(page.getByLabel('当前可信身份 human:old',{exact:true})).toHaveCount(0);
 expect(state.writes).toEqual([]);
});
