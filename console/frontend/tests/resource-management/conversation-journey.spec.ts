import {test,expect,type Page} from '@playwright/test';
const prompt='帮我分析一下最近的销售情况，看看哪里出了问题';
async function fixture(page:Page){
 const state={journal:{version:0,state:null as Record<string,unknown>|null},messages:[] as Record<string,unknown>[],modelCalls:0};
 await page.route('**/api/**',async route=>{const p=new URL(route.request().url()).pathname,method=route.request().method(),body=method==='POST'?route.request().postDataJSON():null;const result=(r:unknown)=>route.fulfill({json:{result:r}});
 if(p.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:development-admin',tenantId:'tenant',securityDomain:'domain'},csrfToken:'csrf',session:{}}});
 if(p.endsWith('/development-administrator'))return result({enabled:true});
 if(p.endsWith('/conversations/capabilities'))return result({enabled:true});
 if(p.endsWith('/conversations'))return method==='POST'?result({conversation_id:'new'}):result({items:[]});
 if(p.endsWith('/new/journey')){if(method==='POST'){if(body.expectedVersion!==state.journal.version)return route.fulfill({status:409,json:{reasonCode:'JOURNEY_VERSION_CONFLICT'}});state.journal={version:state.journal.version+1,state:body.state}}return result(state.journal)}
 if(p.endsWith('/new/messages')){state.messages.push({message_id:'m'+state.messages.length,content:body.content,disposition:'GOAL_RECORDED',created_at:'2026-11-09T08:00:00Z'});return result({identity:'m1'})}
 if(p.endsWith('/conversations/new'))return result({conversation:{conversation_id:'new',title:prompt,version:state.messages.length},messages:state.messages,links:[]});
 if(p.endsWith('/draft-assistance/invocations')){const content=JSON.parse(body.content);if(content.messages.some((m:{id:string})=>!m.id.startsWith('user:')))return route.fulfill({status:404,json:{reasonCode:'DRAFT_CONTEXT_INVALID'}});state.modelCalls++;return result({invocationId:'draft'+state.modelCalls,contextId:'context',turnId:'turn',turnVersion:state.modelCalls,state:'SUCCEEDED',resultKind:'NEEDS_CLARIFICATION',clarificationQuestion:'你想比较哪个时间范围的销售？',draft:null,transport:'REAL_PROVIDER'})}
 if(p.endsWith('/conversation-sources'))return result({items:[{source:{resource_id:'source',revision_id:'1',digest:'a'.repeat(64)},name:'项目销售样本',periods:['2026-08','2026-09'],sourceSchema:'sales-diagnostic-source.v1',synthetic:true}]});
 if(p.endsWith('/problems'))return result({problems:[]});
 return result({items:[]});
 });return state;
}
test('one short message starts understanding and clarification stays in the same conversation after reload',async({page})=>{
 const s=await fixture(page);await page.goto('/work');await page.locator('#private-input').fill(prompt);await page.getByRole('button',{name:'发送',exact:true}).click();await expect(page).toHaveURL(/conversation=new/);await expect(page.getByText('请选择本次要分析的资料范围。',{exact:true})).toBeVisible();expect(s.modelCalls).toBe(0);await expect(page.getByRole('link',{name:'在本会话核对目标与草稿'})).toHaveCount(0);
 await page.reload();await expect(page.getByRole('button',{name:'使用2026-08、2026-09销售测试资料'})).toBeVisible();expect(s.modelCalls).toBe(0);
 await page.getByRole('button',{name:'使用2026-08、2026-09销售测试资料'}).click();await expect.poll(()=>s.modelCalls).toBe(1);await expect(page).toHaveURL(/conversation=new/);await expect(page.locator('.conversation-journey blockquote')).toContainText('项目销售样本');
});
test('an interrupted claimed operation is preserved and never dispatched again on refresh',async({page})=>{
 const s=await fixture(page);s.journal={version:2,state:{key:'k',question:prompt,phase:'UNDERSTAND',pending:'understanding',messages:[{id:'q',text:prompt}],log:['已收到问题']}};
 await page.goto('/work?conversation=new');await expect(page.getByText('上次请求尚未核实，已保留原记录，暂不重复执行。')).toBeVisible();await page.reload();await expect(page.getByText('上次请求尚未核实，已保留原记录，暂不重复执行。')).toBeVisible();expect(s.modelCalls).toBe(0);
});

for(const reason of ['MODEL_AUTHORIZATION_INVALID','NETWORK_UNKNOWN'])test('only known pre-dispatch rejection offers in-conversation continuation: '+reason,async({page})=>{
 const s=await fixture(page);s.journal={version:2,state:{key:'k',question:prompt,phase:'PLAN',pending:'planning',error:'Error: 规划服务未能完成此操作，请核对权限与配置（'+reason+'）',messages:[{id:'user:q',text:prompt}],log:['分析目标已保存']}};
 await page.goto('/work?conversation=new');await expect(page.getByText('本次处理停在当前步骤，已有内容已保留。')).toBeVisible();
 await expect(page.getByRole('button',{name:'配置修复后继续分析'})).toHaveCount(reason==='MODEL_AUTHORIZATION_INVALID'?1:0);expect(s.modelCalls).toBe(0);
});

test('conversation result panel refreshes automatically while execution commands remain read only',async({page})=>{
 const s=await fixture(page),digest='a'.repeat(64),ref={resource_id:'p',revision_id:'1',digest:'b'.repeat(64)};
 s.journal={version:2,state:{key:'k',question:prompt,phase:'RUNNING',execution:digest,problem:{business_problem_id:'p'},messages:[{id:'user:q',text:prompt}],log:['正在执行分析']}};
 let complete=false,posts=0;
 await page.route('**/api/workbench/v1/prepared-executions/**',async route=>{
  if(route.request().method()!=='GET')posts++;
  return route.fulfill({json:{result:{digest,executionStarted:true,preparation:{plan_id:'plan',plan_version:1,plan_digest:'c'.repeat(64),approval_id:'approval',source_snapshot:ref,semantics:{title:'测试分析',target:{problem:ref},tasks:[]},participants:[]},progress:{state:complete?'SUCCEEDED':'RUNNING',version:complete?2:1,tasks:[]},admission:{state:'ADMITTED',reason:null},resourceUses:[],artifacts:[],events:[],outcome:null}}});
 });
 await page.goto('/work?conversation=new');await expect(page.getByRole('button',{name:'请求取消本次执行'})).toBeDisabled();complete=true;
 await expect(page.locator('.prepared-execution')).toHaveClass(/prepared-complete/,{timeout:12000});expect(posts).toBe(0);
});

test('schema-invalid understanding stops honestly and explicitly continues the unchanged question after receipt verification',async({page})=>{
 const s=await fixture(page);let calls=0;const keys:string[]=[];const failure=(id:string)=>({invocationId:id,contextId:'context',turnId:'turn',turnVersion:1,state:'FAILED',reasonCode:'OUTPUT_SCHEMA_INVALID',settlementStatus:'ESTIMATE_SETTLED',localWorkerState:'REAPED',resultKind:null,clarificationQuestion:null,draft:null});
 await page.route('**/draft-assistance/invocations',async route=>{calls++;const body=route.request().postDataJSON();keys.push(body.idempotencyKey);expect(body.parentContextId).toBeUndefined();return route.fulfill({json:{result:failure('failed'+calls)}})});
 await page.route('**/draft-assistance/invocations/failed*',route=>route.fulfill({json:{result:failure('failed'+calls)}}));
 await page.goto('/work');await page.locator('#private-input').fill(prompt);await page.getByRole('button',{name:'发送',exact:true}).click();await page.getByRole('button',{name:'使用2026-08、2026-09销售测试资料'}).click();await expect(page.getByRole('heading',{name:'理解未成功',exact:true})).toBeVisible();expect(calls).toBe(1);const messages=s.messages.length;
 await expect(page.locator('#journey-reply')).toHaveCount(0);await expect(page.getByLabel('全流程进展')).toContainText('理解结果格式未通过校验');await expect(page.getByLabel('模型流式输出')).toHaveCount(0);
 await page.reload();await expect(page.getByRole('button',{name:'沿用原问题重新理解'})).toBeVisible();expect(calls).toBe(1);
 await page.getByRole('button',{name:'沿用原问题重新理解'}).dblclick();await expect.poll(()=>calls).toBe(2);await expect(page.getByRole('heading',{name:'理解未成功',exact:true})).toBeVisible();expect(s.messages).toHaveLength(messages);expect(new Set(keys).size).toBe(2);
});
test('old misleading clarification journal renders stopped and an unknown receipt cannot authorize a new model call',async({page})=>{
 const s=await fixture(page);s.journal={version:2,state:{key:'old',phase:'CLARIFY',question:prompt,messages:[{id:'user:q',text:prompt}],log:[],draft:{invocationId:'failed-old',state:'FAILED',reasonCode:'OUTPUT_SCHEMA_INVALID',settlementStatus:'ESTIMATE_SETTLED',localWorkerState:'REAPED'}}};let posts=0;
 await page.route('**/draft-assistance/invocations',route=>{posts++;return route.abort()});await page.route('**/draft-assistance/invocations/failed-old',route=>route.fulfill({json:{result:{invocationId:'failed-old',state:'UNKNOWN'}}}));
 await page.goto('/work?conversation=new');await expect(page.getByRole('heading',{name:'理解未成功',exact:true})).toBeVisible();await expect(page.locator('#journey-reply')).toHaveCount(0);await page.getByRole('button',{name:'沿用原问题重新理解'}).click();await expect(page.getByText('Error: 原理解调用尚未核实为已结束，不会重新请求。',{exact:true})).toBeVisible();expect(posts).toBe(0);expect(s.journal.version).toBe(2);
});

test('known coverage rejection reads actual gaps and proposes one bounded successor without replaying selection',async({page})=>{
 const s=await fixture(page),ref={resource_id:'source',revision_id:'1',digest:'a'.repeat(64)};let calls=0;
 s.journal={version:10,state:{key:'k',question:prompt,phase:'SELECT_RESOURCES',pending:'select-resources',error:'Error: AUTOMATIC_SELECTION_COVERAGE_BLOCKED',messages:[{id:'user:q',text:prompt}],log:[],source:{source:ref},problem:{business_problem_id:'p'},planning:{result:{proposal:{proposal_id:'proposal',revision:1},proposal_digest:'b'.repeat(64)}},confirmation:{digest:'c'.repeat(64),plan:{plan_id:'proposal',version:1}}}};
 await page.route('**/api/workbench/v1/planning-v2/proposal/resource-coverage?version=1',route=>route.fulfill({json:{result:{planId:'proposal',planVersion:1,planDigest:'c'.repeat(64),subject:'human:development-admin',candidates:[{state:'REJECTED',reason:'PENDING_MEMBER_REQUIREMENT_UNAVAILABLE'}],selection:null,state:'BLOCKED'}}}));
 await page.route('**/question-activity-input',route=>route.fulfill({json:{result:{state:'READY',planningRequest:{target:{},answers:['original goal'],idempotency_key:route.request().postDataJSON().idempotencyKey,policy:{schema_version:'planning-policy.v2',mode:'FREE',required_operations:[],prohibited_operations:[],business_acceptance_as_task:false,template:null},output_language:'zh-CN'}}}}));
 await page.route('**/planning-v2/invocations',route=>{calls++;const body=route.request().postDataJSON();expect(body.source_proposal).toEqual({resource_id:'proposal',revision_id:'1',digest:'b'.repeat(64)});expect(body.answers.at(-1)).toContain('PENDING_MEMBER_REQUIREMENT_UNAVAILABLE');expect(body.idempotency_key).toBe('k:planning:1');return route.fulfill({status:503,json:{reasonCode:'REPAIR_TEST_STOP'}})});
 await page.goto('/work?conversation=new');await expect.poll(()=>calls).toBe(1);await expect(page.getByText('本次处理停在当前步骤，已有内容已保留。')).toBeVisible();expect(s.journal.state?.cycle).toBe(1);expect(s.journal.state?.expectedPlanVersion).toBe(1);await page.reload();await expect(page.getByText('本次处理停在当前步骤，已有内容已保留。')).toBeVisible();expect(calls).toBe(1);
});


test('new-domain criteria stay in the conversation and unavailable tools remain explicit',async({page})=>{
 const s=await fixture(page),source={source:{resource_id:'energy',revision_id:'1',digest:'d'.repeat(64)},name:'能源记录',label:'能耗测试资料',periods:[],sourceSchema:'tabular-diagnostic-source.v1',synthetic:true,completionCriteria:['按计量点和单位分别统计超限记录','缺失数据单列'],assessment:{state:'MISSING_TOOLS',missingOperations:['ANALYZE_DATA'],limitations:['只读分析']}};
 s.journal={version:2,state:{key:'energy',question:'看看能耗哪里异常',phase:'CLARIFY',messages:[{id:'user:q',text:'看看能耗哪里异常'}],sources:[source],log:[]}};
 await page.goto('/work?conversation=new');await expect(page.getByRole('button',{name:'使用现有能耗测试资料'})).toBeDisabled();await expect(page.getByText('“能耗测试资料”可读取，但缺少兼容的执行工具，暂不能自动分析。')).toBeVisible();expect(s.modelCalls).toBe(0);
 s.journal={version:3,state:{...s.journal.state,source,phase:'RUNNING'}};await page.reload();await expect(page.getByText('按计量点和单位分别统计超限记录')).toBeVisible();await expect(page.getByText('缺失数据单列',{exact:true})).toBeVisible();expect(s.modelCalls).toBe(0);
});


test('resource recheck requires a matching durable no-execution receipt and uses a new key',async({page})=>{
 const s=await fixture(page);let writes=0;
 s.journal={version:10,state:{key:'k',question:prompt,phase:'RESOURCES',pending:'resources',error:'Error: 分析所需能力尚未全部就绪：',messages:[{id:'user:q',text:prompt}],log:[],confirmation:{digest:'c'.repeat(64),plan:{plan_id:'p',version:2}}}};
 await page.route('**/planning-v2/p/resource-preparation**',async route=>{
  if(route.request().method()==='GET')return route.fulfill({json:{result:{planId:'p',planVersion:2,planDigest:'c'.repeat(64),subject:'human:development-admin',state:'PARTIALLY_READY',executionStarted:false}}});
  writes++;expect(route.request().postDataJSON().idempotencyKey).toBe('k:resources:0:recheck:1');return route.fulfill({json:{result:{state:'PARTIALLY_READY',assembly:{reason:'MISSING_TOOL'},resources:[]}}});
 });
 await page.goto('/work?conversation=new');await page.getByRole('button',{name:'重新核对可用能力'}).click();await expect.poll(()=>writes).toBe(1);await expect(page.getByText('Error: 分析所需能力尚未全部就绪：MISSING_TOOL')).toBeVisible();expect(s.modelCalls).toBe(0);
});

for(const reason of ['READONLY_CONTINUATION_VALIDATION_FAILED','NETWORK_UNKNOWN'])test('execution continuation is offered only for known validation rejection: '+reason,async({page})=>{
 const s=await fixture(page);s.journal={version:2,state:{key:'k',question:prompt,phase:'EXECUTE',pending:'execute',error:'Error: '+reason,messages:[{id:'user:q',text:prompt}],log:[]}};
 await page.goto('/work?conversation=new');await expect(page.getByRole('button',{name:'配置修复后继续分析'})).toHaveCount(reason==='READONLY_CONTINUATION_VALIDATION_FAILED'?1:0);expect(s.modelCalls).toBe(0);
});

test('empty source dates use the full source scope without sending an empty time range',async({page})=>{
 const s=await fixture(page);s.journal={version:2,state:{key:'latency',question:'看看响应异常',phase:'CLARIFY',messages:[{id:'user:q',text:'看看响应异常'}],sources:[{source:{resource_id:'latency',revision_id:'1',digest:'d'.repeat(64)},name:'响应资料',label:'响应资料',periods:[],sourceSchema:'tabular-diagnostic-source.v1',synthetic:true}],log:[]}};
 await page.goto('/work?conversation=new');await page.getByRole('button',{name:'使用现有响应资料'}).click();await expect.poll(()=>s.modelCalls).toBe(1);expect(s.messages[0].content).toContain('分析范围为该资料包含的全部记录');expect(s.messages[0].content).not.toContain('时间范围为。');
});

test('known exhausted coverage can recheck new capabilities without replaying model or execution',async({page})=>{
 const s=await fixture(page);let selections=0;
 s.journal={version:10,state:{key:'k',question:prompt,cycle:2,phase:'SELECT_RESOURCES',pending:'select-resources',error:'Error: 现有能力仍不能完成该方案，已保留资料与方案缺口。',messages:[{id:'user:q',text:prompt}],log:[],confirmation:{digest:'c'.repeat(64),plan:{plan_id:'p',version:3,semantics:{requirements:[{kind:'EMPLOYEE',selected:null}]}}}}};
 await page.route('**/planning-v2/p/resource-coverage?version=3',route=>route.fulfill({json:{result:{planId:'p',planVersion:3,planDigest:'c'.repeat(64),subject:'human:development-admin',candidates:[],state:'BLOCKED'}}}));
 await page.route('**/planning-v2/p/resource-selection/automatic',route=>{selections++;expect(route.request().postDataJSON().idempotencyKey).toBe('k:selection:2:recheck:1');return route.fulfill({status:409,json:{reasonCode:'AUTOMATIC_SELECTION_COVERAGE_BLOCKED'}})});
 await page.goto('/work?conversation=new');await page.getByRole('button',{name:'能力补齐后继续分析'}).click();await expect.poll(()=>selections).toBe(1);await expect(page.getByRole('button',{name:'能力补齐后继续分析'})).toBeVisible();expect(s.modelCalls).toBe(0);
});

test('running native question survives refresh and an answer continues the exact invocation',async({page})=>{
 const s=await fixture(page),digest='a'.repeat(64),ref={resource_id:'p',revision_id:'1',digest:'b'.repeat(64)};
 s.journal={version:2,state:{key:'k',question:'检查交接说明',phase:'RUNNING',execution:digest,problem:{business_problem_id:'p'},messages:[{id:'user:q',text:'检查交接说明'}],log:[]}};
 let answer:string|null=null,posts=0;
 await page.route('**/api/workbench/v1/prepared-executions/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/native-progress'))return route.fulfill({json:{result:{steps:[{id:'one',decision:{action:'TOOL',tool:'read_document'},output:{lines:[{line:1,text:'交接说明'}]},toolState:'COMPLETED'}],questions:[{invocationId:'invocation',questionKey:'question',questionDigest:'c'.repeat(64),question:'请确认测试环境还是生产环境？',expiresAt:'2099-01-01T00:00:00Z',answer,expired:false}],modelInFlight:false}}});
  if(path.endsWith('/native-answers')){posts++;expect(route.request().postDataJSON()).toEqual({invocationId:'invocation',questionKey:'question',questionDigest:'c'.repeat(64),conversationId:'new',answer:'生产环境'});answer='生产环境';return route.fulfill({json:{result:{accepted:true,replayed:false}}})}
  return route.fulfill({json:{result:{digest,executionStarted:true,preparation:{plan_id:'plan',plan_version:1,plan_digest:'c'.repeat(64),approval_id:'approval',source_snapshot:ref,semantics:{title:'文档检查',target:{problem:ref},tasks:[]},participants:[]},progress:{state:'RUNNING',version:1,tasks:[]},admission:{state:'ADMITTED',reason:null},resourceUses:[],artifacts:[],events:[],outcome:null}}});
 });
 await page.goto('/work?conversation=new');await expect(page.getByText('读取原文与行号',{exact:true})).toBeVisible();await expect(page.locator('#native-clarification-reply')).toBeVisible();await page.reload();await expect(page.locator('#native-clarification-reply')).toBeVisible();expect(posts).toBe(0);
 await page.locator('#native-clarification-reply').fill('生产环境');await page.getByRole('button',{name:'提交回答并继续'}).click();await expect(page.getByText('你的回答：生产环境。已沿用原任务继续处理。')).toBeVisible();await expect(page.locator('#native-clarification-reply')).toHaveCount(0);await page.reload();await expect(page.getByText('你的回答：生产环境。已沿用原任务继续处理。')).toBeVisible();expect(posts).toBe(1);expect(s.modelCalls).toBe(0);
});

test('first understanding request remains visible before the model returns without narration calls',async({page})=>{
 const s=await fixture(page);let release!:()=>void;const gate=new Promise<void>(r=>release=r);let calls=0;
 await page.route('**/draft-assistance/invocations',async route=>{calls++;await gate;await route.fulfill({json:{result:{invocationId:'draft',contextId:'context',turnId:'turn',turnVersion:1,state:'SUCCEEDED',resultKind:'NEEDS_CLARIFICATION',clarificationQuestion:'还需要确认范围',draft:null}}});});
 await page.goto('/work');await page.locator('#private-input').fill(prompt);await page.getByRole('button',{name:'发送',exact:true}).click();await page.getByRole('button',{name:'使用2026-08、2026-09销售测试资料'}).click();
 await expect.poll(()=>calls).toBe(1);await expect(page.getByLabel('全流程进展')).toContainText('正在理解你的问题，等待目标整理结果。');await expect(page.getByLabel('全流程进展').locator('[aria-current=step]')).toContainText('理解问题');expect(s.modelCalls).toBe(0);release();await expect(page.getByText('还需要确认范围',{exact:true})).toBeVisible();expect(calls).toBe(1);
});

test('planning has its own visible pending state before its sole model response',async({page})=>{
 const s=await fixture(page);const ref={resource_id:'source',revision_id:'1',digest:'a'.repeat(64)};s.journal={version:2,state:{key:'plan',phase:'PLAN',question:prompt,source:{source:ref},problem:{business_problem_id:'p'},messages:[],log:[]}};
 let release!:()=>void;const gate=new Promise<void>(r=>release=r);let calls=0;
 await page.route('**/question-activity-input',route=>route.fulfill({json:{result:{state:'READY',planningRequest:{target:{},answers:[]}}}}));
 await page.route('**/planning-v2/invocations',async route=>{calls++;await gate;await route.fulfill({status:503,json:{reasonCode:'TEST_STOP'}});});
 await page.goto('/work?conversation=new');await expect.poll(()=>calls).toBe(1);await expect(page.getByLabel('全流程进展')).toContainText('等待方案返回');await expect(page.getByLabel('全流程进展').locator('[aria-current=step]')).toContainText('准备方案');release();await expect(page.getByLabel('全流程进展')).toContainText('当前处理已停止');expect(calls).toBe(1);expect(s.modelCalls).toBe(0);
});

test('first native model shows progress with no completed steps and polling never overlaps',async({page})=>{
 const s=await fixture(page);const digest='a'.repeat(64);s.journal={version:2,state:{key:'run',phase:'RUNNING',execution:digest,problem:{business_problem_id:'p'},messages:[],log:[]}};
 let release!:()=>void;const gate=new Promise<void>(r=>release=r);let reads=0,posts=0,fail=false,completed=false;
 await page.route('**/api/workbench/v1/prepared-executions/**',async route=>{
  if(route.request().method()!=='GET')posts++;
  if(route.request().url().endsWith('/native-progress')){reads++;if(reads===1)await gate;if(fail)return route.fulfill({status:503,json:{}});return route.fulfill({json:{result:{steps:completed?[{id:'read',decision:{action:'TOOL',tool:'read_document'},toolState:'COMPLETED',output:{lines:[{line:1,text:'文档原文'}]}}]:[],questions:[],modelInFlight:!completed}}});}
  return route.fulfill({json:{result:{digest,preparation:{semantics:{tasks:[]},participants:[]},progress:{state:'RUNNING',tasks:[]},artifacts:[],resourceUses:[],events:[]}}});
 });
 await page.goto('/work?conversation=new');await expect(page.getByRole('region',{name:'实时执行过程'})).toContainText('正在读取已保存的执行进展');await expect.poll(()=>reads).toBe(1);await page.waitForTimeout(1600);expect(reads).toBe(1);release();await expect(page.getByRole('region',{name:'实时执行过程'})).toContainText('等待本轮返回');completed=true;await expect(page.getByText('已读取 1 行原文，可展开查看依据。')).toBeVisible();fail=true;await expect(page.getByText('最新进展暂不可用，下方保留上次读到的记录。')).toBeVisible();await expect(page.getByText('已读取 1 行原文，可展开查看依据。')).toBeVisible();fail=false;await expect(page.getByText('最新进展暂不可用，下方保留上次读到的记录。')).toHaveCount(0,{timeout:10000});expect(posts).toBe(0);expect(s.modelCalls).toBe(0);
});

for(const interrupted of [false,true])test('streamed understanding shows provisional text and never resends after disconnect '+interrupted,async({page})=>{
 const s=await fixture(page);
 await page.addInitScript(()=>{
  const original=window.fetch;let count=0;
  Object.assign(window,{streamCalls:()=>count});
  window.fetch=async(input,init)=>{
   if(String(input).endsWith('/draft-assistance/invocations')){
    count++;const enc=new TextEncoder();let controller:ReadableStreamDefaultController<Uint8Array>;
    const stream=new ReadableStream<Uint8Array>({start(c){controller=c;c.enqueue(enc.encode('event: progress\ndata: '+JSON.stringify({kind:'stream',characters:12,preview:'正在检查交接说明'})+'\n\n'));}});
    Object.assign(window,{finishStream:(interrupted:boolean)=>{if(!interrupted)controller.enqueue(enc.encode('event: result\ndata: '+JSON.stringify({status:201,body:{result:{invocationId:'draft',contextId:'c',turnId:'t',turnVersion:1,state:'SUCCEEDED',resultKind:'NEEDS_CLARIFICATION',clarificationQuestion:'请确认环境',draft:null}}})+'\n\n'));controller.close();}});
    return new Response(stream,{headers:{'Content-Type':'text/event-stream'}});
   }return original(input,init);
  };
 });
 await page.goto('/work');await page.locator('#private-input').fill(prompt);await page.getByRole('button',{name:'发送',exact:true}).click();await page.getByRole('button',{name:'使用2026-08、2026-09销售测试资料'}).click();
 await expect(page.getByLabel('模型流式输出')).toContainText('正在检查交接说明');await expect(page.getByLabel('模型流式输出')).toContainText('尚未核验');expect(s.modelCalls).toBe(0);
 await page.evaluate(interrupted=>Reflect.get(window,'finishStream')(interrupted),interrupted);
 if(interrupted){await expect(page.getByRole('alert')).toContainText('不会自动重发原请求');await page.reload();await expect(page.getByRole('alert')).toContainText('不会自动重发原请求');expect(s.modelCalls).toBe(0);}
 else{await expect(page.getByText('请确认环境',{exact:true})).toBeVisible();expect(await page.evaluate(()=>Reflect.get(window,'streamCalls')())).toBe(1);}
});

async function nativeQuestionFixture(page:Page){
 const state=await fixture(page);state.journal={version:2,state:{key:'f3',phase:'RUNNING',execution:'a'.repeat(64),problem:{business_problem_id:'p'},messages:[],log:[]}};
 const q={invocationId:'invocation',questionKey:'q1',questionDigest:'d1',question:'请确认适用《测试环境交接规范》还是《生产环境交接规范》？',expiresAt:new Date(Date.now()+600000).toISOString(),answer:null as string|null,expired:false};
 const calls:{answer:string;questionKey:string}[]=[];let denied=false,receipt='ok';
 await page.route('**/api/workbench/v1/prepared-executions/**',async route=>{
  if(route.request().url().endsWith('/native-progress'))return denied?route.fulfill({status:403,json:{}}):route.fulfill({json:{result:{steps:[],questions:[q],modelInFlight:false}}});
  if(route.request().method()==='POST'){calls.push(route.request().postDataJSON());await new Promise(r=>setTimeout(r,300));if(receipt==='rejected')return route.fulfill({status:422,json:{reasonCode:'INVALID_ANSWER'}});if(receipt==='unknown')return route.fulfill({status:503,json:{}});q.answer=calls.at(-1)!.answer;if(receipt==='lost')return route.abort();return route.fulfill({json:{result:{accepted:true,replayed:false}}});}
  return route.fulfill({json:{result:{digest:'a'.repeat(64),executionStarted:true,preparation:{plan_id:'plan',plan_version:1,plan_digest:'c'.repeat(64),approval_id:'approval',source_snapshot:{resource_id:'source',revision_id:'1',digest:'b'.repeat(64)},semantics:{title:'文档检查',target:{problem:{resource_id:'p',revision_id:'1',digest:'b'.repeat(64)}},tasks:[]},participants:[]},progress:{state:'RUNNING',version:1,tasks:[]},admission:{state:'ADMITTED',reason:null},artifacts:[],resourceUses:[],events:[],outcome:null}}});
 });return {q,calls,deny:()=>{denied=true},setReceipt:(value:string)=>{receipt=value}};
}
test('F3 fixed composer and right rail preserve exact-question draft on reload and submit once',async({page})=>{
 const s=await nativeQuestionFixture(page);await page.goto('/work?conversation=new');
 await expect(page.locator('.f3-progress-rail').getByLabel('全流程进展')).toBeVisible();
 await expect(page.locator('.f3-composer-dock #native-clarification-reply')).toBeVisible();
 await expect(page.getByRole('button',{name:'生产环境交接规范',exact:true})).toHaveAttribute('aria-pressed','false');
 await page.getByRole('button',{name:'生产环境交接规范',exact:true}).click();await page.reload();
 await expect(page.locator('#native-clarification-reply')).toHaveValue('《生产环境交接规范》');
 const dock=await page.locator('.f3-composer-dock').boundingBox();const stream=page.locator('.px-message-stream');await stream.evaluate(e=>e.scrollTop=e.scrollHeight);expect(await page.locator('.f3-composer-dock').boundingBox()).toEqual(dock);
 await page.getByRole('button',{name:'提交回答并继续'}).dblclick();await expect.poll(()=>s.calls.length).toBe(1);await expect(page.getByText('你的回答：《生产环境交接规范》。已沿用原任务继续处理。')).toBeVisible();expect(s.calls[0].questionKey).toBe('q1');
});
test('F3 expired or replaced question does not reuse another question draft',async({page})=>{
 const s=await nativeQuestionFixture(page);await page.goto('/work?conversation=new');await page.locator('#native-clarification-reply').fill('保留的旧回答');
 s.q.questionKey='q2';s.q.questionDigest='d2';await expect(page.locator('#native-clarification-reply')).toHaveValue('');s.q.expired=true;
 await expect(page.locator('#native-clarification-reply')).toHaveCount(0);await expect(page.getByText('本次等待期限已到，原记录保留；不会自动重跑。')).toBeVisible();expect(s.calls).toHaveLength(0);
});
test('F3 denied current progress removes answer action without submitting',async({page})=>{
 const s=await nativeQuestionFixture(page);await page.goto('/work?conversation=new');await expect(page.locator('#native-clarification-reply')).toBeVisible();s.deny();await expect(page.getByText('最新进展无法读取，请重新核对登录与权限。')).toBeVisible({timeout:10000});await expect(page.locator('#native-clarification-reply')).toHaveCount(0);expect(s.calls).toHaveLength(0);
});
test('F3 new conversation draft survives return and fits a narrow viewport',async({page})=>{
 await fixture(page);await page.setViewportSize({width:390,height:844});await page.goto('/work');await page.locator('#private-input').fill('新的问题草稿');await page.reload();await expect(page.locator('#private-input')).toHaveValue('新的问题草稿');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
test('F3 narrow active conversation keeps the answer visible and progress expandable',async({page})=>{
 await nativeQuestionFixture(page);await page.setViewportSize({width:390,height:844});await page.goto('/work?conversation=new');await expect(page.locator('#native-clarification-reply')).toBeVisible();const box=await page.locator('#native-clarification-reply').boundingBox();if(box!.y+box!.height>=844)console.log(await page.locator('#native-clarification-reply').evaluate(node=>{const out=[];for(let e:Element|null=node;e;e=e.parentElement){const c=getComputedStyle(e);out.push({class:e.className,rect:e.getBoundingClientRect().toJSON(),display:c.display,height:c.height,minHeight:c.minHeight,flex:c.flex,overflow:c.overflow})}return out}));expect(box!.y+box!.height).toBeLessThan(844);await page.getByRole('button',{name:'展开工作进展'}).click();await expect(page.getByLabel('全流程进展')).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

test('F3 actual Chinese-quoted alternatives preserve the selected literal without a default',async({page})=>{
 const s=await nativeQuestionFixture(page);s.q.question='本次检查采用“测试环境交接规范”还是“生产环境交接规范”？';await page.goto('/work?conversation=new');const option=page.getByRole('button',{name:'生产环境交接规范',exact:true});await expect(option).toHaveAttribute('aria-pressed','false');await option.click();await page.reload();await expect(page.locator('#native-clarification-reply')).toHaveValue('“生产环境交接规范”');await expect(option).toHaveAttribute('aria-pressed','true');expect(s.calls).toHaveLength(0);
});
test('F3 explicit answer rejection retains text and only manual resubmission writes again',async({page})=>{
 const s=await nativeQuestionFixture(page);s.setReceipt('rejected');await page.goto('/work?conversation=new');await page.locator('#native-clarification-reply').fill('生产环境');await page.getByRole('button',{name:'提交回答并继续'}).click();await expect(page.getByRole('button',{name:'重新提交回答'})).toBeEnabled();await expect(page.locator('#native-clarification-reply')).toHaveValue('生产环境');expect(s.calls).toHaveLength(1);s.setReceipt('ok');await page.getByRole('button',{name:'重新提交回答'}).click();await expect.poll(()=>s.calls.length).toBe(2);await expect(page.locator('#native-clarification-reply')).toHaveCount(0);
});
for(const receipt of ['unknown','lost'])test('F3 ambiguous answer receipt reads existing state without another POST: '+receipt,async({page})=>{
 const s=await nativeQuestionFixture(page);s.setReceipt(receipt);await page.goto('/work?conversation=new');await page.locator('#native-clarification-reply').fill('生产环境');await page.getByRole('button',{name:'提交回答并继续'}).click();await expect.poll(()=>s.calls.length).toBe(1);
 if(receipt==='lost'){await expect(page.getByText('你的回答：生产环境。已沿用原任务继续处理。')).toBeVisible();await expect(page.locator('#native-clarification-reply')).toHaveCount(0);expect(await page.evaluate(()=>Object.values(sessionStorage).includes('生产环境'))).toBe(false);await expect(page.getByLabel('实时执行过程').getByRole('alert')).toHaveCount(0);}
 else{await expect(page.getByLabel('实时执行过程').getByRole('alert')).toContainText('不会自动重发');await expect(page.locator('#native-clarification-reply')).toHaveValue('生产环境');await expect(page.getByRole('button',{name:'提交回答并继续'})).toBeDisabled();await page.waitForTimeout(1500);}
 expect(s.calls).toHaveLength(1);
});
test('F3 expired input stays only within the old question for optional reference',async({page})=>{
 const s=await nativeQuestionFixture(page);await page.goto('/work?conversation=new');await page.locator('#native-clarification-reply').fill('尚未提交的回答');s.q.expired=true;await expect(page.locator('#native-clarification-reply')).toHaveCount(0);await page.getByText('查看本题未提交内容',{exact:true}).click();await expect(page.getByText('尚未提交的回答',{exact:true})).toBeVisible();expect(s.calls).toHaveLength(0);
});

test('actual unquoted either-or question offers literal options without a default and still allows free text',async({page})=>{
 const s=await nativeQuestionFixture(page);s.q.question='请确认本次完整性检查适用测试环境交接规范，还是生产环境交接规范？';await page.goto('/work?conversation=new');const option=page.getByRole('button',{name:'生产环境交接规范',exact:true});await expect(option).toHaveAttribute('aria-pressed','false');await option.click();await expect(page.locator('#native-clarification-reply')).toHaveValue('生产环境交接规范');await page.reload();await expect(option).toHaveAttribute('aria-pressed','true');await page.locator('#native-clarification-reply').fill('其他范围，暂不检查');await expect(option).toHaveAttribute('aria-pressed','false');expect(s.calls).toHaveLength(0);
});
test('ambiguous unquoted choice wording stays free text rather than inventing alternatives',async({page})=>{
 const s=await nativeQuestionFixture(page);s.q.question='先检查资料还是先确认范围，还是暂停处理？';await page.goto('/work?conversation=new');await expect(page.getByRole('group',{name:'选择明确选项'})).toHaveCount(0);await expect(page.locator('#native-clarification-reply')).toBeVisible();expect(s.calls).toHaveLength(0);
});


test('reopening saved execution waits for authoritative progress without claiming a new execution',async({page})=>{
 const s=await fixture(page),digest='a'.repeat(64),ref={resource_id:'p',revision_id:'1',digest:'b'.repeat(64)};
 s.journal={version:2,state:{key:'saved',question:prompt,phase:'RUNNING',execution:digest,problem:{business_problem_id:'p'},messages:[{id:'user:q',text:prompt}],log:[]}};
 let release!:()=>void;const gate=new Promise<void>(r=>release=r);let posts=0;
 await page.route('**/api/workbench/v1/prepared-executions/**',async route=>{
  if(route.request().method()!=='GET')posts++;
  await gate;
  if(route.request().url().endsWith('/native-progress'))return route.fulfill({json:{result:{steps:[],questions:[],modelInFlight:false}}});
  return route.fulfill({json:{result:{digest,executionStarted:true,preparation:{plan_id:'plan',plan_version:1,plan_digest:'c'.repeat(64),approval_id:'approval',source_snapshot:ref,semantics:{title:'已保存分析',target:{problem:ref},tasks:[]},participants:[]},progress:{state:'SUCCEEDED',version:2,tasks:[]},admission:{state:'ADMITTED',reason:null},resourceUses:[],artifacts:[],events:[],outcome:null}}});
 });
 await page.goto('/work?conversation=new');await expect(page.getByRole('heading',{name:'正在读取本次工作',exact:true})).toBeVisible();
 await expect(page.getByRole('region',{name:'全流程进展'})).toContainText('正在读取已保存的执行进度与结果');await expect(page.locator('.journey-stages [aria-current=step]')).toHaveCount(0);
 await expect(page.getByRole('region',{name:'实时执行过程'})).toContainText('不会重新提交或执行任务');release();
 await expect(page.getByRole('region',{name:'全流程进展'})).toContainText('结果已返回');await expect(page.getByRole('region',{name:'实时执行过程'})).toContainText('执行已结束');expect(posts).toBe(0);expect(s.modelCalls).toBe(0);
});

test('real step opens inside original conversation, remembers disclosure and does not fabricate successful tool state',async({page})=>{
 const s=await fixture(page),digest='a'.repeat(64);s.journal={version:2,state:{key:'run',phase:'RUNNING',execution:digest,problem:{business_problem_id:'p'},messages:[],log:[]}};let posts=0;
 await page.route('**/api/workbench/v1/prepared-executions/**',r=>{if(r.request().method()!=='GET')posts++;if(r.request().url().endsWith('/native-progress'))return r.fulfill({json:{result:{steps:[{id:'actual-step',at:'2026-11-10T00:00:00Z',decision:{action:'TOOL',tool:'read_document'},toolState:'COMPLETED',output:{lines:[{line:1,text:'固定原文'}]}},{id:'unknown-step',decision:{action:'TOOL',tool:'search_documents'},toolState:'UNKNOWN',output:null}],questions:[],modelInFlight:false}}});return r.fulfill({json:{result:{digest,preparation:{semantics:{tasks:[]},participants:[]},progress:{state:'RUNNING',tasks:[]},artifacts:[],resourceUses:[],events:[]}}})});
 await page.goto('/work?conversation=new');const step=page.locator('[data-native-step="actual-step"]');await expect(step).toContainText('本步已返回');await expect(page.locator('[data-native-step="unknown-step"]')).toContainText('状态待核实');await step.click();const detail=page.getByRole('region',{name:'所选步骤详情'});await expect(detail).toBeVisible();await expect(detail.getByText('决策记录时间：',{exact:false})).toBeVisible();await expect(detail.getByLabel('文档阅读')).toContainText('固定原文');await detail.getByText('核对原文与行号',{exact:true}).click();await expect(detail.getByLabel('本步返回原文')).toContainText('第 1 行');await expect(detail.locator('.native-line-text')).toHaveText('固定原文');await expect(detail.locator('pre')).not.toBeVisible();await detail.getByText('查看原始技术记录',{exact:true}).click();await expect(detail.locator('pre')).toContainText('固定原文');await page.reload();await expect(detail.locator('pre')).toBeVisible();await expect(detail.locator('pre')).toContainText('固定原文');await detail.getByRole('button',{name:'收起步骤详情'}).click();await expect(detail).toHaveCount(0);await expect(step).toBeFocused();expect(posts).toBe(0);expect(s.modelCalls).toBe(0);
});

test('document step uses returned source and literal lines; malformed lines keep raw evidence without invented text',async({page})=>{
 const s=await fixture(page),digest='a'.repeat(64);s.journal={version:2,state:{key:'run',phase:'RUNNING',execution:digest,problem:{business_problem_id:'p'},messages:[],log:[]}};
 let output:unknown={documentId:'saved-source',lines:[{line:1,text:'# 原始规范'},{line:3,text:'<script>仅作为原文展示</script>'},{line:8,text:''}]};let posts=0;
 await page.route('**/api/workbench/v1/prepared-executions/**',r=>{if(r.request().method()!=='GET')posts++;if(r.request().url().endsWith('/native-progress'))return r.fulfill({json:{result:{steps:[{id:'document-step',decision:{action:'TOOL',tool:'read_document'},toolState:'COMPLETED',output}],questions:[],modelInFlight:false}}});return r.fulfill({json:{result:{digest,preparation:{semantics:{tasks:[]},participants:[]},progress:{state:'RUNNING',tasks:[]},artifacts:[],resourceUses:[],events:[]}}})});
 await page.goto('/work?conversation=new');const button=page.locator('[data-native-step="document-step"]');await expect(button).toContainText('原始规范');await button.click();const detail=page.getByRole('region',{name:'所选步骤详情'});await expect(detail.locator('.native-line-text')).toHaveText(['# 原始规范','<script>仅作为原文展示</script>','']);await expect(detail.locator('script')).toHaveCount(0);await expect(detail.locator('.native-line-number')).toHaveText(['第 1 行','第 3 行','第 8 行']);await expect(detail.locator('pre')).not.toBeVisible();
 for(const lines of [[{line:0,text:'不应伪造行号'}],[{line:1,text:'甲'},{line:1,text:'乙'}],[{line:1,text:'部分原文'},{line:2,text:42}],[]]){output={documentId:'saved-source',lines};await page.reload();await expect(detail.getByLabel('本步返回原文')).toHaveCount(0);await expect(detail.getByText('本步返回未提供可直接展示的完整原文行记录，请查看实际返回记录。')).toBeVisible();}
 expect(posts).toBe(0);expect(s.modelCalls).toBe(0);
});

test('complete Markdown reads as headings emphasis lists and tables while exact source remains inspectable',async({page})=>{
 const s=await fixture(page),digest='a'.repeat(64);s.journal={version:2,state:{key:'run',phase:'RUNNING',execution:digest,problem:{business_problem_id:'p'},messages:[],log:[]}};
 const text='# 文档标题\n\n## 负责人\n\n**负责人**与*说明*\n\n- 第一项\n- 第二项\n\n> 原文引用\n\n| 项目 | 状态 |\n| --- | --- |\n| 验证 | 待补充 |\n\n```js\nconst x = "原文";\n```\n\n[普通链接](https://example.com) [危险链接](javascript:alert(1))\n\n![测试图片](https://example.com/tracker.png)\n\n<script>window.markdownExecuted=true</script>';
 const lines=text.split('\n').map((text,i)=>({line:i+1,text}));let posts=0,external=0;
 await page.route('https://example.com/**',r=>{external++;return r.abort()});
 await page.route('**/api/workbench/v1/prepared-executions/**',r=>{if(r.request().method()!=='GET')posts++;if(r.request().url().endsWith('/native-progress'))return r.fulfill({json:{result:{steps:[{id:'markdown-step',decision:{action:'TOOL',tool:'read_document'},toolState:'COMPLETED',output:{documentId:'md',lines}}],questions:[],modelInFlight:false}}});return r.fulfill({json:{result:{digest,preparation:{semantics:{tasks:[]},participants:[]},progress:{state:'RUNNING',tasks:[]},artifacts:[],resourceUses:[],events:[]}}})});
 await page.goto('/work?conversation=new');await page.locator('[data-native-step="markdown-step"]').click();const detail=page.getByRole('region',{name:'所选步骤详情'}),reading=detail.getByLabel('文档阅读');await expect(reading.getByRole('heading',{name:'文档标题',level:1})).toBeVisible();await expect(reading.getByRole('heading',{name:'负责人',level:2})).toBeVisible();await expect(reading.locator('strong')).toHaveText('负责人');await expect(reading.locator('em')).toHaveText('说明');await expect(reading.locator('ul li')).toHaveCount(2);await expect(reading.getByRole('table')).toContainText('待补充');await expect(reading.locator('pre code')).toContainText('const x');await expect(reading.locator('script,img')).toHaveCount(0);await expect(reading.getByRole('link',{name:'危险链接'})).toHaveCount(0);expect(external).toBe(0);await expect(detail.getByLabel('本步返回原文')).not.toBeVisible();await detail.getByText('核对原文与行号',{exact:true}).click();expect(await detail.locator('.native-line-text').allTextContents()).toEqual(lines.map(l=>l.text));await page.reload();await expect(detail.getByLabel('本步返回原文')).toBeVisible();expect(posts).toBe(0);expect(s.modelCalls).toBe(0);
});

test('conversation rail separates fixed resource versions from exact attempt records and never links restricted bindings',async({page})=>{
 const s=await fixture(page),digest='a'.repeat(64),resource={resource_id:'skill:shared',revision_id:'old-revision',digest:'b'.repeat(64)},source={resource_id:'knowledge:fixed',revision_id:'source-old',digest:'c'.repeat(64)};s.journal={version:2,state:{key:'run',phase:'RUNNING',execution:digest,problem:{business_problem_id:'p'},messages:[],log:[]}};let posts=0;
 const participants=['read','analyze'].map(task_id=>({task_id,skill:{reference:resource,operation:task_id}}));const uses=[{resourceUseId:'use-read',state:'SUCCEEDED',binding:{kind:'SKILL',resource,taskId:'read',attemptId:'attempt-read',attemptOrdinal:1,operation:'read'}},{resourceUseId:'use-analyze-1',state:'FAILED',binding:{kind:'SKILL',resource,taskId:'analyze',attemptId:'attempt-analyze-1',attemptOrdinal:1,operation:'analyze'}},{resourceUseId:'use-analyze-2',state:'SUCCEEDED',binding:{kind:'SKILL',resource,taskId:'analyze',attemptId:'attempt-analyze-2',attemptOrdinal:2,operation:'analyze'}},{resourceUseId:'restricted',state:'READ_RESTRICTED',binding:{kind:'SKILL',resource:{...resource,resource_id:'secret'},taskId:'read',attemptId:'private',attemptOrdinal:1,operation:'read'}},{resourceUseId:'mismatch',state:'SUCCEEDED',binding:{kind:'SKILL',resource:{...resource,revision_id:'wrong'},taskId:'read',attemptId:'wrong',attemptOrdinal:1,operation:'read'}}];
 await page.route('**/api/workbench/v1/prepared-executions/**',r=>{if(r.request().method()!=='GET')posts++;if(r.request().url().endsWith('/native-progress'))return r.fulfill({json:{result:{steps:[],questions:[],modelInFlight:false}}});return r.fulfill({json:{result:{digest,preparation:{source_snapshot:source,semantics:{tasks:[{task_id:'read',title:'读取资料'},{task_id:'analyze',title:'分析资料'}]},participants},progress:{state:'RUNNING',tasks:[]},artifacts:[],resourceUses:uses,events:[]}}})});
 await page.goto('/work?conversation=new');const rail=page.getByLabel('本次数据与交付');await expect(rail.getByRole('button',{name:'查看结果与引用'})).toBeDisabled();await expect(rail.getByRole('link',{name:'查看本次资料与固定版本'})).toHaveAttribute('href',/resourceRevision=source-old.*fromExecution=.*returnConversation=new/);await rail.getByText('使用资源与来源',{exact:true}).click();await expect(rail).toContainText('1 个已核对资源版本 · 3 条调用记录');await expect(rail).toContainText('2 条关联未完整核实或读取受限');await expect(rail.getByRole('link',{name:'查看本次使用的 Skill 版本'})).toHaveCount(1);await expect(rail.getByRole('link',{name:'查看本次使用的 Skill 版本'})).toHaveAttribute('href',/selected=skill%3Ashared.*resourceRevision=old-revision/);await expect(rail).toContainText('第 1 次 · 调用失败');await expect(rail).toContainText('第 2 次 · 调用完成');await expect(rail).not.toContainText('secret');await page.reload();await expect(rail.getByRole('link',{name:'查看本次使用的 Skill 版本'})).toBeVisible();expect(posts).toBe(0);expect(s.modelCalls).toBe(0);
});

test('saved Native steps arriving before run state remain readback rather than a new execution',async({page})=>{
 const s=await fixture(page),digest='a'.repeat(64);s.journal={version:2,state:{key:'saved',phase:'RUNNING',execution:digest,problem:{business_problem_id:'p'},messages:[],log:[]}};let release!:()=>void;const gate=new Promise<void>(r=>release=r);let posts=0;
 await page.route('**/api/workbench/v1/prepared-executions/**',async r=>{if(r.request().method()!=='GET')posts++;if(r.request().url().endsWith('/native-progress'))return r.fulfill({json:{result:{steps:[{id:'old-step',decision:{action:'TOOL',tool:'read_document'},toolState:'COMPLETED',output:{lines:[{line:1,text:'保存的原文'}]}}],questions:[],modelInFlight:false}}});await gate;return r.fulfill({json:{result:{digest,preparation:{semantics:{tasks:[]},participants:[]},progress:{state:'SUCCEEDED',tasks:[]},artifacts:[],resourceUses:[],events:[]}}})});
 await page.goto('/work?conversation=new');await expect(page.locator('[data-native-step="old-step"]')).toBeVisible();const status=page.getByRole('region',{name:'实时执行过程'}).locator('p[role=status]');await expect(status).toContainText('正在读取已保存的执行状态');await expect(status).not.toContainText('正在衔接下一步');release();await expect(status).toContainText('执行已结束');expect(posts).toBe(0);expect(s.modelCalls).toBe(0);
});
