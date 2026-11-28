import ts from 'typescript';
import {readFileSync} from 'node:fs';
import {test,expect,type Page} from '@playwright/test';
const pending:(()=>void)[]=[];
function gate(){let release=()=>{};const promise=new Promise<void>(done=>{release=done});pending.push(release);return {promise,release}}
test.afterEach(()=>{pending.splice(0).forEach(release=>release())});
async function fixture(page:Page,count=3){
 page.on('pageerror',error=>console.log('FIXTURE_BROWSER_ERROR',error.message));
 const state={secondSource:false,secondRestored:false,historyResult:{available:false,items:[] as {state:string}[]},historyFailure:0,historyRestores:false,restricted:false,count,paging:true,availabilityFailure:0,availabilityOverride:null as null|boolean|string,capabilitySource:null as Record<string,unknown>|null,malformedPage:false,messageFailure:0,initialAdoption:false,denied:false,principal:'human:ordinary',loggedOut:false,unauthorized:false,requests:[] as string[],writes:[] as string[],sessionRequests:0,activeSessions:0,maxSessions:0,capability:gate(),links:gate(),history:gate(),source:gate(),session:gate(),delaySession:false,delayAlpha:false,alpha:gate(),delayOlder:false,older:gate(),sourceFailure:false,sourceMessage:false,routing:false,goalSlots:false};
 const head=(id:string)=>({conversation_id:id,title:'合成历史 '+id,version:state.count,created_at:'2026-11-01T00:00:00Z'});
 const message=(id:string,n:number)=>({message_id:id+'-'+n,sequence:n,author_id:'human:ordinary',content:`${id}消息${n}：保留原文与已提交记录。\n`+'用于阅读位置验证的合成内容。'.repeat(8),disposition:'RECORDED',created_at:'2026-11-01T00:00:00Z'});
 await page.route('**/api/**',async route=>{
  const request=route.request(),url=new URL(request.url()),path=url.pathname,method=request.method();if(!path.startsWith('/api/'))return route.continue();state.requests.push(method+' '+path+url.search);if(method!=='GET')state.writes.push(path);
  const result=(value:unknown)=>route.fulfill({json:{result:value}}).catch(()=>{});
  if(path.endsWith('/session')){
   if(method==='DELETE'){state.loggedOut=true;return route.fulfill({status:204}).catch(()=>{})}
   state.sessionRequests++;state.activeSessions++;state.maxSessions=Math.max(state.maxSessions,state.activeSessions);if(state.delaySession)await state.session.promise;state.activeSessions--;
   if(state.loggedOut)return route.fulfill({status:401,json:{reasonCode:'SESSION_EXPIRED'}}).catch(()=>{});
   return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:state.principal,tenantId:'tenant',securityDomain:'domain'},csrfToken:'synthetic-csrf',session:{expiresAt:'2027-01-01',idleExpiresAt:'2027-01-01'}}}).catch(()=>{});
  }
  if(path.endsWith('/development-administrator'))return result({enabled:false});
  if(path.endsWith('/draft-assistance/capabilities')){await state.capability.promise;return result({conversationUnderstanding:state.routing,conversationRelationRouting:state.routing,initialUnderstandingAdoption:state.initialAdoption})}
  if(path.endsWith('/conversations/capabilities')){if(state.availabilityFailure)return route.fulfill({status:state.availabilityFailure,json:{reasonCode:'CAPABILITIES_UNAVAILABLE'}});return result({enabled:true,historyMessagePaging:state.availabilityOverride??(state.paging?true:undefined),historyReadPreparation:true,conversationGoalSlots:state.goalSlots});}
  if(path.endsWith('/test-resource-access/status'))return result({available:true});
  if(path.includes('/test-resource-access/'))return result({state:'UNKNOWN'});
  if(path.endsWith('/conversations'))return result({items:[]});
  if(path.endsWith('/problems'))return result({problems:[]});
  const identity=path.match(/\/conversations\/([^/]+)\//)?.[1]??'alpha';
  if(path.endsWith('/history-access')){await state.history.promise;if(state.historyFailure)return route.fulfill({status:state.historyFailure,json:{reasonCode:'READ_RESTORE_DENIED'}});if(state.historyRestores)state.restricted=false;return result(state.historyResult)}
  if(path.endsWith('/capability-context'))return result({conversation:head(identity),message:state.capabilitySource});
  if(path.endsWith('/understanding-successes'))return result({conversation:head(identity),items:[],page:{hasMore:false,nextCursor:null,resumeCursor:null},unavailable:false});
  if(!state.paging&&/^\/api\/workbench\/v1\/conversations\/[^/]+$/.test(path))return state.denied?route.fulfill({status:403,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}}):result({conversation:head(identity),messages:Array.from({length:state.count},(_,i)=>message(identity,i+1)),links:[]});
  if(path.endsWith('/sources/cap-original/journey'))return result({version:1,contractDigest:'e'.repeat(64),sourceMessageId:'cap-original',state:{phase:'PREPARE_PLAN',problemId:'p'}});
  if(path.endsWith('/work-links')){await state.links.promise;return result({conversation:head(identity),links:[]})}
  if(path.endsWith('/messages')&&method==='GET'){
   if(state.malformedPage)return result({items:[]});
   if(state.messageFailure)return route.fulfill({status:state.messageFailure,json:{reasonCode:'PAGE_READ_DENIED'}});
   const restrictedAtRead=state.restricted,principalAtRead=state.principal,before=url.searchParams.get('before');if(identity==='alpha'&&state.delayAlpha&&!before)await state.alpha.promise;if(before&&state.delayOlder)await state.older.promise;
   if(state.denied)return route.fulfill({status:403,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}}).catch(()=>{});
   if(state.unauthorized||principalAtRead!=='human:ordinary')return route.fulfill({status:401,json:{reasonCode:'SESSION_EXPIRED'}}).catch(()=>{});
   const ceiling=before?Number(before.split(':')[0].replace('ceiling','')):state.count,start=before?Number(before.split(':')[1]):ceiling+1,low=Math.max(1,start-50),high=start-1;
   const messages=Array.from({length:Math.max(0,high-low+1)},(_,index)=>message(identity,low+index));
   if(before&&messages.length)messages.push(message(identity,start)); // A repeat at the boundary must not duplicate a row.
   if(state.sourceMessage&&high===count){messages[messages.length-1]={...message(identity,count),kind:'SOURCE',content:'已保存的独立答复正文',facts:{assistantResponse:true,state:'SUCCEEDED',source:{kind:'DRAFT',invocationId:'synthetic'},response:{resultKind:'DIRECT_ANSWER',inputSource:{source:{resource_id:'knowledge:synthetic',revision_id:'revision:fixed',digest:'a'.repeat(64)},name:'合成资料',sourceSchema:'synthetic',sourceContentDigest:'b'.repeat(64)}}}} as typeof messages[number]}
   if(state.secondSource)messages[messages.length-2]={...message(identity,count-1),kind:'SOURCE',content:state.secondRestored?'另一条原助手答复正文':'另一条历史回复读取受限',facts:state.secondRestored?{assistantResponse:true,state:'SUCCEEDED',source:{kind:'DRAFT',invocationId:'second-original'},response:{resultKind:'DIRECT_ANSWER'}}:{assistantResponse:true,readable:false,readState:'ACCESS_RESTRICTED'}} as typeof messages[number];
   if(state.sourceMessage&&restrictedAtRead)messages[messages.length-1]={...message(identity,count),kind:'SOURCE',content:'当前回复读取受限',facts:{assistantResponse:true,readable:false,readState:'ACCESS_RESTRICTED'}} as typeof messages[number];
   return result({conversation:head(identity),messages,page:{hasMore:low>1,nextCursor:low>1?'ceiling'+ceiling+':'+low:null,resumeCursor:before??'ceiling'+ceiling+':'+start}});
  }
  if(path.endsWith('/journey'))return result({version:0,state:null});
  if(path.endsWith('/head'))return result({conversation:head(identity)});
  if(path.includes('/resource-directory/knowledge/')){await state.source.promise;return route.fulfill({status:state.sourceFailure?503:403,json:{reasonCode:'SOURCE_UNAVAILABLE'}}).catch(()=>{})}
  if(method!=='GET')return route.fulfill({status:405,json:{reasonCode:'UNEXPECTED_WRITE'}}).catch(()=>{});
  return result({items:[]});
 });
 return state;
}
async function current(page:Page,id='alpha',n=3){await expect(page.locator('#conversation-message-'+id+'-'+n)).toBeVisible()}
async function switchConversation(page:Page,id:string){await page.evaluate(value=>{history.pushState({},'', '/work?conversation='+value);window.dispatchEvent(new PopStateEvent('popstate'))},id)}

test('short messages appear while capability links and precise history restoration are pending; no inventory warming',async({page})=>{
 const state=await fixture(page);await page.goto('/work?conversation=alpha');await current(page);expect(state.requests.some(path=>path.includes('/draft-assistance/capabilities'))).toBe(true);expect(state.requests.some(path=>path.includes('/work-links'))).toBe(true);expect(state.requests.filter(path=>path.includes('/test-resource-access/'))).toEqual([]);expect(state.writes.every(path=>path.endsWith('/history-access'))).toBe(true);await page.locator('#private-input').fill('保留等待接续核对的输入');await expect(page.getByRole('button',{name:'发送',exact:true})).toBeDisabled();
 await expect(page.getByRole('button',{name:'读取更早消息',exact:true})).toHaveCount(0);await page.screenshot({path:'../../../history-short-desktop.png',fullPage:true});state.capability.release();state.links.release();state.history.release();
});

test('older pages keep order deduplicate and retain anchor draft and the messages tab',async({page})=>{
 const state=await fixture(page,120);state.links.release();state.history.release();state.capability.release();await page.goto('/work?conversation=alpha');await current(page,'alpha',120);await expect(page.locator('.private-message')).toHaveCount(50);
 await page.locator('#private-input').fill('未发送的原草稿');state.delayOlder=true;const stream=page.locator('.px-message-stream');await stream.evaluate(node=>{node.dispatchEvent(new WheelEvent('wheel',{deltaY:-100,bubbles:true}));node.scrollTop=0});
 await expect.poll(()=>state.requests.filter(path=>path.includes('before=')).length).toBe(1);const old=page.locator('#conversation-message-alpha-71'),before=await old.evaluate(node=>node.getBoundingClientRect().top);state.older.release();await expect(page.locator('.private-message')).toHaveCount(100);await expect.poll(async()=>Math.abs((await old.evaluate(node=>node.getBoundingClientRect().top))-before)).toBeLessThan(4);const ids=await page.locator('.private-message').evaluateAll(nodes=>nodes.map(node=>Number(node.getAttribute('data-message-id')!.split('-').at(-1))));expect(ids).toEqual(Array.from({length:100},(_,i)=>i+21));await expect(page.locator('#private-input')).toHaveValue('未发送的原草稿');await expect(page.getByRole('button',{name:'会话消息',exact:true})).toHaveAttribute('aria-pressed','true');
 await stream.evaluate(node=>{node.dispatchEvent(new WheelEvent('wheel',{deltaY:-100,bubbles:true}));node.scrollTop=0});await expect(page.locator('.private-message')).toHaveCount(120);expect(state.requests.filter(path=>path.includes('messages?')&&path.includes('before='))).toHaveLength(2);expect(state.requests.filter(path=>path.includes('/test-resource-access/'))).toEqual([]);
});

test('slow then failed exact source reading leaves saved answer readable on mobile',async({page})=>{
 const state=await fixture(page);state.sourceMessage=true;state.sourceFailure=true;state.capability.release();state.links.release();state.history.release();await page.setViewportSize({width:390,height:844});await page.goto('/work?conversation=alpha');await expect(page.getByText('已保存的独立答复正文',{exact:true})).toBeVisible();await page.getByText('查看来源与记录',{exact:true}).click();await page.getByRole('button',{name:'查看本次使用的原文',exact:true}).click();await expect(page.getByText('正在核对原资料版本与读取权限…')).toBeVisible();await expect(page.getByText('已保存的独立答复正文',{exact:true})).toBeVisible();state.source.release();await expect(page.getByText('暂时无法读取本次使用的资料版本，可稍后重新读取。原回答保留。')).toBeVisible();await expect(page.getByText('已保存的独立答复正文',{exact:true})).toBeVisible();await page.screenshot({path:'../../../history-source-mobile.png',fullPage:true});
});

test('late alpha response cannot fill beta after conversation switch',async({page})=>{
 const state=await fixture(page);state.delayAlpha=true;state.links.release();state.history.release();state.capability.release();await page.goto('/work?conversation=alpha');await expect.poll(()=>state.requests.filter(path=>path.includes('/alpha/messages?')).length).toBe(1);await switchConversation(page,'beta');await current(page,'beta');state.alpha.release();await expect(page.locator('[data-message-id^="alpha-"]')).toHaveCount(0);await current(page,'beta');
});

test('principal change before an old GET finishes cannot expose old message content',async({page})=>{
 const state=await fixture(page);state.delayAlpha=true;state.links.release();state.history.release();state.capability.release();await page.goto('/work?conversation=alpha');await expect.poll(()=>state.requests.filter(path=>path.includes('/alpha/messages?')).length).toBe(1);state.principal='human:other';state.alpha.release();await expect(page.getByText('当前登录已失效',{exact:true})).toBeVisible();await expect(page.locator('.private-message')).toHaveCount(0);
});

test('401 on a later page clears existing sensitive rows without replaying work',async({page})=>{
 const state=await fixture(page,70);state.links.release();state.history.release();state.capability.release();await page.goto('/work?conversation=alpha');await current(page,'alpha',70);state.unauthorized=true;await page.getByRole('button',{name:'读取更早消息',exact:true}).click();await expect(page.getByText('当前登录已失效',{exact:true})).toBeVisible();await expect(page.locator('.private-message')).toHaveCount(0);expect(state.writes.every(path=>path.endsWith('/history-access'))).toBe(true);
});

test('logout clears message state without replaying work',async({page})=>{
 const state=await fixture(page);state.delaySession=true;state.links.release();state.history.release();state.capability.release();await page.goto('/work?conversation=alpha');await expect.poll(()=>state.sessionRequests).toBe(1);state.session.release();await current(page);expect(state.maxSessions).toBe(1);await page.locator('summary').filter({hasText:'当前账号'}).click();await page.getByRole('button',{name:'退出登录',exact:true}).click();await expect(page.getByText('已退出登录',{exact:true})).toBeVisible();await expect(page.locator('.private-message')).toHaveCount(0);expect(state.sessionRequests).toBeGreaterThan(1);expect(state.writes.filter(path=>!path.endsWith('/history-access'))).toEqual(['/api/workbench/v1/session']);
});


test('actual session reader shares overlapping GETs without retaining a completed identity or cancelling another reader',async({page})=>{
 const state=await fixture(page);state.delaySession=true;
 await page.route('**/session-unit',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><html><body>Isolated session reader test</body></html>'}));await page.goto('/session-unit');
 const original=readFileSync(new URL('../../src/api/businessWorkspace.ts',import.meta.url),'utf8');
 const compiled=ts.transpileModule(original,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText.replace(/import\s*\{\s*modelResult\s*\}\s*from\s*['"]\.\/modelStream['"];?/,"const modelResult=()=>{throw Error('unused model in session test')}");
 await page.evaluate(async code=>{
  const module=await import('data:text/javascript;base64,'+btoa(code)),controller=new AbortController();
  const first=module.readWorkbenchSession(controller.signal).catch((error:Error)=>error.name),second=module.readWorkbenchSession();
  Object.assign(window,{sessionUnit:{controller,first,second,module}});
 },compiled);
 await expect.poll(()=>state.sessionRequests).toBe(1);
 const outcome=await page.evaluate(async()=>{const unit=(window as unknown as {sessionUnit:{controller:AbortController;first:Promise<string>}}).sessionUnit;unit.controller.abort();return unit.first});expect(outcome).toBe('AbortError');state.session.release();
 await page.evaluate(async()=>{const unit=(window as unknown as {sessionUnit:{second:Promise<unknown>;module:{readWorkbenchSession:()=>Promise<unknown>}}}).sessionUnit;await unit.second;await unit.module.readWorkbenchSession()});expect(state.sessionRequests).toBe(2);expect(state.maxSessions).toBe(1);
});

async function executionFixture(page:Page,mode:'TERMINAL'|'AUTOMATIC'|'WAITING',goal=false){
 const base=await fixture(page,goal?120:1);base.routing=true;base.goalSlots=goal;base.capability.release();base.links.release();base.history.release();
 const state={statusReads:0,progressReads:0,accept:[] as string[],evaluated:mode==='TERMINAL'};
 const digest='a'.repeat(64),ref={resource_id:'source',revision_id:'1',digest:'f'.repeat(64)};
 const journal={key:'saved-run',phase:'RUNNING',execution:digest,problem:{business_problem_id:'p'},source:{source:ref,name:'原精确交接资料',sourceSchema:'document-handover-source.v1',synthetic:true},question:'原交接检查指令',userMessageId:'alpha-1',messages:[{id:'user:alpha-1',text:'原交接检查指令'}],log:[]};
 await page.route('**/conversations/alpha/journey',route=>route.fulfill({json:{result:{version:2,state:journal}}}));
 if(goal)await page.route('**/conversations/alpha/goals**',route=>{const path=new URL(route.request().url()).pathname;base.requests.push(route.request().method()+' '+path);if(route.request().method()!=='GET')base.writes.push(path);return route.fulfill({json:{result:path.endsWith('/journey')?{version:2,state:journal,goalId:'original-goal',goalDigest:'c'.repeat(64),rootMessageId:'alpha-1',goalMode:'INDEPENDENT_GOAL'}:{items:[{goalId:'original-goal',goalDigest:'c'.repeat(64),rootMessageId:'alpha-1',title:'原交接检查',createdAt:'2026-11-01T00:00:00Z'}],hasMore:false,nextCursor:null}}})});
 await page.route('**/prepared-executions/**',async route=>{
  const request=route.request(),path=new URL(request.url()).pathname;if(request.method()!=='GET'){base.writes.push(path);return route.fulfill({status:405,json:{reasonCode:'NO_COMMANDS_IN_READ_TEST'}})}
  if(path.endsWith('/native-progress')){
   state.progressReads++;state.accept.push(request.headers().accept??'');
   const q={invocationId:'i',questionKey:'q',questionDigest:'b'.repeat(64),question:'请确认当前检查范围',expiresAt:'2099-01-01T00:00:00Z',answer:null,expired:false};
   const value={result:{runId:'run-1',steps:[],questions:mode==='WAITING'?[q]:[],modelInFlight:false,durableWaits:mode==='WAITING'?[{...q,state:'WAITING_FOR_USER',humanExpiresAt:q.expiresAt,answerSaved:false,stopConfirmed:true}]:[]}};
   if(request.headers().accept==='text/event-stream')return route.fulfill({contentType:'text/event-stream',body:'event: snapshot\ndata: '+JSON.stringify(value)+'\n\n'});
   return route.fulfill({json:value});
  }
  if(!path.endsWith(digest))return route.fulfill({json:{result:{items:[]}}});
  state.statusReads++;
  return route.fulfill({json:{result:{digest,workflowRunId:'run-1',executionStarted:true,admission:{state:'ADMITTED',reason:null},automation:{kind:'READONLY_CONTINUATION',evaluation:'AUTOMATIC',authorizationExpiresAt:'2099-01-01T00:00:00Z'},outcome:state.evaluated?{outcomeId:'o',version:1,evaluationDigest:'e'.repeat(64),businessResolution:'UNDETERMINED',confirmationId:null,evaluation:{evaluationId:'evaluation',results:[]}}:null,preparation:{plan_id:'plan',plan_version:1,plan_digest:'e'.repeat(64),approval_id:'approval',source_snapshot:ref,semantics:{title:'合成交接核对',target:{problem:{resource_id:'p',revision_id:'1',digest:'c'.repeat(64)}},tasks:[]},participants:[]},progress:{state:mode==='WAITING'?'RUNNING':'SUCCEEDED',version:1,cancellation_request_id:null,tasks:[]},artifacts:[],resourceUses:[],events:[]}}});
 });return {base,state};
}

test('completed historical execution stays quiet and explicit read still fetches current records',async({page})=>{
 await page.clock.install();const {base,state}=await executionFixture(page,'TERMINAL');await page.goto('/work?conversation=alpha');await expect(page.getByRole('region',{name:'Native 执行与成果验收'})).toContainText('已保存的工作记录');await expect(page.getByRole('region',{name:'实时执行过程'})).toContainText('执行已结束');await expect.poll(()=>state.progressReads).toBe(1);expect(state.accept).toEqual(['application/json']);
 await page.waitForLoadState('networkidle');const status=state.statusReads,sessions=base.sessionRequests;await page.clock.runFor(12000);expect(state.statusReads).toBe(status);expect(base.sessionRequests).toBe(sessions);expect(state.progressReads).toBe(1);
 await page.getByRole('button',{name:'刷新正式状态',exact:true}).click();await expect.poll(()=>state.statusReads).toBe(status+1);await page.getByRole('button',{name:'重新读取工作步骤',exact:true}).click();await expect.poll(()=>state.progressReads).toBe(2);expect(base.writes.every(path=>path.endsWith('/history-access'))).toBe(true);
});

test('automatic evaluation continues until its real outcome appears then stops',async({page})=>{
 await page.clock.install();const {state}=await executionFixture(page,'AUTOMATIC');await page.goto('/work?conversation=alpha');await expect(page.getByText('执行已结束，标准评价结果将自动读回。')).toBeVisible();const first=state.statusReads;await page.clock.runFor(3500);await expect.poll(()=>state.statusReads).toBeGreaterThan(first);state.evaluated=true;await page.clock.runFor(3500);await expect(page.getByRole('region',{name:'Native 执行与成果验收'})).toContainText('业务结果：');const settled=state.statusReads;await page.clock.runFor(12000);expect(state.statusReads).toBe(settled);
});

test('running execution and necessary question keep their authorized progress stream',async({page})=>{
 await page.clock.install();const {base,state}=await executionFixture(page,'WAITING');await page.goto('/work?conversation=alpha');await expect(page.getByRole('region',{name:'实时执行过程'})).toContainText('原任务已保留');await expect(page.getByRole('note',{name:'当前正在回答的问题'})).toContainText('请确认当前检查范围');const first=state.progressReads;await page.clock.runFor(3500);await expect.poll(()=>state.progressReads).toBeGreaterThan(first);expect(state.accept.every(value=>value==='text/event-stream')).toBe(true);expect(base.writes.every(path=>path.endsWith('/history-access'))).toBe(true);
});

test('inline progress callback parent rerenders cannot trigger repeated initial reads',async({page})=>{
 await page.clock.install();const {state}=await executionFixture(page,'TERMINAL');await page.goto('/tests/history-paging-harness.html');await expect(page.getByTestId('projection')).toContainText('SUCCEEDED');expect(state.statusReads).toBe(1);for(let i=0;i<5;i++)await page.getByRole('button',{name:'父组件刷新',exact:true}).click();await page.clock.runFor(12000);expect(state.statusReads).toBe(1);await page.getByRole('button',{name:'切换查看上下文',exact:true}).click();await expect.poll(()=>state.statusReads).toBe(2);await page.clock.runFor(6000);expect(state.statusReads).toBe(2);
});


test('original Goal root and exact source outside the latest page still resume their saved necessary question',async({page})=>{
 const {base}=await executionFixture(page,'WAITING',true);await page.goto('/work?conversation=alpha&goal=original-goal');await current(page,'alpha',120);await expect(page.locator('#conversation-message-alpha-1')).toHaveCount(0);await expect(page.locator('.private-message')).toHaveCount(50);await expect(page.getByLabel('选择已有工作')).toHaveValue('original-goal');await expect(page.getByRole('note',{name:'当前正在回答的问题'})).toContainText('请确认当前检查范围');expect(base.requests.some(path=>path.includes('/goals/original-goal/journey'))).toBe(true);expect(base.requests.some(path=>/^GET \/api\/workbench\/v1\/conversations\/alpha$/.test(path))).toBe(false);expect(base.writes.every(path=>path.endsWith('/history-access'))).toBe(true);expect(base.requests.some(path=>path.includes('/draft-assistance/invocations'))).toBe(false);
});

async function savedPosition(page:Page){return page.evaluate(()=>Object.entries(sessionStorage).filter(([key])=>key.startsWith('conversation-message-position.v1:')).map(([,raw])=>JSON.parse(raw)).find(value=>value.messageId.startsWith('alpha-')) as {cursor:string;messageId:string;offset:number}|undefined)}
async function readDeepPage(page:Page,state:Awaited<ReturnType<typeof fixture>>){
 await page.goto('/work?conversation=alpha');await current(page,'alpha',120);const stream=page.locator('.px-message-stream');await stream.evaluate(node=>{node.dispatchEvent(new WheelEvent('wheel',{deltaY:-100,bubbles:true}));node.scrollTop=0});await expect(page.locator('.private-message')).toHaveCount(100);
 await page.locator('#conversation-message-alpha-45').evaluate(node=>{const stream=node.closest('.px-message-stream')!;stream.dispatchEvent(new WheelEvent('wheel',{deltaY:-10,bubbles:true}));stream.scrollTop+=node.getBoundingClientRect().top-stream.getBoundingClientRect().top-20});
 await expect.poll(async()=>(await savedPosition(page))?.cursor).toBe('ceiling120:71');expect(state.requests.filter(path=>path.includes('/test-resource-access/'))).toEqual([]);return (await savedPosition(page))!;
}

test('deep return uses only cursor and anchor metadata after new messages push old latest page away',async({page})=>{
 const state=await fixture(page,120);state.capability.release();state.links.release();state.history.release();const saved=await readDeepPage(page,state);await page.locator('#private-input').fill('切回时保留的草稿');await switchConversation(page,'beta');await current(page,'beta',120);state.count=180;
 const before=state.requests.filter(path=>path.includes('/alpha/messages?')).length;await switchConversation(page,'alpha');const anchor=page.locator('[data-message-id="'+saved.messageId+'"]');await expect(anchor).toBeVisible();await expect.poll(()=>anchor.evaluate(node=>node.getBoundingClientRect().top-node.closest('.px-message-stream')!.getBoundingClientRect().top).then(offset=>Math.abs(offset-saved.offset))).toBeLessThan(4);await expect(page.locator('#conversation-message-alpha-180')).toHaveCount(0);expect(state.requests.filter(path=>path.includes('/alpha/messages?')).length-before).toBe(1);await expect(page.locator('#private-input')).toHaveValue('切回时保留的草稿');expect(Object.keys((await savedPosition(page))!).sort()).toEqual(['cursor','messageId','offset']);
 await page.getByRole('button',{name:'读取最新消息',exact:true}).click();await current(page,'alpha',180);await expect(page.locator('#conversation-message-alpha-180')).toBeInViewport();expect(state.requests.some(path=>/^GET \/api\/workbench\/v1\/conversations\/alpha$/.test(path))).toBe(false);
});

test('deep return freshly rejects revoked access before any old body can appear',async({page})=>{
 const state=await fixture(page,120);state.capability.release();state.links.release();state.history.release();await readDeepPage(page,state);await switchConversation(page,'beta');await current(page,'beta',120);state.denied=true;await switchConversation(page,'alpha');await expect(page.getByRole('alert').filter({hasText:'AUTHORIZATION_NOT_FOUND'})).toBeVisible();await expect(page.locator('.private-message')).toHaveCount(0);const deniedReads=state.requests.filter(path=>path.includes('/alpha/messages?')).length;await page.getByRole('button',{name:'读取最新消息',exact:true}).click();await expect.poll(()=>state.requests.filter(path=>path.includes('/alpha/messages?')).length).toBe(deniedReads+1);await page.waitForLoadState('networkidle');await expect(page.locator('.private-message')).toHaveCount(0);
});

test('another principal cannot reuse the previous account page cursor or message state',async({page})=>{
 const state=await fixture(page,120);state.capability.release();state.links.release();state.history.release();await readDeepPage(page,state);await switchConversation(page,'beta');await current(page,'beta',120);state.principal='human:other';const before=state.requests.length;await switchConversation(page,'alpha');await expect(page.getByText('当前登录已失效',{exact:true})).toBeVisible();await expect(page.locator('.private-message')).toHaveCount(0);const reads=state.requests.slice(before).filter(path=>path.includes('/alpha/messages?'));expect(reads).toHaveLength(1);expect(reads[0]).not.toContain('before=');
});

test('new availability true rejects malformed or failed pages without legacy downgrade',async({page})=>{
 const state=await fixture(page);state.capability.release();state.links.release();state.history.release();state.malformedPage=true;await page.goto('/work?conversation=alpha');await expect(page.getByRole('alert')).toContainText('CONVERSATION_MESSAGE_PAGE_INVALID');expect(state.requests.some(path=>/^GET \/api\/workbench\/v1\/conversations\/alpha$/.test(path))).toBe(false);await expect(page.locator('.private-message')).toHaveCount(0);
 state.malformedPage=false;state.messageFailure=503;await page.getByRole('button',{name:'读取最新消息',exact:true}).click();await expect(page.getByRole('alert')).toContainText('PAGE_READ_DENIED');expect(state.requests.some(path=>/^GET \/api\/workbench\/v1\/conversations\/alpha$/.test(path))).toBe(false);
});

test('successful old capability response without availability flag keeps authorized legacy compatibility',async({page})=>{
 const state=await fixture(page);state.paging=false;state.capability.release();state.links.release();state.history.release();await page.goto('/work?conversation=alpha');await current(page);expect(state.requests.some(path=>/^GET \/api\/workbench\/v1\/conversations\/alpha$/.test(path))).toBe(true);expect(state.requests.some(path=>path.includes('/alpha/messages?'))).toBe(false);state.denied=true;await page.reload();await expect(page.getByRole('alert')).toContainText('AUTHORIZATION_NOT_FOUND');await expect(page.locator('.private-message')).toHaveCount(0);
});

test('bounded capability context outside the page opens its original exact journal without claiming unstarted from truncation',async({page})=>{
 const state=await fixture(page,120);state.capability.release();state.links.release();state.history.release();state.capabilitySource={message_id:'cap-original',sequence:1,kind:'SOURCE',content:'合成能力准备',facts:{readable:true,source:{kind:'CAPABILITY',target:{capabilityId:'cap-fixed',revisionId:'revision-fixed',digest:'d'.repeat(64),objective:'原能力检查目标',inputNotes:'原资料范围'}},observation:{state:'PREPARED_NOT_EXECUTED',title:'原准备',objective:'原能力检查目标',inputNotes:'原资料范围'}}};await page.goto('/work?conversation=alpha');await current(page,'alpha',120);await expect(page.locator('#conversation-message-cap-original')).toHaveCount(0);await expect(page.getByRole('region',{name:'原能力办理记录'})).toContainText('原能力检查目标');await expect(page.getByRole('region',{name:'已保存的工作进度'})).toContainText('目标与完成标准已保存');expect(state.requests.some(path=>path.includes('/sources/cap-original/journey'))).toBe(true);await expect(page.getByText('当前准备 · 未启动',{exact:true})).toHaveCount(0);expect(state.requests.some(path=>/^GET \/api\/workbench\/v1\/conversations\/alpha$/.test(path))).toBe(false);expect(state.writes.every(path=>path.endsWith('/history-access'))).toBe(true);
});

test('unavailable current capability source is retained as unavailable and never treated as no saved work',async({page})=>{
 const state=await fixture(page,120);state.capability.release();state.links.release();state.history.release();state.capabilitySource={message_id:'cap-original',sequence:1,kind:'SOURCE',content:'当前记录不可读',facts:{readable:false,readState:'ACCESS_RESTRICTED'}};await page.goto('/work?conversation=alpha');await current(page,'alpha',120);await expect(page.getByText('原能力办理记录当前不可读，不能当作尚未提交；已保存消息仍可查看。')).toBeVisible();await page.locator('#private-input').fill('保留原工作补充');await expect(page.getByRole('button',{name:'发送',exact:true})).toBeDisabled();expect(state.requests.some(path=>path.includes('/sources/cap-original/journey'))).toBe(false);expect(state.writes.every(path=>path.endsWith('/history-access'))).toBe(true);
});

async function understandingFixture(page:Page,mode:'VALID'|'OTHER_GOAL'|'AMBIGUOUS'|'UNAVAILABLE'|'UNKNOWN'|'WRONG_SOURCE'){
 const state=await fixture(page,120);state.routing=true;state.initialAdoption=true;state.capability.release();state.links.release();state.history.release();
 const initial={state:'SUCCEEDED',resultKind:'NEEDS_CLARIFICATION',invocationId:'original-understanding',contextId:'original-context',turnId:'original-turn',turnVersion:1,aggregateVersion:5,clarificationQuestion:'请确认原检查环境。',dataNeeds:[],draft:null,conversationDelivery:{state:'SAVED',messageId:'original-answer'}};
 const journal={version:7,state:{key:'original-work',phase:'CLARIFY',understandingProtocol:3,userMessageId:'alpha-1',question:'原检查指令',messages:[{id:'user:alpha-1',text:'原检查指令'}],draft:initial,sources:[],log:[]}};
 const target={kind:'UNDERSTANDING',invocationId:initial.invocationId,contextId:initial.contextId,turnId:initial.turnId,turnVersion:1,aggregateVersion:5,journalVersion:7,journeyKey:'original-work'};
 const pairs=[1,2].map(n=>({message:{message_id:'saved-'+n,sequence:n+2,kind:'SOURCE',content:'已保存原回答'+n,facts:{assistantResponse:true,invokedBy:'human:ordinary',requestKey:'saved-request-'+n,userMessageId:'reply-'+n,state:'SUCCEEDED',response:{conversationRoute:{relation:'CURRENT_QUESTION'}},source:{kind:'DRAFT',invocationId:mode==='WRONG_SOURCE'?'wrong-result':'saved-result-'+n}}},userMessage:{message_id:'reply-'+n,sequence:n+1,author_id:'human:ordinary',content:'生产环境'+n,request_key:'saved-user-'+n}}));
 await page.route('**/conversations/alpha/journey',route=>{state.requests.push(route.request().method()+' '+new URL(route.request().url()).pathname);if(route.request().method()!=='GET')state.writes.push(new URL(route.request().url()).pathname);return route.fulfill({json:{result:journal}})});
 await page.route('**/draft-assistance/invocations/original-understanding',route=>route.fulfill({json:{result:initial}}));
 await page.route('**/conversations/alpha/understanding-successes?**',route=>{
  const url=new URL(route.request().url());state.requests.push('GET '+url.pathname+url.search);const second=url.searchParams.has('before'),items=mode==='AMBIGUOUS'||mode==='OTHER_GOAL'?[pairs[second?1:0]]:[pairs[0]];
  return route.fulfill({json:{result:{conversation:{conversation_id:'alpha',title:'原检查',version:120,created_at:'2026-11-01'},items:mode==='UNAVAILABLE'?items.map(pair=>({...pair,message:{...pair.message,facts:{readable:false,readState:'ACCESS_RESTRICTED'}}})):items,page:{hasMore:!second&&(mode==='AMBIGUOUS'||mode==='OTHER_GOAL'),nextCursor:!second&&(mode==='AMBIGUOUS'||mode==='OTHER_GOAL')?'success-page-2':null,resumeCursor:'success-page'},unavailable:mode==='UNAVAILABLE'}}});
 });
 await page.route('**/conversations/alpha/understanding-results/**',route=>{
  const request=route.request(),url=new URL(request.url()),path=url.pathname,n=path.includes('reply-2')?2:1;state.requests.push(request.method()+' '+path);if(request.method()!=='GET')state.writes.push(path);
  if(path.endsWith('/adoption'))return route.fulfill({status:404,json:{reasonCode:'UNDERSTANDING_ADOPTION_NOT_FOUND'}});
  if(path.endsWith('/route'))return route.fulfill({json:{result:{relation:'CURRENT_QUESTION',messageId:'reply-'+n,originalText:'生产环境'+n,target:mode==='OTHER_GOAL'&&n===2?{...target,journeyKey:'another-goal-work'}:target}}});
  return route.fulfill({json:{result:{...initial,state:mode==='UNKNOWN'?'OUTCOME_UNKNOWN':'SUCCEEDED',invocationId:'saved-result-'+n,resultKind:'NEEDS_CLARIFICATION',conversationRoute:{relation:'CURRENT_QUESTION'},conversationDelivery:{state:'SAVED',messageId:'saved-'+n}}}});
 });return state;
}

for(const mode of ['VALID','OTHER_GOAL','AMBIGUOUS','UNAVAILABLE','UNKNOWN','WRONG_SOURCE'] as const)test('bounded saved-answer discovery '+mode+' retains original source and never dispatches',async({page})=>{
 const state=await understandingFixture(page,mode);await page.goto('/work?conversation=alpha');await current(page,'alpha',120);await expect(page.locator('#conversation-message-alpha-1')).toHaveCount(0);await expect.poll(()=>state.requests.some(path=>path.includes('/understanding-successes?'))).toBe(true);
 const resume=page.getByRole('button',{name:'核对并继续已有回答',exact:true});
 if(mode==='VALID'||mode==='OTHER_GOAL')await expect(resume).toBeVisible();else if(mode==='AMBIGUOUS')await expect(page.getByText('发现多条已保存回答，尚不能唯一对应。原记录已保留，未自动提交。')).toBeVisible();else if(mode==='UNAVAILABLE')await expect(page.getByText('部分已保存回答当前不可读取，原记录保留；未推断为尚未提交。')).toBeVisible();else{await page.waitForLoadState('networkidle');await expect(resume).toHaveCount(0)}
 if(mode==='OTHER_GOAL'||mode==='AMBIGUOUS')expect(new Set(state.requests.filter(path=>path.includes('/understanding-successes?'))).size).toBe(2);
 expect(state.requests.some(path=>/^GET \/api\/workbench\/v1\/conversations\/alpha$/.test(path))).toBe(false);expect(state.writes.every(path=>path.endsWith('/history-access'))).toBe(true);expect(state.requests.some(path=>path.includes('/draft-assistance/invocations')&&!path.endsWith('/original-understanding'))).toBe(false);
});


test('explicit false or failed protocol availability cannot silently select legacy reads',async({page})=>{
 const state=await fixture(page);state.availabilityOverride=false;state.capability.release();state.links.release();state.history.release();await page.goto('/work?conversation=alpha');await expect(page.getByRole('alert')).toContainText('当前消息读取方式尚未就绪');expect(state.requests.some(path=>/^GET \/api\/workbench\/v1\/conversations\/alpha$/.test(path))).toBe(false);await expect(page.locator('.private-message')).toHaveCount(0);state.availabilityOverride=null;state.availabilityFailure=503;await page.reload();await expect(page.getByRole('alert')).toContainText('CAPABILITIES_UNAVAILABLE');expect(state.requests.some(path=>/^GET \/api\/workbench\/v1\/conversations\/alpha$/.test(path))).toBe(false);await expect(page.locator('.private-message')).toHaveCount(0);
});

test('cleared old session promise cannot clear or populate the newer in-flight identity',async({page})=>{
 const state=await fixture(page);state.delaySession=true;const oldGate=state.session;
 await page.route('**/session-unit',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><html><body>Session lifecycle fixture</body></html>'}));await page.goto('/session-unit');const original=readFileSync(new URL('../../src/api/businessWorkspace.ts',import.meta.url),'utf8');const code=ts.transpileModule(original,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText.replace(/import\s*\{\s*modelResult\s*\}\s*from\s*['"]\.\/modelStream['"];?/,"const modelResult=()=>{throw Error('unused model')}");
 await page.evaluate(async compiled=>{const module=await import('data:text/javascript;charset=utf-8,'+encodeURIComponent(compiled));Object.assign(window,{sessionRace:{module,old:module.readWorkbenchSession().catch((error:Error)=>error.name)}})},code);await expect.poll(()=>state.sessionRequests).toBe(1);
 state.session=gate();state.principal='human:other';await page.evaluate(()=>{const race=(window as unknown as {sessionRace:{module:{readWorkbenchSession:()=>Promise<unknown>};fresh?:Promise<unknown>}}).sessionRace;window.dispatchEvent(new Event('workbench-session-expired'));race.fresh=race.module.readWorkbenchSession()});await expect.poll(()=>state.sessionRequests).toBe(2);
 const oldResult=await page.evaluate(async()=>{const race=(window as unknown as {sessionRace:{old:Promise<string>;module:{readWorkbenchSession:()=>Promise<unknown>};joined?:Promise<unknown>}}).sessionRace;const result=await race.old;race.joined=race.module.readWorkbenchSession();return result});expect(oldResult).toBe('AbortError');expect(state.sessionRequests).toBe(2);oldGate.release();state.session.release();const principals=await page.evaluate(async()=>{const race=(window as unknown as {sessionRace:{fresh:Promise<{principal:{principalId:string}}>;joined:Promise<{principal:{principalId:string}}>}}).sessionRace;return (await Promise.all([race.fresh,race.joined])).map(session=>session.principal.principalId)});expect(principals).toEqual(['human:other','human:other']);
});


test('redundancy: EFFECTIVE history keeps one message read and no unused problem list',async({page})=>{
 const s=await fixture(page);s.historyResult={available:true,items:[{state:'EFFECTIVE'}]};s.links.release();s.capability.release();s.history.release();await page.goto('/work?conversation=alpha');await current(page);await expect.poll(()=>s.writes.length).toBe(1);await page.waitForTimeout(350);console.log('REDUNDANCY_COUNTS',JSON.stringify({session:s.sessionRequests,messages:s.requests.filter(x=>x.includes('/alpha/messages?')).length,problems:s.requests.filter(x=>x.endsWith('/problems')).length,capabilities:s.requests.filter(x=>x.includes('/draft-assistance/capabilities')).length,post:s.writes.length}));expect(s.requests.filter(x=>x.includes('/alpha/messages?'))).toHaveLength(1);expect(s.requests.filter(x=>x.endsWith('/problems'))).toHaveLength(0);expect(s.writes).toEqual(['/api/workbench/v1/conversations/alpha/history-access']);
});

test('redundancy: APPROVED racing an old restricted GET reads the saved assistant once',async({page})=>{
 const s=await fixture(page);s.sourceMessage=true;s.restricted=true;s.delayAlpha=true;s.historyRestores=true;s.historyResult={available:true,items:[{state:'APPROVED'}]};s.links.release();s.capability.release();await page.goto('/work?conversation=alpha');await expect.poll(()=>s.requests.filter(x=>x.includes('/alpha/messages?')).length).toBe(1);s.history.release();await expect.poll(()=>s.restricted).toBe(false);s.alpha.release();await expect(page.getByText('已保存的独立答复正文',{exact:true})).toBeVisible();await page.waitForTimeout(250);expect(s.requests.filter(x=>x.includes('/alpha/messages?'))).toHaveLength(2);expect(s.writes).toEqual(['/api/workbench/v1/conversations/alpha/history-access']);
});

test('redundancy: EFFECTIVE delayed behind a restricted page performs one necessary readback',async({page})=>{
 const s=await fixture(page);s.sourceMessage=true;s.restricted=true;s.historyRestores=true;s.historyResult={available:true,items:[{state:'EFFECTIVE'}]};s.links.release();s.capability.release();await page.goto('/work?conversation=alpha');await expect(page.locator('.private-message .private-user').getByText('当前回复读取受限',{exact:true})).toBeVisible();s.history.release();await expect(page.getByText('已保存的独立答复正文',{exact:true})).toBeVisible();expect(s.requests.filter(x=>x.includes('/alpha/messages?'))).toHaveLength(2);expect(s.writes).toEqual(['/api/workbench/v1/conversations/alpha/history-access']);
});

for(const mode of ['REVOKED','403']as const)test('redundancy: '+mode+' keeps restricted content and never retries business work',async({page})=>{
 const s=await fixture(page);s.sourceMessage=true;s.restricted=true;s.historyResult={available:true,items:[{state:'REVOKED'}]};s.historyFailure=mode==='403'?403:0;s.links.release();s.capability.release();s.history.release();await page.goto('/work?conversation=alpha');await expect(page.locator('.private-message .private-user').getByText('当前回复读取受限',{exact:true})).toBeVisible();await expect(page.getByText(mode==='403'?'当前无法恢复这部分历史回复的访问，原内容仍保留。':'部分历史回复当前不在可访问范围内，其他消息仍可查看。',{exact:true})).toBeVisible();expect(s.requests.filter(x=>x.includes('/alpha/messages?'))).toHaveLength(1);expect(s.writes).toEqual(['/api/workbench/v1/conversations/alpha/history-access']);
});

test('redundancy: manual association requests its list only when the existing select is engaged',async({page})=>{
 const s=await fixture(page);s.links.release();s.capability.release();s.history.release();await page.goto('/work?conversation=alpha&attachProblem=known-problem');await current(page);expect(s.requests.filter(x=>x.endsWith('/problems'))).toHaveLength(0);await page.getByLabel('关联已有问题').focus();await expect.poll(()=>s.requests.filter(x=>x.endsWith('/problems')).length).toBe(1);expect(s.writes).toEqual(['/api/workbench/v1/conversations/alpha/history-access']);
});


test('mixed readback fix: restored EFFECTIVE A refreshes once beside revoked B and later clean success clears stale notice',async({page})=>{
 const s=await fixture(page);s.sourceMessage=true;s.restricted=true;s.secondSource=true;s.historyFailure=403;s.history.release();s.links.release();s.capability.release();await page.goto('/work?conversation=alpha');
 const a=page.locator('#conversation-message-alpha-3 .private-user'),b=page.locator('#conversation-message-alpha-2 .private-user');
 await expect(a).toHaveText('当前回复读取受限');await expect(b).toHaveText('另一条历史回复读取受限');await expect(page.getByText('当前无法恢复这部分历史回复的访问，原内容仍保留。',{exact:true})).toBeVisible();expect(s.requests.filter(x=>x.includes('/alpha/messages?'))).toHaveLength(1);
 s.historyFailure=0;s.historyRestores=true;s.historyResult={available:true,items:[{state:'EFFECTIVE'},{state:'REVOKED'}]};await page.getByRole('button',{name:'重新读取历史回复',exact:true}).click();
 await expect(a).toHaveText('已保存的独立答复正文');await expect(b).toHaveText('另一条历史回复读取受限');await expect(page.getByText('部分历史回复当前不在可访问范围内，其他消息仍可查看。',{exact:true})).toBeVisible();await expect(page.getByText('当前无法恢复这部分历史回复的访问，原内容仍保留。',{exact:true})).toHaveCount(0);await page.waitForTimeout(200);expect(s.requests.filter(x=>x.includes('/alpha/messages?'))).toHaveLength(2);
 s.secondRestored=true;s.historyResult={available:true,items:[{state:'EFFECTIVE'},{state:'EFFECTIVE'}]};await page.getByRole('button',{name:'重新读取历史回复',exact:true}).click();
 await expect(a).toHaveText('已保存的独立答复正文');await expect(b).toHaveText('另一条原助手答复正文');await expect(page.getByRole('button',{name:'重新读取历史回复',exact:true})).toHaveCount(0);await page.waitForTimeout(200);expect(s.requests.filter(x=>x.includes('/alpha/messages?'))).toHaveLength(3);expect(s.writes).toEqual(Array(3).fill('/api/workbench/v1/conversations/alpha/history-access'));expect(s.requests.some(x=>x.includes('/test-resource-access/'))).toBe(false);
});
