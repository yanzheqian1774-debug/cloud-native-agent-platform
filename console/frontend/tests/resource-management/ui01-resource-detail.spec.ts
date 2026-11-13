import {expect,test,type Page} from '@playwright/test';
const principal={principalId:'human:ui01',tenantId:'ui01-fixture',securityDomain:'isolated'};
const scope={tenantId:principal.tenantId,securityDomain:principal.securityDomain},session={principal,session:{expiresAt:'2099-01-01'},csrfToken:'fixture'},conversation='ui01-original';
const items=['skill','mcp'].map(kind=>({kind,identity:kind+':ui01',revisionId:'revision:1',digest:'a'.repeat(64),name:kind==='skill'?'准确销售技能':'准确连接配置',state:'PUBLISHED',enabled:true,isCurrentPublished:true,isCurrentDraft:false,createdAt:null,executionReady:false,policyReviewed:false}));
async function fixture(page:Page,mode='normal'){
 const writes:string[]=[];
 const readable=mode.startsWith('history')?[...items,{...items[0],revisionId:'revision:old',digest:'c'.repeat(64),isCurrentPublished:false},{...items[0],identity:'skill:unrelated',revisionId:'revision:unrelated'}]:items;
 await page.route('**/api/workbench/v1/**',async route=>{
  const r=route.request(),u=new URL(r.url());if(r.method()!=='GET'){writes.push(r.method()+u.pathname);return route.abort()}
  if(u.pathname.endsWith('/session'))return route.fulfill({json:session});
  if(u.pathname.endsWith('/conversations/capabilities'))return route.fulfill({json:{result:{enabled:true}}});
  if(u.pathname.endsWith('/conversations/'+conversation))return route.fulfill({json:{result:{conversation:{conversation_id:conversation,title:'原会话',version:1,created_at:'2026-11-06'},messages:[],links:[]}}});
  if(u.pathname.endsWith('/conversations'))return route.fulfill({json:{result:{items:[{conversation_id:conversation,title:'原会话',created_at:'2026-11-06'}]}}});
  if(u.pathname.endsWith('/business-problems'))return route.fulfill({json:{problems:[]}});
  if(/resource-management\/(skill|mcp)$/.test(u.pathname))return route.fulfill({json:{result:{subject:principal.principalId,scope,items:[]}}});
  if(u.pathname.endsWith('/resource-directory'))return route.fulfill({json:{result:{subject:principal.principalId,scope,items:readable.filter(i=>!u.searchParams.get('kind')||i.kind===u.searchParams.get('kind')),nextCursor:null,executionAuthority:'NONE'}}});
  if(u.pathname.includes('/resource-directory/')){
   const item=readable.find(i=>u.pathname.endsWith('/'+[i.kind,i.identity,i.revisionId].map(encodeURIComponent).join('/')))!;
   if(!item)return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
   if(mode==='history-denied'&&item.revisionId==='revision:old')return route.fulfill({status:403,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
   if(mode==='denied')return route.fulfill({status:403,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
   return route.fulfill({json:{result:{...item,subject:mode==='identity'?'human:other':principal.principalId,scope,revision:{revisionId:item.revisionId,digest:mode==='version'?'b'.repeat(64):item.digest,state:'PUBLISHED',content:{description:'来自当前准确版本',instructions:(item.revisionId==='revision:old'?'历史独立规则':mode.startsWith('history')?'按已确认期间核对资料，返回摘要并保留异常。':'隔离长规则\n'.repeat(75)),capabilities:['READ_DATA'],inputSchema:{type:'object',properties:{period:{type:'string',description:'需要核对的期间'}},required:['period']},outputSchema:{type:'object',properties:{summary:{type:'string',description:'核对摘要'}}},endpoint:'http://127.0.0.1:8765/mcp',sideEffect:'READ',idempotency:'IDEMPOTENT',timeoutSeconds:5}},usage:[]}}});
  }
  return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
 });return writes;
}
function path(kind='skill'){const item=items.find(i=>i.kind===kind)!;return '/'+(kind==='skill'?'skills':'mcp')+'?'+new URLSearchParams({selected:item.identity,resourceRevision:item.revisionId,returnConversation:conversation})}

test('UI01 right detail scroll contains bottom wheel at the approved viewport',async({page})=>{
 const writes=await fixture(page);await page.setViewportSize({width:1280,height:720});await page.goto(path()+'&resourceView=professional');
 await expect(page.getByRole('heading',{name:'准确销售技能',exact:true})).toBeVisible();
 const detail=page.getByRole('region',{name:'资源详情滚动区'});
 const positions=()=>page.evaluate(()=>({outer:document.scrollingElement!.scrollTop,side:document.querySelector('.px-sidebar')!.scrollTop,nav:document.querySelector('.px-business-nav')!.scrollTop,list:document.querySelector('.resource-detail-list')!.scrollTop,detail:document.querySelector('.resource-directory-detail')!.scrollTop}));
 const before=await positions();await detail.hover();await page.mouse.wheel(0,900);await expect.poll(async()=>(await positions()).detail).toBeGreaterThan(before.detail);
 await detail.evaluate(node=>node.scrollTop=node.scrollHeight);const bottom=await positions();await page.mouse.wheel(0,2000);await page.waitForTimeout(250);expect(await positions()).toEqual(bottom);expect(bottom.outer).toBe(0);expect(bottom.side).toBe(0);expect(bottom.nav).toBe(0);expect(bottom.list).toBe(0);
 expect(await detail.evaluate(node=>getComputedStyle(node).overscrollBehaviorY)).toBe('contain');expect(writes).toEqual([]);
});

test('UI01 original conversation draft survives real navigation and detail reload without writes',async({page})=>{
 const writes=await fixture(page);await page.goto('/work?conversation='+conversation);await page.locator('#private-input').fill('尚未发送的原会话草稿');
 const link=page.getByRole('navigation',{name:'P1 核心产品导航'}).getByRole('link',{name:'技能',exact:true});await page.getByText('资源管理',{exact:true}).first().click();await expect(link).toHaveAttribute('href','/skills?returnConversation='+conversation);await link.click();
 await page.getByRole('link',{name:'查看详情',exact:true}).click();await expect(page.getByRole('heading',{name:'准确销售技能',exact:true})).toBeVisible();await page.reload();await expect(page.getByRole('heading',{name:'准确销售技能',exact:true})).toBeVisible();
 await page.getByRole('link',{name:'返回原会话',exact:true}).click();await expect(page.locator('#private-input')).toHaveValue('尚未发送的原会话草稿');expect(writes).toEqual([]);
});

for(const kind of ['skill','mcp'])test('UI01 '+kind+' uses exact SVG and semantic type color',async({page})=>{
 await fixture(page);await page.goto(path(kind)+'&resourceView=professional');const mark=page.locator('.resource-readonly-detail>header .resource-type-mark');await expect(mark).toBeVisible();expect(await mark.evaluate(node=>getComputedStyle(node).color)).toBe(kind==='skill'?'rgb(49, 94, 192)':'rgb(23, 110, 123)');await expect(mark.locator('svg')).toHaveAttribute('viewBox','0 0 24 24');if(kind==='mcp'){await expect(mark.locator('path')).toHaveCount(4);await expect(mark.locator('path').first()).toHaveAttribute('d','M12 22v-5');await expect(page.getByRole('heading',{name:'连接配置',exact:true})).toBeVisible();await expect(page.getByText('本版本读取接口未返回工具发现和选择记录，不推定其存在。',{exact:false})).toBeVisible()}else {await expect(mark.locator('path')).toHaveCount(4);await expect(mark.locator('path').first()).toHaveAttribute('d','M4 12.15V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.706.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2h-3.35');}
});

for(const mode of ['denied','identity','version'])test('UI01 '+mode+' never presents another or stale version',async({page})=>{
 const writes=await fixture(page,mode);await page.goto(path());await expect(page.getByRole('alert')).toContainText('当前版本详情未读回');await expect(page.locator('.resource-readonly-detail')).toHaveCount(0);expect(writes).toEqual([]);
});


test('UI01 all-kind catalog detail carries the selected kind and exact revision',async({page})=>{
 const writes=await fixture(page);await page.goto('/catalog?returnConversation='+conversation);await page.getByRole('article',{name:'准确连接配置',exact:true}).getByRole('link',{name:'打开资源详情',exact:true}).click();await expect(page).toHaveURL(/kind=mcp/);await expect(page.getByRole('heading',{name:'准确连接配置',exact:true})).toBeVisible();await page.reload();await expect(page.getByRole('heading',{name:'准确连接配置',exact:true})).toBeVisible();expect(writes).toEqual([]);
});


test('F3 readonly business tabs keep exact identity behind evidence and never grant maintenance',async({page},info)=>{
 const writes=await fixture(page);await page.goto(path());
 await expect(page.getByRole('tab',{name:'概览',exact:true})).toHaveAttribute('aria-selected','true');
 await expect(page.getByRole('tab')).toHaveCount(3);
 await expect(page.getByRole('heading',{name:'固定版本',exact:true})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'修改当前发布内容',exact:true})).toHaveCount(0);
 await expect(page.getByRole('navigation',{name:'本页可读资源'})).toBeHidden();
 await page.screenshot({path:info.outputPath('f3-readonly-overview.png')});
 await page.getByRole('tab',{name:'概览',exact:true}).focus();await page.keyboard.press('ArrowRight');
 await expect(page.getByRole('tab',{name:'内容与定义',exact:true})).toBeFocused();
 await expect(page.getByRole('heading',{name:'办理规则与能力',exact:true})).toBeVisible();
 await expect(page.getByRole('tabpanel',{name:'内容与定义'}).getByText('revision:1',{exact:true})).toBeHidden();
 await page.getByText('本版本完整定义与准确依据',{exact:true}).click();
 await expect(page.getByRole('tabpanel',{name:'内容与定义'}).getByText('revision:1',{exact:true})).toBeVisible();
 await page.getByText('版本技术记录',{exact:true}).click();
 await expect(page.getByRole('heading',{name:'固定版本',exact:true})).toBeVisible();
 await page.getByText('版本技术记录',{exact:true}).click();
 await expect(page.getByRole('tab',{name:'内容与定义',exact:true})).toHaveAttribute('aria-selected','true');
 await page.getByRole('tab',{name:'引用与影响',exact:true}).click();
 await expect(page.getByRole('heading',{name:'关联任务中的保存引用',exact:true})).toBeVisible();
 await page.reload();await expect(page.getByRole('tab',{name:'引用与影响',exact:true})).toHaveAttribute('aria-selected','true');
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.screenshot({path:info.outputPath('f3-readonly-impact-mobile.png')});expect(writes).toEqual([]);
});

for(const mode of ['history','history-denied'])test('F3 reader exact authorized history '+mode,async({page},info)=>{
 const writes=await fixture(page,mode);await page.setViewportSize({width:1440,height:900});await page.goto(path());
 await expect(page.getByRole('tab')).toHaveText(['概览','内容与定义','引用与影响']);
 await expect(page.getByRole('button',{name:'查看专业详情'})).toHaveCount(0);
 await expect(page.getByRole('tabpanel',{name:'概览'})).toContainText('修订 1');await expect(page.getByRole('tabpanel',{name:'概览'})).toContainText('当前读取范围未返回，不代表不存在');
 await page.screenshot({path:info.outputPath('readonly-overview-1440.png')});
 await page.getByRole('tab',{name:'内容与定义'}).click();await expect(page.getByRole('tabpanel',{name:'内容与定义'})).toContainText('需要核对的期间');await expect(page.getByRole('tabpanel',{name:'内容与定义'})).toContainText('未返回本版本测试与发布校验回执');await page.screenshot({path:info.outputPath('readonly-content-1440.png')});
 await page.getByRole('tab',{name:'引用与影响'}).click();await expect(page.getByRole('tabpanel',{name:'引用与影响'})).toContainText('当前未读回关联任务的保存引用');await page.screenshot({path:info.outputPath('readonly-impact-1440.png')});
 await page.getByRole('button',{name:'历史记录',exact:true}).click();
 const history=page.getByRole('region',{name:'历史记录',exact:true});
 await expect(history.getByRole('listitem')).toHaveCount(2);
 await expect(history).not.toContainText('revision:unrelated');
 await expect(history).toContainText('仅列出当前目录已加载');
 await expect(page.getByRole('button',{name:/修改|发布|准备技能后继/})).toHaveCount(0);
 await page.screenshot({path:info.outputPath('readonly-history-1440.png')});
 await history.getByRole('listitem').filter({hasText:'revision:old'}).getByRole('link',{name:'查看内容'}).click();
 await expect(page).toHaveURL(/resourceDigest=cccc/);
 if(mode==='history-denied'){await expect(page.getByRole('alert')).toContainText('当前版本详情未读回');await expect(page.getByText('历史独立规则',{exact:true})).toHaveCount(0)}else{
  await expect(page.getByRole('tabpanel',{name:'内容与定义'})).toContainText('历史独立规则');
  await page.reload();await expect(page.getByRole('tabpanel',{name:'内容与定义'})).toContainText('历史独立规则');
  await page.getByText('版本技术记录',{exact:true}).click();await expect(page.getByRole('button',{name:/修改|发布|准备技能后继/})).toHaveCount(0);
  await page.getByRole('button',{name:'历史记录',exact:true}).click();await page.getByRole('button',{name:'返回内容',exact:true}).click();await expect(page.getByRole('tabpanel',{name:'内容与定义'})).toContainText('历史独立规则');
 }
 await expect(page.getByRole('link',{name:'返回原会话',exact:true})).toHaveAttribute('href','/work?conversation='+conversation);expect(writes).toEqual([]);
});
