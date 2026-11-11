import {test,expect,type Page} from '@playwright/test';
async function fixture(page:Page){
 const state={writes:[] as string[],denied:false,unknown:false,foreign:false,changed:false,wrongScope:false,favorite:false,favoriteDenied:false};
 const principal={principalId:'human:home',tenantId:'tenant',securityDomain:'domain'};
 const item={workflowRunId:'run:home',preparationDigest:'a'.repeat(64),title:'检查非表格交接资料',createdAt:'2026-11-11T00:00:00Z',initiatorId:principal.principalId,executionState:'RUNNING',displayState:'waiting',progressVersion:1,problemId:'problem:home',problemRevisionId:'revision:home',problemDigest:'b'.repeat(64),pendingQuestionCount:1,artifactCount:1,businessResolution:'UNDETERMINED',originConversationId:'original',originVerified:true,planVersion:1,participantCount:1,completedTaskCount:0,taskCount:1,updatedAt:null};
 await page.route('**/api/**',async route=>{const url=new URL(route.request().url()),path=url.pathname;if(route.request().method()!=='GET')state.writes.push(path);const result=(r:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:r,continuationIds:[]}});
 if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:state.changed?{...principal,principalId:'human:other'}:principal,csrfToken:'csrf',session:{expiresAt:'2026-11-12T00:00:00Z'}}});
 if(path.endsWith('/business-capabilities')){expect(url.searchParams.get('favoritesOnly')).toBe('true');if(state.favoriteDenied)return route.fulfill({status:503,json:{reasonCode:'UNAVAILABLE'}});return result({items:state.favorite?[{capabilityId:'cap:home',revisionId:'rev:fixed',digest:'c'.repeat(64),title:'交接资料完整性核对',intent:'核对缺项并返回原文依据',businessDomain:'运营管理',currentPublished:{revisionId:'rev:fixed'}}]:[],nextCursor:null})}
 if(path.endsWith('/current-work')){if(state.denied)return route.fulfill({status:503,json:{reasonCode:'UNAVAILABLE'}});return result({schemaVersion:'current-work-directory.v1',scopeFilter:state.wrongScope?'visible':url.searchParams.get('scopeFilter'),subject:state.foreign?'human:other':principal.principalId,tenantId:'tenant',securityDomain:'domain',complete:true,questionStatusComplete:!state.unknown,readAt:'2026-11-11T00:00:00Z',total:1,counts:{waiting:1},items:[{...item,pendingQuestionCount:state.unknown?null:1}],nextCursor:null})}
 if(path.endsWith('/conversations/capabilities'))return result({enabled:true});
 if(path.endsWith('/development-administrator'))return result({enabled:false});
 if(path.endsWith('/problems'))return result({problems:[]});
 return result({items:[]});
 });return state;
}
test('current work, genuine waiting and partial results link to exact original work',async({page})=>{
 const state=await fixture(page);await page.goto('/dashboard');await expect(page.getByRole('region',{name:'需要我处理'})).toContainText('需要我处理 · 1');await expect(page.getByRole('region',{name:'需要我处理'}).getByRole('link',{name:'处理',exact:true})).toHaveAttribute('href','/work?conversation=original');await expect(page.getByRole('region',{name:'最近工作成果'})).toContainText('业务结论尚未确认');await expect(page.getByRole('link',{name:'阅读成果'})).toHaveAttribute('href',/workView=result/);await expect(page.getByText('旧规划记录',{exact:true})).toHaveCount(0);await expect(page.getByText('规划中 · 当前无企业模型目录',{exact:true})).toHaveCount(0);expect(state.writes).toEqual([]);
});
test('home goal enters an isolated conversation draft without starting execution',async({page})=>{
 const state=await fixture(page);await page.goto('/dashboard');const input=page.getByLabel('问题或工作目标',{exact:true});await expect(input).toBeEnabled();await input.fill('帮我检查发布说明的风险');await page.locator('form').getByRole('button',{name:'发起会话',exact:true}).click();await expect(page).toHaveURL(/\/work\?draft=home-/);await expect(page.locator('#private-input')).toHaveValue('帮我检查发布说明的风险');await page.reload();await expect(page.locator('#private-input')).toHaveValue('帮我检查发布说明的风险');expect(state.writes).toEqual([]);
});
test('unknown question coverage never claims no pending work',async({page})=>{const state=await fixture(page);state.unknown=true;await page.goto('/dashboard');await expect(page.getByRole('region',{name:'需要我处理'})).toContainText('部分追问状态尚未完整核对');await expect(page.getByText('当前范围没有已核实的待回答事项。',{exact:true})).toHaveCount(0);expect(state.writes).toEqual([])});
for(const mode of ['denied','foreign'] as const)test('unavailable or foreign scope does not show success counts '+mode,async({page})=>{const state=await fixture(page);state[mode]=true;await page.goto('/dashboard');await expect(page.getByRole('alert')).toContainText('暂未读取成功');await expect(page.getByRole('heading',{name:'检查非表格交接资料',exact:true})).toHaveCount(0);await expect(page.getByText('当前范围没有已核实的待回答事项。',{exact:true})).toHaveCount(0);expect(state.writes).toEqual([])});
test('expired identity withdraws dashboard data and cannot transfer question',async({page})=>{const state=await fixture(page);await page.goto('/dashboard');await expect(page.getByRole('region',{name:'继续已有工作'})).toContainText('检查非表格交接资料');await page.evaluate(()=>dispatchEvent(new Event('workbench-session-expired')));await expect(page.getByRole('heading',{name:'检查非表格交接资料',exact:true})).toHaveCount(0);await expect(page.getByRole('link',{name:'重新登录并读回',exact:true})).toBeVisible();await expect(page.locator('#home-question')).toHaveCount(0);expect(state.writes).toEqual([])});
test('mobile home retains readable cards and no horizontal overflow',async({page},info)=>{const state=await fixture(page);await page.setViewportSize({width:390,height:844});await page.goto('/dashboard');await expect(page.getByRole('region',{name:'最近工作成果'})).toContainText('检查非表格交接资料');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.screenshot({path:info.outputPath('home-mobile.png'),fullPage:true});expect(state.writes).toEqual([])});

test('changed identity cannot transfer a home draft',async({page})=>{const state=await fixture(page);await page.goto('/dashboard');await expect(page.getByLabel('问题或工作目标',{exact:true})).toBeEnabled();await page.getByLabel('问题或工作目标',{exact:true}).fill('检查资料');state.changed=true;await page.locator('form').getByRole('button',{name:'发起会话',exact:true}).click();await expect(page).toHaveURL(/dashboard/);await expect(page.getByRole('alert')).toContainText('登录身份已变化');await expect(page.getByRole('heading',{name:'检查非表格交接资料',exact:true})).toHaveCount(0);expect(state.writes).toEqual([])});
test('response must match the explicitly selected scope',async({page})=>{const state=await fixture(page);state.wrongScope=true;await page.goto('/dashboard');await expect(page.getByRole('alert')).toContainText('返回的工作范围尚未核实');await expect(page.getByRole('heading',{name:'检查非表格交接资料',exact:true})).toHaveCount(0);expect(state.writes).toEqual([])});

test('home favorites reuse authorized catalogue and exact definition links without writes',async({page},info)=>{
 const state=await fixture(page);state.favorite=true;await page.goto('/dashboard');
 const region=page.getByRole('region',{name:'我的收藏能力',exact:true});
 await expect(region).toContainText('交接资料完整性核对');
 await expect(region.getByRole('link',{name:'查看与使用'})).toHaveAttribute('href','/capabilities?'+new URLSearchParams({capability:'cap:home',revision:'rev:fixed',digest:'c'.repeat(64),returnHome:'1'}));
 await region.scrollIntoViewIfNeeded();await page.screenshot({path:info.outputPath('home-real-favorites-layout.png'),fullPage:true});
 state.favorite=false;await region.getByRole('button',{name:'刷新收藏'}).click();
 await expect(region).toContainText('暂无可读取的收藏能力');
 await expect(region.getByRole('link',{name:'查看与使用'})).toHaveCount(0);
 state.favoriteDenied=true;await region.getByRole('button',{name:'刷新收藏'}).click();
 await expect(region.getByRole('alert')).toContainText('暂未读取成功');
 await expect(region.getByText('暂无可读取的收藏能力。可到能力目录收藏常用能力。',{exact:true})).toHaveCount(0);
 expect(state.writes).toEqual([]);
});
