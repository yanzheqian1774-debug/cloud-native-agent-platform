import {test,expect,type Page} from '@playwright/test';
test.use({viewport:{width:1440,height:1000}});
const digest=(i:number)=>i.toString(16).padStart(64,'0');
async function fixture(page:Page){
 const s={conflict:false,accepted:false,unavailable:false,canAccept:true,loseResponse:false,version:0,event:null as Record<string,unknown>|null,receipts:{} as Record<string,unknown>,humanReview:undefined as Record<string,unknown>|undefined,count:1,complete:true,deny:false,failPage:false,changeScope:false,principal:'human:alice',history:true,historyCount:1,historyComplete:true,wrongRun:false,wrongProblem:false,reads:[] as string[],writes:[] as string[]};
 await page.route('**/api/**',async route=>{
  const req=route.request(),u=new URL(req.url()),p=u.pathname;s.reads.push(p+u.search);
  if(req.method()==='POST'&&p.endsWith('/delivery-acceptance')){
 s.writes.push(p);const body=req.postDataJSON();if(s.conflict){s.conflict=false;return route.fulfill({status:409,json:{reasonCode:'DELIVERY_TARGET_CHANGED'}})}s.accepted=body.action==='ACCEPT_DELIVERY';s.version++;s.event={eventId:'event:'+s.version,commandKey:body.idempotencyKey,commandDigest:'f'.repeat(64),preparationDigest:digest(1),workflowRunId:'run:1',packageDigest:'d'.repeat(64),version:s.version,action:body.action,targetEventId:body.targetEventId,actorId:s.principal,reason:body.reason,createdAt:'2026-11-20T00:00:00Z'};s.receipts[body.idempotencyKey]={event:s.event};if(s.loseResponse){s.loseResponse=false;return route.abort()}return route.fulfill({json:{result:{event:s.event}}});}
 if(req.method()!=='GET'){s.writes.push(p);return route.abort()}
 if(p.includes('/delivery-acceptance/commands/'))return route.fulfill({json:{result:s.receipts[decodeURIComponent(p.split('/').at(-1)!)]}});
  const ok=(result:unknown)=>route.fulfill({json:{result}});
  if(p.endsWith('/session'))return route.fulfill({json:{principal:{principalId:s.principal,tenantId:'fixture',securityDomain:'isolated'},session:{expiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(p.endsWith('/current-work')){
   const answered=true,count=s.count;
   if(u.searchParams.get('state')!=='all'||u.searchParams.get('scopeFilter')!=='visible')throw Error('Wrong directory scope');
   const start=Number(u.searchParams.get('cursor')??0);if(start&&s.failPage)return route.fulfill({status:503,json:{reasonCode:'UNAVAILABLE'}});
   const principal=s.principal;if(s.changeScope)s.principal='human:bob';
   return ok({schemaVersion:'current-work-directory.v1',subject:principal,tenantId:'fixture',securityDomain:'isolated',scopeFilter:'visible',complete:true,questionStatusComplete:s.complete,answerHistoryComplete:s.historyComplete,readAt:'2026-11-12T00:00:00Z',total:count,counts:answered?{completed:count}:{waiting:count},items:Array.from({length:Math.max(0,Math.min(25,count-start))},(_,i)=>({workflowRunId:'run:'+(start+i+1),preparationDigest:digest(start+i+1),title:'合成交付检查 '+(start+i+1),createdAt:'2026-11-11T00:00:00Z',executionState:answered?'SUCCEEDED':'RUNNING',displayState:answered?'completed':'waiting',pendingQuestionCount:answered?0:1,answeredQuestionCount:answered?1:0,problemId:'p'+(start+i+1),problemRevisionId:'r1',problemDigest:'a'.repeat(64),originConversationId:'c'+(start+i+1),originVerified:true})),nextCursor:start+25<count?String(start+25):null});
  }
  if(p.endsWith('/conversations/capabilities'))return ok({enabled:true});
  if(p.endsWith('/conversations'))return ok({items:s.history?[{conversation_id:'c1',title:'历史检查'}]:[]});
  if(p.endsWith('/problems'))return route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
  const problem=p.match(/\/problems\/p(\d+)$/);if(problem)return ok({problem:{business_problem_id:'p'+problem[1]},revisions:[{business_problem_id:'p'+problem[1],revision_id:'r1',digest:'a'.repeat(64),title:'合成交付检查 '+problem[1]}]});
  const journey=p.match(/\/conversations\/c(\d+)\/journey$/);if(journey)return ok({state:{execution:digest(Number(journey[1]))}});
  const links=p.match(/\/conversations\/c(\d+)\/work-links$/);if(links)return ok({conversation:{conversation_id:'c'+links[1]},links:[{readable:true,target:{problemId:'p'+links[1],executionDigest:digest(Number(links[1]))}}]});
  const native=p.match(/\/prepared-executions\/([0-9a-f]+)\/native-progress$/);if(native){if(s.deny)return route.fulfill({status:403,json:{reasonCode:'DENIED'}});return ok({questions:[{questionKey:native[1],questionDigest:'b'.repeat(64),question:'请确认规范 '+parseInt(native[1],16),expiresAt:'2099-01-01',answer:s.history?'已选择生产规范':null,expired:false}]})}
  const execution=p.match(/\/prepared-executions\/([0-9a-f]+)$/);if(execution){if(s.deny)return route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});return ok({digest:execution[1],workflowRunId:s.wrongRun?'wrong':'run:'+parseInt(execution[1],16),executionStarted:true,admission:{state:'ADMITTED'},deliveryAcceptance:s.unavailable?{status:'UNAVAILABLE'}:{status:s.accepted?'ACCEPTED':s.version?'RETRACTED':'NOT_RECORDED',packageDigest:'d'.repeat(64),version:s.version,event:s.event,canAccept:s.canAccept&&!s.accepted,canRetract:s.accepted,package:{preparationDigest:execution[1],workflowRunId:'run:'+parseInt(execution[1],16),limitations:['SYNTHETIC_ONLY','REAL_BUSINESS_OUTCOME_UNPROVEN'],snapshot:{artifacts:[{artifact_id:'artifact:1',digest:'b6ce788d9786917c9d19adaa0d904213365607c7f683d7277f508dcf142b4cc2'}]}}},humanReview:s.humanReview,outcome:s.humanReview?.status==='READABLE'?{confirmationId:'confirmation',businessResolution:'UNDETERMINED'}:null,preparation:{plan_version:1,plan_id:'plan',source_snapshot:{resource_id:'source',revision_id:'r1',digest:'c'.repeat(64)},participants:[],semantics:{title:'检查',tasks:[],target:{problem:{resource_id:s.wrongProblem?'wrong':'p'+parseInt(execution[1],16),revision_id:'r1',digest:'a'.repeat(64)}}}},progress:{state:s.history?'SUCCEEDED':'RUNNING',tasks:[]},artifacts:[{artifact_id:'artifact:1',task_id:'t1',kind:'REPORT',schema_version:'report.v1',contentAccess:'AUTHORIZED',bytes:6,created_at:'2026-11-20T00:00:00Z',content:'Report',digest:'b6ce788d9786917c9d19adaa0d904213365607c7f683d7277f508dcf142b4cc2'}],events:[],resourceUses:[]})}
  return ok({items:[],enabled:false});
 });return s;
}


async function open(page:Page){await page.goto('/outcomes?filter=stage');await page.getByRole('button',{name:'阅读成果与依据',exact:true}).click();await page.getByRole('button',{name:'成果与记录',exact:true}).click();}
test('optional accept and retract leave stage unchanged',async({page},testInfo)=>{
 const s=await fixture(page);await open(page);const area=page.getByRole('region',{name:'本次交付接受'});await expect(area).toContainText('不代表业务问题已解决或批准上线');await page.screenshot({path:testInfo.outputPath('delivery-optional.png'),fullPage:true});await area.getByRole('button',{name:'接受本次交付',exact:true}).click();await expect(area).toContainText('已接受本次交付');await page.reload();await expect(area).toContainText('已接受本次交付');await page.getByRole('button',{name:'返回成果与记录',exact:true}).click();await page.getByRole('button',{name:'已确认成果',exact:true}).click();await expect(page.locator('.f3-work-result')).toHaveCount(1);await page.getByRole('button',{name:'阅读成果与依据',exact:true}).click();await area.getByText('撤回本次接受',{exact:true}).click();await area.getByLabel('撤回理由').fill('保留阶段记录');await area.getByRole('button',{name:'撤回接受',exact:true}).click();await expect(area).toContainText('已撤回接受');await page.getByRole('button',{name:'返回成果与记录',exact:true}).click();await expect(page.locator('.f3-work-result')).toHaveCount(0);await page.getByRole('button',{name:'阶段与执行记录',exact:true}).click();await expect(page.locator('.f3-work-result')).toHaveCount(1);expect(s.writes).toHaveLength(2);
});
test('lost response refresh reads receipt without new POST',async({page})=>{
 const s=await fixture(page);s.loseResponse=true;await open(page);const area=page.getByRole('region',{name:'本次交付接受'});await area.getByRole('button',{name:'接受本次交付',exact:true}).click();await expect(area.getByRole('button',{name:'读取原接受结果'})).toBeVisible();await page.reload();await area.getByRole('button',{name:'读取原接受结果'}).click();await expect(area).toContainText('已接受本次交付');expect(s.writes).toHaveLength(1);expect(s.reads.some(x=>x.includes('/delivery-acceptance/commands/'))).toBeTruthy();
});
for(const mode of ['readonly','unavailable'])test('no write for '+mode,async({page})=>{
 const s=await fixture(page);s.canAccept=false;s.unavailable=mode==='unavailable';await open(page);const area=page.getByRole('region',{name:'本次交付接受'});await expect(area.getByRole('button',{name:'接受本次交付',exact:true})).toHaveCount(0);if(s.unavailable)await expect(area).toContainText('不能据此判断是否已接受');expect(s.writes).toEqual([]);
});

test('unknown receipt remains pending without another command',async({page})=>{
 const s=await fixture(page);s.loseResponse=true;await open(page);const area=page.getByRole('region',{name:'本次交付接受'});await area.getByRole('button',{name:'接受本次交付',exact:true}).click();await expect(area.getByRole('button',{name:'读取原接受结果'})).toBeVisible();s.receipts={};await page.reload();await area.getByRole('button',{name:'读取原接受结果'}).click();await expect(area.getByRole('button',{name:'读取原接受结果'})).toBeVisible();await expect(area.getByRole('button',{name:'接受本次交付',exact:true})).toHaveCount(0);expect(s.writes).toHaveLength(1);
});
test('new artifact package never inherits an old acceptance',async({page})=>{
 const s=await fixture(page);await open(page);const area=page.getByRole('region',{name:'本次交付接受'});await area.getByRole('button',{name:'接受本次交付',exact:true}).click();await expect(area).toContainText('已接受本次交付');s.event={...s.event,packageDigest:'0'.repeat(64)};await page.reload();await expect(area).toContainText('不能据此判断是否已接受');await page.getByRole('button',{name:'返回成果与记录',exact:true}).click();await page.getByRole('button',{name:'已确认成果',exact:true}).click();await expect(page.locator('.f3-work-result')).toHaveCount(0);expect(s.writes).toHaveLength(1);
});

test('definite stale CAS refreshes without automatically retrying',async({page})=>{
 const s=await fixture(page);s.conflict=true;await open(page);const area=page.getByRole('region',{name:'本次交付接受'});await area.getByRole('button',{name:'接受本次交付',exact:true}).click();await expect(area).toContainText('本次提交未生效');await expect(area.getByRole('button',{name:'接受本次交付',exact:true})).toBeEnabled();expect(s.writes).toHaveLength(1);await area.getByRole('button',{name:'接受本次交付',exact:true}).click();await expect(area).toContainText('已接受本次交付');expect(s.writes).toHaveLength(2);
});
