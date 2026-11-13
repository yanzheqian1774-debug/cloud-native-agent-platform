import {routingReceiptNotice} from '../../src/problems/conversationRoutingReceipt';
import {test,expect,type Page} from '@playwright/test';
const digest='a'.repeat(64),problem={business_problem_id:'problem',revision_id:'revision',digest:'b'.repeat(64)},ref={resource_id:problem.business_problem_id,revision_id:problem.revision_id,digest:problem.digest};
async function fixture(page:Page,phase='PLAN',enabled=true){
 const question={invocationId:'native-one',questionKey:'question-one',questionDigest:'c'.repeat(64),question:'请确认采用内部交接规范还是外部规范？',expiresAt:'2099-01-01T00:00:00Z',answer:null as string|null,expired:false};
 const state={question,phase,longRail:false,executionState:'RUNNING',failureReason:null as string|null,modelCalls:[] as Record<string,unknown>[],ownerPosts:[] as Record<string,unknown>[],writes:[] as string[],reads:0,relation:'INDEPENDENT',directCurrentWork:false,stale:false,dropStream:false,rejectBefore:false,readUnavailable:false,ownerReceipt:'accepted',hold:null as Promise<void>|null,
  messages:[{message_id:'original',content:'帮我检查交接材料',author_id:'human:alice',disposition:'GOAL_RECORDED',request_key:'original'}] as Record<string,unknown>[],version:1,last:null as Record<string,unknown>|null,
  journal:{version:7,state:{key:'original-work',phase,pending:phase==='PLAN'?'planning':phase==='EXECUTE'?'execute':undefined,error:phase==='EXECUTE'?'上次执行结果尚待核实':undefined,question:'帮我检查交接材料',problem,messages:[{id:'user:original',text:'帮我检查交接材料'}],log:['原工作已保存'],...(phase==='RUNNING'?{execution:digest}:{})}}};
 await page.route('**/api/**',async route=>{
  const req=route.request(),url=new URL(req.url()),path=url.pathname,body=req.method()==='POST'?req.postDataJSON():null,result=(value:unknown)=>route.fulfill({json:{result:value}});
  if(req.method()!=='GET')state.writes.push(path);
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:alice',tenantId:'tenant',securityDomain:'domain'},csrfToken:'csrf',session:{}}});
  if(path.endsWith('/development-administrator'))return result({enabled:false});
  if(path.endsWith('/conversations/capabilities'))return result({enabled:true});
  if(path.endsWith('/draft-assistance/capabilities'))return result({conversationUnderstanding:true,conversationRelationRouting:enabled});
  if(path.endsWith('/conversations/routing/journey')){expect(body).toBeNull();return result(state.journal)}
  if(path.endsWith('/conversations/routing/messages')){expect(body.expectedVersion).toBe(state.version);state.version++;const id='user-'+state.version;state.messages.push({message_id:id,content:body.content,author_id:'human:alice',disposition:'FOLLOWUP_RECORDED',request_key:body.idempotencyKey});return result({identity:id})}
  if(path.endsWith('/conversations/routing/head'))return result({conversation:{conversation_id:'routing',title:'原业务工作',version:state.version}});
  if(path.endsWith('/conversations/routing'))return result({conversation:{conversation_id:'routing',title:'原业务工作',version:state.version},messages:state.messages,links:[]});
  if(path.endsWith('/route')){state.reads++;if(state.stale)return route.fulfill({status:409,json:{reasonCode:'CONVERSATION_ROUTE_STALE'}});const input=state.modelCalls.at(-1)!;const message=state.messages.find(m=>m.message_id===input.conversationMessageId)!;return result({relation:'CURRENT_QUESTION',originalText:message.content,messageId:message.message_id,target:{kind:'NATIVE',invocationId:question.invocationId,executionDigest:digest,questionKey:question.questionKey,questionDigest:question.questionDigest,journalVersion:7,journeyKey:'original-work',problemId:'problem'}})}
  if(path.includes('/understanding-results/')){state.reads++;if(state.readUnavailable)return route.fulfill({status:503,json:{reasonCode:'UNAVAILABLE'}});if(!state.last)return route.fulfill({status:404,json:{reasonCode:'CONVERSATION_REQUEST_NOT_DISPATCHED'}});return result(state.last)}
  if(path.endsWith('/draft-assistance/invocations')){
   state.modelCalls.push(body);expect(body.conversationRouting).toBe(true);expect(body.parentContextId).toBeUndefined();expect(body.predecessorInvocationId).toBeUndefined();expect(body.conversationId).toBe('routing');
   if(state.rejectBefore)return route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
   if(state.hold)await state.hold;
   const relation=state.relation,kind=relation==='INDEPENDENT'||state.directCurrentWork?'DIRECT_ANSWER':relation==='CURRENT_QUESTION'?'CURRENT_QUESTION_ANSWER':'NEEDS_CLARIFICATION',n=state.modelCalls.length;
   const response={state:'SUCCEEDED',resultKind:kind,invocationId:'route-'+n,contextId:'route-context',turnId:'route-turn-'+n,turnVersion:1,aggregateVersion:2,answer:kind==='DIRECT_ANSWER'?'HTTP 是传输网页内容的协议。':null,clarificationQuestion:kind==='NEEDS_CLARIFICATION'?'你是补充当前交接检查，还是提出一个独立问题？':null,draft:null,conversationDelivery:{state:'SAVED',messageId:'answer-'+n},conversationRoute:{relation,currentQuestionToken:relation==='CURRENT_QUESTION'?'token':null,contextDigest:'d'.repeat(64)}};
   state.last=response;state.version++;state.messages.push({message_id:'answer-'+n,content:response.answer??response.clarificationQuestion??'已核对这条回答，等待提交原问题。',kind:'SOURCE',facts:{assistantResponse:true,state:'SUCCEEDED',response,source:{kind:'DRAFT',invocationId:response.invocationId,contextId:'route-context',turnId:'route-turn-'+n,turnVersion:1}}});
   if(state.dropStream)return route.fulfill({headers:{'Content-Type':'text/event-stream'},body:'event: progress\ndata: {"kind":"stage","stage":"processing"}\n\n'});
   return result(response);
  }
  if(path.endsWith('/native-progress'))return result({steps:Array.from({length:state.longRail?20:0},(_,i)=>({id:'step-'+i,decision:{action:'TOOL',tool:'inspect_records'},output:{matches:[]},toolState:'COMPLETED'})),questions:[question],modelInFlight:false});
  if(path.endsWith('/native-answers')){state.ownerPosts.push(body);expect(body).toMatchObject({invocationId:question.invocationId,questionKey:question.questionKey,questionDigest:question.questionDigest,conversationId:'routing'});if(state.ownerReceipt==='rejected')return route.fulfill({status:422,json:{reasonCode:'INVALID_ANSWER'}});question.answer=body.answer;if(state.ownerReceipt==='lost')return route.abort();return result({accepted:true})}
  if(path.includes('/prepared-executions/'))return result({digest,executionStarted:true,preparation:{plan_id:'plan',plan_version:1,plan_digest:'e'.repeat(64),approval_id:'approval',source_snapshot:{resource_id:'source',revision_id:'1',digest:'f'.repeat(64)},semantics:{title:'交接核对',target:{problem:ref},tasks:[]},participants:[]},progress:{state:state.executionState,version:1,tasks:state.executionState==='RUNNING'?[]:[{task_id:'analysis',state:state.executionState,attempt_ordinal:1,reason:state.failureReason}]},resourceUses:[],artifacts:[],events:[],outcome:null,admission:{state:'ADMITTED',reason:null}});
  if(path.endsWith('/problems'))return result({problems:[]});
  if(req.method()!=='GET')return route.fulfill({status:405,json:{reasonCode:'UNEXPECTED_WRITE'}});
  return result({items:[]});
 });return state;
}
const input=(page:Page)=>page.getByLabel('补充要求或提出问题',{exact:true});
async function send(page:Page,text:string){await input(page).fill(text);await page.getByRole('button',{name:'发送',exact:true}).click()}
for(const phase of ['PLAN','EXECUTE','RUNNING'])test(`independent question preserves ${phase} work and existing question`,async({page},info)=>{
 const s=await fixture(page,phase),before=JSON.stringify(s.journal);await page.goto('/work?conversation=routing');await expect(input(page)).toBeVisible();await expect(page.locator('.f3-composer-dock textarea')).toHaveCount(1);
 await send(page,'HTTP 是什么？');await expect(page.getByText('HTTP 是传输网页内容的协议。',{exact:true})).toBeVisible();await expect(page.locator('#conversation-message-answer-1')).toBeInViewport();expect(s.modelCalls).toHaveLength(1);expect(s.ownerPosts).toHaveLength(0);expect(s.question.answer).toBeNull();expect(JSON.stringify(s.journal)).toBe(before);
 await page.reload();await expect(input(page)).toBeVisible();expect(s.modelCalls).toHaveLength(1);expect(JSON.stringify(s.journal)).toBe(before);expect(s.writes.filter(p=>p.endsWith('/journey'))).toHaveLength(0);
 await page.setViewportSize({width:1440,height:900});await page.screenshot({path:info.outputPath('independent-'+phase+'-1440.png'),fullPage:true});
});
test('exact Native answer is revalidated and submitted once to original owner',async({page})=>{
 const s=await fixture(page,'RUNNING');s.relation='CURRENT_QUESTION';const before=JSON.stringify(s.journal);await page.goto('/work?conversation=routing');await expect(page.getByText(s.question.question,{exact:true})).toBeVisible();await send(page,'采用内部交接规范');await expect.poll(()=>s.ownerPosts.length).toBe(1);expect(s.reads).toBe(1);expect(s.modelCalls).toHaveLength(1);expect(s.messages.filter(m=>m.content==='采用内部交接规范')).toHaveLength(1);expect(JSON.stringify(s.journal)).toBe(before);await page.reload();await expect(input(page)).toBeVisible();expect(s.ownerPosts).toHaveLength(1);expect(s.modelCalls).toHaveLength(1);
});
test('changed owner never receives a retargeted answer',async({page})=>{
 const s=await fixture(page,'RUNNING');s.relation='CURRENT_QUESTION';s.stale=true;await page.goto('/work?conversation=routing');await send(page,'采用内部交接规范');await expect(page.getByText(/原工作已变化，这条回答未提交/)).toBeVisible();expect(s.ownerPosts).toHaveLength(0);expect(s.modelCalls).toHaveLength(1);await expect(input(page)).toHaveValue('采用内部交接规范');
});
test('ambiguous reply asks inline and retains real routing-thread context',async({page})=>{
 const s=await fixture(page,'EXECUTE');s.relation='AMBIGUOUS';const before=JSON.stringify(s.journal);await page.goto('/work?conversation=routing');await send(page,'这个应该怎么算？');await expect(page.getByText('你是补充当前交接检查，还是提出一个独立问题？',{exact:true})).toBeVisible();s.relation='INDEPENDENT';await send(page,'这是独立的问题，解释一下 HTTP');await expect(page.getByText('HTTP 是传输网页内容的协议。',{exact:true})).toBeVisible();const content=JSON.parse(s.modelCalls[1].content as string);expect(content.messages.map((m:{text:string})=>m.text)).toEqual(['这个应该怎么算？','这是独立的问题，解释一下 HTTP']);expect(content.previousQuestion).toBe('你是补充当前交接检查，还是提出一个独立问题？');expect(JSON.stringify(s.journal)).toBe(before);expect(s.ownerPosts).toHaveLength(0);await expect(page.getByRole('combobox')).toHaveCount(0);
});
test('recovered answer requires explicit same-request continuation without model replay',async({page})=>{
 const s=await fixture(page,'RUNNING');s.relation='CURRENT_QUESTION';s.dropStream=true;await page.goto('/work?conversation=routing');await send(page,'采用内部交接规范');await expect(page.getByText(/暂未确认这条回复的处理结果/)).toBeVisible();expect(s.ownerPosts).toHaveLength(0);await page.reload();await expect(page.getByRole('button',{name:'继续提交这条回答'})).toBeVisible();expect(s.ownerPosts).toHaveLength(0);expect(s.modelCalls).toHaveLength(1);await page.getByRole('button',{name:'继续提交这条回答'}).click();await expect.poll(()=>s.ownerPosts.length).toBe(1);expect(s.modelCalls).toHaveLength(1);
});
test('typing during a reply preserves new unsent text and cannot double-dispatch',async({page})=>{
 const s=await fixture(page,'PLAN');let release=()=>{};s.hold=new Promise<void>(resolve=>{release=resolve});await page.goto('/work?conversation=routing');await send(page,'HTTP 是什么？');await expect.poll(()=>s.modelCalls.length).toBe(1);await input(page).fill('另一条尚未发送的说明');await input(page).press('Enter');expect(s.modelCalls).toHaveLength(1);release();await expect(page.getByText('HTTP 是传输网页内容的协议。',{exact:true})).toBeVisible();await expect(input(page)).toHaveValue('另一条尚未发送的说明');expect(s.messages.filter(m=>m.content==='另一条尚未发送的说明')).toHaveLength(0);
});
test('unpublished capability leaves the existing route unchanged',async({page})=>{
 const s=await fixture(page,'PLAN',false);await page.goto('/work?conversation=routing');await expect(page.getByText('本次问题、进度和结果都保留在此会话；需要补充时，在这里回答。')).toBeVisible();await expect(input(page)).toHaveCount(0);expect(s.modelCalls).toHaveLength(0);expect(s.writes).toHaveLength(0);
});

test('known owner rejection keeps the original draft editable without automatic retry',async({page})=>{
 const s=await fixture(page,'RUNNING');s.relation='CURRENT_QUESTION';s.ownerReceipt='rejected';await page.goto('/work?conversation=routing');await send(page,'采用内部交接规范');await expect(page.getByText('原问题未接受这条回答，输入已保留，请核对后修改；不会自动重发。',{exact:true})).toBeVisible();await expect(input(page)).toHaveValue('采用内部交接规范');await expect(page.getByRole('button',{name:'发送',exact:true})).toBeEnabled();expect(s.ownerPosts).toHaveLength(1);expect(s.modelCalls).toHaveLength(1);
});
test('lost Native answer receipt is recovered by exact read without another POST',async({page})=>{
 const s=await fixture(page,'RUNNING');s.relation='CURRENT_QUESTION';s.ownerReceipt='lost';await page.goto('/work?conversation=routing');await send(page,'采用内部交接规范');await expect.poll(()=>s.ownerPosts.length).toBe(1);await page.reload();await expect(page.getByText('补充“采用内部交接规范”已由当时的执行追问接收。已核对原记录，没有再次提交。后续问题请以当前工作中的提示为准。',{exact:true})).toBeVisible();await expect(input(page)).toHaveValue('');expect(s.ownerPosts).toHaveLength(1);expect(s.modelCalls).toHaveLength(1);expect(s.writes.some(p=>p.endsWith('/native-progress'))).toBe(false);
});

test('new reply does not pull the user away from reading earlier messages',async({page})=>{
 const s=await fixture(page,'RUNNING');let release=()=>{};s.hold=new Promise<void>(resolve=>{release=resolve});await page.goto('/work?conversation=routing');await send(page,'HTTP 是什么？');await expect.poll(()=>s.modelCalls.length).toBe(1);const stream=page.locator('.px-message-stream');await stream.evaluate(n=>{n.scrollTop=0;n.dispatchEvent(new Event('wheel',{bubbles:true}))});const top=await stream.evaluate(n=>n.scrollTop);release();await expect(page.getByText('HTTP 是传输网页内容的协议。',{exact:true})).toBeVisible();await expect.poll(()=>stream.evaluate(n=>n.scrollTop)).toBeCloseTo(top,0);expect(s.ownerPosts).toHaveLength(0);
});
test('recovering an independent saved reply clears only its original submitted draft',async({page})=>{
 const s=await fixture(page,'PLAN');s.dropStream=true;await page.goto('/work?conversation=routing');await send(page,'HTTP 是什么？');await expect(page.getByText(/暂未确认这条回复的处理结果/)).toBeVisible();await page.reload();await expect(page.getByText('回复已返回本会话，原任务保持不变。',{exact:true})).toBeVisible();await expect(input(page)).toHaveValue('');expect(s.modelCalls).toHaveLength(1);expect(s.ownerPosts).toHaveLength(0);
});

test('current-work explanation is saved without owner adoption or stale clarification context',async({page})=>{
 const s=await fixture(page,'RUNNING');s.relation='CURRENT_WORK';s.directCurrentWork=true;const before=JSON.stringify(s.journal);await page.goto('/work?conversation=routing');await send(page,'解释一下当前任务');await expect(page.getByText('回复已返回本会话，原任务保持不变。')).toBeVisible();await expect(input(page)).toHaveValue('');expect(s.ownerPosts).toHaveLength(0);expect(s.reads).toBe(0);expect(s.question.answer).toBeNull();expect(JSON.stringify(s.journal)).toBe(before);await page.reload();await expect(input(page)).toBeVisible();expect(s.modelCalls).toHaveLength(1);s.relation='INDEPENDENT';s.directCurrentWork=false;await send(page,'HTTP 是什么？');await expect.poll(()=>s.modelCalls.length).toBe(2);const content=JSON.parse(s.modelCalls[1].content as string);expect(content.messages.map((m:{text:string})=>m.text)).toEqual(['HTTP 是什么？']);expect(s.ownerPosts).toHaveLength(0);expect(JSON.stringify(s.journal)).toBe(before);
});

test('initial understanding question keeps its original single-call path outside the current stage',async({page})=>{
 const s=await fixture(page,'CLARIFY');
 Object.assign(s.journal.state,{draft:{state:'SUCCEEDED',resultKind:'NEEDS_CLARIFICATION',invocationId:'initial-understanding',clarificationQuestion:'需要核对哪份材料？'}});
 await page.goto('/work?conversation=routing');
 await expect(page.getByLabel('补充说明',{exact:true})).toBeVisible();
 await expect(input(page)).toHaveCount(0);
 expect(s.modelCalls).toHaveLength(0);expect(s.ownerPosts).toHaveLength(0);expect(s.writes).toEqual([]);
});

test('planning answer routes once to the exact original question and reuses its saved user message',async({page})=>{
 const s=await fixture(page,'PLANNING_CLARIFY');s.relation='CURRENT_QUESTION';
 const original={invocation:{target:{invocation_id:'planning-original',suggestion_context_id:'planning-context',request_revision:1,problem:{problem:ref}}},result:{technical_status:'SUCCEEDED',kind:'NEEDS_CLARIFICATION',questions:['请确认需要核对哪个环境？']},facts_status:'RECORDED'};
 Object.assign(s.journal.state,{planning:original,source:{source:{resource_id:'source',revision_id:'1',digest:'f'.repeat(64)},name:'交接资料',periods:[],sourceSchema:'document-review-source.v1',synthetic:true}});
 s.messages.push({message_id:'planning-question',request_key:'original-work:planning-question:planning-original',kind:'SOURCE',content:'请确认需要核对哪个环境？',facts:{source:{kind:'PLANNING',invocationId:'planning-original',contextId:'planning-context',requestRevision:1,target:original.invocation.target.problem},observation:{state:'SUCCEEDED',resultKind:'NEEDS_CLARIFICATION',questions:original.result.questions}}});s.version++;
 await page.route('**/conversations/routing/journey',route=>{const req=route.request();if(req.method()==='POST'){const body=req.postDataJSON();expect(body.expectedVersion).toBe(s.journal.version);s.journal.version++;s.journal.state=body.state;}return route.fulfill({json:{result:s.journal}})});
 await page.route('**/understanding-results/**/route*',route=>{const request=s.modelCalls.at(-1)!;const message=s.messages.find(m=>m.message_id===request.conversationMessageId)!;return route.fulfill({json:{result:{relation:'CURRENT_QUESTION',messageId:message.message_id,originalText:message.content,target:{kind:'PLANNING',journalVersion:7,journeyKey:'original-work',problemId:'problem',invocationId:'planning-original'}}}})});
 await page.route('**/question-activity-input',route=>route.fulfill({json:{result:{state:'READY',planningRequest:{target:{},policy:{},output_language:'zh',answers:[],idempotency_key:'current-planning'}}}}));
 await page.route('**/planning-v2/preflight',route=>route.fulfill({json:{result:{}}}));
 const plans:Record<string,unknown>[]=[];
 await page.route('**/planning-v2/invocations',route=>{plans.push(route.request().postDataJSON());return route.fulfill({json:{result:{invocation:{target:{invocation_id:'new-planning'}},result:{technical_status:'OUTCOME_UNKNOWN',kind:null}}}})});
 await page.goto('/work?conversation=routing');await send(page,'只核对生产环境');
 await expect.poll(()=>plans.length).toBe(1);
 expect(s.modelCalls).toHaveLength(1);expect(s.ownerPosts).toHaveLength(0);
 expect(plans[0].predecessor_invocation_id).toBe('planning-original');
 expect(JSON.stringify(plans[0].answers)).toContain('只核对生产环境');
 expect(s.messages.filter(m=>m.content==='只核对生产环境')).toHaveLength(1);
 expect(s.journal.state.problem).toEqual(problem);expect(s.journal.state.question).toBe('帮我检查交接材料');
 await page.reload();await expect(input(page)).toBeVisible();expect(plans).toHaveLength(1);expect(s.modelCalls).toHaveLength(1);
});

test('confirmed unstarted question resumes with the same message and request only after an explicit click',async({page})=>{
 const s=await fixture(page);s.rejectBefore=true;await page.goto('/work?conversation=routing');await send(page,'HTTP 是什么？');await expect.poll(()=>s.modelCalls.length).toBe(1);
 await page.evaluate(()=>{const key=Object.keys(sessionStorage).find(k=>k.startsWith('conversation-routing.v1:'))!;const saved=JSON.parse(sessionStorage.getItem(key)!);delete saved.messageId;saved.phase='MESSAGE_PENDING';saved.thread=[];sessionStorage.setItem(key,JSON.stringify(saved))});
 await page.reload();const resume=page.getByRole('button',{name:'继续处理这条问题',exact:true});await expect(resume).toBeVisible();
 expect(s.modelCalls).toHaveLength(1);expect(s.messages.filter(m=>m.content==='HTTP 是什么？')).toHaveLength(1);
 s.rejectBefore=false;await resume.click();await expect(page.getByText('HTTP 是传输网页内容的协议。',{exact:true})).toBeVisible();
 expect(s.modelCalls).toHaveLength(2);expect(s.modelCalls[1]).toEqual(s.modelCalls[0]);expect(s.messages.filter(m=>m.content==='HTTP 是什么？')).toHaveLength(1);expect(s.ownerPosts).toHaveLength(0);
 await page.reload();await expect(input(page)).toBeVisible();expect(s.modelCalls).toHaveLength(2);
});
test('uncertain result read never offers redispatch',async({page})=>{
 const s=await fixture(page);s.rejectBefore=true;s.readUnavailable=true;await page.goto('/work?conversation=routing');await send(page,'HTTP 是什么？');await expect.poll(()=>s.modelCalls.length).toBe(1);await page.reload();
 await expect(page.getByText(/暂未确认这条回复的处理结果/)).toBeVisible();await expect(page.getByRole('button',{name:'继续处理这条问题',exact:true})).toHaveCount(0);expect(s.modelCalls).toHaveLength(1);
});


test('accepted supplement stays bound to earlier question after a later question expires',async({page},info)=>{
 await page.setViewportSize({width:1440,height:1000});
 const s=await fixture(page,'RUNNING');s.relation='CURRENT_QUESTION';await page.goto('/work?conversation=routing');await send(page,'采用内部交接规范');await expect.poll(()=>s.ownerPosts.length).toBe(1);
 await expect(page.getByText('补充“采用内部交接规范”已由当时的执行追问接收。后续问题请以当前工作中的提示为准。',{exact:true})).toBeVisible();
 const saved=await page.evaluate(()=>Object.entries(sessionStorage).filter(([k])=>k.startsWith('conversation-routing.v1:')).map(([,v])=>JSON.parse(v)));expect(saved[0].ownerTarget.questionKey).toBe('question-one');
 s.question.questionKey='question-two';s.question.questionDigest='d'.repeat(64);s.question.question='请补充第二项依据';s.question.answer=null;s.question.expired=true;s.question.expiresAt='2020-01-01T00:00:00Z';
 await expect(page.getByText('本次等待期限已到，原记录保留；不会自动重跑。',{exact:true})).toBeVisible();await expect(page.getByText('回答已提交到原问题，后续进展继续在本会话显示。',{exact:true})).toHaveCount(0);expect(s.ownerPosts).toHaveLength(1);expect(s.modelCalls).toHaveLength(1);
 await page.getByText('本次等待期限已到，原记录保留；不会自动重跑。',{exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:info.outputPath('prior-receipt-later-expired-1440.png'),fullPage:true});await page.reload();await expect(page.getByText('本次等待期限已到，原记录保留；不会自动重跑。',{exact:true})).toBeVisible();expect(s.ownerPosts).toHaveLength(1);expect(s.modelCalls).toHaveLength(1);
});
for(const [state,reason,label] of [['FAILED','InternalError','本次执行已失败，已有进展保留'],['CANCELLED',null,'本次执行已取消'],['UNKNOWN',null,'执行结果尚待核实'],['FAILED','NATIVE_INPUT_EXPIRED','任务记录显示执行追问等待超时']] as const)test('formal execution status is precise '+state+' '+reason,async({page})=>{
 const s=await fixture(page,'RUNNING');s.executionState=state;s.failureReason=reason;s.question.expired=true;s.question.expiresAt='2020-01-01T00:00:00Z';await page.goto('/work?conversation=routing');const progress=page.getByRole('region',{name:'全流程进展'});await expect(progress).toContainText(label);await expect(progress).not.toContainText('失败或取消');if(reason!=='NATIVE_INPUT_EXPIRED')await expect(progress).not.toContainText('等待超时');expect(s.modelCalls).toHaveLength(0);expect(s.ownerPosts).toHaveLength(0);
});
test('routing receipt names the accepting stage instead of the current question',()=>{
 expect(routingReceiptNotice('选择交接资料',{kind:'UNDERSTANDING',invocationId:'old'})).toContain('补充“选择交接资料”已由资料理解接收');expect(routingReceiptNotice('补充计划',{kind:'PLANNING',invocationId:'old'})).toContain('方案准备接收');expect(routingReceiptNotice('原补充')).toContain('原处理阶段接收');
});

for(const width of [1440,900,390])test(`long Native progress rail scrolls independently at ${width}`,async({page},info)=>{
 await page.setViewportSize({width,height:1000});const s=await fixture(page,'RUNNING');s.longRail=true;await page.goto('/work?conversation=routing');
 const rail=page.locator('.f3-progress-rail'),dock=page.locator('.f3-composer-dock');
 if(width<=1100)await page.getByRole('button',{name:'展开工作进展',exact:true}).click();
 await expect(rail.locator('[data-native-step]')).toHaveCount(20);
 const before=await dock.boundingBox();
 const measure=await rail.evaluate(el=>{const b=el.getBoundingClientRect();const ancestors=[];for(let p=el.parentElement;p;p=p.parentElement){const c=getComputedStyle(p);ancestors.push({class:p.className,height:p.getBoundingClientRect().height,display:c.display,rows:c.gridTemplateRows,align:c.alignItems})}el.scrollTop=el.scrollHeight;return {height:b.height,y:b.y,client:el.clientHeight,scroll:el.scrollHeight,top:el.scrollTop,align:getComputedStyle(el).alignSelf,ancestors}});
 await info.attach('rail-measurement',{body:JSON.stringify(measure,null,2),contentType:'application/json'});
 expect(measure.top).toBeGreaterThan(0);expect(measure.y+measure.height).toBeLessThanOrEqual(1001);
 await rail.locator('[data-native-step="step-19"]').scrollIntoViewIfNeeded();
 const bottom=await rail.locator('[data-native-step="step-19"]').boundingBox();expect(bottom!.y+bottom!.height).toBeLessThanOrEqual(measure.y+measure.height+1);
 expect(await dock.boundingBox()).toEqual(before);expect(s.modelCalls).toHaveLength(0);expect(s.ownerPosts).toHaveLength(0);
 await page.screenshot({path:info.outputPath(`rail-${width}.png`),fullPage:true});
});
