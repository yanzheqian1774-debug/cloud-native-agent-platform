import {test,expect,type Page} from '@playwright/test';
async function directFixture(page:Page,firstKind='DIRECT_ANSWER'){
 const state={availableSources:[] as Record<string,unknown>[],missingResult:false,notDispatched:false,lastResult:null as Record<string,unknown>|null,recoveries:0,calls:[] as Record<string,unknown>[],sources:0,writes:[] as string[],journal:{version:0,state:{key:'new-question',phase:'UNDERSTAND',question:'解释一下资料核对的方法',userMessageId:'q1',messages:[{id:'user:1',text:'解释一下资料核对的方法'}],log:[]} as Record<string,unknown>},messages:[{message_id:'q1',content:'解释一下资料核对的方法',author_id:'human:ordinary',disposition:'GOAL_RECORDED'}] as Record<string,unknown>[],version:1};
 await page.route('**/api/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname,body=req.method()==='POST'?req.postDataJSON():null,result=(value:unknown)=>route.fulfill({json:{result:value}});
  if(req.method()!=='GET')state.writes.push(path);
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:ordinary',tenantId:'tenant',securityDomain:'domain'},csrfToken:'csrf',session:{}}});
  if(path.endsWith('/development-administrator'))return result({enabled:false});
  if(path.endsWith('/draft-assistance/capabilities'))return result({conversationUnderstanding:true});
  if(path.endsWith('/conversations/capabilities'))return result({enabled:true});
  if(path.endsWith('/conversations'))return result({items:[]});
  if(path.endsWith('/conversations/direct/journey')){if(body){expect(body.expectedVersion).toBe(state.journal.version);state.journal={version:state.journal.version+1,state:body.state}}return result(state.journal)}
  if(path.endsWith('/conversations/direct/messages')){expect(body.expectedVersion).toBe(state.version);state.version++;const id='q'+state.version;state.messages.push({message_id:id,content:body.content,author_id:'human:ordinary',disposition:'GOAL_RECORDED'});return result({identity:id})}
  if(path.endsWith('/conversations/direct/head'))return result({conversation:{conversation_id:'direct',title:'普通交流',version:state.version}});
  if(path.endsWith('/conversations/direct'))return result({conversation:{conversation_id:'direct',title:'普通交流',version:state.version},messages:state.messages,links:[]});
  if(path.includes('/understanding-results/')){state.recoveries++;if(state.notDispatched)return route.fulfill({status:404,json:{reasonCode:'CONVERSATION_REQUEST_NOT_DISPATCHED'}});if(state.missingResult)return route.fulfill({status:404,json:{reasonCode:'CONVERSATION_RESULT_NOT_FOUND'}});expect(path.endsWith('/q1')).toBe(true);expect(new URL(req.url()).searchParams.get('requestKey')).toBe('new-question:draft:1');return result(state.lastResult)}
  if(path.endsWith('/conversation-sources')){state.sources++;return result({items:state.availableSources})}
  if(path.endsWith('/draft-assistance/invocations')){
   const input=JSON.parse(body.content);expect(input.messages.every((m:{id:string})=>m.id.startsWith('user:')&&m.id.length<=64)).toBe(true);state.calls.push(body);
   if(firstKind==='FORMAT_FAILURE'){state.lastResult={state:'FAILED',resultKind:null,reasonCode:'OUTPUT_SCHEMA_INVALID',settlementStatus:'ESTIMATE_SETTLED',localWorkerState:'REAPED',invocationId:'failed-1',conversationDelivery:{state:'NOT_COMPLETED'}};return result(state.lastResult)}
   expect(body.conversationId).toBe('direct');expect(body.conversationMessageId).toBe(state.messages.at(-1)?.message_id);
   const n=state.calls.length,kind=n===1?firstKind:'DIRECT_ANSWER',answer=kind==='DIRECT_ANSWER'?(n===1?'先**明确核对目标**，再检查资料依据。':'补充说明：逐项记录依据与缺口。'):null;
   const response={state:'SUCCEEDED',resultKind:kind,invocationId:'invocation-'+n,contextId:'context',turnId:'turn-'+n,turnVersion:n,aggregateVersion:2,answer,dataNeeds:[],draft:null,clarificationQuestion:kind==='NEEDS_CLARIFICATION'?'你希望核对哪一份资料？':null,understanding:[],submittedAt:'2026-11-12T02:00:00Z',reasonCode:null,conversationDelivery:{state:'SAVED',messageId:'a'+n}};
   state.messages.push({message_id:'a'+n,content:answer??response.clarificationQuestion,kind:'SOURCE',author_id:'human:ordinary',facts:{assistantResponse:true,state:'SUCCEEDED',requestKey:body.idempotencyKey,userMessageId:body.conversationMessageId,response,source:{kind:'DRAFT',invocationId:response.invocationId,contextId:'context',turnId:response.turnId,turnVersion:n}}});state.version++;state.lastResult=response;return result(response);
  }
  if(path.endsWith('/problems'))return result({problems:[]});
  if(req.method()!=='GET')return route.fulfill({status:405,json:{reasonCode:'UNEXPECTED_EXECUTION'}});
  return result({items:[]});
 });return state;
}

test('simple answer refresh and followup use original conversation without task calls',async({page})=>{
 const state=await directFixture(page);await page.goto('/work?conversation=direct');
 await expect(page.locator('#conversation-message-a1 .private-user')).toContainText('先明确核对目标');
 await expect(page.locator('#conversation-message-a1 .private-user strong')).toHaveText('明确核对目标');
 await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();await expect(page.locator('.f3-progress-rail')).toBeHidden();
 expect(state.calls).toHaveLength(1);expect(state.sources).toBe(0);await expect(page.getByText('已记录',{exact:true})).toHaveCount(0);
 await page.reload();await expect(page.locator('#conversation-message-a1')).toBeVisible();expect(state.calls).toHaveLength(1);
 await page.getByLabel('继续提问',{exact:true}).fill('再详细说一点');await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect(page.locator('#conversation-message-a2 .private-user')).toContainText('补充说明');
 expect(state.calls).toHaveLength(2);expect(state.sources).toBe(0);
 for(const field of ['parentContextId','parentTurnId','expectedParentVersion','predecessorInvocationId'])expect(state.calls[1][field]).toBeUndefined();
 const input=JSON.parse(String(state.calls[1].content));expect(input.schemaVersion).toBe('conversation-understanding-context.v2');expect(input.previousAssistantResponse).toEqual({invocationId:'invocation-1',answer:'先**明确核对目标**，再检查资料依据。'});expect(input.messages.at(-1).text).toBe('再详细说一点');
 await page.getByLabel('继续提问',{exact:true}).fill('再详细说一点');await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect(page.locator('#conversation-message-a3')).toBeVisible();expect(state.calls).toHaveLength(3);
 expect(state.calls[2].conversationMessageId).not.toBe(state.calls[1].conversationMessageId);expect(state.calls[2].idempotencyKey).not.toBe(state.calls[1].idempotencyKey);
 const repeated=JSON.parse(String(state.calls[2].content));expect(repeated.messages.slice(-2).map((m:{text:string})=>m.text)).toEqual(['再详细说一点','再详细说一点']);
 expect(state.writes.every(p=>p.endsWith('/journey')||p.endsWith('/messages')||p.endsWith('/draft-assistance/invocations'))).toBe(true);
});

test('necessary clarification uses fixed input without premature resource discovery',async({page})=>{
 const state=await directFixture(page,'NEEDS_CLARIFICATION');await page.goto('/work?conversation=direct');
 await expect(page.getByRole('heading',{name:'有一点需要确认'})).toBeVisible();await expect(page.getByLabel('补充说明',{exact:true})).toBeVisible();expect(state.sources).toBe(0);
 await page.getByLabel('补充说明',{exact:true}).fill('核对上线交接说明的方法');await page.getByRole('button',{name:'发送补充',exact:true}).click();
 await expect(page.locator('#conversation-message-a2')).toBeVisible();expect(state.calls).toHaveLength(2);expect(state.sources).toBe(0);
 expect(state.calls[1].parentContextId).toBe('context');expect(state.calls[1].predecessorInvocationId).toBe('invocation-1');
});


test('reload recovers only the saved original request without another model call',async({page})=>{
 const state=await directFixture(page);await page.goto('/work?conversation=direct');
 await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();
 state.journal.state={...state.journal.state,phase:'UNDERSTAND',pending:'understanding',draft:undefined};
 await page.reload();await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();
 expect(state.calls).toHaveLength(1);expect(state.recoveries).toBe(1);
});

test('unknown original request is read once and never automatically replayed',async({page})=>{
 const state=await directFixture(page);state.journal.state={...state.journal.state,understandingProtocol:3,pending:'understanding'};state.lastResult={state:'OUTCOME_UNKNOWN',conversationDelivery:{state:'NOT_COMPLETED'}};
 await page.goto('/work?conversation=direct');await expect(page.getByRole('alert')).toContainText('OUTCOME_UNKNOWN');
 expect(state.calls).toHaveLength(0);expect(state.recoveries).toBe(1);
 await expect(page.getByLabel('暂存补充',{exact:true})).toBeEnabled();await page.getByLabel('暂存补充',{exact:true}).fill('保留我的后续要求');
 await expect(page.getByRole('button',{name:'等待结果核实'})).toBeDisabled();await expect(page.locator('.journey-stages')).toHaveCount(0);
 await expect(page.getByRole('alert').getByText('原调用状态：OUTCOME_UNKNOWN。未重新调用模型，原请求保留。')).toBeHidden();
 await page.reload();await expect(page.getByRole('alert')).toContainText('OUTCOME_UNKNOWN');await expect(page.getByLabel('暂存补充',{exact:true})).toHaveValue('保留我的后续要求');
 expect(state.calls).toHaveLength(0);expect(state.recoveries).toBe(2);expect(state.writes).toEqual([]);
});


test('settled format failure is not a clarification and does not discover resources',async({page})=>{
 const state=await directFixture(page,'FORMAT_FAILURE');await page.goto('/work?conversation=direct');
 await expect(page.getByRole('heading',{name:'理解未成功',exact:true})).toBeVisible();
 await expect(page.getByRole('alert',{name:'理解结果未通过校验'})).toContainText('不需要你重复描述问题');
 await expect(page.getByLabel('补充说明',{exact:true})).toBeHidden();
 expect(state.calls).toHaveLength(1);expect(state.sources).toBe(0);
 await page.reload();await expect(page.getByRole('heading',{name:'理解未成功',exact:true})).toBeVisible();
 expect(state.calls).toHaveLength(1);expect(state.sources).toBe(0);
});

test('recovery of settled failure retains an explicit retry without dispatching',async({page})=>{
 const state=await directFixture(page);state.journal.state={...state.journal.state,understandingProtocol:3,pending:'understanding'};
 state.lastResult={state:'FAILED',resultKind:null,reasonCode:'OUTPUT_SCHEMA_INVALID',settlementStatus:'ESTIMATE_SETTLED',localWorkerState:'REAPED',invocationId:'failed-1',conversationDelivery:{state:'NOT_COMPLETED'}};
 await page.goto('/work?conversation=direct');
 await expect(page.getByRole('heading',{name:'理解未成功',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'沿用原问题重新理解'})).toBeVisible();
 expect(state.calls).toHaveLength(0);expect(state.sources).toBe(0);expect(state.recoveries).toBe(1);
});


test('confirmed pre-dispatch rejection repairs message references before continuing same question',async({page})=>{
 const state=await directFixture(page);state.missingResult=true;state.journal.state={...state.journal.state,understandingProtocol:3,pending:'understanding',error:'Error: CONVERSATION_REQUEST_CONTENT_INVALID',messages:[{id:'old-unprefixed-message',text:'解释一下资料核对的方法'}]};
 await page.goto('/work?conversation=direct');await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();
 expect(state.recoveries).toBe(1);expect(state.calls).toHaveLength(1);
 expect(JSON.parse(String(state.calls[0].content)).messages[0].id).toBe('user:old-unprefixed-message');
 expect(state.messages.filter(m=>m.author_id==='human:ordinary'&&!m.kind)).toHaveLength(1);
});

test('own successful send follows latest and remains at latest after refresh',async({page})=>{
 const state=await directFixture(page);state.messages[0].content='较长的历史问题。\n'.repeat(100);
 await page.goto('/work?conversation=direct');await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();
 const stream=page.locator('.px-message-stream');await stream.evaluate(node=>{node.dispatchEvent(new Event('wheel',{bubbles:true}));node.scrollTop=0});
 await page.getByLabel('继续提问',{exact:true}).fill('补充说明');await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect(page.locator('#conversation-message-a2')).toBeAttached();
 await expect(page.getByRole('button',{name:'回到最新消息'})).toBeHidden();
 await expect.poll(()=>stream.evaluate(node=>node.scrollHeight-node.scrollTop-node.clientHeight)).toBeLessThan(72);
 await page.reload();await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'回到最新消息'})).toBeHidden();expect(state.calls).toHaveLength(2);
 await expect(page.getByLabel('继续提问',{exact:true})).toHaveAttribute('placeholder','继续提问，或补充你的要求');
 await expect(page.locator('#conversation-message-a2 .private-receipt > details > summary')).toHaveText('查看来源与记录');
 expect(await page.locator('#conversation-message-a2 .knowledge-document-reading').evaluate(node=>getComputedStyle(node).whiteSpace)).toBe('normal');
});

for(const mode of ['repaired','withdrawn'] as const)test('data request rechecks '+mode+' source instead of using cached capability',async({page})=>{
 const state=await directFixture(page,'NEEDS_DATA');const old={name:'交接资料',sourceSchema:'document-review-source.v1',synthetic:true,periods:[],source:{resource_id:'knowledge:1',revision_id:'revision:1',digest:'old'},assessment:{state:'MISSING_TOOLS',missingOperations:['READ_DATA'],limitations:[]}};
 state.journal.state={...state.journal.state,source:old,sources:[old]};
 const current={...old,source:mode==='repaired'?old.source:{resource_id:'knowledge:1',revision_id:'revision:2',digest:'new'},assessment:{...old.assessment,state:'BOUNDED_ANALYSIS_AVAILABLE',missingOperations:[]}};state.availableSources=[current];
 await page.goto('/work?conversation=direct');await expect(page.getByLabel('补充说明',{exact:true})).toBeVisible();expect(state.sources).toBe(1);expect(state.calls).toHaveLength(1);
 expect(state.journal.state.sources).toEqual([current]);expect(state.journal.state.source).toEqual(mode==='repaired'?current:undefined);
 expect(state.writes.some(p=>p.endsWith('/problems')||p.includes('/execute'))).toBe(false);
});

for(const mode of ['repaired','withdrawn'] as const)test('waiting conversation reload reads current sources without model or journal writes '+mode,async({page})=>{
 const state=await directFixture(page,'NEEDS_DATA');
 const old={name:'交接资料',sourceSchema:'document-review-source.v1',synthetic:true,periods:[],source:{resource_id:'knowledge:1',revision_id:'revision:1',digest:'old'},assessment:{state:'MISSING_TOOLS',missingOperations:['READ_DATA'],limitations:[]}};
 state.journal.state={...state.journal.state,understandingProtocol:3,phase:'CLARIFY',draft:{state:'SUCCEEDED',resultKind:'NEEDS_DATA'},sources:[old],source:mode==='withdrawn'?old:undefined};
 const snapshot=JSON.stringify(state.journal);
 state.availableSources=[{...old,source:mode==='repaired'?old.source:{...old.source,revision_id:'revision:2',digest:'new'},assessment:{state:'BOUNDED_ANALYSIS_AVAILABLE',missingOperations:[],limitations:[]}}];
 await page.goto('/work?conversation=direct');await expect(page.getByLabel('补充说明',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'使用现有交付测试资料',exact:true})).toBeEnabled();
 if(mode==='withdrawn')await expect(page.getByRole('status').filter({hasText:'原先选定的资料'})).toContainText('原先选定的资料或执行能力当前不可用');
 await page.getByLabel('补充说明',{exact:true}).fill('尚未发送的补充');
 await page.reload();await expect(page.getByLabel('补充说明',{exact:true})).toHaveValue('尚未发送的补充');
 expect(state.calls).toHaveLength(0);expect(state.sources).toBe(2);expect(state.writes).toHaveLength(0);expect(JSON.stringify(state.journal)).toBe(snapshot);
});

test('new request retains previous answer and user constraints without old execution admission',async({page})=>{
 const state=await directFixture(page);
 const question='说明资料核对标准，只读检查，不修改源文件。';
 state.messages[0].content=question;state.journal.state.question=question;state.journal.state.messages=[{id:'user:1',text:question}];
 await page.goto('/work?conversation=direct');await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();
 await page.getByLabel('继续提问',{exact:true}).fill('按刚才的标准继续，仍然只读。');await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect(page.locator('#conversation-message-a2')).toBeVisible();
 const input=JSON.parse(String(state.calls[1].content));
 expect(input.messages.map((m:{text:string})=>m.text)).toEqual([question,'按刚才的标准继续，仍然只读。']);
 expect(input.previousAssistantResponse.answer).toBe('先**明确核对目标**，再检查资料依据。');
 expect(state.calls[1].parentContextId).toBeUndefined();expect(state.calls).toHaveLength(2);
 expect(state.journal.state.question).toBe('按刚才的标准继续，仍然只读。');expect(state.journal.state.key).toBe('question:'+state.calls[1].conversationMessageId);
});


test('server confirmed absent request resumes same key without duplicate user message',async({page})=>{
 const state=await directFixture(page);state.notDispatched=true;state.journal.state={...state.journal.state,understandingProtocol:3,pending:'understanding'};
 await page.goto('/work?conversation=direct');await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();
 expect(state.calls).toHaveLength(1);expect(state.calls[0].idempotencyKey).toBe('new-question:draft:1');expect(state.calls[0].conversationMessageId).toBe('q1');
 expect(state.messages.filter(m=>!m.kind)).toHaveLength(1);
 await page.reload();await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();expect(state.calls).toHaveLength(1);
});


test('conversation reading width stays bounded and composer aligned across viewports',async({page})=>{
 const state=await directFixture(page);await page.goto('/work?conversation=direct');await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();
 state.messages.at(-1)!.content='## 阅读宽度核对\n\n'+('这是保留的长正文，用于核对阅读、固定输入和局部溢出。\n\n'.repeat(12))+'\n```text\n'+('long-code-'.repeat(100))+'\n```\n\n|项目|内容|\n|---|---|\n|长字段|'+('abc'.repeat(200))+'|';
 await page.reload();
 for(const width of [1440,1920,2560,980,390]){
  await page.setViewportSize({width,height:1000});await expect(page.getByRole('heading',{name:'阅读宽度核对'})).toBeAttached();
  const geometry=await page.evaluate(()=>{const stream=document.querySelector('.px-message-stream')!.getBoundingClientRect(),form=document.querySelector('.private-composer')!.getBoundingClientRect();return {stream:{x:stream.x,width:stream.width},form:{x:form.x,width:form.width},overflow:document.documentElement.scrollWidth-innerWidth,boxes:['.px-content','.f3-conversation','.px-conversation','.px-message-stream'].map(s=>{const e=document.querySelector(s)!;return [s,e.getBoundingClientRect().width,getComputedStyle(e).minWidth,getComputedStyle(e).maxWidth,getComputedStyle(e).alignItems]})}});
  expect(geometry.stream.width,JSON.stringify(geometry)).toBeLessThanOrEqual(960);expect(geometry.overflow).toBeLessThanOrEqual(1);
  expect(Math.abs(geometry.stream.x-geometry.form.x)).toBeLessThanOrEqual(1);expect(Math.abs(geometry.stream.width-geometry.form.width)).toBeLessThanOrEqual(1);
 }
 expect(state.calls).toHaveLength(1);
});

test('narrow conversation exposes existing progress through explicit toggle',async({page})=>{
 const state=await directFixture(page);state.journal.state={...state.journal.state,phase:'UNDERSTAND',understandingProtocol:3,pending:'understanding'};
 state.lastResult={state:'OUTCOME_UNKNOWN',invocationId:'unknown-1',resultKind:null};
 await page.setViewportSize({width:980,height:900});await page.goto('/work?conversation=direct');
 const toggle=page.getByRole('button',{name:'展开工作进展'});await expect(toggle).toBeVisible();await toggle.click();await expect(page.getByRole('button',{name:'收起工作进展'})).toHaveAttribute('aria-expanded','true');
 await expect(page.locator('.f3-rail-content')).toBeVisible();expect(state.calls).toHaveLength(0);
});


test('narrow progress preserves bottom composer draft and reading position',async({page},testInfo)=>{
 const state=await directFixture(page);state.journal.state={...state.journal.state,phase:'UNDERSTAND',understandingProtocol:3,pending:'understanding'};
 state.messages.unshift(...Array.from({length:20},(_,i)=>({message_id:'history-'+i,content:'已保存的上下文记录 '+i,author_id:'human:ordinary',disposition:'GOAL_RECORDED'})));
 state.lastResult={state:'OUTCOME_UNKNOWN',invocationId:'unknown-1',resultKind:null};
 for(const width of [980,390]){
  await page.setViewportSize({width,height:900});await page.goto('/work?conversation=direct');
  const input=page.getByLabel('暂存补充',{exact:true});await expect(input).toBeVisible();await input.fill('关闭进展后继续这份草稿');
  const geometry=()=>page.evaluate(()=>{const dock=document.querySelector('.f3-composer-dock')!.getBoundingClientRect(),stream=document.querySelector('.px-message-stream')!;return {bottom:dock.bottom,top:dock.top,scroll:stream.scrollTop,height:stream.clientHeight,streamTop:stream.getBoundingClientRect().top,railBottom:document.querySelector('.f3-progress-rail')!.getBoundingClientRect().bottom}});
  await page.locator('.px-message-stream').evaluate(e=>{e.scrollTop=120});
  const before=await geometry();expect(before.scroll).toBeGreaterThan(0);await page.getByRole('button',{name:'展开工作进展'}).click();
  await expect(page.locator('.f3-rail-content')).toBeVisible();const expanded=await geometry();
  expect(Math.abs(expanded.bottom-before.bottom)).toBeLessThanOrEqual(1);expect(expanded.bottom).toBeGreaterThan(870);expect(expanded.height).toBeGreaterThan(100);expect(expanded.streamTop).toBeGreaterThanOrEqual(expanded.railBottom);
  await page.screenshot({path:testInfo.outputPath('progress-expanded-'+width+'.png')});
  await page.getByRole('button',{name:'收起工作进展'}).click();await expect(input).toHaveValue('关闭进展后继续这份草稿');
  const after=await geometry();expect(Math.abs(after.scroll-before.scroll)).toBeLessThanOrEqual(1);expect(Math.abs(after.bottom-before.bottom)).toBeLessThanOrEqual(1);
 }
 expect(state.calls).toHaveLength(0);expect(state.writes).toEqual([]);
});


test('saved-message cleanup retains actionable routing hints and answer provenance',async({page})=>{
 const state=await directFixture(page);await page.goto('/work?conversation=direct');await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();state.messages.push({message_id:'clarify',content:'继续处理原有工作',author_id:'human:ordinary',disposition:'CLARIFY_WORK'},{message_id:'new-goal',content:'另一个目标',author_id:'human:ordinary',disposition:'NEW_GOAL_REVIEW'});
 await page.goto('/work?conversation=direct');await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();
 await expect(page.getByText('已记录',{exact:true})).toHaveCount(0);
 await expect(page.getByText('这条要求指向哪项工作？请选择下方关联工作后补充，原消息会保留。',{exact:true})).toBeVisible();
 await expect(page.getByRole('link',{name:'核对新的业务目标'})).toBeVisible();
 await page.getByText('查看来源与记录',{exact:true}).click();await expect(page.getByText('助手答复已保存',{exact:true})).toBeVisible();
});

for(const outcome of ['readable','denied','wrong-version'])test('answer source stays exact and authorized '+outcome,async({page},testInfo)=>{
 const state=await directFixture(page);await page.goto('/work?conversation=direct');await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();
 const answer=state.messages.find(m=>m.message_id==='a1')!;const facts=answer.facts as {response:Record<string,unknown>};facts.response.inputSource={source:{resource_id:'knowledge:original',revision_id:'revision:original',digest:'a'.repeat(64)},name:'原交接说明',sourceSchema:'document-review-source.v1',sourceContentDigest:'b'.repeat(64)};
 let reads=0;await page.route('**/api/workbench/v1/resource-directory/**',route=>{reads++;expect(new URL(route.request().url()).searchParams.get('projection')).toBe('content');expect(decodeURIComponent(new URL(route.request().url()).pathname)).toBe('/api/workbench/v1/resource-directory/knowledge/knowledge:original/revision:original');if(outcome==='denied')return route.fulfill({status:403,json:{reasonCode:'READ_DENIED'}});return route.fulfill({json:{result:{kind:'knowledge',identity:'knowledge:original',subject:'human:ordinary',scope:{tenantId:'tenant',securityDomain:'domain'},revision:{revisionId:outcome==='wrong-version'?'revision:latest':'revision:original',digest:'a'.repeat(64),content:{documents:[{documentId:'doc',chunks:[{content:'# 原版本依据\n\n**责任人**：李明'+('\n\n原文核对段落。'.repeat(40))}]}]}}}}})});
 await page.reload();await page.getByText('查看来源与记录',{exact:true}).click();expect(reads).toBe(0);await page.getByRole('button',{name:'查看本次使用的原文'}).click();
 if(outcome==='readable'){await expect(page.getByRole('heading',{name:'原版本依据'})).toBeVisible();await expect(page.getByRole('region',{name:'本次回答使用的资料'}).locator('.knowledge-document-reading strong')).toHaveText('责任人');const widths=await page.evaluate(()=>({source:document.querySelector('.conversation-source-reading')!.getBoundingClientRect().width,stream:document.querySelector('.px-message-stream')!.getBoundingClientRect().width}));expect(widths.source).toBeGreaterThan(widths.stream*.85);for(const width of [1440,980,390]){await page.setViewportSize({width,height:1000});const reading=page.getByLabel('原文阅读区',{exact:true});await reading.evaluate(e=>e.scrollTop=e.scrollHeight);await expect(page.getByRole('button',{name:'收起原文'})).toBeInViewport();const size=await page.evaluate(()=>({reader:document.querySelector('.conversation-source-reading')!.getBoundingClientRect().width,stream:document.querySelector('.px-message-stream')!.getBoundingClientRect().width}));expect(size.reader).toBeGreaterThan(size.stream*.8);await page.screenshot({path:testInfo.outputPath('source-reading-'+width+'.png')})}}else{await expect(page.getByRole('alert')).toContainText(outcome==='denied'?'当前无权读取此资料版本':'资料版本核对不一致');await expect(page.getByRole('heading',{name:'原版本依据'})).toHaveCount(0)}
 await page.getByRole('button',{name:'收起原文'}).click();await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();expect(reads).toBe(1);expect(state.calls).toHaveLength(1);
});

for(const code of ['CONTEXT_ADMISSION_SOURCE_MISMATCH','PLANNING_OUTPUT_SOURCE_MISMATCH'])test(`source mismatch ${code} preserves conversation and never redispatches`,async({page},testInfo)=>{
 await page.setViewportSize({width:1440,height:1000});
 const state=await directFixture(page);
 // Fault-injected saved planning state; this does not verify real intent routing.
 state.journal.state={...state.journal.state,phase:'PLAN',pending:'planning',error:'Error: '+code};
 await page.goto('/work?conversation=direct');
 const alert=page.getByRole('alert').filter({hasText:'方案使用的资料与本次已确认的资料不一致'});
 await expect(alert).toBeVisible();
 await expect(alert).toContainText('无需重新描述问题');
 await expect(page.getByRole('region',{name:'全流程进展'})).toContainText('已暂停：资料不一致');
 await expect(page.getByRole('region',{name:'全流程进展'})).not.toContainText('最新进展暂无法确认');
 await page.locator('#source-mismatch-reply').fill('补充先暂存，不发送');
 await expect(page.getByRole('button',{name:'暂不能发送'})).toBeDisabled();
 await expect(alert.locator('details p')).toBeHidden();
 await alert.scrollIntoViewIfNeeded();
 await page.screenshot({path:testInfo.outputPath('source-mismatch.png'),fullPage:true});
 await alert.getByText('技术详情',{exact:true}).click();
 await expect(alert.locator('details p')).toHaveText('Error: '+code);
 await expect(page.locator('#conversation-message-q1')).toContainText('解释一下资料核对的方法');
 await page.reload();
 await expect(alert).toBeVisible();
 expect(state.calls).toHaveLength(0);
 expect(state.writes).toEqual([]);
 expect(state.journal.state.error).toBe('Error: '+code);
 await expect(page.locator('#source-mismatch-reply')).toHaveValue('补充先暂存，不发送');
});

test('saved answer downloads original Markdown and provenance after a fresh authorized read without model calls',async({page})=>{
 const state=await directFixture(page);await page.goto('/work?conversation=direct');
 const message=page.locator('#conversation-message-a1');await expect(message).toContainText('先明确核对目标');
 // Wait for the answer journey to settle before measuring download-only writes.
 await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();
 expect(state.journal.state.phase).toBe('DIRECT_DONE');
 const beforeCalls=state.calls.length,beforeWrites=state.writes.length;
 const event=page.waitForEvent('download');await message.getByRole('button',{name:'下载答复与来源（Markdown）'}).click();const download=await event;
 expect(download.suggestedFilename()).toBe('会话答复-a1.md');
 const {readFile}=await import('node:fs/promises');const content=await readFile((await download.path())!,'utf8');
 expect(content.startsWith('先**明确核对目标**，再检查资料依据。\n\n---')).toBe(true);
 expect(content).toContain('"会话": "direct"');expect(content).toContain('"答复": "a1"');expect(content).toContain('"invocationId": "invocation-1"');
 expect(state.calls.length).toBe(beforeCalls);expect(state.writes.length).toBe(beforeWrites);
});

for(const failure of ['denied','identity'])test(`saved answer download rejects ${failure} rather than exporting cached text`,async({page})=>{
 const state=await directFixture(page);await page.goto('/work?conversation=direct');
 const message=page.locator('#conversation-message-a1');await expect(message).toContainText('先明确核对目标');let downloads=0;page.on('download',()=>downloads++);
 if(failure==='denied')state.messages.find(m=>m.message_id==='a1')!.facts={readable:false};
 else await page.route('**/session',route=>route.fulfill({json:{principal:{principalId:'human:other',tenantId:'tenant',securityDomain:'domain'},csrfToken:'other',session:{}}}));
 await message.getByRole('button',{name:'下载答复与来源（Markdown）'}).click();await expect(message.getByRole('alert')).toBeVisible();expect(downloads).toBe(0);expect(state.calls.length).toBe(1);
});

test('Chinese punctuation bold renders without altering code escaped text or the downloaded answer',async({page})=>{
 const state=await directFixture(page);
 const markdown='**结论：**两份规范不同。\n\n**适用限制：**仅用于测试。\n\n`**代码：**保持原样`\n\n```text\n**代码块：**保持原样\n```\n\n\\*\\*字面：\\*\\*保持原样\n\n**English:**literal';
 state.journal.state={...state.journal.state,phase:'DIRECT_DONE'};
 state.messages.push({message_id:'cjk-answer',kind:'SOURCE',content:markdown,facts:{assistantResponse:true,state:'SUCCEEDED',response:{resultKind:'DIRECT_ANSWER'},source:{kind:'DRAFT',invocationId:'saved-invocation',contextId:'saved-context',turnId:'saved-turn',turnVersion:1}}});
 await page.goto('/work?conversation=direct');
 const message=page.locator('#conversation-message-cjk-answer'),reading=message.locator('.knowledge-document-reading');
 await expect(reading.locator('strong')).toHaveText(['结论：','适用限制：']);
 await expect(reading.locator('code')).toHaveText(['**代码：**保持原样','**代码块：**保持原样\n']);
 await expect(reading).toContainText('**字面：**保持原样');await expect(reading).toContainText('**English:**literal');
 const event=page.waitForEvent('download');await message.getByRole('button',{name:'下载答复与来源（Markdown）'}).click();const download=await event;
 const {readFile}=await import('node:fs/promises');expect((await readFile((await download.path())!,'utf8')).startsWith(markdown+'\n\n---')).toBe(true);
 expect(state.calls).toHaveLength(0);expect(state.writes).toHaveLength(0);
 await page.reload();await expect(page.locator('#conversation-message-cjk-answer strong')).toContainText(['结论：','适用限制：']);
 expect(state.messages.at(-1)?.content).toBe(markdown);expect(state.calls).toHaveLength(0);expect(state.writes).toHaveLength(0);
});

test('sending a followup reads only owned version metadata before append, then refreshes authorized history',async({page})=>{
 const state=await directFixture(page);await page.goto('/work?conversation=direct');await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();
 let sent=false,unnecessaryReads=0;
 await page.route('**/conversations/direct/messages',route=>{sent=true;return route.fallback()});
 await page.route('**/conversations/direct',route=>{if(!sent){unnecessaryReads++;return route.fulfill({status:503,json:{reasonCode:'HISTORY_SHOULD_NOT_GATE_APPEND'}})}return route.fallback()});
 await page.getByLabel('继续提问',{exact:true}).fill('请继续解释核对方法');await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect(page.locator('#conversation-message-a2')).toContainText('补充说明');expect(unnecessaryReads).toBe(0);expect(sent).toBe(true);expect(state.calls).toHaveLength(2);
});

test('keyboard send respects newline IME repeat and pending outcome',async({page})=>{
 const state=await directFixture(page);await page.goto('/work?conversation=direct');
 const input=page.getByLabel('继续提问',{exact:true});await expect(input).toBeVisible();
 await input.fill('第一行');await input.press('Shift+Enter');await input.press('a');
 await expect(input).toHaveValue('第一行\na');expect(state.calls).toHaveLength(1);
 await input.dispatchEvent('compositionstart');await input.press('Enter');expect(state.calls).toHaveLength(1);
 await input.dispatchEvent('compositionend');await input.dispatchEvent('keydown',{key:'Enter',keyCode:229});
 await input.dispatchEvent('keydown',{key:'Enter',repeat:true});expect(state.calls).toHaveLength(1);
 await input.press('Enter');await expect(page.locator('#conversation-message-a2')).toBeVisible();
 expect(state.calls).toHaveLength(2);expect(state.messages.filter(m=>m.content==='第一行\na')).toHaveLength(1);
});

test('keyboard cannot dispatch while original result is unknown',async({page})=>{
 const state=await directFixture(page);state.journal.state={...state.journal.state,understandingProtocol:3,pending:'understanding'};state.lastResult={state:'OUTCOME_UNKNOWN',conversationDelivery:{state:'NOT_COMPLETED'}};
 await page.goto('/work?conversation=direct');const input=page.getByLabel('暂存补充',{exact:true});await input.fill('先保留');await input.press('Enter');
 await expect(input).toHaveValue('先保留');expect(state.calls).toHaveLength(0);expect(state.writes).toEqual([]);
});

test('controlled incremental content preserves reading anchor and shows only real new content',async({page})=>{
 const state=await directFixture(page);state.messages[0].content='较长的历史问题。\n'.repeat(100);
 await page.goto('/work?conversation=direct');await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();
 const stream=page.locator('.px-message-stream');
 await stream.evaluate(n=>{n.dispatchEvent(new WheelEvent('wheel',{deltaY:-100,bubbles:true}));n.scrollTop=120});
 await expect(page.getByRole('button',{name:'回到最新消息'})).toBeVisible();
 expect(await page.getByRole('button',{name:'回到最新消息'}).evaluate(n=>getComputedStyle(n).borderRadius)).toBe('50%');
 const circle=await page.getByRole('button',{name:'回到最新消息'}).boundingBox();expect(circle!.width).toBe(circle!.height);
 await stream.evaluate(n=>{const p=document.createElement('div');p.className='journey-progress';p.textContent='受控增量内容一';n.append(p)});
 await expect(page.getByText('有新消息',{exact:true})).toBeVisible();
 await expect.poll(()=>stream.evaluate(n=>n.scrollTop)).toBe(120);
 await page.getByRole('button',{name:'回到最新消息'}).click();
 await expect.poll(()=>stream.evaluate(n=>n.scrollHeight-n.scrollTop-n.clientHeight)).toBeLessThan(72);
 await expect(page.getByText('有新消息',{exact:true})).toBeHidden();
 await stream.evaluate(n=>{n.querySelector('.journey-progress')!.textContent+='\n受控增量内容二'.repeat(20)});
 await expect.poll(()=>stream.evaluate(n=>n.scrollHeight-n.scrollTop-n.clientHeight)).toBeLessThan(72);
 await stream.evaluate(n=>{n.dispatchEvent(new WheelEvent('wheel',{deltaY:-100,bubbles:true}));n.scrollTop=120});
 await stream.evaluate(n=>{const p=n.querySelector('.journey-progress')!;p.replaceWith(p.cloneNode(true))});
 await expect(page.getByText('有新消息',{exact:true})).toBeHidden();
 expect(state.calls).toHaveLength(1);
});

// The model output is controlled here: this proves propagation of a corrected
// goal into owner requests, not the real model's semantic understanding.
for(const longDescription of [false,true])test(`corrected task keeps canonical goal in criteria and planning ${longDescription}`,async({page})=>{
 const state=await directFixture(page);
 const original='检查上线材料完整性，生成待补清单';
 const title='比较测试与生产规范';
 const description='只比较两份规范的适用范围，不检查上线材料完整性，也不生成待补清单。'+(longDescription?'保留逐条原文依据，不推断技术正确性。'.repeat(40):'');
 const source={source:{resource_id:'source',revision_id:'source-v1',digest:'a'.repeat(64)},name:'两份交接规范',periods:[],sourceSchema:'document-review-source.v1',synthetic:true,completionCriteria:['提供逐条原文依据']};
 const problem={business_problem_id:'corrected-problem',revision_id:'corrected-revision',digest:'b'.repeat(64),title,description};
 state.journal.state={...state.journal.state,understandingProtocol:3,phase:'CLARIFY',question:original,source,messages:[{id:'user:q1',text:original}],draft:{state:'SUCCEEDED',resultKind:'NEEDS_CLARIFICATION',invocationId:'previous-understanding',contextId:'previous-context',turnId:'previous-turn',turnVersion:1,clarificationQuestion:'需要按哪份规范检查完整性？',draft:null},log:[]};
 state.availableSources=[source];
 await page.route('**/draft-assistance/invocations',route=>{
  const body=route.request().postDataJSON(),input=JSON.parse(body.content);state.calls.push(body);
  expect(input.messages.at(-1).text).toBe(description);expect(input.previousQuestion).toBe('需要按哪份规范检查完整性？');expect(body.predecessorInvocationId).toBe('previous-understanding');
  const response={state:'SUCCEEDED',resultKind:'DRAFT_READY',invocationId:'corrected-understanding',contextId:'corrected-context',turnId:'corrected-turn',turnVersion:2,draft:{title,description},conversationDelivery:{state:'SAVED',messageId:'corrected-answer'}};
  state.messages.push({message_id:'corrected-answer',kind:'SOURCE',content:description,facts:{assistantResponse:true,state:'SUCCEEDED',response}});state.version++;return route.fulfill({json:{result:response}});
 });
 const criteria:Record<string,unknown>[]=[],planning:Record<string,unknown>[]=[],creates:Record<string,unknown>[]=[];
 await page.route('**/api/workbench/v1/problems',route=>{
  if(route.request().method()!=='POST')return route.fallback();creates.push(route.request().postDataJSON());return route.fulfill({json:{result:{revision:problem}}});
 });
 await page.route('**/api/workbench/v1/problems/corrected-problem',route=>route.fulfill({json:{result:{problem:{aggregate_version:1},revisions:[problem]}}}));
 await page.route('**/api/workbench/v1/problems/corrected-problem/criteria-sets',route=>route.fulfill({json:{result:{revision:{}}}}));
 await page.route('**/api/workbench/v1/problems/corrected-problem/lifecycle',route=>route.fulfill({json:{result:{}}}));
 await page.route('**/draft-assistance/invocations/corrected-understanding/problem-link',route=>route.fulfill({json:{result:{}}}));
 await page.route('**/api/workbench/v1/success-criteria',route=>{criteria.push(route.request().postDataJSON());return route.fulfill({json:{result:{revision:{revision_id:'criterion-corrected'}}}})});
 await page.route('**/conversations/direct/links',route=>route.fulfill({json:{result:{}}}));
 await page.route('**/question-activity-input',route=>{planning.push(route.request().postDataJSON());return route.fulfill({json:{result:{state:'READY',planningRequest:{target:{problem:{resource_id:problem.business_problem_id,revision_id:problem.revision_id,digest:problem.digest}},answers:[title]}}}})});
 await page.route('**/planning-v2/preflight',route=>route.fulfill({status:409,json:{reasonCode:'CONTROLLED_STOP_BEFORE_MODEL'}}));
 await page.goto('/work?conversation=direct');
 await page.getByLabel('补充说明',{exact:true}).fill(description);await page.getByRole('button',{name:'发送补充',exact:true}).click();
 await expect.poll(()=>planning.length).toBe(1);
 expect(creates).toHaveLength(1);expect(creates[0].description).toBe(description);
 expect(criteria).toHaveLength(1);expect((criteria[0].measurement as {rubric:string}).rubric).toContain('回答已确认的用户目标：'+description);
 expect((criteria[0].measurement as {rubric:string}).rubric).not.toContain('回答已确认的用户目标：'+original);
 expect(planning[0].question).toBe(title);expect(planning[0].problemId).toBe(problem.business_problem_id);expect(planning[0].source).toEqual(source.source);
 expect(state.journal.state.question).toBe(original);expect((state.journal.state.messages as {text:string}[])[0].text).toBe(original);
 await expect(page.getByRole('alert')).toBeVisible();await page.reload();await expect(page.getByRole('alert')).toBeVisible();
 expect(planning).toHaveLength(1);expect(creates).toHaveLength(1);expect(criteria).toHaveLength(1);expect(state.calls).toHaveLength(1);
});

for(const question of ['你好','解释一下缓存和数据库的区别'])test('unclassified ordinary question remains lightweight '+question,async({page})=>{
 const state=await directFixture(page);state.messages[0].content=question;state.journal.state.question=question;state.journal.state.messages=[{id:'user:1',text:question}];
 let release!:()=>void;const gate=new Promise<void>(resolve=>{release=resolve});
 await page.route('**/draft-assistance/invocations',async route=>{await gate;await route.fallback()});
 await page.goto('/work?conversation=direct');
 await expect(page.getByRole('region',{name:'全流程进展'})).toBeVisible();
 await expect(page.locator('.journey-stages')).toHaveCount(0);
 expect(state.writes.some(p=>p.endsWith('/problems')||p.includes('/execute'))).toBe(false);
 release();await expect(page.locator('#conversation-message-a1')).toBeVisible();
 expect(state.calls).toHaveLength(1);expect(state.sources).toBe(0);
 expect(JSON.parse(String(state.calls[0].content)).messages.at(-1).text).toBe(question);
});

test('conversation admission refusal retains first cause across refresh without read or redispatch',async({page},testInfo)=>{
 const state=await directFixture(page);state.missingResult=true;
 state.journal.state={...state.journal.state,understandingProtocol:3,pending:'understanding',error:'Error: CONTEXT_ADMISSION_CONVERSATION_BINDING_REQUIRED'};
 const original=JSON.stringify(state.journal);
 await page.goto('/work?conversation=direct');
 await expect(page.getByRole('heading',{name:'本次提问尚未开始处理',exact:true})).toBeVisible();
 await expect(page.getByRole('alert')).toContainText('原提问已保留');
 await expect(page.locator('.journey-stages')).toHaveCount(0);
 await page.screenshot({path:testInfo.outputPath('admission-not-started.png')});
 await page.reload();await expect(page.getByRole('heading',{name:'本次提问尚未开始处理',exact:true})).toBeVisible();
 expect(state.recoveries).toBe(0);expect(state.calls).toHaveLength(0);expect(state.writes).toEqual([]);
 expect(JSON.stringify(state.journal)).toBe(original);
 await expect(page.getByText('DRAFT_ASSISTANCE_NOT_FOUND',{exact:false})).toHaveCount(0);
});

for(const reason of ['CONVERSATION_INPUT_ACCESS_DENIED','CONVERSATION_INPUT_SERVICE_UNAVAILABLE','CONVERSATION_SOURCE_STALE_OR_UNREADABLE'])test('known input refusal remains stopped after absent invocation read '+reason,async({page})=>{
 const state=await directFixture(page);state.notDispatched=true;
 state.journal.state={...state.journal.state,understandingProtocol:3,pending:'understanding',error:'Error: '+reason};
 const original=JSON.stringify(state.journal);
 await page.goto('/work?conversation=direct');
 await expect(page.getByRole('alert')).toContainText('原提问已保留');
 await expect.poll(()=>state.recoveries).toBeGreaterThan(0);
 await page.reload();await expect(page.getByRole('alert')).toContainText('原提问已保留');
 expect(state.calls).toHaveLength(0);expect(state.writes).toEqual([]);expect(JSON.stringify(state.journal)).toBe(original);
});

for(const variant of ['saved','new-goal','denied','wrong-message','wrong-actor','not-source','not-succeeded','wrong-kind','independent','conflicting-route','admin-viewer','admin-wrong-actor'] as const)test('persisted relation replaces stale disposition only with exact readable facts '+variant,async({page},info)=>{
 const state=await directFixture(page);state.journal.state={...state.journal.state,phase:'RUNNING',key:'retained-work'};
 state.messages.push({message_id:'native-reply',content:'按生产规范检查',author_id:'human:ordinary',disposition:variant==='new-goal'?'NEW_GOAL_REVIEW':'CLARIFY_WORK'});
 const facts:Record<string,unknown>={assistantResponse:true,readable:true,state:'SUCCEEDED',invokedBy:'human:ordinary',userMessageId:'native-reply',requestKey:'retained-route',source:{kind:'DRAFT',invocationId:'route-original',contextId:'context-route',turnId:'turn-route',turnVersion:1},response:{resultKind:'CURRENT_QUESTION_ANSWER',conversationRoute:{relation:'CURRENT_QUESTION'}}};
 if(variant==='denied')facts.readable=false;
 if(variant==='wrong-message')facts.userMessageId='different-user-message';
 if(variant==='wrong-actor'||variant==='admin-wrong-actor')facts.invokedBy='human:other';
 if(variant==='not-succeeded')facts.state='FAILED';
 if(variant==='independent')facts.response={resultKind:'DIRECT_ANSWER',conversationRoute:{relation:'INDEPENDENT'}};
 if(variant==='wrong-kind')facts.response={resultKind:'DIRECT_ANSWER',conversationRoute:{relation:'CURRENT_QUESTION'}};
 state.messages.push({message_id:'retained-route-response',content:'已理解这条补充，将核对当前问题后接续。',author_id:'human:ordinary',disposition:'GOAL_RECORDED',kind:variant==='not-source'?'OTHER':'SOURCE',facts});
 if(variant==='conflicting-route')state.messages.push({message_id:'other-route-response',content:'单独回复',kind:'SOURCE',facts:{...facts,response:{resultKind:'DIRECT_ANSWER',conversationRoute:{relation:'INDEPENDENT'}}}});
 if(variant==='admin-viewer'||variant==='admin-wrong-actor'){await page.route('**/api/workbench/v1/session',route=>route.fulfill({json:{principal:{principalId:'human:development-admin',tenantId:'tenant',securityDomain:'domain'},csrfToken:'csrf',session:{}}}));await page.route('**/development-administrator',route=>route.fulfill({json:{result:{enabled:true}}}));}
 const resolved=variant==='saved'||variant==='new-goal'||variant==='admin-viewer';
 await page.setViewportSize({width:1440,height:900});await page.goto('/work?conversation=direct');
 const message=page.locator('#conversation-message-native-reply');await expect(message).toBeVisible();
 await expect(message.getByText('这条补充已识别为当前问题的回答，接续状态见本会话当前工作。',{exact:true})).toHaveCount(resolved?1:0);
 await expect(message.getByText('这条要求指向哪项工作？请选择下方关联工作后补充，原消息会保留。',{exact:true})).toHaveCount(resolved?0:1);
 if(variant==='new-goal')await expect(message.getByRole('link',{name:'核对新的业务目标'})).toHaveCount(0);
 if(variant==='saved')await page.screenshot({path:info.outputPath('persisted-route-hint-1440.png'),fullPage:true});
 await page.reload();await expect(message).toBeVisible();await expect(message.getByText('这条补充已识别为当前问题的回答，接续状态见本会话当前工作。',{exact:true})).toHaveCount(resolved?1:0);expect(state.calls).toHaveLength(0);expect(state.writes).toHaveLength(0);
});
