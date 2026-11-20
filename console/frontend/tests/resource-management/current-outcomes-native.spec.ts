import {test,expect,type Page} from '@playwright/test';
const digest=(i:number)=>i.toString(16).padStart(64,'0');
async function fixture(page:Page){
 const s={count:1,complete:true,deny:false,failPage:false,changeScope:false,principal:'human:alice',history:true,historyCount:1,historyComplete:true,wrongRun:false,wrongProblem:false,reads:[] as string[],writes:[] as string[]};
 await page.route('**/api/**',async route=>{
  const req=route.request(),u=new URL(req.url()),p=u.pathname;s.reads.push(p+u.search);
  if(req.method()!=='GET'){s.writes.push(p);return route.abort()}
  const ok=(result:unknown)=>route.fulfill({json:{result}});
  if(p.endsWith('/session'))return route.fulfill({json:{principal:{principalId:s.principal,tenantId:'fixture',securityDomain:'isolated'},session:{expiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(p.endsWith('/current-work')){
   const answered=true,count=s.count;
   if(u.searchParams.get('state')!=='all'||u.searchParams.get('scopeFilter')!=='visible')throw Error('Wrong directory scope');
   const start=Number(u.searchParams.get('cursor')??0);if(start&&s.failPage)return route.fulfill({status:503,json:{reasonCode:'UNAVAILABLE'}});
   const principal=s.principal;if(s.changeScope)s.principal='human:bob';
   return ok({schemaVersion:'current-work-directory.v1',subject:principal,tenantId:'fixture',securityDomain:'isolated',scopeFilter:'visible',complete:true,questionStatusComplete:s.complete,answerHistoryComplete:s.historyComplete,readAt:'2026-11-12T00:00:00Z',total:count,counts:answered?{completed:count}:{waiting:count},items:Array.from({length:Math.max(0,Math.min(25,count-start))},(_,i)=>({workflowRunId:'run:'+(start+i+1),preparationDigest:digest(start+i+1),title:'待答检查 '+(start+i+1),createdAt:'2026-11-11T00:00:00Z',executionState:answered?'SUCCEEDED':'RUNNING',displayState:answered?'completed':'waiting',pendingQuestionCount:answered?0:1,answeredQuestionCount:answered?1:0,problemId:'p'+(start+i+1),problemRevisionId:'r1',problemDigest:'a'.repeat(64),originConversationId:'c'+(start+i+1),originVerified:true})),nextCursor:start+25<count?String(start+25):null});
  }
  if(p.endsWith('/conversations/capabilities'))return ok({enabled:true});
  if(p.endsWith('/conversations'))return ok({items:s.history?[{conversation_id:'c1',title:'历史检查'}]:[]});
  if(p.endsWith('/problems'))return route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
  const problem=p.match(/\/problems\/p(\d+)$/);if(problem)return ok({problem:{business_problem_id:'p'+problem[1]},revisions:[{business_problem_id:'p'+problem[1],revision_id:'r1',digest:'a'.repeat(64),title:'待答检查 '+problem[1]}]});
  const journey=p.match(/\/conversations\/c(\d+)\/journey$/);if(journey)return ok({state:{execution:digest(Number(journey[1]))}});
  const links=p.match(/\/conversations\/c(\d+)\/work-links$/);if(links)return ok({conversation:{conversation_id:'c'+links[1]},links:[{readable:true,target:{problemId:'p'+links[1],executionDigest:digest(Number(links[1]))}}]});
  const native=p.match(/\/prepared-executions\/([0-9a-f]+)\/native-progress$/);if(native){if(s.deny)return route.fulfill({status:403,json:{reasonCode:'DENIED'}});return ok({questions:[{questionKey:native[1],questionDigest:'b'.repeat(64),question:'请确认规范 '+parseInt(native[1],16),expiresAt:'2099-01-01',answer:s.history?'已选择生产规范':null,expired:false}]})}
  const execution=p.match(/\/prepared-executions\/([0-9a-f]+)$/);if(execution){if(s.deny)return route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});return ok({digest:execution[1],workflowRunId:s.wrongRun?'wrong':'run:'+parseInt(execution[1],16),executionStarted:true,admission:{state:'ADMITTED'},outcome:null,preparation:{plan_version:1,plan_id:'plan',source_snapshot:{resource_id:'source',revision_id:'r1',digest:'c'.repeat(64)},participants:[],semantics:{title:'检查',tasks:[],target:{problem:{resource_id:s.wrongProblem?'wrong':'p'+parseInt(execution[1],16),revision_id:'r1',digest:'a'.repeat(64)}}}},progress:{state:s.history?'SUCCEEDED':'RUNNING',tasks:[]},artifacts:[],events:[],resourceUses:[]})}
  return ok({items:[],enabled:false});
 });return s;
}

test('ordinary stage outcomes use exact directory with legacy LIST denied; accepted stays unconnected',async({page})=>{
 const s=await fixture(page);await page.goto('/outcomes');await expect(page.getByText('成果验收状态尚未接通。',{exact:false})).toBeVisible();
 await page.getByRole('button',{name:'阶段与执行记录',exact:true}).click();await expect(page.locator('.f3-work-result')).toHaveCount(1);
 await page.getByLabel('搜索工作',{exact:false}).fill('待答检查');await page.getByRole('button',{name:'阅读成果与依据',exact:true}).click();
 await expect(page.getByRole('heading',{name:'成果预览',exact:true})).toBeVisible();await expect(page.getByRole('link',{name:'回到原会话',exact:true})).toHaveAttribute('href','/work?conversation=c1');
 await page.getByRole('button',{name:'返回成果与记录',exact:true}).click();await expect(page.getByLabel('搜索工作',{exact:false})).toHaveValue('待答检查');await expect(page.locator('.f3-work-result')).toHaveCount(1);
 await page.reload();await expect(page.locator('.f3-work-result')).toHaveCount(1);expect(s.reads.filter(p=>p.endsWith('/problems'))).toEqual([]);expect(s.writes).toEqual([]);
});
test('outcomes read every authorized directory page',async({page})=>{
 const s=await fixture(page);s.count=27;await page.goto('/outcomes?filter=stage');await expect(page.locator('.f3-work-result')).toHaveCount(27);expect(s.reads.filter(p=>p.includes('/current-work?'))).toHaveLength(2);expect(s.writes).toEqual([]);
});
for(const mode of ['deny','wrongRun','wrongProblem'] as const)test('unverified outcome omitted with visible partial notice '+mode,async({page})=>{
 const s=await fixture(page);s[mode]=true;await page.goto('/outcomes?filter=stage');await expect(page.getByText('部分关联记录当前未能读取。',{exact:false})).toBeVisible();await expect(page.locator('.f3-work-result')).toHaveCount(0);expect(s.writes).toEqual([]);
});
test('page failure does not masquerade as complete outcome list',async({page})=>{
 const s=await fixture(page);s.count=26;s.failPage=true;await page.goto('/outcomes?filter=stage');await expect(page.getByRole('heading',{name:'当前工作暂不可读'})).toBeVisible();await expect(page.locator('.f3-work-result')).toHaveCount(0);expect(s.writes).toEqual([]);
});
test('account change discards outcomes before content reads',async({page})=>{
 const s=await fixture(page);s.changeScope=true;await page.goto('/outcomes?filter=stage');await expect(page.getByRole('heading',{name:'当前工作暂不可读'})).toBeVisible();expect(s.reads.filter(p=>p.includes('/prepared-executions/'))).toEqual([]);expect(s.writes).toEqual([]);
});
