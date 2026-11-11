import {test,expect,type Page} from '@playwright/test';
const digest=(i:number)=>i.toString(16).padStart(64,'0');
async function fixture(page:Page){
 const s={count:0,complete:true,deny:false,failPage:false,changeScope:false,principal:'human:alice',history:false,historyCount:1,historyComplete:true,reads:[] as string[],writes:[] as string[]};
 await page.route('**/api/**',async route=>{
  const req=route.request(),u=new URL(req.url()),p=u.pathname;s.reads.push(p+u.search);
  if(req.method()!=='GET'){s.writes.push(p);return route.abort()}
  const ok=(result:unknown)=>route.fulfill({json:{result}});
  if(p.endsWith('/session'))return route.fulfill({json:{principal:{principalId:s.principal,tenantId:'fixture',securityDomain:'isolated'},session:{expiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(p.endsWith('/current-work')){
   const answered=u.searchParams.get('state')==='answered',count=answered?(s.history?s.historyCount:0):s.count;
   if(!['waiting','answered'].includes(u.searchParams.get('state')??'')||u.searchParams.get('scopeFilter')!=='visible')throw Error('Wrong directory scope');
   const start=Number(u.searchParams.get('cursor')??0);if(start&&s.failPage)return route.fulfill({status:503,json:{reasonCode:'UNAVAILABLE'}});
   const principal=s.principal;if(s.changeScope)s.principal='human:bob';
   return ok({schemaVersion:'current-work-directory.v1',subject:principal,tenantId:'fixture',securityDomain:'isolated',scopeFilter:'visible',complete:true,questionStatusComplete:s.complete,answerHistoryComplete:s.historyComplete,readAt:'2026-11-12T00:00:00Z',total:count,counts:answered?{completed:count}:{waiting:count},items:Array.from({length:Math.max(0,Math.min(25,count-start))},(_,i)=>({workflowRunId:'run:'+(start+i+1),preparationDigest:digest(start+i+1),title:'待答检查 '+(start+i+1),createdAt:'2026-11-11T00:00:00Z',executionState:answered?'SUCCEEDED':'RUNNING',displayState:answered?'completed':'waiting',pendingQuestionCount:answered?0:1,answeredQuestionCount:answered?1:0,problemId:'p'+(start+i+1),problemRevisionId:'r1',problemDigest:'a'.repeat(64),originConversationId:'c'+(start+i+1),originVerified:true})),nextCursor:start+25<count?String(start+25):null});
  }
  if(p.endsWith('/conversations/capabilities'))return ok({enabled:true});
  if(p.endsWith('/conversations'))return ok({items:s.history?[{conversation_id:'c1',title:'历史检查'}]:[]});
  if(p.endsWith('/problems'))return ok({problems:s.history?[{business_problem_id:'p1',revision_id:'r1',digest:'a'.repeat(64),title:'历史检查'}]:[]});
  const problem=p.match(/\/problems\/p(\d+)$/);if(problem)return ok({problem:{business_problem_id:'p'+problem[1]},revisions:[{business_problem_id:'p'+problem[1],revision_id:'r1',digest:'a'.repeat(64),title:'待答检查 '+problem[1]}]});
  const journey=p.match(/\/conversations\/c(\d+)\/journey$/);if(journey)return ok({state:{execution:digest(Number(journey[1]))}});
  const links=p.match(/\/conversations\/c(\d+)\/work-links$/);if(links)return ok({conversation:{conversation_id:'c'+links[1]},links:[{readable:true,target:{problemId:'p'+links[1],executionDigest:digest(Number(links[1]))}}]});
  const native=p.match(/\/prepared-executions\/([0-9a-f]+)\/native-progress$/);if(native){if(s.deny)return route.fulfill({status:403,json:{reasonCode:'DENIED'}});return ok({questions:[{questionKey:native[1],questionDigest:'b'.repeat(64),question:'请确认规范 '+parseInt(native[1],16),expiresAt:'2099-01-01',answer:s.history?'已选择生产规范':null,expired:false}]})}
  const execution=p.match(/\/prepared-executions\/([0-9a-f]+)$/);if(execution)return ok({digest:execution[1],preparation:{plan_version:1,participants:[],semantics:{title:'检查',tasks:[],target:{problem:{resource_id:'p'+parseInt(execution[1],16),revision_id:'r1',digest:'a'.repeat(64)}}}},progress:{state:s.history?'SUCCEEDED':'RUNNING',tasks:[]},artifacts:[],events:[],resourceUses:[]});
  return ok({items:[],enabled:false});
 });return s;
}
test('empty pending inbox uses authorized directory without traversing history',async({page})=>{
 const s=await fixture(page);await page.goto('/attention');await expect(page.locator('.f3-work-inbox')).toBeVisible();await expect(page.getByText('已读记录先行展示，正在继续核对其余会话；数量尚未完整。',{exact:true})).toHaveCount(0);expect(s.reads.filter(p=>/work-links|\/journey|prepared-executions/.test(p))).toEqual([]);expect(s.reads.filter(p=>p.includes('/current-work?'))).toHaveLength(1);expect(s.writes).toEqual([]);
});
test('all pending pages retain exact questions and original conversations',async({page})=>{
 const s=await fixture(page);s.count=27;await page.goto('/attention');await expect(page.locator('.f3-work-decision')).toHaveCount(27);await expect(page.getByRole('link',{name:'在原会话回答',exact:true}).last()).toHaveAttribute('href','/work?conversation=c27');expect(s.reads.filter(p=>p.includes('/current-work?'))).toHaveLength(2);expect(s.reads.filter(p=>p.endsWith('/native-progress'))).toHaveLength(27);expect(s.writes).toEqual([]);
});
test('unknown aggregate and denied exact questions never become complete empty claims',async({page})=>{
 const s=await fixture(page);s.count=1;s.complete=false;s.deny=true;await page.goto('/attention');await expect(page.getByText('部分关联记录当前未能读取。',{exact:false})).toBeVisible();await expect(page.locator('.f3-work-decision')).toHaveCount(0);expect(s.writes).toEqual([]);
});
test('failed continuation does not silently truncate pending questions',async({page})=>{
 const s=await fixture(page);s.count=26;s.failPage=true;await page.goto('/attention');await expect(page.getByRole('heading',{name:'当前工作暂不可读'})).toBeVisible();await expect(page.locator('.f3-work-decision')).toHaveCount(0);expect(s.writes).toEqual([]);
});
test('identity change withdraws pending inbox',async({page})=>{
 const s=await fixture(page);s.count=1;s.changeScope=true;await page.goto('/attention');await expect(page.getByRole('heading',{name:'当前工作暂不可读'})).toBeVisible();await expect(page.locator('.f3-work-decision')).toHaveCount(0);expect(s.reads.filter(p=>p.includes('/prepared-executions/'))).toEqual([]);
});
test('handled tab preserves answered terminal history and pending tab does not reuse it',async({page})=>{
 const s=await fixture(page);s.history=true;await page.goto('/attention');await expect(page.locator('.f3-work-inbox')).toBeVisible();await page.getByRole('button',{name:'已处理',exact:true}).click();await expect(page.getByText('已回答：已选择生产规范',{exact:true})).toBeVisible();await expect(page.getByRole('link',{name:'查看原处理记录',exact:true})).toHaveAttribute('href','/work?conversation=c1');await page.getByRole('button',{name:'待你处理',exact:true}).click();await expect(page.getByText('已回答：已选择生产规范',{exact:true})).toHaveCount(0);await expect(page.locator('.f3-work-inbox')).toBeVisible();expect(s.writes).toEqual([]);
});
test('switching to handled cancels a pending continuation and ignores its late response',async({page})=>{
 const s=await fixture(page);s.count=26;let entered=false,release!:()=>void;const held=new Promise<void>(resolve=>{release=resolve});
 await page.route('**/current-work?*',async route=>{if(new URL(route.request().url()).searchParams.get('cursor')){entered=true;await held}return route.fallback()});
 try{await page.goto('/attention');await expect.poll(()=>entered).toBe(true);await expect(page.locator('.f3-work-decision')).toHaveCount(25);s.history=true;await page.getByRole('button',{name:'已处理',exact:true}).click();await expect(page.getByText('已回答：已选择生产规范',{exact:true})).toBeVisible();release();await expect(page.locator('.f3-work-decision')).toHaveCount(1);await expect(page.getByRole('button',{name:'已处理',exact:true})).toHaveAttribute('aria-pressed','true');expect(s.writes).toEqual([])}finally{release()}
});
test('unknown empty coverage is visibly incomplete',async({page})=>{
 const s=await fixture(page);s.complete=false;await page.goto('/attention');await expect(page.getByText('部分关联记录当前未能读取。',{exact:false})).toBeVisible();await expect(page.locator('.f3-work-decision')).toHaveCount(0);expect(s.reads.filter(p=>p.includes('/prepared-executions/'))).toEqual([]);expect(s.writes).toEqual([]);
});
test('background reread retains the current question until refreshed data arrives',async({page})=>{
 const s=await fixture(page);s.count=1;await page.clock.install();let reads=0,release!:()=>void;const held=new Promise<void>(resolve=>{release=resolve});
 await page.route('**/current-work?*',async route=>{reads++;if(reads===2)await held;return route.fallback()});
 try{await page.goto('/attention');await expect(page.getByText('请确认规范 1',{exact:true})).toBeVisible();await page.clock.runFor(10001);await expect.poll(()=>reads).toBe(2);await expect(page.getByText('请确认规范 1',{exact:true})).toBeVisible();await expect(page.getByRole('link',{name:'在原会话回答',exact:true})).toHaveAttribute('href','/work?conversation=c1');expect(s.writes).toEqual([])}finally{release()}
});
test('an initially empty inbox discovers a later question through read-only refresh',async({page})=>{
 const s=await fixture(page);await page.clock.install();await page.goto('/attention');await expect(page.locator('.f3-work-inbox')).toBeVisible();await expect(page.locator('.f3-work-decision')).toHaveCount(0);s.count=1;await page.clock.runFor(10001);await expect(page.getByText('请确认规范 1',{exact:true})).toBeVisible();expect(s.reads.filter(p=>p.includes('/current-work?'))).toHaveLength(2);expect(s.writes).toEqual([]);
});
test('handled history reads every page and retains terminal answers and exact origins',async({page})=>{
 const s=await fixture(page);s.history=true;s.historyCount=27;await page.goto('/attention?filter=done');await expect(page.locator('.f3-work-decision')).toHaveCount(27);await expect(page.getByRole('link',{name:'查看原处理记录',exact:true}).last()).toHaveAttribute('href','/work?conversation=c27');expect(s.reads.filter(p=>p.includes('/current-work?'))).toHaveLength(2);expect(s.reads.filter(p=>p.endsWith('/native-progress'))).toHaveLength(27);expect(s.reads.filter(p=>p.endsWith('/problems'))).toEqual([]);expect(s.writes).toEqual([]);
});
test('unknown terminal answer coverage is not a successful empty history',async({page})=>{
 const s=await fixture(page);s.historyComplete=false;await page.goto('/attention?filter=done');await expect(page.getByText('部分关联记录当前未能读取。',{exact:false})).toBeVisible();await expect(page.locator('.f3-work-decision')).toHaveCount(0);expect(s.writes).toEqual([]);
});
