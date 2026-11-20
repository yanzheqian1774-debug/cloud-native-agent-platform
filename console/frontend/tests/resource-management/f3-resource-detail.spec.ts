import {expect,test,type Page} from '@playwright/test';
import {fixture,skillId} from '../helpers/resourceMaintenanceFixture';
async function published(page:Page){const state=await fixture(page,true);state.resource.revisions[0].state='PUBLISHED';state.resource.publishedRevisionId='revision:1';state.resource.currentDraftRevisionId=null;state.resource.lifecycleState='PUBLISHED';return state}
const href='/skills?managedResource='+encodeURIComponent(skillId);
test('F3 default detail reads publication and keeps exact technical identities below the business view',async({page},info)=>{
 const state=await published(page);await page.goto(href);
 await expect(page.getByRole('tab')).toHaveText(['概览','内容与定义','引用与影响']);
 await expect(page.locator('.f3-detail-heading')).toContainText('当前发布内容');
 await expect(page.locator('.f3-detail-heading h1')).toHaveCSS('font-size','24px');
 await expect(page.getByRole('tab',{name:'概览',exact:true})).toHaveCSS('font-size','12px');
 await expect(page.getByRole('heading',{name:'用途与交付'})).toBeVisible();
 await expect(page.getByText(skillId,{exact:true})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'运行测试',exact:true})).toHaveCount(0);
 await page.screenshot({path:info.outputPath('f3-overview-desktop.png')});
 await page.getByRole('tab',{name:'内容与定义',exact:true}).click();
 await page.getByText('本版本完整定义与准确依据',{exact:true}).click();
 await expect(page.getByText(skillId,{exact:true})).toBeVisible();
 expect(state.posts).toHaveLength(0);
});
test('modify published content creates one draft and opens editing without replacing publication',async({page})=>{
 const state=await published(page),old=structuredClone(state.resource.revisions[0]);await page.goto(href);
 await page.getByRole('button',{name:'创建修改草稿',exact:true}).click();
 await expect(page.getByRole('form',{name:'资源配置表单'})).toBeVisible();
 await expect(page.getByRole('tab',{name:'内容与定义',exact:true})).toHaveAttribute('aria-selected','true');
 expect(state.posts.map(x=>x.action)).toEqual(['successor']);
 expect(state.resource.publishedRevisionId).toBe('revision:1');expect(state.resource.revisions[0]).toEqual(old);
 await page.getByLabel('用途说明',{exact:true}).fill('修改后的独立草稿');await page.getByRole('button',{name:'保存草稿',exact:true}).click();
 await expect(page.locator('.rm-success')).toContainText('草稿修改已保存');expect(state.posts.map(x=>x.action)).toEqual(['successor','edit']);
 await page.getByRole('button',{name:'编辑草稿',exact:true}).click();await expect(page.getByLabel('用途说明',{exact:true})).toHaveValue('修改后的独立草稿');expect(state.posts).toHaveLength(2);
});
test('publication stays default when a draft exists and history selection performs no command',async({page})=>{
 const state=await published(page);state.resource.currentDraftRevisionId='revision:2';state.resource.revisions.push({...structuredClone(state.resource.revisions[0]),revisionId:'revision:2',digest:'b'.repeat(64),state:'DRAFT',content:{...state.resource.revisions[0].content,description:'未发布的新内容'}});
 await page.goto(href);await expect(page.getByRole('tabpanel',{name:'概览'})).toContainText('维护原用途');await expect(page.getByRole('tabpanel',{name:'概览'})).not.toContainText('未发布的新内容');
 await page.getByRole('button',{name:'查看修改草稿',exact:true}).click();await expect(page.getByRole('tabpanel',{name:'内容与定义'})).toContainText('未发布的新内容');
 await page.getByRole('button',{name:'历史记录',exact:true}).click();await page.locator('.f3-detail-history-list li').filter({hasText:'当前发布内容'}).getByRole('button',{name:'查看内容'}).click();await expect(page.getByRole('tabpanel',{name:'内容与定义'})).toContainText('维护原用途');expect(state.posts).toEqual([]);
});
test('legacy maintenance link stays in three-tab F3 frame and retains test controls',async({page})=>{
 const state=await published(page);await page.goto(href+'&resourceView=professional&resourceTab='+encodeURIComponent('测试'));await expect(page.getByRole('tab')).toHaveText(['概览','内容与定义','引用与影响']);await expect(page.getByRole('region',{name:'契约样例测试'})).toBeVisible();await expect(page.getByRole('navigation',{name:'当前配置内容'}).getByRole('button',{name:'测试',exact:true})).toHaveAttribute('aria-current','page');await page.getByRole('tab',{name:'概览',exact:true}).click();await page.reload();await expect(page.getByRole('heading',{name:'用途与交付'})).toBeVisible();expect(state.posts).toEqual([]);
});
test('F3 reference view returns from exact employee to same business tab and filter',async({page})=>{
 await published(page);await page.goto(href+'&resourceSection=impact&query='+encodeURIComponent('维护'));
 await page.getByRole('link',{name:'查看引用员工',exact:true}).click();await page.getByRole('link',{name:/返回资源维护/}).click();await expect(page.getByRole('tab',{name:'引用与影响',exact:true})).toHaveAttribute('aria-selected','true');expect(new URL(page.url()).searchParams.get('query')).toBe('维护');
});
test('F3 narrow tabs and primary edit entry remain reachable with keyboard',async({page},info)=>{
 await published(page);await page.setViewportSize({width:390,height:844});await page.goto(href);await page.getByRole('tab',{name:'概览',exact:true}).focus();await page.keyboard.press('ArrowRight');await expect(page.getByRole('tab',{name:'内容与定义',exact:true})).toBeFocused();await expect(page.getByRole('tab',{name:'内容与定义',exact:true})).toHaveAttribute('aria-selected','true');await expect(page.getByRole('button',{name:'创建修改草稿',exact:true})).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.screenshot({path:info.outputPath('f3-content-mobile.png')});
});

test('saved edit follows its new immutable draft while preserving published and historical content',async({page})=>{
 const state=await published(page);await page.route('**/resource-management/skill/commands',async route=>{
  const command=route.request().postDataJSON();if(command.action!=='edit')return route.fallback();
  state.posts.push(command);const previous=state.resource.revisions.at(-1)!;
  state.resource.revisions.push({...structuredClone(previous),revisionId:'revision:edited',digest:'e'.repeat(64),content:command.content});state.resource.currentDraftRevisionId='revision:edited';state.resource.aggregateVersion++;
  state.receipt={schemaVersion:'resource-management-receipt.v1',kind:'skill',action:command.action,identity:skillId,commandKey:command.commandKey,aggregateVersion:state.resource.aggregateVersion,resource:structuredClone(state.resource),executionStarted:false,modelCalls:0,credentialMaterial:'NOT_INCLUDED'};
  await route.fulfill({json:{result:state.receipt}});
 });
 await page.goto(href);await page.getByRole('button',{name:'创建修改草稿',exact:true}).click();await page.getByLabel('用途说明',{exact:true}).fill('编辑后的新准确修订');await page.getByRole('button',{name:'保存草稿',exact:true}).click();
 await expect.poll(()=>new URL(page.url()).searchParams.get('viewRevision')).toBe('revision:edited');await expect(page.getByRole('tabpanel',{name:'内容与定义'})).toContainText('编辑后的新准确修订');expect(state.resource.revisions[0].content.description).toBe('维护原用途');expect(state.posts.map(x=>x.action)).toEqual(['successor','edit']);
});
test('unknown requested revision does not silently display current publication',async({page})=>{
 const state=await published(page);await page.goto(href+'&viewRevision=revision%3Aabsent');await expect(page.getByRole('alert')).toContainText('当前版本未能核对');await expect(page.getByRole('heading',{name:'用途与交付'})).toHaveCount(0);expect(state.posts).toEqual([]);
});

test('impact counts distinct employees separately from version references',async({page})=>{
 const state=await published(page);
 await page.route('**/impact',route=>route.fulfill({json:{result:{current:{revisionId:'revision:1',digest:state.resource.revisions[0].digest},changes:[],authorizedUses:[],testCoverage:{ready:false,checks:[]},dependencies:{incoming:[1,2,3].map(i=>({kind:'EMPLOYEE',identity:i===3?'employee:other':'employee:same',revision:'revision:'+i,name:'同名员工',distance:1})),outgoing:[],limitations:[]}}}}));
 await page.goto(href+'&resourceSection=impact');const group=page.locator('.rd-impact-group').filter({hasText:'数字员工'});await expect(group.locator('h3 strong')).toHaveText('2');await expect(group).toContainText('3 条版本引用');expect(state.posts).toHaveLength(0);
});

test('history has no publication action and publication is an explicit content step',async({page})=>{
 const state=await published(page);await page.goto(href);await page.getByRole('button',{name:'创建修改草稿',exact:true}).click();await page.getByRole('button',{name:'取消',exact:true}).click();await page.getByRole('button',{name:'历史记录',exact:true}).click();await expect(page.getByRole('region',{name:'集中更新选定引用'})).toHaveCount(0);await expect(page.getByRole('button',{name:'验证全部操作后发布'})).toHaveCount(0);await page.getByRole('button',{name:'返回内容',exact:true}).click();await page.getByRole('tab',{name:'内容与定义'}).click();await page.getByRole('button',{name:'发布检查',exact:true}).click();await expect(page.getByRole('tabpanel',{name:'发布检查'})).toBeVisible();expect(state.posts.map(x=>x.action)).toEqual(['successor']);
});
test('single conversation return and directory fallback do not show duplicate primary returns',async({page})=>{
 const state=await published(page);await page.goto(href+'&returnConversation=original-test');await expect(page.locator('.f3-detail-heading').getByRole('link',{name:'返回原会话'})).toHaveCount(1);await expect(page.getByRole('button',{name:'返回来源'})).toHaveCount(0);await expect(page.getByRole('button',{name:'返回目录',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'查看资源目录'})).toBeVisible();expect(state.posts).toEqual([]);
});
