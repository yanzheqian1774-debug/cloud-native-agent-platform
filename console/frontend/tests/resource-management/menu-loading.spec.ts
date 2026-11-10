import {test,expect,type Page} from '@playwright/test';
async function fixture(page:Page){
 const state={principal:'old',authenticated:true,lists:0,hold:false,pending:0,releases:[] as Array<()=>void>,writes:[] as string[]};
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname,method=route.request().method();
  if(method!=='GET')state.writes.push(method+' '+path);
  if(path.endsWith('/session')){
   if(method==='DELETE'){state.authenticated=false;return route.fulfill({status:204})}
   return route.fulfill(state.authenticated?{json:{principal:{principalId:state.principal,tenantId:'tenant',securityDomain:'domain'},csrfToken:'csrf',session:{expiresAt:'2099-01-01'}}}:{status:401,json:{reasonCode:'AUTHENTICATION_REQUIRED'}});
  }
  if(path.endsWith('/conversations/capabilities'))return route.fulfill({json:{result:{enabled:true}}});
  if(path.endsWith('/conversations')){
   state.lists++;const principal=state.principal;
   if(state.hold){state.pending++;await new Promise<void>(resolve=>state.releases.push(resolve))}
   return route.fulfill({json:{result:{items:Array.from({length:30},(_,i)=>({conversation_id:'c'+i,title:principal+'私有会话'+i,created_at:'2026-11-10T01:00:00Z'}))}}}).catch(()=>{});
  }
  if(/\/conversations\/c\d+$/.test(path))return route.fulfill({json:{result:{conversation:{conversation_id:path.split('/').at(-1),title:'会话内容',version:1},messages:[],links:[]}}});
  if(path.endsWith('/problems'))return route.fulfill({json:{result:{problems:[]}}});
  return route.fulfill({json:{result:{items:[],enabled:false}}});
 });return state;
}
const summary=(page:Page)=>page.getByText('☰ 菜单',{exact:true});
const menu=(page:Page)=>page.getByRole('navigation',{name:'全部功能',exact:true});

test('closed menu avoids duplicate list read; keyboard open reports loading; reopen reads fresh',async({page})=>{
 const s=await fixture(page);await page.goto('/work?conversation=c20');
 await expect(page.locator('.px-sidebar').getByRole('link',{name:/old私有会话20/})).toBeVisible();
 await expect(page.locator('.conversation-navigation')).toHaveCount(1);expect(s.lists).toBe(1);
 s.hold=true;await summary(page).focus();await page.keyboard.press('Enter');
 await expect(menu(page).getByText('正在读取会话…',{exact:true})).toBeVisible();await expect.poll(()=>s.pending).toBe(1);
 await summary(page).click();await expect(menu(page)).toHaveCount(0);s.hold=false;s.releases.splice(0).forEach(release=>release());
 await summary(page).click();await expect(menu(page).getByRole('link',{name:/old私有会话20/})).toBeVisible();expect(s.lists).toBe(3);
 await menu(page).getByText('资源管理',{exact:true}).click();await expect(menu(page)).toBeVisible();expect(s.lists).toBe(3);expect(s.writes).toEqual([]);
});

test('menu preserves scroll and selected conversation; route reload and breakpoint retain entries',async({page})=>{
 await fixture(page);await page.goto('/work?conversation=c20');await summary(page).click();
 const list=menu(page).getByLabel('可访问的会话',{exact:true});await expect(list.getByRole('link',{name:/old私有会话20/})).toHaveAttribute('aria-current','page');
 await list.evaluate(n=>{n.scrollTop=180;n.dispatchEvent(new Event('scroll',{bubbles:true}))});await expect.poll(()=>list.evaluate(n=>n.scrollTop)).toBeGreaterThan(100);
 const top=await list.evaluate(n=>n.scrollTop);await summary(page).click();await summary(page).click();
 await expect(list.getByRole('link',{name:/old私有会话20/})).toHaveAttribute('aria-current','page');await expect.poll(()=>list.evaluate(n=>n.scrollTop)).toBeCloseTo(top,0);
 await page.setViewportSize({width:390,height:844});await expect(menu(page).getByRole('link',{name:'数字员工',exact:true})).toBeVisible();
 await menu(page).getByRole('link',{name:'帮助中心',exact:true}).click();await expect(page).toHaveURL(/\/help$/);await expect(menu(page)).toHaveCount(0);
 await summary(page).click();await expect(menu(page).getByRole('link',{name:'数字员工',exact:true})).toBeVisible();await page.reload();await expect(menu(page)).toHaveCount(0);
 await page.setViewportSize({width:1424,height:820});await summary(page).click();await expect(menu(page).getByRole('link',{name:'数字员工',exact:true})).toBeVisible();
});

for(const mode of ['logout','expiry','identity'])test('open menu removes prior identity and rejects delayed data: '+mode,async({page})=>{
 const s=await fixture(page);await page.goto('/work?conversation=c20');await expect(page.locator('.px-sidebar').getByRole('link',{name:/old私有会话20/})).toBeVisible();
 s.hold=true;await summary(page).click();await expect.poll(()=>s.pending).toBe(1);
 if(mode==='logout'){await page.locator('.px-identity-menu > summary').click();await page.getByRole('button',{name:'退出登录',exact:true}).click();}
 else if(mode==='expiry'){s.authenticated=false;await page.evaluate(()=>window.dispatchEvent(new Event('workbench-session-expired')));}
 else{s.principal='new';s.hold=false;await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect(page.locator('.px-sidebar').getByRole('link',{name:/new私有会话20/})).toBeVisible();}
 s.hold=false;s.releases.splice(0).forEach(release=>release());await expect(menu(page)).toHaveCount(0);await expect(page.getByText(/old私有会话/)).toHaveCount(0);
 await summary(page).click();
 if(mode==='identity')await expect(menu(page).getByRole('link',{name:/new私有会话20/})).toBeVisible();
 else await expect(menu(page).getByText('登录后读取当前账号的会话记录。',{exact:true})).toBeVisible();
 await expect(page.getByText(/old私有会话/)).toHaveCount(0);expect(s.writes).toEqual(mode==='logout'?['DELETE /api/workbench/v1/session']:[]);
});
