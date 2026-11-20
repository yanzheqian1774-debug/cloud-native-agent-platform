import {durableQuestionState} from '../../src/problems/nativeDurableWait';
import {test,expect,type Page} from '@playwright/test';
const prompt='帮我分析一下最近的销售情况，看看哪里出了问题';
async function fixture(page:Page){
 const state={title:prompt,journal:{version:0,state:null as Record<string,unknown>|null},messages:[] as Record<string,unknown>[],modelCalls:0};
 await page.route('**/api/**',async route=>{const p=new URL(route.request().url()).pathname,method=route.request().method(),body=method==='POST'?route.request().postDataJSON():null;const result=(r:unknown)=>route.fulfill({json:{result:r}});
 if(p.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:development-admin',tenantId:'tenant',securityDomain:'domain'},csrfToken:'csrf',session:{}}});
 if(p.endsWith('/development-administrator'))return result({enabled:true});
 if(p.endsWith('/draft-assistance/capabilities'))return result({conversationUnderstanding:true,conversationRelationRouting:true});
 if(p.endsWith('/conversations/capabilities'))return result({enabled:true});
 if(p.endsWith('/conversations'))return method==='POST'?result({conversation_id:'new'}):result({items:[]});
 if(p.endsWith('/new/journey')){if(method==='POST'){if(body.expectedVersion!==state.journal.version)return route.fulfill({status:409,json:{reasonCode:'JOURNEY_VERSION_CONFLICT'}});state.journal={version:state.journal.version+1,state:body.state}}return result(state.journal)}
 if(p.endsWith('/new/messages')){state.messages.push({message_id:'m'+state.messages.length,content:body.content,disposition:'GOAL_RECORDED',created_at:'2026-11-09T08:00:00Z'});return result({identity:'m1'})}
 if(p.endsWith('/conversations/new/head'))return result({conversation:{conversation_id:'new',title:state.title,version:state.messages.length}});
 if(p.endsWith('/conversations/new'))return result({conversation:{conversation_id:'new',title:state.title,version:state.messages.length},messages:state.messages,links:[]});
 if(p.endsWith('/draft-assistance/invocations')){const content=JSON.parse(body.content);if(content.messages.some((m:{id:string})=>!m.id.startsWith('user:')))return route.fulfill({status:404,json:{reasonCode:'DRAFT_CONTEXT_INVALID'}});state.modelCalls++;return result({invocationId:'draft'+state.modelCalls,contextId:'context',turnId:'turn',turnVersion:state.modelCalls,state:'SUCCEEDED',resultKind:'NEEDS_CLARIFICATION',clarificationQuestion:'你想比较哪个时间范围的销售？',draft:null,transport:'REAL_PROVIDER'})}
 if(p.endsWith('/conversation-sources'))return result({items:[{source:{resource_id:'source',revision_id:'1',digest:'a'.repeat(64)},name:'项目销售样本',periods:['2026-08','2026-09'],sourceSchema:'sales-diagnostic-source.v1',synthetic:true}]});
 if(p.endsWith('/problems'))return result({problems:[]});
 return result({items:[]});
 });return state;
}


for(const mode of ['WAITING_FOR_USER','ANSWER_SAVED','STOP_CONFIRMED','CONTINUATION_CLAIMED','ADVANCING','EXPIRED','BLOCKED','BAD_DIGEST','WRONG_RUN','DONE','MULTI','AMBIGUOUS','READ_ERROR'])test('durable wait '+mode,async({page})=>{
 const s=await fixture(page),digest='a'.repeat(64);s.journal={version:2,state:{key:'run',phase:'RUNNING',execution:digest,problem:{business_problem_id:'p'},messages:[],log:[]}};let posts=0;
 const saved=['ANSWER_SAVED','STOP_CONFIRMED','CONTINUATION_CLAIMED','ADVANCING'].includes(mode);
 const q={invocationId:'i',questionKey:'q',questionDigest:'b'.repeat(64),question:'请确认当前检查范围',expiresAt:'2099-01-01T00:00:00Z',answer:saved?'对':null,expired:mode==='EXPIRED'};
 const w={invocationId:'i',questionKey:'q',questionDigest:mode==='BAD_DIGEST'?'wrong':q.questionDigest,state:mode==='STOP_CONFIRMED'?'ANSWER_SAVED':['BAD_DIGEST','WRONG_RUN','DONE','MULTI'].includes(mode)?'WAITING_FOR_USER':mode,humanExpiresAt:q.expiresAt,answerSaved:saved,stopConfirmed:['STOP_CONFIRMED','CONTINUATION_CLAIMED','ADVANCING'].includes(mode)};
 await page.route('**/api/workbench/v1/prepared-executions/**',async r=>{
 if(r.request().method()!=='GET')posts++;
 if(mode==='READ_ERROR'&&r.request().url().endsWith('/native-progress'))return r.fulfill({status:403,json:{reasonCode:'READ_UNAVAILABLE'}});
 if(r.request().url().endsWith('/native-progress'))return r.fulfill({json:{result:{runId:mode==='WRONG_RUN'?'other':'run-1',steps:[],questions:mode==='AMBIGUOUS'?[{...q,invocationId:'other-i',questionKey:'other-q',question:'另一个未答问题'},q]:mode==='MULTI'?[{...q,invocationId:'old',questionKey:'old-q',question:'过去的问题',answer:'先前回答'},q]:[q],modelInFlight:false,durableWaits:mode==='MULTI'?[{...w,invocationId:'old',questionKey:'old-q',state:'COMPLETED',answerSaved:true,stopConfirmed:true},w]:[w],hostDispatch:{state:'READY',preparationDigest:digest,runId:'run-1',observedAt:null,reasonCode:null}}}});
 return r.fulfill({json:{result:{digest,workflowRunId:'run-1',executionStarted:true,admission:{state:'ADMITTED',reason:null},outcome:null,preparation:{plan_id:'plan',plan_version:1,plan_digest:'e'.repeat(64),approval_id:'approval',source_snapshot:{resource_id:'source',revision_id:'1',digest:'f'.repeat(64)},semantics:{title:'交接核对',target:{problem:{resource_id:'p',revision_id:'1',digest:'c'.repeat(64)}},tasks:[]},participants:[]},progress:{state:mode==='DONE'?'SUCCEEDED':'RUNNING',tasks:[]},artifacts:[],resourceUses:[],events:[]}}});});
 await page.goto('/work?conversation=new');const rail=page.getByRole('region',{name:'实时执行过程'});
 const labels:Record<string,string>={WAITING_FOR_USER:'原任务已保留',ANSWER_SAVED:'正在准备续接原任务',STOP_CONFIRMED:'等待原任务续接',CONTINUATION_CLAIMED:'正在接续原任务',ADVANCING:'原任务已接续',EXPIRED:'本题等待期限已到',BLOCKED:'当前继续条件尚未满足',BAD_DIGEST:'最新等待状态暂时无法核实',WRONG_RUN:'最新等待状态暂时无法核实',DONE:'执行已结束',MULTI:'原任务已保留',AMBIGUOUS:'最新等待状态暂时无法核实',READ_ERROR:'最新进展无法读取'};
 await expect(rail).toContainText(labels[mode]);await expect(page.getByText(/TypeError:/)).toHaveCount(0);await expect(rail).not.toContainText('执行环境已就绪');
 const cue=page.getByRole('note',{name:'当前正在回答的问题'});
 if(['WAITING_FOR_USER','MULTI'].includes(mode)){
  await expect(cue).toContainText(q.question);await expect(cue).toBeVisible();
  await expect(cue.locator('textarea,input')).toHaveCount(0);
  if(mode==='WAITING_FOR_USER'){
   await page.evaluate(()=>{const w=window as unknown as {cueScrolls:number};w.cueScrolls=0;const original=Element.prototype.scrollIntoView;Element.prototype.scrollIntoView=function(options){w.cueScrolls++;return original.call(this,options)}});
   await page.waitForResponse(r=>r.url().endsWith('/native-progress'));
   expect(await page.evaluate(()=>(window as unknown as {cueScrolls:number}).cueScrolls)).toBe(0);
  }

  await cue.getByRole('button',{name:'查看原问题'}).click();
  await expect(page.locator('blockquote').filter({hasText:q.question})).toBeFocused();
 }else await expect(cue).toHaveCount(0);
 if(mode==='DONE'){await expect(rail).not.toContainText('持续更新');await expect(rail).toContainText('刷新仅重新读取');const panel=page.getByRole('region',{name:'Native 执行与成果验收'});await expect(panel).toContainText('已保存的工作记录；刷新只读，不重新执行');await expect(panel).not.toContainText('进行中的状态自动更新')}
 if(mode==='WAITING_FOR_USER')await expect(page.getByRole('region',{name:'Native 执行与成果验收'})).toContainText('进行中的状态自动更新');

 if(['BLOCKED','EXPIRED','BAD_DIGEST','WRONG_RUN','READ_ERROR'].includes(mode))await expect(page.getByRole('button',{name:'提交回答并继续',exact:true})).toHaveCount(0);
 if(mode==='STOP_CONFIRMED')await page.screenshot({path:test.info().outputPath('answer-saved-awaiting-continuation.png'),fullPage:true});
 if(mode==='MULTI'){await expect(page.getByText('本题的等待处理已完成；整个任务是否完成，以实际工作步骤和结果为准。',{exact:true})).toBeVisible();await expect(rail).not.toContainText('等待处理已完成');}
 await page.reload();await expect(rail).toContainText(labels[mode]);expect(posts).toBe(0);expect(s.modelCalls).toBe(0);
});

test('projection preserves legacy and rejects malformed or conflicting records',()=>{
 const q={invocationId:'i',questionKey:'q',questionDigest:'d',answer:null};
 const w={...q,state:'WAITING_FOR_USER',humanExpiresAt:'2099-01-01',answerSaved:false,stopConfirmed:true};
 expect(durableQuestionState(undefined,q,undefined,undefined)).toBeNull();
 expect(durableQuestionState([w,w],q,'r','r')?.canAnswer).toBe(false);
 expect(durableQuestionState([{...w,answerSaved:'false'}],q,'r','r')?.canAnswer).toBe(false);
 expect(durableQuestionState([w],q,'r','other')?.canAnswer).toBe(false);
 expect(durableQuestionState([{...w,questionDigest:'other'}],q,'r','r')?.canAnswer).toBe(false);
 expect(durableQuestionState([{...w,invocationId:'other'}],q,'r','r')).toBeNull();
});
test('on-time saved answer remains pending continuation after human deadline',()=>{
 const q={invocationId:'i',questionKey:'q',questionDigest:'d',answer:'对'};
 const w={...q,state:'ANSWER_SAVED',humanExpiresAt:'2000-01-01',answerSaved:true,stopConfirmed:true};
 expect(durableQuestionState([w],q,'r','r')?.text).toContain('等待原任务续接');
 expect(durableQuestionState([w],q,'r','r')?.canAnswer).toBe(false);
});
