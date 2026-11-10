import {test,expect} from '@playwright/test';
const teamEnabled=process.env.VITE_TEAM_DEFINITIONS_ENABLED==='true';
const peopleNav=teamEnabled?'数字人团队':'数字员工';
const peoplePath=teamEnabled?/teams/:/employees/;

test('shared frame persists across navigation back and reload without business writes',async({page})=>{
 const writes:string[]=[];
 await page.route('**/api/**',route=>{const request=route.request(),p=new URL(request.url()).pathname;if(request.method()!=='GET')writes.push(p);if(p.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:frame',tenantId:'tenant',securityDomain:'domain'},session:{expiresAt:'2099-01-01T00:00:00Z',idleExpiresAt:'2099-01-01T00:00:00Z'},csrfToken:'fixture'}});if(p.endsWith('/resource-directory'))return route.fulfill({json:{result:{subject:'human:frame',scope:{tenantId:'tenant',securityDomain:'domain'},items:[],nextCursor:null}}});return route.fulfill({json:{result:{items:[],problems:[],enabled:false}}});});
 const geometry=async()=>{await expect(page.locator('.f3-workspace-frame')).toHaveCount(1);expect(await page.locator('.px-sidebar').evaluate(n=>({width:n.getBoundingClientRect().width,top:n.getBoundingClientRect().top}))).toEqual({width:216,top:0});expect(await page.locator('.px-topbar').evaluate(n=>({x:n.getBoundingClientRect().x,height:n.getBoundingClientRect().height}))).toEqual({x:216,height:64});await expect(page.locator('.skill-frame-navigation').getByRole('link',{name:'首页 · 我的工作台',exact:true}).locator('svg path').first()).toHaveAttribute('d','M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8');};
 await page.goto('/skills');await geometry();
 await page.locator('.skill-frame-navigation').getByRole('link',{name:peopleNav,exact:true}).click();await expect(page).toHaveURL(peoplePath);await geometry();if(teamEnabled){await page.getByRole('link',{name:'查看数字员工',exact:true}).click();await expect(page).toHaveURL(/employees/);await geometry();}
 await page.locator('.skill-frame-navigation').getByRole('link',{name:'我的任务',exact:true}).click();await expect(page).toHaveURL(/tasks/);await geometry();
 await page.locator('.skill-frame-actions').getByRole('link',{name:'＋ 发起会话',exact:true}).click();await expect(page).toHaveURL(/work\?draft=/);await geometry();
 await page.goBack();await expect(page).toHaveURL(/tasks/);await geometry();await page.reload();await geometry();expect(writes).toEqual([]);
});

test('mobile shared navigation closes on route change and chrome stays inside viewport',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.route('**/api/**',r=>r.fulfill({status:401,json:{reasonCode:'AUTHENTICATION_REQUIRED'}}));await page.goto('/skills');await page.getByText('☰ 菜单',{exact:true}).click();await page.getByRole('navigation',{name:'全部功能',exact:true}).getByRole('link',{name:peopleNav,exact:true}).click();await expect(page.locator('.skill-frame-menu>details')).not.toHaveAttribute('open','');expect(await page.locator('.px-topbar').evaluate(n=>n.getBoundingClientRect().right)).toBeLessThanOrEqual(390);expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test('verified identity does not flash back to login while a route rechecks the same session',async({page})=>{
 let hold=false;const releases:Array<()=>void>=[];
 await page.route('**/api/**',async route=>{const p=new URL(route.request().url()).pathname;if(p.endsWith('/session')){if(hold)await new Promise<void>(r=>releases.push(r));return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:stable',tenantId:'tenant',securityDomain:'domain'},session:{expiresAt:'2099-01-01T00:00:00Z',idleExpiresAt:'2099-01-01T00:00:00Z'},csrfToken:'fixture'}}).catch(()=>{});}return route.fulfill({json:{result:{items:[],problems:[],enabled:false}}});});
 await page.goto('/skills');await expect(page.getByLabel('当前可信身份 human:stable')).toBeVisible();hold=true;await page.locator('.skill-frame-navigation').getByRole('link',{name:peopleNav,exact:true}).click();await expect(page).toHaveURL(peoplePath);await expect.poll(()=>releases.length).toBeGreaterThan(0);await expect(page.getByLabel('当前可信身份 human:stable')).toBeVisible();await expect(page.locator('.skill-frame-identity').getByText('核对登录状态',{exact:true})).toHaveCount(0);hold=false;for(const release of releases)release();
});
