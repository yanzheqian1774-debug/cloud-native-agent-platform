import {test,expect,type Page} from '@playwright/test';
const source={source:{resource_id:'source',revision_id:'1',digest:'a'.repeat(64)},sourceContentDigest:'b'.repeat(64),name:'交接材料',periods:[],sourceSchema:'document-review-source.v1',synthetic:true,assessment:{state:'READY',limitations:[]},completionCriteria:['返回材料缺口']};
async function fixture(page:Page,needsData=false,retained?:Awaited<ReturnType<typeof freshState>>){
 const state=retained??freshState(needsData);
 const initial=state.journal.state.draft;
 await installRoutes(page,state,initial);return state;
}
function freshState(needsData=false){
 const initial={state:'SUCCEEDED',resultKind:needsData?'NEEDS_DATA':'NEEDS_CLARIFICATION',invocationId:'initial',contextId:'initial-context',turnId:'initial-turn',turnVersion:1,aggregateVersion:5,clarificationQuestion:needsData?null:'请确认需要检查的环境。',dataNeeds:needsData?['请提供交接材料']:[],draft:null,conversationDelivery:{state:'SAVED',messageId:'original-answer'}};
 const state={calls:[] as Record<string,unknown>[],adoptions:[] as Record<string,unknown>[],writes:[] as string[],version:2,relation:'CURRENT_QUESTION',stale:false,lost:false,reject:false,receipt:null as Record<string,unknown>|null,last:null as Record<string,unknown>|null,target:null as Record<string,unknown>|null,denyReads:false,rejectCode:'UNDERSTANDING_ADOPTION_BUDGET_UNRESOLVED',rejectStatus:409,adoptionReadStatus:0,journalFailure:false,guardAfterCommit:false,sourceObservation:null as Record<string,unknown>|null,sourceCapability:undefined as string|undefined,
 journal:{version:7,state:{key:'work',phase:'CLARIFY',understandingProtocol:3,userMessageId:'original',question:'请检查交接材料',messages:[{id:'user:original',text:'请检查交接材料'}],draft:initial,sources:needsData?[source]:[],source:undefined as typeof source|undefined,log:[] as string[]}},
 messages:[{message_id:'original',content:'请检查交接材料',author_id:'human:alice',disposition:'GOAL_RECORDED'},{message_id:'original-answer',content:initial.clarificationQuestion??'请提供交接材料',kind:'SOURCE',facts:{assistantResponse:true,state:'SUCCEEDED',response:initial,source:{kind:'DRAFT',invocationId:initial.invocationId,contextId:initial.contextId,turnId:initial.turnId,turnVersion:initial.turnVersion}}}] as Record<string,unknown>[]};
 return state;
}
async function installRoutes(page:Page,state:ReturnType<typeof freshState>,initial:ReturnType<typeof freshState>['journal']['state']['draft']){
 await page.route('**/api/**',async route=>{
  const req=route.request(),url=new URL(req.url()),p=url.pathname,b=req.method()==='POST'?req.postDataJSON():null,result=(v:unknown)=>route.fulfill({json:{result:v}});
  if(!p.startsWith('/api/'))return route.continue();
  if(b)state.writes.push(p);
  if(p.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:alice',tenantId:'tenant',securityDomain:'domain'},csrfToken:'csrf',session:{}}});
  if(p.endsWith('/development-administrator'))return result({enabled:false});
  if(p.endsWith('/conversations/capabilities'))return result({enabled:true});
  if(p.endsWith('/draft-assistance/capabilities'))return result({conversationUnderstanding:true,conversationRelationRouting:true,initialUnderstandingAdoption:true,selectedSourceContext:state.sourceCapability});
  if(p.endsWith('/conversations/adoption/journey')){if(b){if(state.journalFailure)return route.fulfill({status:503,json:{reasonCode:'JOURNAL_UNAVAILABLE'}});expect(b.expectedVersion).toBe(state.journal.version);state.journal={version:state.journal.version+1,state:b.state}}return result(state.journal)}
  if(p.endsWith('/conversations/adoption/messages')){expect(b.expectedVersion).toBe(state.version);state.version++;const id='user-'+state.version;state.messages.push({message_id:id,content:b.content,author_id:'human:alice',disposition:'FOLLOWUP_RECORDED',request_key:b.idempotencyKey});return result({identity:id})}
  if(p.endsWith('/conversations/adoption/head'))return result({conversation:{conversation_id:'adoption',version:state.version,title:'交接检查'}});
  if(p.endsWith('/conversations/adoption'))return result({conversation:{conversation_id:'adoption',version:state.version,title:'交接检查'},messages:state.messages,links:[]});
  if(p.endsWith('/draft-assistance/invocations/initial'))return result({...initial,inputSource:source,sourceInputObservation:state.sourceObservation});
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
   if(!b&&state.adoptionReadStatus)return route.fulfill({status:state.adoptionReadStatus,json:{reasonCode:'ADOPTION_READ_UNAVAILABLE'}});
   if(b){state.adoptions.push(b);if(state.reject)return route.fulfill({status:state.rejectStatus,json:{reasonCode:state.rejectCode}});const old=state.journal;state.receipt={adoption:{target:{original_invocation_id:old.state.draft.invocationId,journal_version:old.version,journey_key:old.state.key,message_id:state.calls.at(-1)!.conversationMessageId},actualResult:{invocationId:state.last!.invocationId}},understanding:state.last,modelDispatched:false};if(state.guardAfterCommit)return route.fulfill({status:409,json:{reasonCode:'UNDERSTANDING_ADOPTION_QUESTION_CHANGED'}});if(state.lost)return route.abort();}
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
test('unsettled budget rejection preserves original question and input',async({page})=>{const s=await fixture(page);s.reject=true;const before=JSON.stringify(s.journal);await page.goto('/work?conversation=adoption');await send(page,'生产环境');await expect(page.getByText('原问题和回答均已保留，将先核对是否已有接续记录。无需重新提问，也无需修改回答来解决平台校验问题。',{exact:true}).first()).toBeVisible();expect(JSON.stringify(s.journal)).toBe(before);await expect(input(page)).toHaveValue('生产环境');expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(1)});
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

for(const mode of ['guard','access','read','server','journal'] as const)test(`adoption feedback distinguishes ${mode} without execution UNKNOWN`,async({page})=>{
 const s=await fixture(page);
 if(mode==='guard'){s.reject=true;s.rejectCode='UNDERSTANDING_ADOPTION_RESULT_NOT_ADOPTABLE'}
 if(mode==='access')s.adoptionReadStatus=403;
 if(mode==='read')s.adoptionReadStatus=503;
 if(mode==='server'){s.reject=true;s.rejectStatus=503;s.rejectCode='UPSTREAM_UNAVAILABLE'}
 if(mode==='journal')s.journalFailure=true;
 await page.goto('/work?conversation=adoption');await send(page,'生产环境');
 const titles={guard:'本次接续校验未通过',access:'当前无法核对回答的接续记录',read:'暂时无法读取回答的接续记录',server:'正在核对回答是否已接回',journal:'正在核对原会话接续记录'};
 await expect(page.getByRole('heading',{name:titles[mode],exact:true})).toBeVisible();
 await expect(page.getByText('不会自动重发可能已执行的请求。恢复后仍在本会话继续。',{exact:true})).toHaveCount(0);
 const alert=page.locator('.conversation-journey [role="alert"]');await expect(alert.locator('details')).not.toHaveAttribute('open','');await expect(alert.locator('details p')).not.toBeVisible();
 expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(['access','read'].includes(mode)?0:1);expect(s.journal.state.draft.invocationId).toBe('initial');
 if(mode==='journal')expect(s.receipt).not.toBeNull();
});

for(const code of ['CONVERSATION_INPUT_ACCESS_DENIED','OUTCOME_UNKNOWN'])test(`existing ${code} semantics stay distinct from adoption`,async({page})=>{
 const s=await fixture(page);Object.assign(s.journal.state,{error:code});await page.goto('/work?conversation=adoption');
 if(code==='OUTCOME_UNKNOWN')await expect(page.getByText('结果待核实',{exact:true})).toBeVisible();
 else await expect(page.getByText('当前访问校验未通过，原提问已保留。请在访问恢复后继续，无需重新描述问题。',{exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'本次接续校验未通过',exact:true})).toHaveCount(0);expect(s.calls).toHaveLength(0);expect(s.adoptions).toHaveLength(0);
});

test('NEEDS_DATA renders exact requested document content before generic hints',async({page})=>{
 const s=await fixture(page,true);s.journal.state.source=source;s.journal.state.draft.dataNeeds=['请提供上线交接说明正文。','请补充文中引用的清单与附件。'];await page.goto('/work?conversation=adoption');
 const needs=page.getByRole('list',{name:'本次回复提到的资料需求'});await expect(needs).toContainText('请提供上线交接说明正文。');await expect(needs).toContainText('请补充文中引用的清单与附件。');await expect(page.getByText('请补充你最关注的问题，例如关注的指标、时间或对象。',{exact:true})).toHaveCount(0);expect(s.calls).toHaveLength(0);expect(s.adoptions).toHaveLength(0);
});

test('guard response cannot erase a concurrent saved adoption or enable model replay',async({page})=>{
 const s=await fixture(page);s.guardAfterCommit=true;await page.goto('/work?conversation=adoption');await send(page,'生产环境');
 await expect(page.getByRole('heading',{name:'本次接续校验未通过',exact:true})).toBeVisible();const button=page.getByRole('button',{name:'继续提交这条回答',exact:true});await expect(button).toBeVisible();expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(1);expect(s.journal.state.draft.invocationId).toBe('initial');
 await button.click();await expect.poll(()=>s.journal.state.draft.invocationId).toBe('adopted-1');expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(1);
});

test('prewrite rejection can explicitly continue the same saved answer after repair',async({page})=>{
 const s=await fixture(page);s.reject=true;s.rejectCode='UNDERSTANDING_ADOPTION_RESULT_NOT_ADOPTABLE';await page.goto('/work?conversation=adoption');await send(page,'生产环境');
 const button=page.getByRole('button',{name:'核对并继续已有回答',exact:true});await expect(button).toBeVisible();expect(s.adoptions).toHaveLength(1);expect(s.calls).toHaveLength(1);const key=s.adoptions[0].requestKey;s.reject=false;
 await button.click();await expect.poll(()=>s.journal.state.draft.invocationId).toBe('adopted-1');expect(s.adoptions).toHaveLength(2);expect(s.adoptions[1].requestKey).toBe(key);expect(s.calls).toHaveLength(1);
});

test('explicit continuation rechecks stale route without exposing its technical code',async({page})=>{
 const s=await fixture(page);s.reject=true;await page.goto('/work?conversation=adoption');await send(page,'生产环境');const button=page.getByRole('button',{name:'核对并继续已有回答',exact:true});await expect(button).toBeVisible();s.stale=true;await button.click();await expect(page.getByText('暂未确认这条回复的处理结果。原问题已保留，请核查状态；不会自动重复提交。',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'发送',exact:true})).toBeDisabled();await page.reload();await expect(page.getByRole('button',{name:'发送',exact:true})).toBeDisabled();await expect(page.getByText('Error: CONVERSATION_ROUTING_CONTEXT_CHANGED',{exact:true})).toHaveCount(0);expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(1);
});

test('permission loss during uncertain adoption continuation preserves readback without new model',async({page})=>{
 const s=await fixture(page);s.reject=true;await page.goto('/work?conversation=adoption');await send(page,'生产环境');const button=page.getByRole('button',{name:'核对并继续已有回答',exact:true});await expect(button).toBeVisible();s.denyReads=true;await button.click();await expect(page.getByRole('button',{name:'发送',exact:true})).toBeDisabled();await page.reload();await expect(page.getByRole('button',{name:'发送',exact:true})).toBeDisabled();expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(1);
});

for(const mode of ['metadata-off','metadata-now-on','body','unverified','mismatch'] as const)test(`exact source input presentation ${mode}`,async({page})=>{
 const s=await fixture(page,true);s.journal.state.source=source;s.journal.state.draft.dataNeeds=['请补充交接验收负责人。'];s.sourceCapability=mode==='metadata-off'?'METADATA_ONLY':'BODY_SUPPORTED';
 s.sourceObservation={state:mode==='body'?'BODY_CONTEXT':mode==='unverified'?'UNVERIFIED':'METADATA_ONLY',invocationId:mode==='mismatch'?'other':'initial',aggregateVersion:5,source,basis:'RECORDED_ADAPTER_CONTRACT'};
 await page.goto('/work?conversation=adoption');
 if(mode.startsWith('metadata')){await expect(page.getByRole('heading',{name:'系统待接续资料处理',exact:true})).toBeVisible();await expect(page.locator('.journey-progress')).toContainText('系统待接续资料处理');await expect(page.getByText(mode==='metadata-off'?/当前正文接入尚未启用/:/当前已具备正文接入能力/).first()).toBeVisible();}
 else if(mode==='body'){await expect(page.getByRole('heading',{name:'还需要补充信息',exact:true})).toBeVisible();await expect(page.getByRole('list',{name:'需要补充的资料'})).toContainText('请补充交接验收负责人。');await expect(page.locator('.journey-progress')).toContainText('等待你的回答');}
 else await expect(page.getByRole('heading',{name:'资料处理状态待核对',exact:true})).toBeVisible();
 const details=page.getByText('本次能做什么与完成标准',{exact:true}).locator('..');await expect(details).not.toHaveAttribute('open','');await expect(page.locator('.conversation-journey .conversation-message-time')).toHaveCount(0);expect(s.calls).toHaveLength(0);expect(s.adoptions).toHaveLength(0);
});
test('late source observation cannot replace a newer question owner',async({page})=>{
 const s=await fixture(page,true);s.journal.state.source=source;let release!:()=>void;const pending=new Promise<void>(resolve=>{release=resolve});
 await page.route('**/draft-assistance/invocations/initial',async route=>{await pending;await route.fulfill({json:{result:{...s.journal.state.draft,invocationId:'initial',contextId:'initial-context',aggregateVersion:5,inputSource:source,sourceInputObservation:{state:'METADATA_ONLY',invocationId:'initial',aggregateVersion:5,source,basis:'RECORDED_ADAPTER_CONTRACT'}}}})});
 await page.goto('/work?conversation=adoption');await send(page,'验收负责人是项目经理');await expect.poll(()=>s.journal.state.draft.invocationId).toBe('adopted-1');release();await expect(page.getByRole('heading',{name:'有一点需要确认',exact:true})).toBeVisible();await expect(page.getByRole('heading',{name:'系统待接续资料处理',exact:true})).toHaveCount(0);expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(1);
});

for(const reason of ['UNDERSTANDING_ADOPTION_BUSINESS_SCOPE_DENIED','NETWORK_UNCONFIRMED'])test(`CREATE pause preserves fixed input and exact ${reason} meaning`,async({page})=>{
 const s=await fixture(page);Object.assign(s.journal.state,{phase:'CREATE',pending:'create-problem',error:'Error: '+reason,source});Object.assign(s.journal.state.draft,{resultKind:'DRAFT_READY',draft:{title:'检查交接说明',description:'核对原文并返回缺口'}});
 await page.goto('/work?conversation=adoption');await expect(input(page)).toBeEditable();await input(page).fill('请保留这项补充要求');await expect(page.getByRole('button',{name:'发送',exact:true})).toBeDisabled();await expect(page.getByRole('link',{name:'发起另一个问题',exact:true})).toHaveCount(0);await page.reload();await expect(input(page)).toHaveValue('请保留这项补充要求');
 if(reason==='UNDERSTANDING_ADOPTION_BUSINESS_SCOPE_DENIED'){
  await expect(page.getByRole('heading',{name:'草案已保存，后续处理暂未获准',exact:true})).toBeVisible();await expect(page.locator('.journey-progress')).toContainText('草案已保存，后续处理暂未获准');await expect(page.locator('.conversation-journey [role="alert"] details p')).not.toBeVisible();await expect(page.getByText('不会自动重发可能已执行的请求。恢复后仍在本会话继续。',{exact:true})).toHaveCount(0);
 }else await expect(page.getByRole('heading',{name:'草案已保存，后续处理暂未获准',exact:true})).toHaveCount(0);
 expect(s.calls).toHaveLength(0);expect(s.adoptions).toHaveLength(0);expect(s.writes).toHaveLength(0);
});

for(const outcome of ['NOT_CREATED','CREATED','UNKNOWN','DENIED','MISMATCH','LOST_CREATE','MALFORMED_CREATE'] as const)test(`same saved CREATE recovery ${outcome} uses owner readback`,async({page})=>{
 const s=await fixture(page);Object.assign(s.journal.state,{phase:'CREATE',pending:'create-problem',error:'Error: UNDERSTANDING_ADOPTION_BUSINESS_SCOPE_DENIED',source});Object.assign(s.journal.state.draft,{resultKind:'DRAFT_READY',draft:{title:'检查交接说明',description:'原草案'}});
 const revision={business_problem_id:'original-created',revision_id:'r1',digest:'a'.repeat(64),title:'检查交接说明',description:'原草案'};let reads=0,created=false;const creates:Record<string,unknown>[]=[];
 await page.route('**/conversations/adoption/create-status?**',async route=>{reads++;const url=new URL(route.request().url());expect(url.searchParams.get('requestKey')).toBe('work:problem');expect(url.searchParams.get('draftInvocationId')).toBe('initial');
  if(outcome==='DENIED')return route.fulfill({status:403,json:{reasonCode:'CREATE_STATUS_ACCESS_DENIED'}});
  return route.fulfill({json:{result:{state:created||outcome==='CREATED'?'CREATED':outcome==='UNKNOWN'?'UNKNOWN':'NOT_CREATED',draftInvocationId:outcome==='MISMATCH'?'other':'initial',requestKey:'work:problem',journeyKey:'work',journalVersion:s.journal.version,aggregateVersion:5,revision:created||outcome==='CREATED'?revision:undefined}}});
 });
 await page.route('**/problems',async route=>{if(route.request().method()==='GET')return route.fulfill({json:{result:{problems:[]}}});creates.push(route.request().postDataJSON());created=true;if(outcome==='LOST_CREATE')return route.abort();return route.fulfill({status:201,json:{result:{revision:outcome==='MALFORMED_CREATE'?null:revision}}})});
 await page.goto('/work?conversation=adoption');const button=page.getByRole('button',{name:'核对并继续当前工作',exact:true});await expect(button).toBeVisible();expect(reads).toBe(0);expect(creates).toHaveLength(0);await input(page).fill('保留补充');await button.click();
 if(['LOST_CREATE','MALFORMED_CREATE'].includes(outcome)){await expect(page.getByText('暂未确认本次接续状态。草案和输入均已保留；再次继续前会先读取原记录，不会重新理解问题。',{exact:true})).toBeVisible();await page.reload();await expect(input(page)).toHaveValue('保留补充');expect(creates).toHaveLength(1);await button.click();}
 if(['NOT_CREATED','CREATED','LOST_CREATE','MALFORMED_CREATE'].includes(outcome)){await expect.poll(()=>s.journal.state.phase).toBe('CRITERION');expect((s.journal.state as unknown as {problem:typeof revision}).problem).toEqual(revision);expect(creates).toHaveLength(outcome==='CREATED'?0:1);if(creates.length){expect(creates[0].idempotencyKey).toBe('work:problem');expect(creates[0].draftInvocationId).toBe('initial')}}
 else {await expect(button).toBeEnabled();expect(s.journal.state.phase).toBe('CREATE');expect(creates).toHaveLength(0);await expect(input(page)).toHaveValue('保留补充')}
 expect(s.calls).toHaveLength(0);expect(s.adoptions).toHaveLength(0);expect(s.journal.state.draft.invocationId).toBe('initial');
});

for(const exact of [true,false])test(`CREATE source-read statement requires exact observed source ${exact}`,async({page})=>{
 const s=await fixture(page);Object.assign(s.journal.state,{phase:'CREATE',pending:'create-problem',error:'Error: UNDERSTANDING_ADOPTION_BUSINESS_SCOPE_DENIED',source});Object.assign(s.journal.state.draft,{resultKind:'DRAFT_READY',draft:{title:'检查交接说明',description:'原草案'}});s.sourceObservation={state:'BODY_CONTEXT',invocationId:'initial',aggregateVersion:5,basis:'RECORDED_ADAPTER_CONTRACT',source:exact?source:{...source,sourceContentDigest:'c'.repeat(64)}};
 await page.goto('/work?conversation=adoption');await expect(page.getByRole('heading',{name:'草案已保存，后续处理暂未获准',exact:true})).toBeVisible();
 if(exact)await expect(page.getByText(/资料正文已读取，草案已保存/).first()).toBeVisible();else await expect(page.getByText(/资料正文已读取，草案已保存/)).toHaveCount(0);expect(s.calls).toHaveLength(0);expect(s.writes).toHaveLength(0);
});

for(const outcome of ['NOT_WRITTEN','WRITTEN','UNKNOWN','DENIED','MISMATCH','LOST','DOUBLE'] as const)test(`criterion recovery ${outcome} preserves exact work and saved input`,async({page})=>{
 const s=await fixture(page);const problem={business_problem_id:'problem',revision_id:'problem-r1',digest:'a'.repeat(64),description:'原草案'};Object.assign(s.journal.state,{phase:'CRITERION',pending:'criterion',error:'Error: OWNED_BUSINESS_RESULT_CHANGED',problem,source});Object.assign(s.journal.state.draft,{resultKind:'DRAFT_READY',draft:{title:'检查材料',description:'原草案'}});
 let written=false,reads=0;const writes:Record<string,unknown>[]=[];const revision={revision_id:'criterion-r1',success_criterion_id:'criterion',digest:'c'.repeat(64)};
 await page.route('**/conversations/adoption/criterion-status?**',async route=>{reads++;expect(new URL(route.request().url()).searchParams.get('requestKey')).toBe('work:criterion');if(outcome==='DENIED')return route.fulfill({status:403,json:{reasonCode:'ACCESS_DENIED'}});return route.fulfill({json:{result:{state:written||outcome==='WRITTEN'?'WRITTEN':outcome==='UNKNOWN'?'UNKNOWN':'NOT_WRITTEN',draftInvocationId:'initial',draftAggregateVersion:5,observedAggregateVersion:6,requestKey:'work:criterion',journeyKey:'work',journalVersion:outcome==='MISMATCH'?0:s.journal.version,problem:{resource_id:problem.business_problem_id,revision_id:problem.revision_id,digest:problem.digest},revision:written||outcome==='WRITTEN'?revision:undefined}}})});
 await page.route('**/draft-assistance/invocations/initial/problem-link',route=>route.fulfill({json:{result:{}}}));
 await page.route('**/success-criteria',async route=>{writes.push(route.request().postDataJSON());written=true;if(outcome==='LOST')return route.abort();return route.fulfill({json:{result:{revision}}})});
 await page.goto('/work?conversation=adoption');const button=page.getByRole('button',{name:'核对并继续当前工作',exact:true});await expect(button).toBeVisible();await expect(page.getByRole('heading',{name:'草案已保存，完成标准暂未接续',exact:true})).toBeVisible();await expect(input(page)).toBeEditable();await input(page).fill('保留未发送说明');expect(reads).toBe(0);expect(writes).toHaveLength(0);if(outcome==='DOUBLE')await button.evaluate(element=>{(element as HTMLButtonElement).click();(element as HTMLButtonElement).click()});else await button.click();
 if(outcome==='LOST'){await expect(page.getByText('暂未确认完成标准的接续状态。当前工作和输入已保留，再次继续时会先核对原记录，不会重新理解问题。',{exact:true})).toBeVisible();await page.reload();await expect(input(page)).toHaveValue('保留未发送说明');await button.click()}
 if(['NOT_WRITTEN','WRITTEN','LOST','DOUBLE'].includes(outcome)){await expect.poll(()=>s.journal.state.phase).toBe('ACTIVATE');expect(writes).toHaveLength(outcome==='WRITTEN'?0:1);if(writes.length)expect(writes[0].idempotencyKey).toBe('work:criterion')}
 else{await expect(button).toBeEnabled();expect(s.journal.state.phase).toBe('CRITERION');expect(writes).toHaveLength(0)}
 expect(s.calls).toHaveLength(0);expect(s.adoptions).toHaveLength(0);
});

for(const outcome of ['NOT_STARTED','RECORDED','DENIED','CHANGED','DOUBLE','SERVICE_DOWN','READ_UNAVAILABLE','UNVERIFIED','LOST_DISPATCH'] as const)test(`planning preparation continuation ${outcome} keeps original key`,async({page})=>{
 const s=await fixture(page);const problem={business_problem_id:'problem',revision_id:'problem-r1',digest:'a'.repeat(64),title:'检查材料',description:'原草案'};Object.assign(s.journal.state,{phase:'PLAN',pending:'planning',planningRequestKey:'work:planning',error:'Error: QUESTION_INPUT_SERVICE_UNAVAILABLE',problem,source});Object.assign(s.journal.state.draft,{resultKind:'DRAFT_READY',draft:{title:'检查材料',description:'原草案'}});
 let reads=0;const inputs:Record<string,unknown>[]=[],models:Record<string,unknown>[]=[];const phases:string[]=[];
 await page.route('**/conversations/adoption/planning-start-status?**',async route=>{reads++;expect(new URL(route.request().url()).searchParams.get('requestKey')).toBe('work:planning');if(outcome==='DENIED')return route.fulfill({status:403,json:{reasonCode:'ACCESS_DENIED'}});return route.fulfill({json:{result:{state:outcome==='RECORDED'?'RECORDED':'NOT_STARTED',draftInvocationId:'initial',draftAggregateVersion:5,observedAggregateVersion:6,requestKey:'work:planning',journeyKey:'work',journalVersion:outcome==='CHANGED'?0:s.journal.version,problem:{resource_id:problem.business_problem_id,revision_id:problem.revision_id,digest:problem.digest},source}}})});
 await page.route('**/question-activity-input',async route=>{inputs.push(route.request().postDataJSON());phases.push('input');if(outcome==='SERVICE_DOWN')return route.fulfill({status:503,json:{reasonCode:'QUESTION_INPUT_SERVICE_UNAVAILABLE'}});if(outcome==='READ_UNAVAILABLE'||outcome==='UNVERIFIED')return route.fulfill({json:{result:{state:'BLOCKED_CAPABILITY_'+outcome,planningRequest:null,modelCalls:0,executionStarted:false}}});return route.fulfill({json:{result:{state:'READY',planningRequest:{target:{},policy:{},answers:[],idempotency_key:'work:planning',output_language:'zh-CN'}}}})});
 await page.route('**/planning-v2/preflight',async route=>{phases.push('preflight');await route.fulfill({json:{result:{status:'EXPLICIT_CONSTRAINTS_VALID'}}})});
 await page.route('**/planning-v2/invocations',async route=>{models.push(route.request().postDataJSON());phases.push('model');if(outcome==='LOST_DISPATCH')return route.abort();await route.fulfill({json:{result:{invocation:{target:{invocation_id:'planning-1'}},result:{technical_status:'SUCCEEDED',kind:'NEEDS_CLARIFICATION',questions:['是否包含附件清单？']}}}})});
 await page.goto('/work?conversation=adoption');await expect(page.getByRole('heading',{name:'方案准备暂时暂停',exact:true}).first()).toBeVisible();await expect(input(page)).toBeEditable();await input(page).fill('保留后续说明');await expect.poll(()=>reads).toBeGreaterThan(0);expect(inputs).toHaveLength(0);expect(models).toHaveLength(0);
 if(['RECORDED','DENIED','CHANGED'].includes(outcome)){await expect(page.getByRole('button',{name:'核对并继续当前工作',exact:true})).toHaveCount(0);return}
 const button=page.getByRole('button',{name:'核对并继续当前工作',exact:true});await expect(button).toBeVisible();if(outcome==='DOUBLE')await button.evaluate(element=>{(element as HTMLButtonElement).click();(element as HTMLButtonElement).click()});else await button.click();
 if(outcome==='CHANGED'){await expect(button).toBeEnabled();expect(inputs).toHaveLength(0)}
 else if(['SERVICE_DOWN','READ_UNAVAILABLE','UNVERIFIED'].includes(outcome)){await expect.poll(()=>inputs.length).toBe(1);await expect(button).toBeVisible();await expect(page.getByText(/本次准备尚未调用规划模型/).first()).toBeVisible();if(outcome!=='SERVICE_DOWN')await expect(page.getByText(/不能据此判断缺少工具/).first()).toBeVisible();expect(models).toHaveLength(0);expect(phases).toEqual(['input']);await page.reload();await expect(input(page)).toHaveValue('保留后续说明');await expect(button).toBeVisible();expect(inputs).toHaveLength(1);expect(models).toHaveLength(0)}
 else if(outcome==='LOST_DISPATCH'){await expect.poll(()=>models.length).toBe(1);await page.reload();await expect(input(page)).toHaveValue('保留后续说明');expect(inputs).toHaveLength(1);expect(models).toHaveLength(1)}
 else{await expect.poll(()=>s.journal.state.phase).toBe('PLANNING_CLARIFY');expect(phases).toEqual(['input','preflight','model']);expect(inputs[0].idempotencyKey).toBe('work:planning');expect(models[0].idempotency_key).toBe('work:planning')}
 expect(s.calls).toHaveLength(0);expect(s.adoptions).toHaveLength(0);
});

for(const failure of [403,503])test(`planning preparation successful observation is withdrawn on ${failure}`,async({page})=>{
 const s=await fixture(page);const problem={business_problem_id:'problem',revision_id:'r1',digest:'a'.repeat(64)};Object.assign(s.journal.state,{phase:'PLAN',pending:'planning',planningRequestKey:'work:planning',error:'Error: QUESTION_INPUT_SERVICE_UNAVAILABLE',problem,source});Object.assign(s.journal.state.draft,{resultKind:'DRAFT_READY',draft:{title:'检查',description:'原草案'}});let denied=false;
 await page.route('**/conversations/adoption/planning-start-status?**',route=>denied?route.fulfill({status:failure,json:{reasonCode:'READ_UNAVAILABLE'}}):route.fulfill({json:{result:{state:'NOT_STARTED',draftInvocationId:'initial',draftAggregateVersion:5,observedAggregateVersion:6,requestKey:'work:planning',journeyKey:'work',journalVersion:s.journal.version,problem:{resource_id:problem.business_problem_id,revision_id:problem.revision_id,digest:problem.digest},source}}}));
 await page.goto('/work?conversation=adoption');await expect(page.getByRole('button',{name:'核对并继续当前工作',exact:true})).toBeVisible();denied=true;await page.getByRole('button',{name:'读取处理进展',exact:true}).click();await expect(page.getByRole('button',{name:'核对并继续当前工作',exact:true})).toHaveCount(0);await expect(page.getByText('已核对：本次规划请求尚未建立。服务恢复后可沿用当前工作继续。',{exact:true})).toHaveCount(0);await expect(page.getByText('暂未核实原工作记录，暂不重新提交。',{exact:true})).toBeVisible();expect(s.calls).toHaveLength(0);expect(s.writes).toHaveLength(0);
});

for(const lost of [false,true])test(`explicit source correction preserves old owner and original chat lost=${lost}`,async({page},info)=>{
 const s=await fixture(page);Object.assign(s.journal.state,{phase:'CREATE',pending:'create-problem',error:'Error: OWNED_BUSINESS_SOURCE_NOT_AUTHORIZED',source});Object.assign(s.journal.state.draft,{resultKind:'DRAFT_READY',draft:{title:'检查交接说明',description:'原草案'}});
 const allowed={...source,name:'生产上线交接与检查规范（合成测试）',label:'文档检查资料',source:{...source.source,resource_id:'production'},businessEligibility:{state:'SOURCE_SCOPE_MATCHED',executionReady:false}},readonly={...source,businessEligibility:{state:'READ_ONLY',executionReady:false}};
 let corrections=0,models=0;
 await page.route('**/conversations/adoption/sources',route=>route.fulfill({json:{result:{items:[readonly,allowed]}}}));
 await page.route('**/conversations/adoption/source-correction',async route=>{corrections++;const body=route.request().postDataJSON();expect(body.source.source).toEqual(allowed.source);expect(body.draftInvocationId).toBe('initial');expect(body.requestKey).toBe('work:problem');if(lost)return route.abort();const correction={id:'user:correction-message',text:'更正本次资料为生产上线交接与检查规范，保留原问题和要求。'};s.messages.push({message_id:'correction-message',content:correction.text,author_id:'human:alice',disposition:'FOLLOWUP_RECORDED'});const next={...s.journal.state,key:'source-correction:message',phase:'UNDERSTAND',pending:undefined,error:undefined,draft:undefined,userMessageId:'correction-message',source:allowed,messages:[...s.journal.state.messages,correction]};s.journal={version:s.journal.version+1,state:next as unknown as typeof s.journal.state};return route.fulfill({json:{result:s.journal}})});
 await page.route('**/draft-assistance/invocations',async route=>{models++;const body=route.request().postDataJSON();expect(body.idempotencyKey).toContain('source-correction:message:draft:');expect(body.conversationMessageId).toBe('correction-message');expect(body.parentContextId).toBeUndefined();expect(body.predecessorInvocationId).toBeUndefined();expect(JSON.parse(body.content).messages.at(-1).text).toContain('更正本次资料');return route.fulfill({json:{result:{state:'SUCCEEDED',resultKind:'NEEDS_CLARIFICATION',invocationId:'corrected-primary',contextId:'new-context',turnId:'new-turn',turnVersion:1,aggregateVersion:1,clarificationQuestion:'请确认本次检查范围',draft:null,inputSource:allowed,conversationDelivery:{state:'SAVED',messageId:'corrected-response'}}}})});
 await page.route('**/understanding-results/**',route=>route.fulfill({status:503,json:{reasonCode:'READBACK_UNAVAILABLE'}}));
 await page.goto('/work?conversation=adoption');await expect(page.getByRole('heading',{name:'请更正本次处理的资料',exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'核对并继续当前工作',exact:true})).toHaveCount(0);expect(corrections).toBe(0);expect(models).toBe(0);
 await page.getByRole('button',{name:'重新选择可处理资料',exact:true}).click();await expect(page.getByRole('button',{name:'选择交接材料',exact:true})).toBeDisabled();await page.getByRole('button',{name:'选择生产上线交接与检查规范（合成测试）',exact:true}).click();expect(corrections).toBe(0);await expect(page.getByText(/将本次资料从“交接材料”更正为/)).toBeVisible();await page.screenshot({path:info.outputPath('source-correction-confirm.png'),fullPage:true});
 await page.getByRole('button',{name:'确认变更资料并继续',exact:true}).click();await expect.poll(()=>corrections).toBe(1);if(lost){await expect(page.getByText('暂未确认资料是否已变更。请先读取原记录，不会重复提交变更或调用模型。',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'确认变更资料并继续',exact:true})).toBeDisabled();expect(s.journal.state.draft.invocationId).toBe('initial')}
 if(!lost)await expect.poll(()=>s.journal.state.draft?.invocationId).toBe('corrected-primary');await page.reload();expect(corrections).toBe(1);expect(models).toBe(lost?0:1);await expect(page).toHaveURL(/conversation=adoption/);
});

test('owned source selection uses published name and distinguishes readable scope',async({page})=>{
 const s=await fixture(page,true);const allowed={...source,name:'生产上线交接与检查规范（合成测试）',label:'文档检查资料',businessEligibility:{state:'SOURCE_SCOPE_MATCHED',executionReady:false}},readonly={...source,name:'旧交接说明',businessEligibility:{state:'READ_ONLY',executionReady:false}};
 await page.route('**/conversations/adoption/sources',route=>route.fulfill({json:{result:{items:[readonly,allowed]}}}));await page.goto('/work?conversation=adoption');await expect(page.getByRole('button',{name:'使用生产上线交接与检查规范（合成测试）',exact:true})).toBeEnabled();await expect(page.getByRole('button',{name:'使用旧交接说明',exact:true})).toBeDisabled();await expect(page.getByText('文档检查资料 · 已匹配当前资料处理范围，仍需核对本次要求与执行条件。',{exact:true})).toBeVisible();expect(s.calls).toHaveLength(0);expect(s.writes).toHaveLength(0);
});

for(const eligible of [true,false])test(`persisted failed understanding discovers original message and explicit continuation eligible=${eligible}`,async({page},info)=>{
 const s=await fixture(page);s.journal.state.source=source;
 s.messages.push({message_id:'failed-user',content:'生产环境',author_id:'human:alice',disposition:'FOLLOWUP_RECORDED'});
 const d=s.journal.state.draft,target={kind:'UNDERSTANDING',invocationId:d.invocationId,contextId:d.contextId,turnId:d.turnId,turnVersion:d.turnVersion,aggregateVersion:d.aggregateVersion,journalVersion:s.journal.version,journeyKey:s.journal.state.key};
 let reads=0;
 await page.route('**/conversations/adoption/understanding-failures',route=>{reads++;return route.fulfill({json:{result:{items:[{invocationId:'failed-call',messageId:'failed-user',originalText:'生产环境',state:'FAILED',reasonCode:'OUTPUT_SCHEMA_INVALID',target,inputSource:source,continuationEligible:eligible&&!s.last,successorRequestKey:'failed-understanding:fixed',successor:s.last}],complete:true,modelDispatched:false}}})});
 await page.goto('/work?conversation=adoption');await expect.poll(()=>reads).toBeGreaterThan(0);
 await expect(page.getByText('本次补充的回复格式校验未通过，生成文字未被采纳。原问题、输入与原任务均保留，不会自动重试。',{exact:true})).toBeVisible();
 const retry=page.getByRole('button',{name:'沿用原补充继续理解',exact:true});
 if(!eligible){await expect(retry).toHaveCount(0);expect(s.calls).toHaveLength(0);return}
 await expect(retry).toBeVisible();await page.reload();await expect(retry).toBeVisible();expect(s.calls).toHaveLength(0);
 await page.screenshot({path:info.outputPath('persisted-failure.png'),fullPage:true});
 await retry.click();await expect.poll(()=>s.calls.length).toBe(1);expect(s.calls[0].failedRetryOf).toBe('failed-call');expect(s.calls[0].idempotencyKey).toBe('failed-understanding:fixed');expect(s.calls[0].conversationMessageId).toBe('failed-user');expect(JSON.parse(s.calls[0].content as string).messages).toEqual([{id:'user:failed-user',text:'生产环境'}]);expect(s.writes.filter(p=>p.endsWith('/messages'))).toHaveLength(0);
 await expect.poll(()=>s.adoptions.length).toBe(1);await page.reload();expect(s.calls).toHaveLength(1);expect(s.adoptions).toHaveLength(1);
});

test('persisted successor is read after new login without dispatch or automatic adoption',async({page})=>{
 const s=await fixture(page);s.journal.state.source=source;
 const d=s.journal.state.draft,target={kind:'UNDERSTANDING',invocationId:d.invocationId,contextId:d.contextId,turnId:d.turnId,turnVersion:d.turnVersion,aggregateVersion:d.aggregateVersion,journalVersion:s.journal.version,journeyKey:s.journal.state.key};
 const successor={...d,invocationId:'already-succeeded',contextId:'new-context',turnId:'new-turn',resultKind:'NEEDS_CLARIFICATION',clarificationQuestion:'确认检查边界',conversationDelivery:{state:'SAVED',messageId:'saved-response'},conversationRoute:{relation:'CURRENT_QUESTION',currentQuestionToken:'token',contextDigest:'d'.repeat(64)}};
 await page.route('**/conversations/adoption/understanding-failures',route=>route.fulfill({json:{result:{items:[{invocationId:'failed-call',messageId:'failed-user',originalText:'生产环境',state:'FAILED',reasonCode:'OUTPUT_SCHEMA_INVALID',target,continuationEligible:false,successorRequestKey:'fixed-successor',successor}],complete:true}}}));
 await page.goto('/work?conversation=adoption');await expect(page.getByRole('button',{name:'继续提交这条回答',exact:true})).toBeVisible();expect(s.calls).toHaveLength(0);expect(s.adoptions).toHaveLength(0);expect(s.writes).toHaveLength(0);
});


test('redundancy: source metadata shares the current Loader observation and focus renews it',async({page})=>{
 const state=await fixture(page,true);state.journal.state.source=source;state.sourceCapability='METADATA_ONLY';state.sourceObservation={state:'METADATA_ONLY',invocationId:'initial',aggregateVersion:5,source,basis:'RECORDED_ADAPTER_CONTRACT'};
 let capabilities=0,sourceReads=0;page.on('request',request=>{const path=new URL(request.url()).pathname;if(path.endsWith('/draft-assistance/capabilities'))capabilities++;if(path.endsWith('/draft-assistance/invocations/initial'))sourceReads++});
 await page.goto('/work?conversation=adoption');await expect.poll(()=>sourceReads).toBe(1);await expect.poll(()=>capabilities).toBe(1);await page.waitForTimeout(200);expect(capabilities).toBe(1);expect(state.calls).toHaveLength(0);expect(state.writes).toEqual([]);
 await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect.poll(()=>sourceReads).toBe(2);expect(capabilities).toBe(2);expect(state.calls).toHaveLength(0);expect(state.writes).toEqual([]);
});
