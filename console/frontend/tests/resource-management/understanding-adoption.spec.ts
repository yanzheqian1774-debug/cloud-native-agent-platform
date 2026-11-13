import {test,expect,type Page} from '@playwright/test';
const source={source:{resource_id:'source',revision_id:'1',digest:'a'.repeat(64)},sourceContentDigest:'b'.repeat(64),name:'交接材料',periods:[],sourceSchema:'document-review-source.v1',synthetic:true,assessment:{state:'READY',limitations:[]},completionCriteria:['返回材料缺口']};
async function fixture(page:Page,needsData=false,retained?:Awaited<ReturnType<typeof freshState>>){
 const state=retained??freshState(needsData);
 const initial=state.journal.state.draft;
 await installRoutes(page,state,initial);return state;
}
function freshState(needsData=false){
 const initial={state:'SUCCEEDED',resultKind:needsData?'NEEDS_DATA':'NEEDS_CLARIFICATION',invocationId:'initial',contextId:'initial-context',turnId:'initial-turn',turnVersion:1,aggregateVersion:5,clarificationQuestion:needsData?null:'请确认需要检查的环境。',dataNeeds:needsData?['请提供交接材料']:[],draft:null,conversationDelivery:{state:'SAVED',messageId:'original-answer'}};
 const state={calls:[] as Record<string,unknown>[],adoptions:[] as Record<string,unknown>[],writes:[] as string[],version:2,relation:'CURRENT_QUESTION',stale:false,lost:false,reject:false,receipt:null as Record<string,unknown>|null,last:null as Record<string,unknown>|null,target:null as Record<string,unknown>|null,denyReads:false,
 journal:{version:7,state:{key:'work',phase:'CLARIFY',understandingProtocol:3,userMessageId:'original',question:'请检查交接材料',messages:[{id:'user:original',text:'请检查交接材料'}],draft:initial,sources:needsData?[source]:[],source:undefined as typeof source|undefined,log:[] as string[]}},
 messages:[{message_id:'original',content:'请检查交接材料',author_id:'human:alice',disposition:'GOAL_RECORDED'},{message_id:'original-answer',content:initial.clarificationQuestion??'请提供交接材料',kind:'SOURCE',facts:{assistantResponse:true,state:'SUCCEEDED',response:initial,source:{kind:'DRAFT',invocationId:initial.invocationId,contextId:initial.contextId,turnId:initial.turnId,turnVersion:initial.turnVersion}}}] as Record<string,unknown>[]};
 return state;
}
async function installRoutes(page:Page,state:ReturnType<typeof freshState>,initial:ReturnType<typeof freshState>['journal']['state']['draft']){
 await page.route('**/api/**',async route=>{
  const req=route.request(),url=new URL(req.url()),p=url.pathname,b=req.method()==='POST'?req.postDataJSON():null,result=(v:unknown)=>route.fulfill({json:{result:v}});
  if(b)state.writes.push(p);
  if(p.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:alice',tenantId:'tenant',securityDomain:'domain'},csrfToken:'csrf',session:{}}});
  if(p.endsWith('/development-administrator'))return result({enabled:false});
  if(p.endsWith('/conversations/capabilities'))return result({enabled:true});
  if(p.endsWith('/draft-assistance/capabilities'))return result({conversationUnderstanding:true,conversationRelationRouting:true,initialUnderstandingAdoption:true});
  if(p.endsWith('/conversations/adoption/journey')){if(b){expect(b.expectedVersion).toBe(state.journal.version);state.journal={version:state.journal.version+1,state:b.state}}return result(state.journal)}
  if(p.endsWith('/conversations/adoption/messages')){expect(b.expectedVersion).toBe(state.version);state.version++;const id='user-'+state.version;state.messages.push({message_id:id,content:b.content,author_id:'human:alice',disposition:'FOLLOWUP_RECORDED',request_key:b.idempotencyKey});return result({identity:id})}
  if(p.endsWith('/conversations/adoption/head'))return result({conversation:{conversation_id:'adoption',version:state.version,title:'交接检查'}});
  if(p.endsWith('/conversations/adoption'))return result({conversation:{conversation_id:'adoption',version:state.version,title:'交接检查'},messages:state.messages,links:[]});
  if(p.endsWith('/draft-assistance/invocations')){
   state.calls.push(b);expect(b.conversationRouting).toBe(true);expect(b.predecessorInvocationId).toBeUndefined();const n=state.calls.length;
   const value={...initial,invocationId:'adopted-'+n,contextId:'result-context-'+n,turnId:'result-turn-'+n,resultKind:state.relation==='INDEPENDENT'?'DIRECT_ANSWER':'NEEDS_CLARIFICATION',clarificationQuestion:state.relation==='INDEPENDENT'?null:'还需要确认交接范围。',answer:state.relation==='INDEPENDENT'?'HTTP 是传输协议。':null,conversationDelivery:{state:'SAVED',messageId:'answer-'+n},conversationRoute:{relation:state.relation,currentQuestionToken:state.relation==='INDEPENDENT'?null:'token',contextDigest:'d'.repeat(64)}};
   state.last=value;const d=state.journal.state.draft;state.target={kind:'UNDERSTANDING',invocationId:d.invocationId,contextId:d.contextId,turnId:d.turnId,turnVersion:d.turnVersion,aggregateVersion:d.aggregateVersion,journalVersion:state.journal.version,journeyKey:state.journal.state.key};state.version++;state.messages.push({message_id:'answer-'+n,content:value.answer??value.clarificationQuestion,kind:'SOURCE',facts:{assistantResponse:true,invokedBy:'human:alice',requestKey:b.idempotencyKey,userMessageId:b.conversationMessageId,state:'SUCCEEDED',response:value,source:{kind:'DRAFT',invocationId:value.invocationId,contextId:value.contextId,turnId:value.turnId,turnVersion:value.turnVersion}}});return result(value);
  }
  if(p.includes('/understanding-results/')&&state.denyReads)return route.fulfill({status:403,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
  if(p.includes('/understanding-results/')&&p.endsWith('/route')){
   if(state.stale)return route.fulfill({status:409,json:{reasonCode:'CONVERSATION_ROUTING_CONTEXT_CHANGED'}});
   const last=state.calls.at(-1)!;return result({relation:state.relation,originalText:JSON.parse(last.content as string).messages.at(-1).text,messageId:last.conversationMessageId,target:state.target});
  }
  if(p.includes('/understanding-results/')&&p.endsWith('/adoption')){
   if(b){state.adoptions.push(b);if(state.reject)return route.fulfill({status:409,json:{reasonCode:'UNDERSTANDING_ADOPTION_BUDGET_UNRESOLVED'}});const old=state.journal;state.receipt={adoption:{target:{original_invocation_id:old.state.draft.invocationId,journal_version:old.version,journey_key:old.state.key,message_id:state.calls.at(-1)!.conversationMessageId},actualResult:{invocationId:state.last!.invocationId}},understanding:state.last,modelDispatched:false};if(state.lost)return route.abort();}
   return state.receipt?result(state.receipt):route.fulfill({status:404,json:{reasonCode:'UNDERSTANDING_ADOPTION_NOT_FOUND'}});
  }
  if(p.includes('/understanding-results/'))return result(state.last);
  if(p.endsWith('/conversation-sources')||p.endsWith('/conversations/adoption/sources'))return result({items:[source]});
  if(p.endsWith('/problems'))return result({problems:[]});
  if(b)return route.fulfill({status:405,json:{reasonCode:'UNEXPECTED_WRITE'}});
  return result({items:[]});
 });
}
const input=(p:Page)=>p.getByLabel('补充要求或提出问题',{exact:true});
async function send(p:Page,text:string){await input(p).fill(text);await p.getByRole('button',{name:'发送',exact:true}).click()}
test('initial reply adopts saved full result using one model call',async({page},info)=>{
 const s=await fixture(page);await page.goto('/work?conversation=adoption');await expect(page.locator('.f3-composer-dock textarea')).toHaveCount(1);await send(page,'生产环境');await expect.poll(()=>s.journal.state.draft.invocationId).toBe('adopted-1');expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(1);expect(s.journal.state.messages.at(-1)?.text).toBe('生产环境');await expect(page.getByText('还需要确认交接范围。',{exact:true}).first()).toBeVisible();await page.screenshot({path:info.outputPath('adopted-original-conversation.png'),fullPage:true});
 await page.reload();await expect(input(page)).toBeVisible();expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(1);
});
test('unrelated answer preserves the initial pending question and journal',async({page})=>{const s=await fixture(page);s.relation='INDEPENDENT';const before=JSON.stringify(s.journal);await page.goto('/work?conversation=adoption');await send(page,'HTTP 是什么？');await expect(page.getByText('HTTP 是传输协议。',{exact:true})).toBeVisible();expect(s.adoptions).toHaveLength(0);expect(JSON.stringify(s.journal)).toBe(before);expect(s.calls).toHaveLength(1)});
test('explicit source selection routes once without replacing original question',async({page})=>{const s=await fixture(page,true);await page.goto('/work?conversation=adoption');await page.getByRole('button',{name:'使用现有交付测试资料'}).click();await expect.poll(()=>s.journal.state.draft.invocationId).toBe('adopted-1');expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(1);expect(s.journal.state.source?.source).toEqual(source.source);expect(s.journal.state.question).toBe('请检查交接材料')});
test('stale question never adopts or sends a second model call',async({page})=>{const s=await fixture(page);s.stale=true;const before=JSON.stringify(s.journal);await page.goto('/work?conversation=adoption');await send(page,'生产环境');await expect(input(page)).toHaveValue('生产环境');await expect(page.getByText('暂未确认这条回复的处理结果。原问题已保留，请核查状态；不会自动重复提交。',{exact:true})).toBeVisible();expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(0);expect(JSON.stringify(s.journal)).toBe(before)});
test('unsettled budget rejection preserves original question and input',async({page})=>{const s=await fixture(page);s.reject=true;const before=JSON.stringify(s.journal);await page.goto('/work?conversation=adoption');await send(page,'生产环境');await expect(page.getByText('原问题未接受这条回答，输入已保留，请核对后修改；不会自动重发。',{exact:true})).toBeVisible();expect(JSON.stringify(s.journal)).toBe(before);await expect(input(page)).toHaveValue('生产环境');expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(1)});
test('lost adoption receipt refresh is read only and explicit continuation reuses result',async({page})=>{const s=await fixture(page);s.lost=true;await page.goto('/work?conversation=adoption');await send(page,'生产环境');await expect.poll(()=>s.adoptions.length).toBe(1);await page.reload();await expect(page.getByRole('button',{name:'继续提交这条回答'})).toBeVisible();expect(s.journal.state.draft.invocationId).toBe('initial');expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(1);await page.getByRole('button',{name:'继续提交这条回答'}).click();await expect.poll(()=>s.journal.state.draft.invocationId).toBe('adopted-1');expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(1)});

test('ready draft waiting for data uses the same adoption path after explicit source selection',async({page})=>{const s=await fixture(page,true);s.journal.state.draft={...s.journal.state.draft,resultKind:'DRAFT_READY',dataNeeds:[]};await page.goto('/work?conversation=adoption');await page.getByRole('button',{name:'使用现有交付测试资料'}).click();await expect.poll(()=>s.journal.state.draft.invocationId).toBe('adopted-1');expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(1);expect(s.journal.state.source?.source).toEqual(source.source)});

for(const lost of [false,true])test(`closed browser recovers persisted answer, receipt saved=${lost}`,async({page,browser})=>{
 const s=await fixture(page);s.reject=!lost;s.lost=lost;await page.goto('/work?conversation=adoption');await send(page,'生产环境');await expect.poll(()=>s.adoptions.length).toBe(1);
 const base=new URL(page.url()).origin;await page.close();s.reject=false;s.lost=false;
 const context=await browser.newContext();const fresh=await context.newPage();await fixture(fresh,false,s);await fresh.goto(base+'/work?conversation=adoption');
 const button=fresh.getByRole('button',{name:'核对并继续已有回答',exact:true});await expect(button).toBeVisible();const writes=s.writes.length;await fresh.reload();await expect(button).toBeVisible();expect(s.writes).toHaveLength(writes);expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(1);
 await button.click();await expect.poll(()=>s.journal.state.draft.invocationId).toBe('adopted-1');expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(lost?1:2);
 await fresh.reload();await expect(button).toHaveCount(0);expect(s.calls).toHaveLength(1);await context.close();
});
for(const invalid of ['foreign','stale','ambiguous','duplicate','denied','wrong-source'] as const)test(`persistent recovery refuses ${invalid}`,async({page,browser})=>{
 const s=await fixture(page);s.reject=true;await page.goto('/work?conversation=adoption');await send(page,'生产环境');await expect.poll(()=>s.adoptions.length).toBe(1);
 const base=new URL(page.url()).origin;await page.close();
 const facts=s.messages.at(-1)!.facts as {invokedBy:string;source:{invocationId:string};response:{conversationRoute:{relation:string}}};
 if(invalid==='foreign')facts.invokedBy='human:bob';
 if(invalid==='stale')s.target={...s.target,invocationId:'other-original'};
 if(invalid==='ambiguous')facts.response.conversationRoute.relation='AMBIGUOUS';
 if(invalid==='duplicate')s.messages.push({...s.messages.at(-1)!,message_id:'duplicate-answer'});
 if(invalid==='denied')s.denyReads=true;
 if(invalid==='wrong-source')facts.source.invocationId='unrelated-result';
 const writes=s.writes.length,context=await browser.newContext(),fresh=await context.newPage();await fixture(fresh,false,s);await fresh.goto(base+'/work?conversation=adoption');await expect(input(fresh)).toBeVisible();await expect(fresh.getByRole('button',{name:'核对并继续已有回答'})).toHaveCount(0);expect(s.writes).toHaveLength(writes);expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(1);await context.close();
});

test('persisted owner is available while source listing is delayed',async({page,browser})=>{
 const s=await fixture(page,true);s.reject=true;await page.goto('/work?conversation=adoption');await send(page,'使用原交接材料');await expect.poll(()=>s.adoptions.length).toBe(1);
 const base=new URL(page.url()).origin;await page.close();s.reject=false;
 const context=await browser.newContext(),fresh=await context.newPage();await fixture(fresh,true,s);
 let release!:()=>void;const pending=new Promise<void>(resolve=>{release=resolve});
 await fresh.route('**/conversations/adoption/sources',async route=>{await pending;await route.fulfill({json:{result:{items:[source]}}})});
 await fresh.goto(base+'/work?conversation=adoption');const button=fresh.getByRole('button',{name:'核对并继续已有回答'});await expect(button).toBeVisible();expect(s.calls).toHaveLength(1);await button.click();await expect.poll(()=>s.journal.state.draft.invocationId).toBe('adopted-1');release();await expect(button).toHaveCount(0);expect(s.calls).toHaveLength(1);await context.close();
});
