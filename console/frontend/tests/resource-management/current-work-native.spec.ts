import {test,expect,type Page} from '@playwright/test';
async function fixture(page:Page){
 const state={mode:'completed',historyRestricted:false,questionStatusComplete:true,principal:'human:alice',error:false,requests:[] as string[],writes:[] as string[]};
 await page.route('**/api/**',async route=>{
  const req=route.request(),url=new URL(req.url()),p=url.pathname;
  if(req.method()!=='GET'){state.writes.push(p);return route.abort()}
  if(p.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:state.principal,tenantId:'fixture',securityDomain:'isolated'},session:{expiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(p.endsWith('/conversations/capabilities'))return route.fulfill({json:{result:{enabled:true}}});
  if(p.endsWith('/current-work')){
   state.requests.push(url.search);
   if(state.error)return route.fulfill({status:503,json:{reasonCode:'CURRENT_WORK_AUTHORITY_UNAVAILABLE'}});
   const scope=url.searchParams.get('scopeFilter')??'visible',query=url.searchParams.get('query')??'',filter=url.searchParams.get('state')??'all',offset=Number(url.searchParams.get('cursor')??0);
   const all=Array.from({length:34},(_,i)=>({workflowRunId:'run:'+i,preparationDigest:(i+1).toString(16).padStart(64,'0'),title:'交接检查 '+(i+1),createdAt:'2026-11-10T01:00:00Z',initiatorId:i<21?'human:alice':'human:bob',executionState:i===0&&state.mode!=='completed'?'RUNNING':'SUCCEEDED',displayState:i===0?state.mode:'completed',progressVersion:3,problemId:'p'+i,problemRevisionId:'r'+i,problemDigest:'a'.repeat(64),pendingQuestionCount:i===0&&(state.mode==='unknown'||state.historyRestricted)?null:i===0&&state.mode==='waiting'?1:0,artifactCount:3,businessResolution:'UNDETERMINED',originConversationId:i<26?'c'+i:null,originVerified:i<26,planVersion:4,participantCount:1,completedTaskCount:3,taskCount:3,updatedAt:'2026-11-10T02:00:00Z'})).filter(i=>(scope==='visible'||i.initiatorId===state.principal)&&i.title.includes(query)&&filter!=='waiting');
   return route.fulfill({json:{result:{schemaVersion:'current-work-directory.v1',scopeFilter:scope,subject:state.principal,tenantId:'fixture',securityDomain:'isolated',complete:true,questionStatusComplete:state.questionStatusComplete,readAt:'2026-11-10T03:00:00Z',total:all.length,counts:all.reduce<Record<string,number>>((counts,item)=>{counts[item.displayState]=(counts[item.displayState]??0)+1;return counts},{completed:0,waiting:0,running:0,failed:0,cancelled:0,unknown:0}),items:all.slice(offset,offset+25),nextCursor:offset+25<all.length?String(offset+25):null}}});
  }
  if(p.includes('/prepared-executions/'))return route.fulfill({status:403,json:{reasonCode:'DETAIL_READ_DENIED'}});
  return route.fulfill({json:{result:{items:[],enabled:false}}});
 });return state;
}
test('scope is explicit, retained on reload and resets pagination',async({page})=>{
 const state=await fixture(page);await page.goto('/tasks');await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(25);
 await page.getByRole('button',{name:'下一页',exact:true}).click();await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(9);
 await page.getByLabel('查看范围',{exact:true}).selectOption('initiated');await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(21);await expect(page).not.toHaveURL(/cursor=/);
 await page.reload();await expect(page.getByLabel('查看范围',{exact:true})).toHaveValue('initiated');await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(21);expect(state.writes).toEqual([]);
});
test('page reload and detail return retain exact page and focused row',async({page})=>{
 await fixture(page);await page.goto('/tasks');await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(25);await page.getByRole('button',{name:'下一页',exact:true}).click();await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(9);await page.reload();await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(9);
 const row=page.getByRole('row').filter({hasText:'交接检查 30'});await row.getByRole('button',{name:'查看任务'}).click();await expect(page.getByRole('heading',{name:'当前无法读取这项工作'})).toBeVisible();await page.getByRole('button',{name:'返回我的任务',exact:true}).click();await expect(row.getByRole('button',{name:'查看任务'})).toBeFocused();await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(9);await page.getByRole('button',{name:'上一页',exact:true}).click();await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(25);
});
test('slow prior query cannot overwrite newer search results',async({page})=>{
 await fixture(page);let release=()=>{};const held=new Promise<void>(resolve=>{release=resolve});
 await page.route('**/api/workbench/v1/current-work?*',async route=>{if(new URL(route.request().url()).searchParams.get('query')==='旧请求')await held;await route.fallback().catch(()=>{})});
 await page.goto('/tasks');await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(25);const input=page.getByLabel('搜索工作',{exact:false});await input.fill('旧请求');await page.waitForRequest(r=>new URL(r.url()).searchParams.get('query')==='旧请求');await input.fill('交接检查 34');await expect(page.locator('.f3-work-table tbody tr')).toHaveCount(1);release();await expect(page.locator('.f3-work-table tbody')).toHaveText(/交接检查 34/);
});
test('authority outage is not rendered as an empty successful list',async({page})=>{
 const state=await fixture(page);state.error=true;await page.goto('/tasks');await expect(page.getByRole('alert')).toBeVisible();await expect(page.getByText('当前筛选下没有可读取的执行记录。',{exact:true})).toHaveCount(0);await expect(page.getByText('CURRENT_WORK_AUTHORITY_UNAVAILABLE',{exact:true})).not.toBeVisible();state.error=false;await page.getByRole('button',{name:'重新核对',exact:true}).click();await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(25);
});
test('a new identity does not inherit the prior explicit scope',async({page})=>{
 const state=await fixture(page);await page.goto('/tasks');await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(25);await page.getByLabel('查看范围',{exact:true}).selectOption('initiated');await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(21);state.principal='human:bob';await page.goto('/tasks');await expect(page.getByLabel('查看范围',{exact:true})).toHaveValue('visible');await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(25);
});
test('mobile detail return preserves table horizontal position and pagination remains reachable',async({page})=>{
 await fixture(page);await page.setViewportSize({width:390,height:844});await page.goto('/tasks');const button=page.getByRole('button',{name:'查看任务',exact:true}).first();await button.waitFor();await button.scrollIntoViewIfNeeded();const table=page.locator('.f3-work-table-wrap'),left=await table.evaluate(n=>n.scrollLeft);expect(left).toBeGreaterThan(0);await button.click();await expect(page.getByRole('heading',{name:'当前无法读取这项工作'})).toBeVisible();await page.getByRole('button',{name:'返回我的任务',exact:true}).click();await expect(button).toBeFocused();await expect.poll(()=>table.evaluate(n=>n.scrollLeft)).toBeCloseTo(left,0);const next=page.getByRole('button',{name:'下一页',exact:true});await next.scrollIntoViewIfNeeded();await next.click();await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(9);
});

test('unknown question coverage never claims zero waiting tasks',async({page})=>{
 const state=await fixture(page);state.questionStatusComplete=false;
 await page.goto('/tasks?filter=waiting');
 await expect(page.getByText('暂未发现可确认的待补充任务，尚不能判断是否全部无需补充。')).toBeVisible();
 await expect(page.getByText('待核实',{exact:true})).toBeVisible();
 await expect(page.getByText('部分任务的追问状态暂不可读取，待补充列表可能不完整；可在全部任务中查看已保存进度。')).toBeVisible();
 expect(state.writes).toEqual([]);
});


test('directory deadline ends waiting and retries only after explicit action',async({page})=>{
 const state=await fixture(page);let release=()=>{},held=true,requests=0;const pending=new Promise<void>(resolve=>{release=resolve});
 await page.route('**/api/workbench/v1/current-work?*',async route=>{requests++;if(held){await pending;await route.abort().catch(()=>{});return}await route.fallback()});
 await page.clock.install();
 try{
  await page.goto('/tasks');await expect.poll(()=>requests).toBe(1);
  await page.clock.fastForward(30_001);
  await expect(page.getByRole('alert')).toContainText('读取超过 30 秒，请重新核对。');
  await expect(page.getByText('正在读取任务、当前权限和保存结果…',{exact:true})).toHaveCount(0);
  await page.clock.fastForward(60_000);expect(requests).toBe(1);
  held=false;release();await page.getByRole('button',{name:'重新核对',exact:true}).click();
  await expect(page.getByRole('button',{name:'查看任务',exact:true})).toHaveCount(25);expect(requests).toBe(2);expect(state.writes).toEqual([]);
 }finally{release()}
});

test('row preserves unknown clarification instead of claiming live progress',async({page},testInfo)=>{
 const state=await fixture(page);state.mode='unknown';state.questionStatusComplete=false;await page.goto('/tasks');
 const row=page.getByRole('row').filter({has:page.getByText('交接检查 1',{exact:true})});
 await expect(row).toContainText('进展待核实');await expect(row).toContainText('必要追问状态暂不可读取');await expect(row).not.toContainText('正在推进');
 await page.screenshot({path:testInfo.outputPath('unknown-clarification-list.png'),fullPage:true});
 state.mode='running';state.questionStatusComplete=true;await page.getByRole('button',{name:'重新读取',exact:true}).click();
 await expect(row).toContainText('正在推进');await expect(row).not.toContainText('必要追问状态暂不可读取');
 state.mode='waiting';await page.getByRole('button',{name:'重新读取',exact:true}).click();
 await expect(row).toContainText('待你补充');await expect(row).toContainText('在原会话回答必要信息');expect(state.writes).toEqual([]);
 await page.screenshot({path:testInfo.outputPath('known-pending-question-list.png'),fullPage:true});
});

test('completed task distinguishes unavailable history from active pending questions',async({page})=>{
 const s=await fixture(page);s.historyRestricted=true;await page.goto('/tasks');await expect(page.getByText('任务已结束；历史追问记录暂不可读取',{exact:true})).toBeVisible();const metric=page.getByRole('region',{name:'任务记录概览'}).locator('article').filter({hasText:'待补充任务'});await expect(metric).toContainText('0');await expect(metric).toContainText('正在执行任务中的有效追问');expect(s.writes).toEqual([]);
});
