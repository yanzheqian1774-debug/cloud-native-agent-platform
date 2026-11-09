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
 const s=await fixture(page);await page.goto('/work');await page.locator('#private-input').fill(prompt);await page.getByRole('button',{name:'发送',exact:true}).click();await expect(page).toHaveURL(/conversation=new/);await expect(page.getByText('你想比较哪个时间范围的销售？',{exact:true})).toBeVisible();expect(s.modelCalls).toBe(1);await expect(page.getByRole('link',{name:'在本会话核对目标与草稿'})).toHaveCount(0);
 await page.reload();await expect(page.getByRole('button',{name:'使用2026-08、2026-09销售测试资料'})).toBeVisible();expect(s.modelCalls).toBe(1);
 await page.getByRole('button',{name:'使用2026-08、2026-09销售测试资料'}).click();await expect.poll(()=>s.modelCalls).toBe(2);await expect(page).toHaveURL(/conversation=new/);await expect(page.locator('.conversation-journey blockquote')).toContainText('项目销售样本');
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

test('known settled invalid understanding keeps the question and offers source clarification without automatic retry',async({page})=>{
 const s=await fixture(page);let calls=0;
 await page.route('**/draft-assistance/invocations',async route=>{calls++;const body=route.request().postDataJSON();if(calls===2)expect(body.parentContextId).toBeUndefined();return route.fulfill({json:{result:{invocationId:'failed'+calls,contextId:'context'+calls,turnId:'turn',turnVersion:1,state:'FAILED',reasonCode:'OUTPUT_SCHEMA_INVALID',settlementStatus:'ESTIMATE_SETTLED',localWorkerState:'REAPED',resultKind:null,clarificationQuestion:null,draft:null}}})});
 await page.goto('/work');await page.locator('#private-input').fill(prompt);await page.getByRole('button',{name:'发送',exact:true}).click();await expect(page.getByRole('button',{name:'使用2026-08、2026-09销售测试资料'})).toBeVisible();expect(calls).toBe(1);expect(s.journal.state?.draft).toMatchObject({state:'FAILED'});
 await page.reload();await expect(page.getByRole('button',{name:'使用2026-08、2026-09销售测试资料'})).toBeVisible();expect(calls).toBe(1);await page.getByRole('button',{name:'使用2026-08、2026-09销售测试资料'}).click();await expect.poll(()=>calls).toBe(2);await expect(page.getByText('请补充你最关注的问题，例如关注的指标、时间或对象。')).toBeVisible();
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
