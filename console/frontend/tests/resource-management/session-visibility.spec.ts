import {test,expect} from '@playwright/test';

for(const mode of ['logout-late-list','expired-late-list','expired-late-session'])test(`${mode} removes previous identity metadata and rejects late reads`,async({page})=>{
 let hold=false,authenticated=true;const releases:Array<()=>void>=[];const writes:string[]=[];
 await page.route('**/api/**',async route=>{
  const pathname=new URL(route.request().url()).pathname,method=route.request().method();
  if(method!=='GET')writes.push(method+' '+pathname);
  if(pathname.endsWith('/session')){
   if(method==='DELETE'){authenticated=false;return route.fulfill({status:204})}
   const previouslyAuthenticated=authenticated;
   if(hold&&mode==='expired-late-session')await new Promise<void>(r=>releases.push(r));
   return route.fulfill(previouslyAuthenticated?{json:{principal:{principalId:'human:one',tenantId:'tenant',securityDomain:'domain'},csrfToken:'csrf',session:{expiresAt:'2099-01-01T00:00:00Z'}}}:{status:401,json:{reasonCode:'AUTHENTICATION_REQUIRED'}}).catch(()=>{});
  }
  if(pathname.endsWith('/conversations/capabilities'))return route.fulfill({json:{result:{enabled:true}}});
  if(pathname.endsWith('/conversations')){
   if(hold&&mode!=='expired-late-session')await new Promise<void>(r=>releases.push(r));
   return route.fulfill({json:{result:{items:[{conversation_id:'old',title:'上一身份的保密会话标题',created_at:'2026-11-09T08:00:00Z'}]}}}).catch(()=>{});
  }
  if(pathname.endsWith('/problems'))return route.fulfill({json:{result:{problems:[]}}});
  return route.fulfill({json:{result:{items:[],enabled:false}}});
 });
 await page.goto('/work');await expect(page.locator('.px-sidebar').getByRole('link',{name:/上一身份的保密会话标题/})).toBeVisible();
 await page.evaluate(()=>{sessionStorage.setItem('work-view.v1:old:answer','旧答案');sessionStorage.setItem('conversation-view.v1:old','旧标题');sessionStorage.setItem('324.command.original','retain-unknown-receipt');});
 hold=true;await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect.poll(()=>releases.length).toBeGreaterThan(0);
 if(mode.startsWith('logout')){await page.locator('.px-identity-menu > summary').click();await page.getByRole('button',{name:'退出登录',exact:true}).click();await expect(page.getByRole('heading',{name:'已退出登录',exact:true})).toBeVisible();}
 else{authenticated=false;await page.evaluate(()=>window.dispatchEvent(new Event('workbench-session-expired')));await expect(page.getByRole('heading',{name:'当前登录已失效',exact:true})).toBeVisible();}
 await expect(page.getByText('上一身份的保密会话标题',{exact:true})).toHaveCount(0);await expect(page.getByText('按当前权限可见 · 已保存会话',{exact:true})).toHaveCount(0);
 hold=false;for(const release of releases)release();await page.waitForTimeout(150);
 await expect(page.getByText('上一身份的保密会话标题',{exact:true})).toHaveCount(0);await expect(page.locator('.px-header-identity')).toHaveCount(0);
 expect(await page.evaluate(()=>sessionStorage.getItem('work-view.v1:old:answer'))).toBeNull();expect(await page.evaluate(()=>sessionStorage.getItem('conversation-view.v1:old'))).toBeNull();expect(await page.evaluate(()=>sessionStorage.getItem('324.command.original'))).toBe('retain-unknown-receipt');
 await page.locator('.px-sidebar').getByRole('link',{name:'数字员工',exact:true}).click();await expect(page.getByRole('heading',{name:mode.startsWith('logout')?'已退出登录':'当前登录已失效',exact:true})).toBeVisible();
 expect(writes).toEqual(mode.startsWith('logout')?['DELETE /api/workbench/v1/session']:[]);
});
