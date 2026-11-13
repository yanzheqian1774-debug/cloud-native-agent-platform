import {test,expect,type Page} from '@playwright/test';
async function fixture(page:Page){
 const writes:string[]=[];
 const problem={business_problem_id:'legacy-only',revision_id:'old-r1',revision:1,title:'未关联会话的历史问题',description:'保留旧问题与修订',created_at:'2026-11-01T00:00:00Z',digest:'a'.repeat(64),status:'DRAFT'};
 await page.route('**/api/**',route=>{
  const request=route.request(),path=new URL(request.url()).pathname,result=(value:unknown)=>route.fulfill({json:{result:value}});
  if(request.method()!=='GET'){writes.push(path);return route.fulfill({status:405,json:{reasonCode:'READ_ONLY_AUDIT'}})}
  if(path.startsWith('/api/internal/'))return route.fulfill({json:[]});
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:ordinary',tenantId:'tenant',securityDomain:'domain'},csrfToken:'csrf',session:{}}});
  if(path.endsWith('/development-administrator'))return result({enabled:false});
  if(path.endsWith('/conversations/capabilities'))return result({enabled:true});
  if(path.endsWith('/conversations'))return result({items:Array.from({length:30},(_,i)=>({conversation_id:'c'+i,title:'历史会话 '+i,created_at:'2026-11-12T00:00:00Z'}))});
  if(path.endsWith('/journey'))return result({version:0,state:null});
  if(/\/conversations\/c\d+$/.test(path))return result({conversation:{conversation_id:path.split('/').at(-1),title:'我的保留会话',version:1},messages:[{message_id:'old',content:'已保存的说明',author_id:'human:ordinary',created_at:'2026-11-12T00:00:00Z',disposition:'GOAL_RECORDED'}],links:[]});
  if(path.endsWith('/problems'))return result({problems:[problem]});
  if(path.endsWith('/problems/legacy-only'))return result({problem:{...problem,current_revision_id:'old-r1'},revisions:[problem]});
  return result({items:[],entries:[],problems:[],criteria:[],sets:[],rejectedResources:0});
 });return writes;
}
const nav=(page:Page)=>page.locator('.skill-frame-navigation');
test('one conversation fold retains input, history position and selected conversation across routes and refresh',async({page},testInfo)=>{
 const writes=await fixture(page);await page.setViewportSize({width:1440,height:900});await page.goto('/work?conversation=c0');
 const group=nav(page).locator('[data-navigation-group="conversations"]'),history=nav(page).getByLabel('可访问的会话');
 await expect(group).toHaveAttribute('open','');await expect(nav(page).getByRole('button',{name:'会话记录',exact:true})).toHaveCount(0);
 await expect(history.getByRole('link',{name:/历史会话 0/})).toHaveAttribute('aria-current','page');
 const first=await history.locator('a').first().boundingBox(),box=await history.boundingBox();expect(first!.y).toBeGreaterThanOrEqual(box!.y);
 await page.locator('#private-input').fill('尚未发送的测试补充');
 await history.evaluate(n=>{n.scrollTop=420;n.dispatchEvent(new Event('scroll'))});const top=await history.evaluate(n=>n.scrollTop);
 await group.locator('summary').click();await expect(group).not.toHaveAttribute('open','');
 await nav(page).getByRole('link',{name:'我的任务',exact:true}).click();await expect(group).not.toHaveAttribute('open','');
 await expect(nav(page).getByRole('link',{name:'我的任务',exact:true})).toHaveAttribute('class','active');
 await group.locator('summary').click();await expect.poll(()=>history.evaluate(n=>n.scrollTop)).toBe(top);
 await history.locator('a[href="/work?conversation=c0"]').click();await expect(page.locator('#private-input')).toHaveValue('尚未发送的测试补充');
 await history.evaluate(n=>{n.scrollTop=420;n.dispatchEvent(new Event('scroll'))});await nav(page).evaluate(n=>{n.dispatchEvent(new Event('wheel'));n.scrollTop=120;n.dispatchEvent(new Event('scroll'))});const outerTop=await nav(page).evaluate(n=>n.scrollTop);await page.reload();
 await expect(page.locator('#private-input')).toHaveValue('尚未发送的测试补充');await expect.poll(()=>history.evaluate(n=>n.scrollTop)).toBe(top);await expect.poll(()=>nav(page).evaluate(n=>n.scrollTop)).toBe(outerTop);
 await expect(history.locator('a[href="/work?conversation=c0"]')).toHaveAttribute('aria-current','page');
 await history.evaluate(n=>{n.scrollTop=0;n.dispatchEvent(new Event('scroll'))});await nav(page).evaluate(n=>{n.scrollTop=0;n.dispatchEvent(new Event('scroll'))});const home=await nav(page).getByRole('link',{name:'首页 · 我的工作台',exact:true}).boundingBox(),navBox=await nav(page).boundingBox();expect(home!.y).toBeGreaterThanOrEqual(navBox!.y);await page.screenshot({path:testInfo.outputPath('navigation-1440.png')});expect(writes).toEqual([]);
});
test('legacy problem remains a secondary independent reader and scrollbar width is stable',async({page})=>{
 const writes=await fixture(page);await page.goto('/work?conversation=c0');
 const link=nav(page).getByRole('link',{name:'历史业务问题',exact:true});await expect(link).toHaveAttribute('href','/work?legacy=1&panel=existing');await link.click();
 await expect(page.getByRole('navigation',{name:'业务问题列表'}).getByRole('button',{name:/未关联会话的历史问题/})).toBeVisible({timeout:15000});
 const area=nav(page),before=await area.evaluate(n=>n.clientWidth);await area.hover();expect(await area.evaluate(n=>n.clientWidth)).toBe(before);
 await expect.poll(()=>area.evaluate(n=>getComputedStyle(n).scrollbarGutter)).toBe('stable');
 await expect(nav(page).locator('a[href="/work?conversation=c0"]')).toHaveCount(1);expect(writes).toEqual([]);
});
test('narrow menu uses the same single layer and selected destination icon',async({page},testInfo)=>{
 const writes=await fixture(page);await page.setViewportSize({width:390,height:844});await page.goto('/work?conversation=c0');
 await page.locator('.skill-frame-menu>details>summary').click();const menu=page.getByRole('navigation',{name:'移动端全部产品导航'});
 await expect(menu.locator('[data-navigation-group="conversations"]')).toHaveAttribute('open','');await expect(menu.getByRole('button',{name:'会话记录',exact:true})).toHaveCount(0);
 await menu.getByRole('link',{name:'我的任务',exact:true}).click();await page.locator('.skill-frame-menu>details>summary').click();
 const task=menu.getByRole('link',{name:'我的任务',exact:true});await expect(task).toHaveAttribute('aria-current','page');
 expect(await task.locator('svg').evaluate(n=>getComputedStyle(n).stroke)).toBe(await task.evaluate(n=>getComputedStyle(n).color));
 await page.screenshot({path:testInfo.outputPath('navigation-390.png')});expect(writes).toEqual([]);
});

test('selected task, resource and employee navigation share icon styling',async({page})=>{
 const writes=await fixture(page);const colors=[];
 for(const [route,label] of [['/tasks','我的任务'],['/skills','技能'],['/digital-employees','数字员工']]){
  await page.goto(route);const link=nav(page).getByRole('link',{name:label,exact:true});await expect(link).toHaveAttribute('aria-current','page');
  colors.push(await link.evaluate(n=>getComputedStyle(n).color));expect(await link.locator('svg').evaluate(n=>getComputedStyle(n).stroke)).toBe(colors.at(-1));
 }
 expect(new Set(colors).size).toBe(1);expect(writes).toEqual([]);
});
