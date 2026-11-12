import {test,expect,type Page} from '@playwright/test';
async function directFixture(page:Page,firstKind='DIRECT_ANSWER'){
 const state={availableSources:[] as Record<string,unknown>[],missingResult:false,lastResult:null as Record<string,unknown>|null,recoveries:0,calls:[] as Record<string,unknown>[],sources:0,writes:[] as string[],journal:{version:0,state:{key:'new-question',phase:'UNDERSTAND',question:'解释一下资料核对的方法',userMessageId:'q1',messages:[{id:'user:1',text:'解释一下资料核对的方法'}],log:[]} as Record<string,unknown>},messages:[{message_id:'q1',content:'解释一下资料核对的方法',author_id:'human:ordinary',disposition:'GOAL_RECORDED'}] as Record<string,unknown>[],version:1};
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
  if(path.endsWith('/conversations/direct'))return result({conversation:{conversation_id:'direct',title:'普通交流',version:state.version},messages:state.messages,links:[]});
  if(path.includes('/understanding-results/')){state.recoveries++;if(state.missingResult)return route.fulfill({status:404,json:{reasonCode:'CONVERSATION_RESULT_NOT_FOUND'}});expect(path.endsWith('/q1')).toBe(true);expect(new URL(req.url()).searchParams.get('requestKey')).toBe('new-question:draft:1');return result(state.lastResult)}
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
 expect(state.calls).toHaveLength(1);expect(state.sources).toBe(0);
 await page.reload();await expect(page.locator('#conversation-message-a1')).toBeVisible();expect(state.calls).toHaveLength(1);
 await page.getByLabel('继续提问',{exact:true}).fill('再详细说一点');await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect(page.locator('#conversation-message-a2 .private-user')).toContainText('补充说明');
 expect(state.calls).toHaveLength(2);expect(state.sources).toBe(0);
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
 expect(state.calls).toHaveLength(0);expect(state.recoveries).toBe(2);
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

test('new reply indicator clears when latest is visible and stays clear after refresh',async({page})=>{
 const state=await directFixture(page);state.messages[0].content='较长的历史问题。\n'.repeat(100);
 await page.goto('/work?conversation=direct');await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();
 const stream=page.locator('.px-message-stream');await stream.evaluate(node=>{node.dispatchEvent(new Event('wheel',{bubbles:true}));node.scrollTop=0});
 await page.getByLabel('继续提问',{exact:true}).fill('补充说明');await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect(page.locator('#conversation-message-a2')).toBeAttached();
 await expect(page.getByRole('button',{name:'有新消息，回到最新'})).toBeVisible();
 await page.getByRole('button',{name:'有新消息，回到最新'}).click();
 await expect(page.getByRole('button',{name:'有新消息，回到最新'})).toBeHidden();
 await expect.poll(()=>stream.evaluate(node=>node.scrollHeight-node.scrollTop-node.clientHeight)).toBeLessThan(72);
 await page.reload();await expect(page.getByLabel('继续提问',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'有新消息，回到最新'})).toBeHidden();expect(state.calls).toHaveLength(2);
 await expect(page.getByLabel('继续提问',{exact:true})).toHaveAttribute('placeholder','继续提问，或补充你的要求');
 await expect(page.locator('#conversation-message-a2 .private-receipt summary')).toHaveText('查看来源与记录');
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
