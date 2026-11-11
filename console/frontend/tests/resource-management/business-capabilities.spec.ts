import type {CapabilityDetail} from '../../src/api/businessCapabilities';
import type {BusinessRelationCommand} from '../../src/api/businessProcesses';
import type {CapabilitySaveDraft} from '../../src/capabilities/CapabilityEditor';
import {createHash} from 'node:crypto';
import {test,expect,type Page} from '@playwright/test';
const digest='a'.repeat(64);
const members=[{kind:'EMPLOYEE',resourceId:'worker',revisionId:'worker-v1',digest,name:'交接核对助手'}];
const revision={schemaVersion:'business-capability.v1',scope:{namespace:'tenant',security_domain:'domain'},capability_id:'handover',revision_id:'r2',predecessor_revision_id:'r1',title:'交接材料核对',intent:'找出交接资料中的缺项和责任不清之处',inputs:'交接说明和责任清单',outputs:'缺项清单及对应原文',business_scope:'已授权交接文档',business_domain:'运营管理',exclusions:'自动部署或对外发送',manual_involvement:'负责人核实待补事项',acceptance_criteria:['逐项提供原文依据'],known_limitations:'无法证明实际部署状态',origin:{kind:'INDEPENDENT',workflow:null,preparation_digest:null},bindings:[{kind:'EMPLOYEE',reference:{resource_id:'worker',revision_id:'worker-v1',digest},purpose:'核对材料并列出待补事项'}]};
async function fixture(page:Page){
 const work={writes:[] as {path:string;body:Record<string,unknown>}[],messages:[] as Record<string,unknown>[],criterion:null as Record<string,unknown>|null,set:null as Record<string,unknown>|null,active:false,problem:null as Record<string,unknown>|null,unknownCreate:false,unknownReceipt:false,changedDuringPreparation:false};
 const state={preferences:{version:0,state:{query:'',layout:'cards',favoritesOnly:false,favorites:[] as string[],scrollTop:0},commandId:null as string|null,replayed:false},preferenceWrites:[] as Record<string,unknown>[],preferenceConflict:false,preferenceLost:false,runtime:false,work,journal:{version:0,contractDigest:'d'.repeat(64),sourceMessageId:'source-message',state:null as Record<string,unknown>|null},journalWrites:[] as Record<string,unknown>[],journalUnknown:false,answerUnknown:false,answerWrites:[] as Record<string,unknown>[],published:false,deny:false,unknown:false,contractMismatch:false,writes:[] as {commandId:string;reason:string}[],sources:[] as {idempotencyKey:string;expectedVersion:number;source:{kind:string;target:Record<string,string>}}[],saves:[] as {revision:typeof revision;expectedVersion:number;commandId:string}[]};
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  const json=(result:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result,continuationIds:[]}});
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:tester',tenantId:'tenant',securityDomain:'domain'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'csrf-test'}});
  if(path.endsWith('/business-capabilities/domains'))return json({domains:['运营管理'],hasUnassigned:true,readableFavoriteCount:state.preferences.state.favorites.filter(id=>id==='handover').length});
  if(path.endsWith('/business-capabilities/preferences')){
   if(route.request().method()==='POST'){
    const body=route.request().postDataJSON();state.preferenceWrites.push(body);
    if(state.preferenceConflict||body.expectedVersion!==state.preferences.version)return route.fulfill({status:409,json:{reasonCode:'CAPABILITY_PREFERENCES_VERSION_CONFLICT'}});
    state.preferences={version:state.preferences.version+1,state:body.state,commandId:body.commandId,replayed:false};
    if(state.preferenceLost)return route.abort('failed');
   }
   return json(state.preferences);
  }
  if(path.endsWith('/conversations/capabilities'))return json({enabled:true});
  if(path.endsWith('/conversations/original/sources')){const body=route.request().postDataJSON();if(!state.sources.some(s=>s.idempotencyKey===body.idempotencyKey))state.sources.push(body);return json({identity:'source-message',replayed:false})}
  if(path.endsWith('/sources/source-message/execution-contract')){const source=state.sources[0].source.target;const contract={schemaVersion:'capability-execution-constraints.v1',scope:{tenantId:'tenant',securityDomain:'domain'},conversationId:'original',sourceMessageId:'source-message',capability:{resource_id:'handover',revision_id:'r2',digest:state.contractMismatch?'f'.repeat(64):digest},objective:source.objective,inputNotes:source.inputNotes,inputs:revision.inputs,outputs:revision.outputs,acceptanceCriteria:revision.acceptance_criteria,businessScope:revision.business_scope,exclusions:revision.exclusions,manualInvolvement:revision.manual_involvement,knownLimitations:revision.known_limitations,bindings:revision.bindings};return json({contractDigest:'d'.repeat(64),admissionState:'NOT_ADMITTED',executionAuthorized:false,executionStarted:false,contract,workInput:{problem:{title:source.objective.slice(0,200),description:source.objective},criterion:{criterionType:'HUMAN_EVALUATED',measurement:{rubric:revision.acceptance_criteria.join('\n')},requiredEvidenceKinds:[],evaluatorType:'HUMAN',evaluatorVersion:'v1',applicability:{capabilityContractDigest:'d'.repeat(64),capabilityConstraints:contract}}}})}
  if(path.endsWith('/sources/source-message/journey')){
   if(route.request().method()==='POST'){
    const body=route.request().postDataJSON();state.journalWrites.push(body);expect(route.request().headers()['x-csrf-token']).toBe('csrf-test');
    if(body.expectedVersion!==state.journal.version)return route.fulfill({status:409,json:{reasonCode:'JOURNEY_VERSION_CONFLICT'}});
    state.journal={...state.journal,version:state.journal.version+1,state:body.state};
    if(state.journalUnknown)return route.abort('failed');
   }
   return json(state.journal);
  }
  if(path.endsWith('/conversations/original/messages')&&route.request().method()==='POST'){
   const body=route.request().postDataJSON();state.answerWrites.push(body);work.messages.push({message_id:'answer-message',kind:'USER',content:body.content,request_key:body.idempotencyKey,disposition:'FOLLOWUP_RECORDED'});
   if(state.answerUnknown)return route.abort('failed');
   return json({identity:'answer-message'});
  }
  if(path.endsWith('/conversations/original/journey'))return json({version:0,state:null});
  if(path.endsWith('/conversations/original'))return json({conversation:{conversation_id:'original',title:'原会话',version:state.sources.length,created_at:'2026-11-11'},links:[],messages:[...work.messages,...state.sources.map((entry,index)=>({message_id:'source-message',request_key:entry.idempotencyKey,sequence:index+1,content:'业务能力与本次输入已保存',kind:'SOURCE',disposition:'SOURCE',author_id:'human:tester',facts:{source:entry.source,observation:{state:'PREPARED_NOT_EXECUTED',title:revision.title,objective:entry.source.target.objective,inputNotes:entry.source.target.inputNotes,capability:{capabilityId:'handover',revisionId:'r2',digest,inputs:revision.inputs,outputs:revision.outputs,acceptanceCriteria:revision.acceptance_criteria,manualInvolvement:revision.manual_involvement,exclusions:revision.exclusions}}}}))]});
  if(route.request().method()==='POST'&&(path.endsWith('/intents')||path.endsWith('/problems')||path.endsWith('/success-criteria')||path.endsWith('/criteria-sets')||path.endsWith('/lifecycle'))){
   const body=route.request().postDataJSON();work.writes.push({path,body});expect(route.request().headers()['x-csrf-token']).toBe('csrf-test');
   if(path.endsWith('/intents')){work.messages.push({message_id:'intent-message',kind:'ACTION_INTENT',disposition:'ACTION_INTENT',facts:{intentId:'intent-one',messageId:'source-message',action:'CREATE_PROBLEM',ownerRequestKey:body.payload.idempotencyKey,source:body.source,attemptState:'NOT_SUBMITTED'}});return json({intentId:'intent-one',claimed:false})}
   if(path.endsWith('/problems')){expect(route.request().headers()['x-conversation-intent']).toBe('intent-one');work.problem={...body,business_problem_id:'new-problem',revision_id:'new-revision',digest:'e'.repeat(64)};work.messages[0]={...work.messages[0],facts:{...(work.messages[0].facts as Record<string,unknown>),attemptState:'UNKNOWN'}};work.messages.push({message_id:'receipt',kind:'OWNER_RECEIPT',disposition:'OWNER_RECEIPT',facts:{intentId:'intent-one',state:'SUCCEEDED',source:{kind:'PROBLEM',target:{problemId:'new-problem',revisionId:'new-revision',problemDigest:'e'.repeat(64)}}}});if(work.unknownCreate)return route.abort('failed');return json({revision:work.problem})}
   if(path.endsWith('/success-criteria')){work.criterion={revision_id:'criterion-one',criterion_type:body.criterionType,evaluator_type:body.evaluatorType,evaluator_version:body.evaluatorVersion,measurement:body.measurement,applicability:body.applicability};return json({revision:work.criterion})}
   if(path.endsWith('/criteria-sets')){work.set={problem_revision_id:'new-revision',ordered_criterion_revision_ids:body.orderedCriterionRevisionIds};if(work.changedDuringPreparation)work.problem={...work.problem,revision_id:'concurrently-revised'};return json({revision:work.set})}
   work.active=true;return json({businessProblemId:'new-problem',aggregateVersion:3});
  }
  if(path.endsWith('/intents/intent-one'))return work.unknownReceipt?json({state:'UNKNOWN'}):json({state:'SUCCEEDED',source:{kind:'PROBLEM',target:{problemId:'new-problem',revisionId:'new-revision',problemDigest:'e'.repeat(64)}}});
  if(path.endsWith('/problems/new-problem/criteria'))return json({revisions:work.criterion?[work.criterion]:[]});
  if(path.endsWith('/problems/new-problem/criteria-sets'))return json({revisions:work.set?[work.set]:[]});
  if(path.endsWith('/problems/new-problem'))return json({problem:{current_revision_id:work.problem?.revision_id??'new-revision',aggregate_version:work.set?2:1,current_state:work.active?'ACTIVE':'DRAFT'},revisions:[work.problem]});
  if(path.endsWith('/problems'))return json({problems:[]});
  if(path.endsWith('/employees'))return json({items:[{employeeDefinitionId:'worker',employeeDefinitionRevisionId:'worker-v1',employeeDefinitionDigest:digest,role:'交接核对助手',publicationState:'PUBLISHED'}]});
  if(path.includes('/employees/'))return route.fulfill({status:404,json:{reasonCode:'AUTHORITY_DENIED'}});
  if(path.endsWith('/resource-directory'))return json({subject:'human:tester',scope:{tenantId:'tenant',securityDomain:'domain'},items:[{identity:'workflow:handover',revisionId:'workflow-v1',digest,name:'交接流程',enabled:true,isCurrentPublished:true}],nextCursor:null});
  if(path.endsWith('/business-capabilities')&&route.request().method()==='POST'){state.saves.push(route.request().postDataJSON());return json({state:'DRAFT'})}
  const saved=state.saves.find(item=>path.endsWith('/revisions/'+encodeURIComponent(item.revision.revision_id)));
  if(saved)return json({revision:saved.revision,members,digest,aggregateVersion:saved.expectedVersion+1,headRevisionId:saved.revision.revision_id,publishedRevisionId:null,currentDraftRevisionId:saved.revision.revision_id,state:'DRAFT',executionAuthorized:false});
  if(path.endsWith('/publication-preview'))return json({capabilityId:'handover',revisionId:'r2',revisionDigest:digest,aggregateVersion:2,impactDigest:'b'.repeat(64),fieldChanges:[{field:'outputs',before:'说明',after:'缺项清单及对应原文'}],bindingChanges:[],previousPublishedRevisionId:'r1',automaticReferenceUpdates:false,executionAuthorized:false});
  if(path.endsWith('/publication')){
   expect(route.request().headers()['x-csrf-token']).toBe('csrf-test');state.writes.push(route.request().postDataJSON());
   if(state.unknown&&state.writes.length===1)return route.abort('failed');
   state.published=true;return json({state:'PUBLISHED',aggregateVersion:3});
  }
  if(path.endsWith('/revisions/r2')){
   if(state.deny)return route.fulfill({status:404,json:{reasonCode:'AUTHORITY_DENIED'}});
   return json({revision:state.runtime?{...revision,bindings:[...revision.bindings,{kind:'RUNTIME_PROFILE',reference:{resource_id:'runtime',revision_id:'runtime-v1',digest},purpose:'执行隔离'}]}:revision,members:state.runtime?[...members,{kind:'RUNTIME_PROFILE',resourceId:'runtime',revisionId:'runtime-v1',digest,name:'旧版隔离运行环境'}]:members,digest,aggregateVersion:state.published?3:2,headRevisionId:'r2',publishedRevisionId:state.published?'r2':'r1',currentDraftRevisionId:state.published?null:'r2',state:state.published?'PUBLISHED':'DRAFT',executionAuthorized:false});
  }
  if(path.endsWith('/business-capabilities'))return json({items:[{capabilityId:'handover',revisionId:'r2',title:revision.title,intent:revision.intent,inputs:revision.inputs,outputs:revision.outputs,employeeNames:['交接核对助手'],employeeNamesUnavailable:0,employeeResponsibilities:['核对资料'],exclusions:revision.exclusions,originKind:'INDEPENDENT',businessDomain:revision.business_domain,digest,state:state.published?'PUBLISHED':'DRAFT',aggregateVersion:2,currentPublished:state.published?{revisionId:'r2',title:revision.title,intent:revision.intent,digest}:null,currentDraft:{revisionId:'r2',title:revision.title,intent:revision.intent,digest}}],nextCursor:null});
  return json({items:[],conversations:[]});
 });return state;
}
test('capability catalogue and detail preserve fixed facts at desktop and mobile',async({page},info)=>{
 const state=await fixture(page);await page.goto('/capabilities?returnConversation=original');await page.getByRole('button',{name:'查看详情',exact:true}).click();
 await expect(page.getByRole('heading',{name:revision.title,exact:true})).toBeVisible();await expect(page.getByText(revision.outputs,{exact:true})).toBeVisible();
 await page.getByText('查看数字人与资源组成',{exact:true}).click();await page.getByText('查看固定引用',{exact:true}).click();await expect(page.locator('.capability-binding').getByText('worker-v1',{exact:true})).toBeVisible();
 await expect(page.getByRole('link',{name:'返回原会话'})).toHaveAttribute('href','/work?conversation=original');
 for(const width of [1280,390]){await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.screenshot({path:info.outputPath(`capability-${width}.png`),fullPage:true})}
 expect(state.writes).toEqual([]);
});
test('publication is explicit and an unknown outcome retains exactly the same command',async({page})=>{
 const state=await fixture(page);state.unknown=true;await page.goto('/capabilities?capability=handover&revision=r2');await page.getByRole('button',{name:'查看变更与发布影响'}).click();
 await expect(page.getByRole('button',{name:'确认并发布'})).toBeDisabled();expect(state.writes).toHaveLength(0);
 await page.getByLabel('发布说明').fill('核对范围与固定资源后发布');await page.getByRole('button',{name:'确认并发布'}).click();await expect(page.getByRole('alert')).toContainText('尚未核实');
 await page.getByRole('button',{name:'核实并重试本次发布'}).click();await expect(page.getByRole('status')).toContainText('已发布');expect(state.writes).toHaveLength(2);expect(state.writes[1]).toEqual(state.writes[0]);
});
test('denied read and expired session withdraw definition content',async({page})=>{
 const state=await fixture(page);state.deny=true;await page.goto('/capabilities?capability=handover&revision=r2');await expect(page.getByRole('alert')).toContainText('当前无法读取');await expect(page.getByText(revision.outputs,{exact:true})).toHaveCount(0);
 state.deny=false;await page.getByRole('button',{name:'重新读取'}).click();await expect(page.getByText(revision.outputs,{exact:true})).toBeVisible();await page.evaluate(()=>window.dispatchEvent(new Event('workbench-session-expired')));await expect(page.getByText(revision.outputs,{exact:true})).toHaveCount(0);expect(state.writes).toHaveLength(0);
});

for(const source of ['independent','workflow'])test('creates '+source+' capability with owner-selected fixed employee and reads it back',async({page})=>{
 const state=await fixture(page);await page.goto('/capabilities');await page.getByRole('button',{name:source==='workflow'?'从执行方案设计能力':'创建独立能力',exact:true}).click();
 const form=page.getByRole('form',{name:'业务能力编辑'});
 for(const label of ['能力名称','希望完成什么','需要提供哪些资料','将交付什么','适用范围','不包含哪些操作','需要人工参与什么','当前已知限制'])await form.getByLabel(label,{exact:true}).fill(label==='能力名称'?'新设计的文档核对':label+'的业务说明');
 await form.getByLabel('业务领域（可选）').fill('运营管理');
 await form.getByLabel('完成标准（每行一项）').fill('指出每一项缺失内容');
 if(source==='workflow'){await form.getByLabel('已发布资源',{exact:true}).selectOption({label:'交接流程'});await form.getByRole('button',{name:'固定来源执行方案'}).click();await form.getByLabel('资源类别').selectOption('EMPLOYEE')}
 await form.getByLabel('已发布资源',{exact:true}).selectOption({label:'交接核对助手'});await form.getByLabel('本次承担什么职责').fill('核对文档并引用依据');await form.getByRole('button',{name:'加入能力组成'}).click();
 await form.getByRole('button',{name:'保存草稿',exact:true}).click();await expect(page.getByRole('heading',{name:'新设计的文档核对',exact:true})).toBeVisible();
 expect(state.saves).toHaveLength(1);expect(state.saves[0].expectedVersion).toBe(0);expect(state.saves[0].revision.bindings[0].reference).toEqual({resource_id:'worker',revision_id:'worker-v1',digest});expect(state.saves[0].revision.origin.kind).toBe(source==='workflow'?'WORKFLOW_REVISION':'INDEPENDENT');
 await page.reload();await expect(page.getByRole('heading',{name:'新设计的文档核对',exact:true})).toBeVisible();expect(state.writes).toHaveLength(0);
});
test('editing appends a successor with the exact prior revision and expected version',async({page})=>{
 const state=await fixture(page);await page.goto('/capabilities?capability=handover&revision=r2');await page.getByRole('button',{name:'修改能力',exact:true}).click();await page.getByLabel('能力名称',{exact:true}).fill('交接核对修改稿');await page.getByRole('button',{name:'保存草稿',exact:true}).click();await expect(page.getByRole('heading',{name:'交接核对修改稿',exact:true})).toBeVisible();expect(state.saves).toHaveLength(1);expect(state.saves[0].revision.predecessor_revision_id).toBe('r2');expect(state.saves[0].expectedVersion).toBe(2);expect(state.saves[0].revision.bindings).toEqual(revision.bindings);expect(revision.title).toBe('交接材料核对');
});

test('fixed employee navigation returns to the same capability revision and conversation',async({page})=>{
 const state=await fixture(page);await page.goto('/capabilities?capability=handover&revision=r2&returnConversation=original');await page.getByText('查看数字人与资源组成',{exact:true}).click();
 const target=new URL((await page.locator('.capability-binding').getByRole('link',{name:'交接核对助手',exact:true}).getAttribute('href'))!,page.url());expect(target.searchParams.get('employeeDefinitionRevisionId')).toBe('worker-v1');expect(target.searchParams.get('employeeDefinitionDigest')).toBe(digest);
 await page.locator('.capability-binding').getByRole('link',{name:'交接核对助手',exact:true}).click();await page.getByRole('link',{name:'返回业务能力详情',exact:false}).click();await expect(page.getByRole('heading',{name:revision.title,exact:true})).toBeVisible();expect(new URL(page.url()).searchParams.get('revision')).toBe('r2');expect(new URL(page.url()).searchParams.get('digest')).toBe(digest);await expect(page.getByRole('link',{name:'返回原会话',exact:true})).toHaveAttribute('href','/work?conversation=original');expect(state.writes).toHaveLength(0);expect(state.saves).toHaveLength(0);
});
test('mismatched capability reference is not displayed',async({page})=>{
 await fixture(page);await page.goto('/capabilities?capability=handover&revision=r2&digest='+ 'c'.repeat(64));await expect(page.getByRole('alert')).toContainText('内容或登录身份已变化');await expect(page.getByText(revision.outputs,{exact:true})).toHaveCount(0);
});

test('capability input check saves the fixed preparation in the original conversation without executing',async({page})=>{
 const state=await fixture(page);state.published=true;await page.goto('/capabilities?capability=handover&revision=r2&returnConversation=original');await page.getByRole('button',{name:'在会话中使用',exact:true}).click();
 await expect(page.getByLabel('希望完成什么',{exact:true})).toHaveValue(revision.intent);await page.getByLabel('已提供的资料与范围').fill('使用已确认的交接文档，回退步骤仍需负责人核实');await page.getByRole('button',{name:'检查输入并继续',exact:true}).click();expect(state.sources).toHaveLength(0);
 await expect(page.getByText('确认保存到原会话',{exact:true})).toBeVisible();await page.getByRole('button',{name:'准备工作并进入会话',exact:true}).click();await expect(page).toHaveURL(/\/work\?conversation=original$/);await expect(page.getByText('业务能力准备已保存',{exact:true})).toBeVisible();
 expect(state.work.writes).toHaveLength(5);expect(state.work.active).toBe(true);expect(state.sources).toHaveLength(1);expect(state.sources[0].source.target.digest).toBe(digest);expect(state.sources[0].source.target.revisionId).toBe('r2');expect(state.writes).toHaveLength(0);expect(state.saves).toHaveLength(0);await expect(page.getByRole('link',{name:'查看本次固定能力与资源'})).toHaveAttribute('href','/capabilities?capability=handover&revision=r2&digest='+digest+'&returnConversation=original');
});


test('blank capability inputs stay editable and do not save a preparation',async({page})=>{
 const state=await fixture(page);state.published=true;await page.goto('/capabilities?capability=handover&revision=r2&returnConversation=original');await page.getByRole('button',{name:'在会话中使用',exact:true}).click();
 await page.getByLabel('已提供的资料与范围').fill('   ');await page.getByRole('button',{name:'检查输入并继续',exact:true}).click();await expect(page.getByRole('alert')).toContainText('不能只输入空格');await expect(page.getByLabel('已提供的资料与范围')).toBeEditable();await expect(page.getByRole('button',{name:'准备工作并进入会话',exact:true})).toHaveCount(0);expect(state.sources).toHaveLength(0);
 await page.getByLabel('已提供的资料与范围').fill('已保存的交接说明');await page.getByRole('button',{name:'检查输入并继续',exact:true}).click();await expect(page.getByRole('alert')).toHaveCount(0);await expect(page.getByRole('button',{name:'准备工作并进入会话',exact:true})).toBeVisible();expect(state.sources).toHaveLength(0);
});

for(const mode of ['exact','mismatch','denied'])test('authoring reuses only verified published Employee facts '+mode,async({page})=>{
 const state=await fixture(page);
 await page.route('**/employees/worker/revisions/worker-v1',route=>mode==='denied'?route.fulfill({status:403,json:{reasonCode:'EXACT_READ_REQUIRED'}}):route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{resourceKind:'DIGITAL_EMPLOYEE_DEFINITION',employeeDefinitionId:'worker',employeeDefinitionRevisionId:'worker-v1',employeeDefinitionDigest:mode==='mismatch'?'f'.repeat(64):digest,role:'交接核对助手',publicationState:'PUBLISHED',responsibilities:['逐项检查交接内容','引用文档依据'],members:[{kind:'SKILL',resourceId:'skill:review',revisionId:'skill-v1',digest:'b'.repeat(64)},{kind:'AGENT',resourceId:'agent:review',revisionId:'agent-v1',digest:'c'.repeat(64)}]},continuationIds:[]}}));
 await page.goto('/capabilities');await page.getByRole('button',{name:'创建独立能力',exact:true}).click();const form=page.getByRole('form',{name:'业务能力编辑'});await form.getByLabel('能力名称',{exact:true}).fill('我填写的能力名称');await form.getByLabel('已发布资源',{exact:true}).selectOption({label:'交接核对助手'});await form.getByRole('button',{name:'带入已保存职责与资源',exact:true}).click();
 if(mode==='exact'){
  await expect(form.getByRole('status')).toContainText('2 项固定引用');await expect(form.getByLabel('能力名称',{exact:true})).toHaveValue('我填写的能力名称');await expect(form.getByLabel('希望完成什么',{exact:true})).toHaveValue('逐项检查交接内容；引用文档依据');await expect(form.getByLabel('完成标准（每行一项）')).toHaveValue('');
  await form.getByRole('button',{name:'带入已保存职责与资源',exact:true}).click();await expect(form.getByRole('status')).toContainText('0 项固定引用');await expect(form.getByRole('button',{name:'移除',exact:true})).toHaveCount(2);
  for(const label of ['需要提供哪些资料','将交付什么','适用范围','不包含哪些操作','需要人工参与什么','当前已知限制'])await form.getByLabel(label,{exact:true}).fill(label+'由用户核对');await form.getByLabel('完成标准（每行一项）').fill('缺项必须引用原文');await form.getByRole('button',{name:'保存草稿',exact:true}).click();await expect(page.getByRole('heading',{name:'我填写的能力名称',exact:true})).toBeVisible();expect(state.saves).toHaveLength(1);expect(state.saves[0].revision.bindings.map(b=>b.reference.revision_id)).toEqual(['worker-v1','skill-v1']);
 }else{await expect(page.getByRole('alert')).toContainText('已有填写保持不变');await expect(form.getByLabel('能力名称',{exact:true})).toHaveValue('我填写的能力名称');await expect(form.getByLabel('希望完成什么',{exact:true})).toHaveValue('');await expect(form.getByRole('button',{name:'移除',exact:true})).toHaveCount(0);expect(state.saves).toHaveLength(0)}expect(state.writes).toHaveLength(0);
});


test('saved capability preparation does not claim completion when fixed contract differs',async({page})=>{
 const state=await fixture(page);state.published=true;state.contractMismatch=true;await page.goto('/capabilities?capability=handover&revision=r2&returnConversation=original');await page.getByRole('button',{name:'在会话中使用',exact:true}).click();await page.getByLabel('已提供的资料与范围',{exact:true}).fill('待核对交接资料');await page.getByRole('button',{name:'检查输入并继续',exact:true}).click();await page.getByRole('button',{name:'准备工作并进入会话',exact:true}).click();await expect(page.getByRole('alert')).toContainText('固定执行范围未能核对');await expect(page).toHaveURL(/\/capabilities\?/);expect(state.sources).toHaveLength(1);expect(state.writes).toHaveLength(0);expect(state.saves).toHaveLength(0);await expect(page.getByRole('button',{name:'核实本次准备记录',exact:true})).toBeVisible();
});


for(const unknown of [false,true])test('capability work reconciles lost creation response without duplicate dispatch '+unknown,async({page})=>{
 const state=await fixture(page);state.published=true;state.work.unknownCreate=true;state.work.unknownReceipt=unknown;
 await page.goto('/capabilities?capability=handover&revision=r2&returnConversation=original');await page.getByRole('button',{name:'在会话中使用',exact:true}).click();await page.getByLabel('已提供的资料与范围').fill('保留完整原始交接说明与核对范围');await page.getByRole('button',{name:'检查输入并继续',exact:true}).click();await page.getByRole('button',{name:'准备工作并进入会话',exact:true}).click();await expect(page.getByRole('alert')).toBeVisible();
 await page.getByRole('button',{name:'核实本次准备记录',exact:true}).click();
 if(unknown){await expect(page.getByRole('alert')).toContainText('不会重复创建');expect(state.work.active).toBe(false)}else{await expect(page).toHaveURL(/\/work\?conversation=original$/);expect(state.work.active).toBe(true);expect(state.work.criterion?.applicability).toMatchObject({capabilityConstraints:{inputNotes:'保留完整原始交接说明与核对范围'}})}
 expect(state.sources).toHaveLength(1);expect(state.work.writes.filter(w=>w.path.endsWith('/problems'))).toHaveLength(1);expect(state.work.writes.filter(w=>w.path.endsWith('/intents'))).toHaveLength(1);
});


for(const mode of ['ready','partial','unknown','changed'] as const)test('original conversation resumes exact preparation without replaying completed owners '+mode,async({page})=>{
 const state=await fixture(page);state.published=true;
 await page.goto('/capabilities?capability=handover&revision=r2&returnConversation=original');await page.getByRole('button',{name:'在会话中使用',exact:true}).click();await page.getByLabel('已提供的资料与范围').fill('保留这次交接文档的已确认范围');await page.getByRole('button',{name:'检查输入并继续',exact:true}).click();await page.getByRole('button',{name:'准备工作并进入会话',exact:true}).click();await expect(page).toHaveURL(/\/work\?conversation=original$/);
 const before=state.work.writes.length;
 if(mode==='partial'){state.work.criterion=null;state.work.set=null;state.work.active=false}
 if(mode==='unknown')state.work.unknownReceipt=true;
 if(mode==='changed')state.work.criterion={...state.work.criterion,measurement:{rubric:'替换完成标准'}};
 await page.reload();await page.getByRole('button',{name:'核验并继续准备',exact:true}).click();
 if(mode==='unknown'||mode==='changed'){await expect(page.locator('.capability-work-resume').getByRole('alert')).toContainText(mode==='unknown'?'不会重复创建':'不同的完成标准');expect(state.work.writes).toHaveLength(before)}
 else{await expect(page.locator('.capability-work-resume').getByRole('status')).toContainText('已核实目标和完成标准');expect(state.work.writes).toHaveLength(before+(mode==='partial'?3:0));expect(state.work.active).toBe(true)}
 expect(state.work.writes.filter(w=>w.path.endsWith('/problems'))).toHaveLength(1);expect(state.sources).toHaveLength(1);
});


test('capability preparation stops when target changes before activation',async({page})=>{
 const state=await fixture(page);state.published=true;state.work.changedDuringPreparation=true;
 await page.goto('/capabilities?capability=handover&revision=r2&returnConversation=original');await page.getByRole('button',{name:'在会话中使用',exact:true}).click();await page.getByLabel('已提供的资料与范围').fill('本次交接材料');await page.getByRole('button',{name:'检查输入并继续',exact:true}).click();await page.getByRole('button',{name:'准备工作并进入会话',exact:true}).click();await expect(page.getByRole('alert')).toContainText('准备期间发生变化');expect(state.work.active).toBe(false);expect(state.work.writes.filter(w=>w.path.endsWith('/lifecycle'))).toHaveLength(0);
});

for(const lost of [false,true])test('saved capability progress survives refresh and never rewinds on preparation recheck '+lost,async({page})=>{
 const state=await fixture(page);state.published=true;state.journalUnknown=lost;
 await page.goto('/capabilities?capability=handover&revision=r2&returnConversation=original');
 await page.getByRole('button',{name:'在会话中使用',exact:true}).click();
 await page.getByLabel('已提供的资料与范围').fill('已确认的交接材料');
 await page.getByRole('button',{name:'检查输入并继续',exact:true}).click();
 await page.getByRole('button',{name:'准备工作并进入会话',exact:true}).click();
 if(lost){await expect(page.getByRole('alert')).toBeVisible();state.journalUnknown=false;await page.getByRole('button',{name:'核实本次准备记录',exact:true}).click()}
 await expect(page).toHaveURL(/\/work\?conversation=original$/);
 const progress=page.getByRole('region',{name:'已保存的工作进度',exact:true});
 await expect(progress).toContainText('等待方案准备');expect(state.journalWrites).toHaveLength(1);
 const writes=state.work.writes.length;
 await page.reload();await expect(progress).toContainText('等待方案准备');
 state.journal={...state.journal,version:2,state:{phase:'WAITING_FOR_CLARIFICATION',problemId:'new-problem'}};
 await page.getByRole('button',{name:'核验并继续准备',exact:true}).click();
 await expect(page.locator('.capability-work-resume').getByRole('status')).toContainText('已核实目标');
 await expect(progress).toContainText('后续办理记录已保留');expect(state.journal.version).toBe(2);expect(state.journalWrites).toHaveLength(1);expect(state.work.writes).toHaveLength(writes);
});

for(const mode of ['stream','lost','unavailable','adaptive'] as const)test('original capability conversation plans with one durable dispatch '+mode,async({page})=>{
 const state=await fixture(page);state.published=true;let dispatches=0,reads=0;let release=()=>{};const gate=new Promise<void>(resolve=>{release=resolve});
 const requestKey='capability:'+'d'.repeat(64)+':planning';
 const proposal={proposal_id:'proposal-one',revision:1,semantics:{title:'交接材料核验方案',tasks:[{task_id:'read',title:'读取交接资料',responsibility:'引用原文并核对缺项'}]}};
 const value={invocation:{target:{invocation_id:'invocation-one',problem:{problem:{resource_id:'new-problem'}}},request:{idempotency_key:requestKey}},result:{technical_status:'SUCCEEDED',kind:'PROPOSAL',proposal},facts_status:'AVAILABLE'};
 await page.route('**/capability-planning-input',route=>route.fulfill({json:{result:{state:'CAPABILITY_READY_FOR_GOVERNED_PLANNING',planningRequest:{target:{problem:{resource_id:'new-problem'}},idempotency_key:requestKey,answers:[],output_language:'zh-CN',policy:{}},capabilitySource:{conversationId:'original',sourceMessageId:'source-message',contractDigest:'d'.repeat(64)}}}}));
 await page.route('**/planning-v2/preflight',route=>route.fulfill(mode==='unavailable'?{status:503,json:{reasonCode:'PLANNING_NOT_CONFIGURED'}}:{json:{result:{dispatch_count:0}}}));
 await page.route('**/planning-v2/invocations',async route=>{
  dispatches++;expect(state.journal.state?.phase).toBe('PLANNING_PENDING');
  if(mode==='lost')return route.abort('failed');
  if(mode==='stream')await gate;
  return route.fulfill({contentType:'text/event-stream',body:'event: progress\ndata: '+JSON.stringify({kind:'stream',preview:'正在核对交接材料'})+'\n\nevent: result\ndata: '+JSON.stringify({status:201,body:{result:value}})+'\n\n'});
 });
 await page.route('**/planning-v2/requests/*/read-only-chain',route=>{reads++;
  const last=mode==='adaptive'?{...value,invocation:{...value.invocation,target:{...value.invocation.target,invocation_id:'child-invocation'},request:{idempotency_key:'planning-repair:derived'}},adaptive:{attempts:[{invocation_id:'invocation-one'},{invocation_id:'child-invocation'}]}}:value;
  return route.fulfill({json:{result:{rootRequestKey:requestKey,rootInvocationId:'invocation-one',value:last}}})});
 await page.goto('/capabilities?capability=handover&revision=r2&returnConversation=original');await page.getByRole('button',{name:'在会话中使用',exact:true}).click();await page.getByLabel('已提供的资料与范围').fill('已确认交接材料');await page.getByRole('button',{name:'检查输入并继续',exact:true}).click();await page.getByRole('button',{name:'准备工作并进入会话',exact:true}).click();
 await expect(page.getByRole('button',{name:'继续准备方案',exact:true})).toBeVisible();expect(dispatches).toBe(0);
 await page.getByRole('button',{name:'继续准备方案',exact:true}).click();
 const panel=page.getByRole('region',{name:'本次方案进展',exact:true}),rail=page.getByRole('region',{name:'当前工作方案进展',exact:true});
 if(mode==='stream'){await expect(rail.getByRole('status')).toContainText('正在生成方案');await expect.poll(()=>dispatches).toBe(1);release()}
 if(mode==='unavailable'){await expect(panel.getByRole('alert')).toContainText('模型服务尚未接通');await expect(rail).toContainText('需要处理');expect(dispatches).toBe(0);expect(state.journal.state?.phase).toBe('PREPARE_PLAN');return}
 if(mode==='lost'){await expect(panel.getByRole('alert')).toContainText('不会自动重发');expect(state.journal.state?.phase).toBe('PLANNING_PENDING')}
 else {await expect(panel).toContainText('交接材料核验方案');await expect(rail).toContainText('方案已返回');await expect(rail).toContainText('尚未确认或启动执行');}
 await page.reload();await expect(page.getByRole('button',{name:'读取原方案调用',exact:true})).toBeVisible();expect(dispatches).toBe(1);
 await page.getByRole('button',{name:'读取原方案调用',exact:true}).click();await expect(panel).toContainText('交接材料核验方案');await expect(page.getByRole('button',{name:'读取原方案调用',exact:true})).toBeEnabled();expect(dispatches).toBe(1);expect(reads).toBe(mode==='lost'?1:2);expect(state.journal.state?.phase).toBe('PLAN_READY');
});

for(const lost of [false,true])test('clarification answer continues same capability work without duplicate answer '+lost,async({page})=>{
 const state=await fixture(page);state.published=true;state.answerUnknown=lost;const requests:Record<string,unknown>[]=[];
 await page.route('**/conversations/original/journey',route=>route.fulfill({json:{result:{version:1,state:{key:'original-question',phase:'CLARIFY',question:'原有待补充问题',messages:[],sources:[],log:[]}}}}));
 const root='capability:'+'d'.repeat(64)+':planning',followup='capability-followup:'+createHash('sha256').update(JSON.stringify(['d'.repeat(64),'clarification-one'])).digest('hex');
 await page.route('**/capability-planning-input',route=>{const request=route.request().postDataJSON();return route.fulfill({json:{result:{state:'CAPABILITY_READY_FOR_GOVERNED_PLANNING',planningRequest:{target:{problem:{resource_id:'new-problem'}},idempotency_key:request.idempotencyKey,answers:['保留固定范围'],policy:{},output_language:'zh-CN'},capabilitySource:{conversationId:'original',sourceMessageId:'source-message',contractDigest:'d'.repeat(64)}}}})});
 await page.route('**/planning-v2/preflight',route=>route.fulfill({json:{result:{dispatch_count:0}}}));
 const value=(key:string)=>({invocation:{target:{invocation_id:key===root?'clarification-one':'final-two',problem:{problem:{resource_id:'new-problem'}}},request:{idempotency_key:key}},result:key===root?{technical_status:'SUCCEEDED',kind:'NEEDS_CLARIFICATION',questions:['按生产环境还是演示环境核对？']}:{technical_status:'SUCCEEDED',kind:'PROPOSAL',proposal:{semantics:{title:'按生产环境核对的方案',tasks:[]}}}});
 await page.route('**/planning-v2/invocations',route=>{const body=route.request().postDataJSON();requests.push(body);return route.fulfill({json:{result:value(body.idempotency_key)}})});
 await page.route('**/planning-v2/requests/*/read-only-chain',route=>{const key=decodeURIComponent(new URL(route.request().url()).pathname.split('/').at(-2)!);return route.fulfill({json:{result:{rootRequestKey:key,rootInvocationId:key===root?'clarification-one':'final-two',value:value(key)}}})});
 await page.goto('/capabilities?capability=handover&revision=r2&returnConversation=original');await page.getByRole('button',{name:'在会话中使用',exact:true}).click();await page.getByLabel('已提供的资料与范围').fill('交接材料');await page.getByRole('button',{name:'检查输入并继续',exact:true}).click();await page.getByRole('button',{name:'准备工作并进入会话',exact:true}).click();await page.getByRole('button',{name:'继续准备方案',exact:true}).click();
 await expect(page.locator('.f3-composer-dock').getByLabel('方案补充说明')).toBeVisible();
 await expect(page.locator('.capability-preparation-card textarea')).toHaveCount(0);
 await page.getByLabel('方案补充说明').fill('按生产环境核对，只检查材料，不部署。');
 await page.reload();await page.getByRole('button',{name:'读取原方案调用',exact:true}).click();await expect(page.getByLabel('方案补充说明')).toHaveValue('按生产环境核对，只检查材料，不部署。');expect(requests).toHaveLength(1);
 await page.getByRole('button',{name:'补充原有工作',exact:true}).click();await expect(page.locator('#journey-reply')).toBeVisible();await expect(page.getByLabel('方案补充说明')).toHaveCount(0);
 await page.getByRole('button',{name:'补充这项工作',exact:true}).click();await expect(page.getByLabel('方案补充说明')).toHaveValue('按生产环境核对，只检查材料，不部署。');await expect(page.locator('.f3-composer-dock textarea:visible')).toHaveCount(1);
 await page.getByRole('button',{name:'保存补充并继续',exact:true}).click();
 if(lost){await expect(page.getByRole('region',{name:'本次方案进展'}).getByRole('alert')).toContainText('保存状态尚未核实');expect(requests).toHaveLength(1);state.answerUnknown=false;await page.getByRole('button',{name:'保存补充并继续',exact:true}).click()}
 await expect(page.getByText('按生产环境核对的方案',{exact:true})).toBeVisible();await expect(page.locator('.private-message').getByText('按生产环境核对，只检查材料，不部署。',{exact:true})).toBeVisible();expect(requests).toHaveLength(2);expect(requests[1].idempotency_key).toBe(followup);expect(requests[1].predecessor_invocation_id).toBe('clarification-one');expect(requests[1].answers).toEqual(['保留固定范围','按生产环境核对，只检查材料，不部署。']);expect(state.answerWrites).toHaveLength(1);
 await expect(page.getByRole('button',{name:'读取原方案调用',exact:true})).toBeEnabled();await page.reload();await expect(page.getByRole('button',{name:'读取原方案调用',exact:true})).toBeVisible();expect(requests).toHaveLength(2);
});

for(const mode of ['normal','lost','mismatch'] as const)test('capability plan confirmation stays in original conversation '+mode,async({page})=>{
 const state=await fixture(page);state.published=true;let posts=0,committed=false;
 const key='capability:'+'d'.repeat(64)+':planning',hash='e'.repeat(64);
 const target={problem:{resource_id:'new-problem',revision_id:'p1',digest:'a'.repeat(64)},criteria:{resource_id:'criteria',revision_id:'c1',digest:'b'.repeat(64)}};
 const proposal={proposal_id:'proposal-confirm',revision:1,semantics:{title:'交接核查方案',target,tasks:[]}};
 const confirmation={plan:{plan_id:proposal.proposal_id,version:1,source_proposal_revision:1,source_proposal_digest:hash,semantics:proposal.semantics},digest:'f'.repeat(64),approval:{approval_decision_id:'approval',decided_at:'2026-11-11'},execution_status:'NOT_STARTED'};
 await page.route('**/planning-v2/requests/*/read-only-chain',route=>route.fulfill({json:{result:{rootRequestKey:key,rootInvocationId:'invocation-confirm',value:{invocation:{target:{invocation_id:'invocation-confirm',problem:{problem:{resource_id:'new-problem'}}},request:{idempotency_key:key}},result:{technical_status:'SUCCEEDED',kind:'PROPOSAL',proposal,proposal_digest:hash},facts_status:'AVAILABLE'}}}}));
 await page.route('**/planning-v2/proposal-confirm?version=1',route=>route.fulfill({json:{result:{proposal,digest:mode==='mismatch'?'9'.repeat(64):hash,snapshot:null}}}));
 await page.route('**/planning-v2/proposal-confirm/history',route=>route.fulfill({json:{result:{plans:committed?[confirmation]:[],proposals:[proposal]}}}));
 await page.route('**/planning-v2/proposal-confirm/confirmation/automatic',route=>{posts++;const body=route.request().postDataJSON();expect(body.capabilityConversationId).toBe('original');expect(body.capabilityMessageId).toBe('source-message');expect(body.capabilityContractDigest).toBe('d'.repeat(64));expect(state.journal.state?.phase).toBe('PLAN_CONFIRMING');committed=true;return mode==='lost'?route.abort('failed'):route.fulfill({json:{result:{confirmation,executionStarted:false}}})});
 await page.goto('/capabilities?capability=handover&revision=r2&returnConversation=original');await page.getByRole('button',{name:'在会话中使用',exact:true}).click();await page.getByLabel('已提供的资料与范围').fill('已确认交接材料');await page.getByRole('button',{name:'检查输入并继续',exact:true}).click();await page.getByRole('button',{name:'准备工作并进入会话',exact:true}).click();await expect(page).toHaveURL(/\/work\?conversation=original$/);
 state.journal={...state.journal,version:2,state:{phase:'PLAN_READY',problemId:'new-problem',planningRequestKey:key,invocationId:'invocation-confirm'}};
 await page.reload();await page.getByRole('button',{name:'读取原方案调用',exact:true}).click();await expect(page.getByText('交接核查方案', {exact:true})).toBeVisible();
 const panel=page.getByRole('region',{name:'本次方案确认',exact:true});await panel.getByRole('button',{name:'确认本次方案',exact:true}).click();
 if(mode==='mismatch'){await expect(panel.getByRole('alert')).toContainText('版本或目标不一致');expect(posts).toBe(0);return}
 if(mode==='lost'){await expect(panel.getByRole('alert')).toBeVisible();expect(posts).toBe(1);await page.reload();await panel.getByRole('button',{name:'读取原确认记录',exact:true}).click()}
 await expect(panel).toContainText('方案确认已读回');expect(posts).toBe(1);expect(state.journal.state?.phase).toBe('PLAN_CONFIRMED');
 await page.reload();await panel.getByRole('button',{name:'读取原确认记录',exact:true}).click();await expect(panel).toContainText('方案确认已读回');expect(posts).toBe(1);
});

for(const mode of ['normal','selection-lost','preparation-lost','wrong-resource'] as const)test('fixed capability resources resume original receipts '+mode,async({page})=>{
 const state=await fixture(page);state.published=true;let selections=0,preparations=0,selected=false,prepared=false;
 const employee=revision.bindings[0].reference;
 const base={plan:{plan_id:'fixed-plan',version:1,source_proposal_revision:1,semantics:{target:{problem:{resource_id:'new-problem'}}}},digest:'1'.repeat(64)};
 const next={...base,plan:{...base.plan,version:2,source_proposal_revision:2},digest:'2'.repeat(64)};
 await page.route('**/planning-v2/fixed-plan/history',route=>route.fulfill({json:{result:{plans:[base,...(selected?[next]:[])],proposals:[]}}}));
 await page.route('**/planning-v2/fixed-plan/resource-selection*',route=>{
  const post=route.request().method()==='POST';
  if(post){selections++;expect(state.journal.state?.phase).toBe('RESOURCE_SELECTING');expect(route.request().postDataJSON().employee).toEqual(employee);expect(route.request().postDataJSON().capabilityMessageId).toBe('source-message');selected=true;if(mode==='selection-lost')return route.abort('failed')}
  if(!selected)return route.fulfill({status:404,json:{reasonCode:'RESOURCE_SELECTION_NOT_FOUND'}});
  return route.fulfill({json:{result:{confirmation:next,executionStarted:false,preflight:{employeeReference:mode==='wrong-resource'?{...employee,revision_id:'other'}:employee},capabilitySource:{conversationId:'original',sourceMessageId:'source-message',contractDigest:'d'.repeat(64)}}}});
 });
 await page.route('**/planning-v2/fixed-plan/resource-preparation*',route=>{
  if(route.request().method()==='POST'){preparations++;expect(state.journal.state?.phase).toBe('RESOURCES_PREPARING');prepared=true;if(mode==='preparation-lost')return route.abort('failed')}
  if(!prepared)return route.fulfill({status:404,json:{reasonCode:'RESOURCE_PREPARATION_NOT_FOUND'}});
  return route.fulfill({json:{result:{planId:'fixed-plan',planVersion:2,planDigest:next.digest,requestKey:'capability-resources:'+next.digest,state:'READY',executionStarted:false,assembly:{definition:employee},resources:[]}}});
 });
 await page.goto('/capabilities?capability=handover&revision=r2&returnConversation=original');await page.getByRole('button',{name:'在会话中使用',exact:true}).click();await page.getByLabel('已提供的资料与范围').fill('已确认交接材料');await page.getByRole('button',{name:'检查输入并继续',exact:true}).click();await page.getByRole('button',{name:'准备工作并进入会话',exact:true}).click();await expect(page).toHaveURL(/\/work\?conversation=original$/);
 state.journal={...state.journal,version:2,state:{phase:'PLAN_CONFIRMED',problemId:'new-problem',confirmedPlan:{id:'fixed-plan',version:1,digest:base.digest}}};
 await page.reload();const panel=page.getByRole('region',{name:'本次固定资源准备',exact:true});await panel.getByRole('button',{name:'继续准备资源',exact:true}).click();
 if(mode==='wrong-resource'){await expect(panel.getByRole('alert')).toContainText('固定能力不一致');expect(preparations).toBe(0);return}
 if(mode.endsWith('lost')){await expect(panel.getByRole('alert')).toBeVisible();await page.reload();await panel.getByRole('button',{name:'核实并继续准备资源',exact:true}).click()}
 await expect(panel).toContainText('本次固定资源已就绪');expect(selections).toBe(1);expect(preparations).toBe(1);expect(state.journal.state?.phase).toBe('RESOURCES_READY');
 await page.reload();await panel.getByRole('button',{name:'读取资源准备记录',exact:true}).click();await expect(panel).toContainText('本次固定资源已就绪');expect(selections).toBe(1);expect(preparations).toBe(1);
});

for(const mode of ['normal','lost','wrong-source','wrong-artifact'] as const)test('capability execution returns document findings to exact conversation '+mode,async({page})=>{
 const state=await fixture(page);state.published=true;let posts=0,reads=0,started=false;
 const executionDigest='6'.repeat(64),source={resource_id:'document-source',revision_id:'doc-v1',digest:'7'.repeat(64)},selectedPlan={id:'execution-plan',version:2,digest:'8'.repeat(64)};
 const report={schemaVersion:'document-review-output.v1',operation:'RENDER_REPORT',sourceSnapshot:mode==='wrong-artifact'?{...source,revision_id:'wrong'}:source,documentReview:{scope:'上线交接',findings:[{section:'回退步骤',status:'MISSING',requirement:{documentId:'standard',line:1,text:'需要回退步骤',body:[]},evidence:null}],missingSections:['回退步骤'],incompleteSections:[]}};
 await page.route('**/planning-v2/execution-plan/readonly-continuation*',route=>{
  if(route.request().method()==='POST'){posts++;expect(state.journal.state?.phase).toBe('EXECUTION_PENDING');expect(route.request().postDataJSON().capabilityMessageId).toBe('source-message');started=true;if(mode==='lost')return route.abort('failed')}
  else reads++;
  if(!started)return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
  const done=reads>1,task={task_id:'review',title:'核对交接文档',responsibility:'引用原文查找缺项',depends_on:[]};
  const view={digest:executionDigest,executionStarted:true,preparation:{plan_id:'execution-plan',plan_version:3,plan_digest:'9'.repeat(64),approval_id:'approved',source_snapshot:source,semantics:{title:'交接检查',target:{problem:{resource_id:'new-problem'}},tasks:[task]},participants:[{task_id:'review',instance_id:'instance',assignment_id:'assignment',definition:revision.bindings[0].reference,skill:{reference:source,operation:'RENDER_REPORT'},profile:source}]},progress:{state:done?'SUCCEEDED':'RUNNING',version:reads,cancellation_request_id:null,tasks:[{task_id:'review',state:done?'SUCCEEDED':'RUNNING',attempt_ordinal:1,reason:null}]},admission:{state:'ADMITTED',reason:null},resourceUses:[],artifacts:done?[{artifact_id:'report',task_id:'review',digest:'5'.repeat(64),bytes:JSON.stringify(report).length,created_at:'2026-11-11T01:00:00Z',contentAccess:'AUTHORIZED',content:JSON.stringify(report)}]:[],events:[],outcome:done?{outcomeId:'outcome',version:1,evaluationDigest:'4'.repeat(64),businessResolution:'UNDETERMINED',confirmationId:null,evaluation:{evaluationId:'evaluation',results:[{criterionRevisionId:'criterion',criterionDigest:'3'.repeat(64),result:'UNDETERMINED',reason:'需要负责人核实',artifactIds:['report']}]}}:null};
  return route.fulfill({json:{result:{receipt:{subject:'human:tester',sourcePlanId:selectedPlan.id,sourcePlanVersion:selectedPlan.version,sourcePlanDigest:selectedPlan.digest,preparationDigest:executionDigest,executionStarted:true,capabilitySource:{conversationId:mode==='wrong-source'?'other':'original',sourceMessageId:'source-message',contractDigest:'d'.repeat(64)}},execution:view}}});
 });
 await page.goto('/capabilities?capability=handover&revision=r2&returnConversation=original');await page.getByRole('button',{name:'在会话中使用',exact:true}).click();await page.getByLabel('已提供的资料与范围').fill('已确认交接材料');await page.getByRole('button',{name:'检查输入并继续',exact:true}).click();await page.getByRole('button',{name:'准备工作并进入会话',exact:true}).click();await expect(page).toHaveURL(/\/work\?conversation=original$/);
 state.journal={...state.journal,version:2,state:{phase:'RESOURCES_READY',problemId:'new-problem',selectedPlan}};
 await page.reload();const panel=page.getByRole('region',{name:'本次执行与结果',exact:true});await panel.getByRole('button',{name:'继续执行本次工作',exact:true}).click();
 if(mode==='wrong-source'){await expect(panel.getByRole('alert')).toContainText('来源不一致');await expect(panel.getByRole('heading',{name:'完成标准核对'})).toHaveCount(0);expect(posts).toBe(1);return}
 if(mode==='lost'){await expect.poll(()=>posts).toBe(1);await page.reload();await expect(panel.getByRole('button',{name:'读取原执行记录',exact:true})).toBeVisible()}
 await expect(panel).toContainText('业务结果尚未确认解决',{timeout:10000});
 if(mode==='wrong-artifact'){await expect(panel).toContainText('来源版本不一致');await expect(panel.getByRole('region',{name:'文档检查结果',exact:true})).toHaveCount(0)}else{await expect(panel.getByRole('region',{name:'文档检查结果',exact:true})).toContainText('缺少回退步骤')}
 expect(posts).toBe(1);await page.reload();await expect(panel).toContainText('业务结果尚未确认解决');expect(posts).toBe(1);await expect(page).toHaveURL(/\/work\?conversation=original$/);
});

for(const mode of ['complete','confirmation-lost','wrong-resource'] as const)test('one live capability journey advances through policy owners '+mode,async({page})=>{
 const state=await fixture(page);state.published=true;
 const calls={model:0,confirmation:0,selection:0,preparation:0,execution:0};
 let confirmed=false,selected=false,prepared=false,started=false;
 const key='capability:'+'d'.repeat(64)+':planning',pd='1'.repeat(64),cd='2'.repeat(64),sd='3'.repeat(64),ed='4'.repeat(64),employee=revision.bindings[0].reference;
 const target={problem:{resource_id:'new-problem',revision_id:'p1',digest:'5'.repeat(64)},criteria:{resource_id:'criteria',revision_id:'c1',digest:'6'.repeat(64)}};
 const task={task_id:'review',title:'核对交接文档',responsibility:'查找缺项并提供规范依据',depends_on:[]};
 const proposal={proposal_id:'continuous-plan',revision:1,semantics:{title:'交接完整性检查',target,tasks:[task]}};
 const base={plan:{plan_id:proposal.proposal_id,version:1,source_proposal_revision:1,source_proposal_digest:pd,semantics:proposal.semantics},digest:cd,approval:{approval_decision_id:'approval',decided_at:'2026-11-11'},execution_status:'NOT_STARTED'};
 const next={...base,plan:{...base.plan,version:2,source_proposal_revision:2,source_proposal_digest:sd},digest:sd};
 const value={invocation:{target:{invocation_id:'continuous-invocation',problem:{problem:{resource_id:'new-problem'}}},request:{idempotency_key:key}},result:{technical_status:'SUCCEEDED',kind:'PROPOSAL',proposal,proposal_digest:pd},facts_status:'AVAILABLE'};
 const source={resource_id:'document-source',revision_id:'v1',digest:'7'.repeat(64)},capabilitySource={conversationId:'original',sourceMessageId:'source-message',contractDigest:'d'.repeat(64)};
 await page.route('**/capability-planning-input',route=>route.fulfill({json:{result:{state:'CAPABILITY_READY_FOR_GOVERNED_PLANNING',planningRequest:{target,idempotency_key:key,answers:[],output_language:'zh-CN',policy:{}},capabilitySource}}}));
 await page.route('**/planning-v2/preflight',route=>route.fulfill({json:{result:{}}}));
 await page.route('**/planning-v2/invocations',route=>{calls.model++;return route.fulfill({contentType:'text/event-stream',body:'event: result\ndata: '+JSON.stringify({status:201,body:{result:value}})+'\n\n'})});
 await page.route('**/planning-v2/requests/*/read-only-chain',route=>route.fulfill({json:{result:{rootRequestKey:key,rootInvocationId:'continuous-invocation',value}}}));
 await page.route('**/planning-v2/continuous-plan?version=1',route=>route.fulfill({json:{result:{proposal,digest:pd,snapshot:null}}}));
 await page.route('**/planning-v2/continuous-plan/history',route=>route.fulfill({json:{result:{plans:[...(confirmed?[base]:[]),...(selected?[next]:[])],proposals:[proposal]}}}));
 await page.route('**/planning-v2/continuous-plan/confirmation/automatic',route=>{calls.confirmation++;confirmed=true;return mode==='confirmation-lost'?route.abort('failed'):route.fulfill({json:{result:{confirmation:base,executionStarted:false}}})});
 await page.route('**/planning-v2/continuous-plan/resource-selection*',route=>{
  if(route.request().method()==='POST'){calls.selection++;expect(confirmed).toBe(true);selected=true}
  return route.fulfill({json:{result:{confirmation:next,preflight:{employeeReference:mode==='wrong-resource'?{...employee,revision_id:'wrong'}:employee},capabilitySource,executionStarted:false}}});
 });
 await page.route('**/planning-v2/continuous-plan/resource-preparation*',route=>{
  if(route.request().method()==='POST'){calls.preparation++;expect(selected).toBe(true);prepared=true}
  return route.fulfill({json:{result:{planId:proposal.proposal_id,planVersion:2,planDigest:sd,requestKey:'capability-resources:'+sd,state:'READY',executionStarted:false,assembly:{definition:employee},resources:[]}}});
 });
 await page.route('**/planning-v2/continuous-plan/readonly-continuation*',route=>{
  if(route.request().method()==='POST'){calls.execution++;expect(prepared).toBe(true);started=true}
  expect(started).toBe(true);
  const report={schemaVersion:'document-review-output.v1',operation:'RENDER_REPORT',sourceSnapshot:source,documentReview:{scope:'上线交接',findings:[{section:'回退步骤',status:'MISSING',requirement:{documentId:'规范',line:1,text:'需提供回退步骤',body:[]},evidence:null}],missingSections:['回退步骤'],incompleteSections:[]}};
  const view={digest:ed,executionStarted:true,preparation:{plan_id:proposal.proposal_id,plan_version:3,plan_digest:'8'.repeat(64),approval_id:'approved',source_snapshot:source,semantics:proposal.semantics,participants:[{task_id:task.task_id,instance_id:'instance',assignment_id:'assignment',definition:employee,skill:{reference:source,operation:'RENDER_REPORT'},profile:source}]},progress:{state:'SUCCEEDED',version:3,cancellation_request_id:null,tasks:[{task_id:task.task_id,state:'SUCCEEDED',attempt_ordinal:1,reason:null}]},admission:{state:'ADMITTED',reason:null},resourceUses:[],events:[],outcome:null,artifacts:[{artifact_id:'report',task_id:task.task_id,digest:'9'.repeat(64),bytes:JSON.stringify(report).length,created_at:'2026-11-11T01:00:00Z',contentAccess:'AUTHORIZED',content:JSON.stringify(report)}]};
  return route.fulfill({json:{result:{receipt:{subject:'human:tester',sourcePlanId:proposal.proposal_id,sourcePlanVersion:2,sourcePlanDigest:sd,preparationDigest:ed,executionStarted:true,capabilitySource},execution:view}}});
 });
 await page.goto('/capabilities?capability=handover&revision=r2&returnConversation=original');await page.getByRole('button',{name:'在会话中使用',exact:true}).click();await page.getByLabel('已提供的资料与范围').fill('已确认交接材料');await page.getByRole('button',{name:'检查输入并继续',exact:true}).click();await page.getByRole('button',{name:'准备工作并进入会话',exact:true}).click();await expect(page).toHaveURL(/\/work\?conversation=original$/);
 await page.getByRole('button',{name:'继续准备方案',exact:true}).click();
 if(mode==='complete'){await expect(page.getByRole('region',{name:'文档检查结果',exact:true})).toContainText('缺少回退步骤');expect(calls).toEqual({model:1,confirmation:1,selection:1,preparation:1,execution:1})}
 else {const panel=page.getByRole('region',{name:mode==='confirmation-lost'?'本次方案确认':'本次固定资源准备',exact:true});await expect(panel.getByRole('alert')).toBeVisible();expect(calls.execution).toBe(0);expect(calls.preparation).toBe(0);expect(calls.selection).toBe(mode==='confirmation-lost'?0:1)}
 const before={...calls};await page.reload();await expect(page.getByRole('button',{name:'读取原方案调用',exact:true})).toBeVisible();expect(calls).toEqual(before);await expect(page).toHaveURL(/\/work\?conversation=original$/);
});

test('catalogue layouts preserve facts and exact detail return with honest filtered empty state',async({page},info)=>{
 const state=await fixture(page);await page.goto('/capabilities?returnConversation=original');
 await expect(page.getByRole('button',{name:'卡片',exact:true})).toHaveAttribute('aria-pressed','true');
 await expect(page.locator('.capability-grid')).toContainText(revision.outputs);
 await page.getByLabel('搜索业务能力').fill('  核对资料  ');
 await page.getByRole('button',{name:'列表',exact:true}).click();
 await expect(page.getByRole('table')).toContainText(revision.outputs);
 await expect(page.getByRole('table')).toContainText(revision.exclusions);
 await page.getByRole('button',{name:'查看详情',exact:true}).click();
 await expect(page).toHaveURL(/capability=handover&revision=r2/);
 await page.getByRole('button',{name:'返回业务能力',exact:true}).click();
 await expect(page.getByRole('button',{name:'列表',exact:true})).toHaveAttribute('aria-pressed','true');
 await expect(page.getByLabel('搜索业务能力')).toHaveValue('  核对资料  ');
 await expect(page.getByRole('link',{name:'返回原会话'})).toHaveAttribute('href','/work?conversation=original');
 for(const width of [1280,390]){await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.screenshot({path:info.outputPath(`catalogue-list-${width}.png`),fullPage:true})}
 await page.getByLabel('搜索业务能力').fill('不存在的能力');
 await expect(page.getByText('没有匹配的可读能力。请调整关键词、业务领域或收藏筛选。',{exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'暂无可读取的业务能力'})).toHaveCount(0);
 await page.getByRole('button',{name:'卡片',exact:true}).click();
 await expect(page.getByText('没有匹配的可读能力。请调整关键词、业务领域或收藏筛选。',{exact:true})).toBeVisible();
 expect(state.writes).toHaveLength(0);expect(state.saves).toHaveLength(0);
});

test('catalogue favorites and layout survive refresh and conflict never overwrites server state',async({page})=>{
 const state=await fixture(page);await page.goto('/capabilities');
 await page.getByRole('button',{name:'收藏'+revision.title,exact:true}).click();
 await expect.poll(()=>state.preferences.state.favorites).toEqual(['handover']);
 await page.getByRole('button',{name:'列表',exact:true}).click();
 await page.getByRole('button',{name:'我的收藏',exact:true}).click();
 await page.getByLabel('搜索业务能力').fill('交接');
 await expect.poll(()=>state.preferences.state.query).toBe('交接');
 await page.reload();
 await expect(page.getByLabel('搜索业务能力')).toHaveValue('交接');
 await expect(page.getByRole('button',{name:'列表',exact:true})).toHaveAttribute('aria-pressed','true');
 await expect(page.getByRole('button',{name:'我的收藏',exact:true})).toHaveAttribute('aria-pressed','true');
 await page.getByRole('button',{name:'取消收藏'+revision.title,exact:true}).click();
 await expect(page.getByRole('table').getByRole('button',{name:revision.title,exact:true})).toHaveCount(0);
 await expect.poll(()=>state.preferences.state.favorites).toEqual([]);
 state.preferenceConflict=true;
 await page.getByLabel('搜索业务能力').fill('不覆盖其他窗口');
 await expect(page.getByRole('alert')).toContainText('已在其他位置更新');
 const writes=state.preferenceWrites.length;
 expect(state.preferences.state.query).toBe('交接');
 await page.getByRole('button',{name:'重新读取目录设置'}).click();
 await expect(page.getByLabel('搜索业务能力')).toHaveValue('交接');
 expect(state.preferenceWrites).toHaveLength(writes);
});

test('catalogue lost save response is reconciled without another write',async({page})=>{
 const state=await fixture(page);state.preferenceLost=true;await page.goto('/capabilities');
 await page.getByRole('button',{name:'收藏'+revision.title,exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('保存结果尚未核实');
 expect(state.preferenceWrites).toHaveLength(1);
 await page.getByRole('button',{name:'重新读取目录设置'}).click();
 await expect(page.getByRole('button',{name:'取消收藏'+revision.title,exact:true})).toBeEnabled();
 expect(state.preferenceWrites).toHaveLength(1);
 await page.reload();
 await expect(page.getByRole('button',{name:'取消收藏'+revision.title,exact:true})).toBeEnabled();
 expect(state.preferenceWrites).toHaveLength(1);
});

test('catalogue requests combined owner filters and restores saved domain',async({page})=>{
 const state=await fixture(page);const requests:URL[]=[];
 page.on('request',request=>{const url=new URL(request.url());if(url.pathname.endsWith('/business-capabilities')&&request.method()==='GET')requests.push(url)});
 await page.goto('/capabilities');await page.getByLabel('业务领域',{exact:true}).selectOption('运营管理');
 await page.getByLabel('搜索业务能力').fill('交接');
 await expect.poll(()=>requests.some(url=>url.searchParams.get('query')==='交接'&&url.searchParams.get('domain')==='运营管理')).toBe(true);
 await page.getByRole('button',{name:'收藏'+revision.title,exact:true}).click();
 await page.getByRole('button',{name:'我的收藏',exact:true}).click();
 await expect.poll(()=>requests.some(url=>url.searchParams.get('favoritesOnly')==='true'&&url.searchParams.get('domain')==='运营管理')).toBe(true);
 await expect.poll(()=>state.preferences.state).toMatchObject({domain:'运营管理',query:'交接',favoritesOnly:true});
 await page.reload();await expect(page.getByLabel('业务领域',{exact:true})).toHaveValue('运营管理');
 await page.getByRole('button',{name:'查看详情',exact:true}).click();
 await expect(page.getByText('业务领域：运营管理',{exact:true})).toBeVisible();
});

test('home origin survives a nested fixed employee visit',async({page})=>{
 const state=await fixture(page);await page.goto('/capabilities?capability=handover&revision=r2&returnHome=1');
 await page.locator('.capability-fixed-table').getByRole('link',{name:'交接核对助手',exact:true}).click();
 await page.getByRole('link',{name:'返回业务能力详情',exact:false}).click();
 await expect(page.getByRole('link',{name:'返回工作台',exact:true})).toHaveAttribute('href','/dashboard');
 expect(new URL(page.url()).searchParams.get('revision')).toBe('r2');
 expect(new URL(page.url()).searchParams.get('digest')).toBe(digest);
 expect(state.writes).toHaveLength(0);expect(state.saves).toHaveLength(0);
});

test('catalogue restores second-page extent and scroll after refresh and detail return',async({page})=>{
 const state=await fixture(page);
 const template={revisionId:'r2',title:revision.title,intent:revision.intent,inputs:revision.inputs,outputs:revision.outputs,exclusions:revision.exclusions,employeeResponsibilities:['核对资料'],businessDomain:'运营管理',digest,state:'DRAFT',currentPublished:null,currentDraft:{revisionId:'r2'}};
 const entries=Array.from({length:60},(_,i)=>({...template,capabilityId:i===59?'handover':'other-'+i,title:i===59?revision.title:'核对能力 '+i}));
 await page.route('**/business-capabilities?*',route=>{const cursor=new URL(route.request().url()).searchParams.get('cursor');return route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:cursor?entries.slice(50):entries.slice(0,50),nextCursor:cursor?null:'second-page'},continuationIds:[]}})});
 await page.goto('/capabilities');await page.getByRole('button',{name:'加载更多',exact:true}).click();await expect(page.getByRole('button',{name:'查看详情',exact:true})).toHaveCount(60);
 const container=page.locator('.skill-frame-content');await container.evaluate(node=>{node.scrollTop=node.scrollHeight});
 await expect.poll(()=>state.preferences.state.scrollTop).toBeGreaterThan(1000);
 await expect.poll(()=>state.preferences.state).toMatchObject({loadedCount:60});
 await expect(page.getByText('正在保存目录设置…',{exact:true})).toHaveCount(0);
 const savedWrites=state.preferenceWrites.length;await page.waitForTimeout(800);expect(state.preferenceWrites).toHaveLength(savedWrites);
 const top=state.preferences.state.scrollTop;
 await page.reload();await expect(page.getByRole('button',{name:'查看详情',exact:true})).toHaveCount(60);await expect.poll(()=>container.evaluate((node,expected)=>Math.abs(node.scrollTop-expected),top)).toBeLessThan(5);
 await page.getByRole('button',{name:'查看详情',exact:true}).last().click();await expect(page.getByRole('heading',{name:revision.title,exact:true})).toBeVisible();
 await page.getByRole('button',{name:'返回业务能力',exact:true}).click();await expect(page.getByRole('button',{name:'查看详情',exact:true})).toHaveCount(60);await expect.poll(()=>container.evaluate(node=>node.scrollTop)).toBeGreaterThan(1000);
 await page.getByLabel('搜索业务能力').fill('改用新的筛选');await expect.poll(()=>state.preferences.state).toMatchObject({query:'改用新的筛选',loadedCount:50,scrollTop:0});
 expect(state.writes).toHaveLength(0);expect(state.saves).toHaveLength(0);
});

for(const mode of ['exact','prefixed','denied','mismatch','digest-mismatch'] as const)test('fixed Runtime drilldown retains original reference '+mode,async({page},info)=>{
 const state=await fixture(page);state.runtime=true;const reads:string[]=[],writes:string[]=[];
 page.on('request',r=>{reads.push(new URL(r.url()).pathname);if(r.method()!=='GET')writes.push(r.url())});
 await page.route('**/resource-directory/runtime/runtime/runtime-v1',route=>route.fulfill(mode==='denied'?{status:404,json:{reasonCode:'NOT_FOUND'}}:{json:{schemaVersion:'workbench-operation.v1',result:{kind:'runtime',identity:'runtime',name:'旧版隔离运行环境',subject:'human:tester',scope:{tenantId:'tenant',securityDomain:'domain'},revision:{revisionId:mode==='mismatch'?'runtime-v2':'runtime-v1',digest:mode==='prefixed'?'sha256:'+digest:mode==='digest-mismatch'?'b'.repeat(64):digest,state:'PUBLISHED',content:{provider:'NATIVE_KUBERNETES',resources:{cpuRequest:'250m',cpuLimit:'500m',memoryRequest:'256Mi',memoryLimit:'1Gi'},isolation:'NAMESPACE',stateMode:'STATELESS',sessionAffinity:'NONE',secretReferences:[],openClawPackageRef:null}}},continuationIds:[]}}));
 await page.goto('/capabilities?capability=handover&revision=r2&returnHome=1&returnConversation=original');
 await page.locator('.capability-fixed-table').getByRole('link',{name:'旧版隔离运行环境',exact:true}).click();
 await expect(page).toHaveURL(/runtime-profiles/);
 if(mode==='exact'||mode==='prefixed'){
  await expect(page.getByRole('heading',{name:'旧版隔离运行环境',exact:true})).toBeVisible();await expect(page.getByText('250m / 500m',{exact:true})).toBeVisible();
  await page.getByText('查看版本与配置依据',{exact:true}).click();await expect(page.getByText('runtime-v1',{exact:true})).toBeVisible();
  for(const width of [1280,390]){await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.locator('.skill-frame-content').evaluate(node=>node.scrollTop=0);await page.screenshot({path:info.outputPath(`fixed-runtime-${width}.png`),fullPage:true})}
 }else{await expect(page.getByRole('alert')).toContainText(mode==='denied'?'暂时无法读取':'版本未能核对');await expect(page.getByRole('heading',{name:'旧版隔离运行环境',exact:true})).toHaveCount(0)}
 await page.getByRole('link',{name:'返回业务能力详情',exact:false}).click();await expect(page.getByRole('heading',{name:revision.title,exact:true})).toBeVisible();
 await expect(page.getByRole('link',{name:'返回工作台',exact:true})).toHaveAttribute('href','/dashboard');await expect(page.getByRole('link',{name:'返回原会话',exact:true})).toHaveAttribute('href','/work?conversation=original');
 expect(new URL(page.url()).searchParams.get('revision')).toBe('r2');expect(new URL(page.url()).searchParams.get('digest')).toBe(digest);
 expect(reads.some(path=>path.includes('/api/internal/'))).toBe(false);expect(writes).toEqual([]);
});
test('partial Runtime reference never falls back to management or latest revision',async({page})=>{
 await fixture(page);const reads:string[]=[];page.on('request',r=>reads.push(r.url()));await page.goto('/runtime-profiles?resourceId=runtime&resourceRevision=runtime-v1');
 await expect(page.getByRole('alert')).toContainText('版本未能核对');expect(reads.some(path=>path.includes('/api/internal/'))).toBe(false);
 await expect(page.getByRole('button',{name:'Create Native Kubernetes Profile'})).toHaveCount(0);
});

 test('catalogue session failure ends loading and explicit retry recovers',async({page})=>{
 const state=await fixture(page);let unavailable=true;
 await page.route('**/api/workbench/v1/session',route=>unavailable?route.fulfill({status:503,json:{reasonCode:'UNAVAILABLE'}}):route.fallback());
 await page.goto('/capabilities');
 await expect(page.getByRole('alert').filter({hasText:'暂时无法获取能力信息'})).toBeVisible();
 await expect(page.getByText('正在读取业务能力…',{exact:true})).toHaveCount(0);
 unavailable=false;await page.getByRole('button',{name:'重新读取',exact:true}).click();
 await expect(page.getByRole('button',{name:revision.title,exact:true})).toBeVisible();
 expect(state.writes).toEqual([]);expect(state.preferenceWrites).toEqual([]);
 });

for(const layout of ['cards','list'] as const)test('catalogue direct use and truthful metadata '+layout,async({page},info)=>{
 const state=await fixture(page);state.published=true;
 await page.goto('/capabilities?returnConversation=original');
 if(layout==='list')await page.getByRole('button',{name:'列表',exact:true}).click();
 const catalogue=page.locator(layout==='cards'?'.capability-grid':'.capability-catalogue-table');
 await expect(catalogue.getByText('交接核对助手',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'我的收藏',exact:true})).toHaveText('我的收藏（0）');
 await catalogue.getByRole('button',{name:'收藏'+revision.title,exact:true}).click();
 await expect(page.getByRole('button',{name:'我的收藏',exact:true})).toHaveText('我的收藏（1）');
 await catalogue.getByText('查看版本',{exact:true}).click();await expect(catalogue.getByText('r2',{exact:true})).toBeVisible();
 for(const width of [1406,390]){await page.setViewportSize({width,height:1000});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.screenshot({path:info.outputPath(`catalogue-${layout}-${width}.png`),fullPage:true})}
 const writes=state.preferenceWrites.length;
 await catalogue.getByRole('button',{name:'在会话中使用',exact:true}).click();
 await expect(page.getByRole('region',{name:'能力本次输入'})).toBeVisible();
 await expect(page.getByLabel('希望完成什么')).toHaveValue(revision.intent);
 expect(state.sources).toEqual([]);expect(state.work.writes).toEqual([]);expect(state.writes).toEqual([]);
 expect(state.preferenceWrites.length).toBe(writes);
 await page.reload();await expect(page.getByRole('region',{name:'能力本次输入'})).toHaveCount(0);
});

for(const mode of ['reuse','unreadable','other','edited'])test('original input context '+mode,async({page})=>{
 const state=await fixture(page);state.published=true;
 let release:()=>void=()=>{};const delayed=new Promise<void>(resolve=>{release=resolve});
 await page.route('**/conversations/original',async route=>{
  if(mode==='edited')await delayed;
  return route.fulfill({json:{result:{conversation:{conversation_id:'original',title:'原会话',version:1},links:[],messages:[{message_id:'saved-input',sequence:1,kind:'SOURCE',facts:{readable:mode!=='unreadable',source:{kind:'CAPABILITY',target:{capabilityId:mode==='other'?'different':'handover',revisionId:'r1',digest,objective:'此前确认的交接核对目标',inputNotes:'已保存的说明文件及责任清单'}}}}]}}});
 });
 await page.goto('/capabilities?capability=handover&revision=r2&returnConversation=original');await page.getByRole('button',{name:'在会话中使用',exact:true}).click();
 if(mode==='edited'){await page.getByLabel('已提供的资料与范围').fill('用户本次新增范围');release()}
 if(mode==='reuse'||mode==='edited'){
  await expect(page.getByText('已参考原会话中本能力最近保存的目标与资料；保留你已编辑的内容，请按本次需要调整。历史版本的执行结果不会自动重跑。')).toBeVisible();
  await expect(page.getByLabel('希望完成什么',{exact:true})).toHaveValue('此前确认的交接核对目标');
  await expect(page.getByLabel('已提供的资料与范围')).toHaveValue(mode==='edited'?'用户本次新增范围':'已保存的说明文件及责任清单');
 }else{
  await expect(page.getByText('原会话尚无本能力可复用的资料说明，请补充本次范围。')).toBeVisible();await expect(page.getByLabel('已提供的资料与范围')).toHaveValue('');
 }
 expect(state.sources).toHaveLength(0);expect(state.work.writes).toHaveLength(0);
});

test('duplicate employee names display actual duties and fixed version preview',async({page})=>{
 await fixture(page);
 await page.route('**/employees?*',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:['one','two'].map(id=>({employeeDefinitionId:id,employeeDefinitionRevisionId:'revision-'+id,employeeDefinitionDigest:digest,role:'同名助手',publicationState:'PUBLISHED'}))}}}));
 await page.route('**/employees/*/revisions/*',route=>{const id=new URL(route.request().url()).pathname.includes('/one/')?'one':'two';return route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{employeeDefinitionId:id,employeeDefinitionRevisionId:'revision-'+id,employeeDefinitionDigest:digest,role:'同名助手',publicationState:'PUBLISHED',responsibilities:[id==='one'?'检查回退步骤':'核对责任清单']}}})});
 await page.goto('/capabilities');await page.getByRole('button',{name:'创建独立能力',exact:true}).click();
 const picker=page.getByLabel('已发布资源',{exact:true});await expect(picker.locator('option').filter({hasText:'检查回退步骤'})).toHaveCount(1);await expect(picker.locator('option').filter({hasText:'核对责任清单'})).toHaveCount(1);
 await picker.selectOption({label:'同名助手 · 核对责任清单 · 已发布 · sion-two'});const preview=page.getByRole('region',{name:'所选固定资源'});await expect(preview).toContainText('核对责任清单');await preview.getByText('查看资源与版本依据').click();await expect(preview).toContainText('revision-two');await expect(preview).toContainText('资源：two');
});

for(const mode of ['new','same','denied','mismatch','owner-mismatch','withdrawn','historical','lost-save','changed-head','changed-resource'])test('resource upgrade compares exact published versions '+mode,async({page})=>{
 const state=await fixture(page);state.published=true;const newer='b'.repeat(64);let ownerReads=0,headReads=0;
 const employee=(id:string)=>({employeeDefinitionId:'worker',employeeDefinitionRevisionId:id,employeeDefinitionDigest:id==='worker-v2'?newer:digest,role:'交接核对助手',publicationState:'PUBLISHED',responsibilities:[id==='worker-v2'?'补充核对回退责任':'核对交接材料'],members:[]});
 await page.route('**/employees?*',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:[employee(mode==='same'?'worker-v1':'worker-v2')]}}}));
 await page.route('**/employees/worker/revisions/*',route=>{
  if(mode==='denied')return route.fulfill({status:404,json:{reasonCode:'AUTHORITY_DENIED'}});
  const id=new URL(route.request().url()).pathname.endsWith('worker-v2')?'worker-v2':'worker-v1';return route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{...employee(id),...(mode==='historical'&&id==='worker-v1'?{publicationState:'NOT_PUBLISHED'}:{}),...(mode==='mismatch'&&id==='worker-v2'?{employeeDefinitionDigest:'c'.repeat(64)}:{})}}});
 });
 await page.route('**/employees/worker/revisions/worker-v1/authoring',route=>{ownerReads++;return route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{basis:'OWNER_FACT_ORDER',parent:{employeeDefinitionId:mode==='owner-mismatch'?'different':'worker',employeeDefinitionRevisionId:'worker-v1',employeeDefinitionDigest:digest},publication:mode==='withdrawn'||mode==='changed-resource'&&ownerReads>1?{status:'WITHDRAWN'}:{status:'AVAILABLE',definition:employee(mode==='same'?'worker-v1':'worker-v2')}}}})});
 if(mode==='changed-head')await page.route('**/business-capabilities/handover/revisions/r2',route=>{headReads++;return route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{revision,members,digest,aggregateVersion:headReads>1?4:3,headRevisionId:headReads>1?'r3':'r2',publishedRevisionId:'r2',currentDraftRevisionId:null,state:'PUBLISHED',executionAuthorized:false}}})});
 if(mode==='lost-save')await page.route('**/business-capabilities',route=>{if(route.request().method()!=='POST')return route.fallback();state.saves.push(route.request().postDataJSON());return route.abort('failed')});
 if(mode==='historical')await page.route('**/business-capabilities/handover/revisions/r2',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{revision,members,digest,aggregateVersion:4,headRevisionId:'r3',publishedRevisionId:'r3',currentDraftRevisionId:null,state:'PUBLISHED',executionAuthorized:false}}}));
 await page.goto('/capabilities?capability=handover&revision=r2&returnConversation=original');await page.getByRole('button',{name:'检查资源更新',exact:true}).click();const panel=page.getByRole('region',{name:'资源版本升级'});
 if(['new','lost-save','changed-head','changed-resource'].includes(mode)){
  await expect(panel).toContainText('补充核对回退责任');await expect(panel).toContainText('核对交接材料');await expect(panel.getByRole('button',{name:'创建能力新版本草稿'})).toBeDisabled();expect(state.saves).toHaveLength(0);
  await panel.getByRole('checkbox').check();await panel.getByRole('button',{name:'创建能力新版本草稿'}).click();
  if(mode==='changed-head'||mode==='changed-resource'){await expect(panel.getByRole('alert')).toContainText('已变化');expect(state.saves).toHaveLength(0);return}
  if(mode==='lost-save'){await expect(panel.getByRole('alert')).toContainText('草稿结果尚未核实');expect(state.saves).toHaveLength(1);await panel.getByRole('button',{name:'读取原草稿',exact:true}).click();await expect(panel).toHaveCount(0);expect(state.saves).toHaveLength(1)}
  await expect.poll(()=>state.saves.length).toBe(1);
  const saved=state.saves[0];expect(saved.expectedVersion).toBe(3);expect(saved.revision.predecessor_revision_id).toBe('r2');expect(saved.revision.bindings).toEqual([{...revision.bindings[0],reference:{resource_id:'worker',revision_id:'worker-v2',digest:newer}}]);
  for(const field of ['intent','inputs','outputs','acceptance_criteria','origin','business_scope','exclusions'] as const)expect(saved.revision[field]).toEqual(revision[field]);expect(state.writes).toHaveLength(0);expect(state.sources).toHaveLength(0);
 }else if(mode==='historical'){await expect(panel.getByRole('checkbox')).toHaveCount(0);await expect(panel).toContainText('正在比较历史版本');await expect(panel.getByRole('button',{name:'创建能力新版本草稿'})).toHaveCount(0);expect(state.saves).toHaveLength(0);
 }else{
  await expect(panel).toContainText(mode==='same'?'当前引用已一致，无需创建升级草稿。':mode==='withdrawn'?'当前发布版本暂不可核实':'当前或候选版本未能核实');await expect(panel.getByRole('button',{name:'创建能力新版本草稿'})).toHaveCount(0);expect(state.saves).toHaveLength(0);
 }
});

for(const mode of ['historical','mismatch','denied'] as const){
 test(`workflow provenance exact source ${mode}`,async({page})=>{
  const state=await fixture(page);let reads=0,denied=mode==='denied';
  await page.route('**/business-capabilities/handover/revisions/r2',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{revision:{...revision,origin:{kind:'WORKFLOW_REVISION',workflow:{resource_id:'workflow:handover',revision_id:'workflow-v1',digest},preparation_digest:null}},members,digest,aggregateVersion:2,headRevisionId:'r2',publishedRevisionId:'r2',currentDraftRevisionId:null,state:'PUBLISHED',executionAuthorized:false}}}));
  await page.route('**/workflows/workflow%3Ahandover/revisions/workflow-v1',route=>{
   reads++;
   if(denied)return route.fulfill({status:403,json:{reasonCode:'AUTHORITY_DENIED'}});
   return route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{subject:'human:tester',scope:{tenantId:'tenant',securityDomain:'domain'},definition:{workflowDefinitionId:'workflow:handover',name:'历史交接流程'},revision:{revisionId:'workflow-v1',digest:'sha256:'+(mode==='mismatch'?'b'.repeat(64):digest),state:'ARCHIVED',content:{description:'固定历史说明',inputs:['交接说明'],outputs:['核对清单'],tasks:[{taskId:'one',name:'核对责任分工',inputs:['人员记录'],outputs:['待补事项']}]}}}}});
  });
  await page.route('**/business-capabilities?**',route=>{
   const query=new URL(route.request().url()).searchParams;
   if(!query.has('workflowId'))return route.fallback();
   expect(query.get('workflowId')).toBe('workflow:handover');expect(query.get('workflowRevision')).toBe('workflow-v1');expect(query.get('workflowDigest')).toBe(digest);
   return route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:[{capabilityId:'related',revisionId:'related-r1',digest,title:'同源责任核对',intent:'核对职责',state:'DRAFT',currentPublished:null,currentDraft:null}],nextCursor:null}}});
  });
  await page.goto('/capabilities?capability=handover&revision=r2&returnConversation=original');
  await expect(page.getByRole('button',{name:'查看来源执行方案',exact:true})).toBeVisible();expect(reads).toBe(0);
  await page.getByRole('button',{name:'查看来源执行方案',exact:true}).click();
  if(mode==='historical'){
   await expect(page.getByRole('heading',{name:'历史交接流程'})).toBeVisible();await expect(page.getByText('核对责任分工',{exact:true})).toBeVisible();
   await page.getByText('查看来源固定版本',{exact:true}).click();await expect(page.getByText('workflow-v1',{exact:true})).toBeVisible();
   await page.getByRole('button',{name:'查看由此执行方案形成的能力'}).click();await expect(page.getByRole('link',{name:'同源责任核对'})).toHaveAttribute('href',`/capabilities?capability=related&revision=related-r1&digest=${digest}&returnConversation=original`);
  }else{
   await expect(page.getByText('来源执行方案暂时无法读取，或当前账号无权查看此版本。未展示未经核对的内容。')).toBeVisible();
   await expect(page.getByText('固定历史说明',{exact:true})).toHaveCount(0);
   if(mode==='denied'){denied=false;await page.getByRole('button',{name:'重新读取来源执行方案'}).click();await expect(page.getByRole('heading',{name:'历史交接流程'})).toBeVisible()}
  }
  await expect(page.getByRole('link',{name:'返回原会话'})).toHaveAttribute('href','/work?conversation=original');
  expect(state.saves).toEqual([]);expect(state.writes).toEqual([]);expect(state.sources).toEqual([]);
 });
}
test('independent capability has no invented workflow provenance',async({page})=>{
 await fixture(page);let reads=0;page.on('request',request=>{if(request.url().includes('/workflows/'))reads++});
 await page.goto('/capabilities?capability=handover&revision=r2');await expect(page.getByRole('heading',{name:revision.title,exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'查看来源执行方案',exact:true})).toHaveCount(0);expect(reads).toBe(0);
});

for(const mode of ['normal','source-lost','capability-lost','draft-return','draft-isolation','draft-storage-failure'])test(`process design automatically records fixed source and resumes original receipt ${mode}`,async({page})=>{
 await fixture(page);
 const source={resource_id:'process-one',revision_id:'process-v1',digest},activity={activity_id:'activity-one',name:'核对证据',inputs:['原始说明'],outputs:['缺项清单'],human_boundary:'负责人确认',completion_conditions:['每项有原文'],employee:{resource_id:'worker',revision_id:'worker-v1',digest}};
 const sourceUrl='/business-processes?'+new URLSearchParams({process:source.resource_id,revision:source.revision_id,digest,activity:activity.activity_id});
 let saved:CapabilityDetail,relation:BusinessRelationCommand;const capabilityWrites:CapabilitySaveDraft[]=[],relationWrites:BusinessRelationCommand[]=[];
 await page.route('**/api/workbench/v1/business-processes/**',route=>{
  const path=new URL(route.request().url()).pathname;
  const json=(result:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result}});
  if(path.endsWith('/capability-relations')&&route.request().method()==='POST'){
   relation=route.request().postDataJSON();relationWrites.push(relation);
   if(mode==='source-lost')return route.abort('failed');
   return json({relationId:relation.relation.relation_id,relationRevisionId:relation.relation.relation_revision_id,relationVersion:1,digest,executionAuthorized:false});
  }
  if(path.includes('/capability-relations/commands/'))return json({relationId:relation.relation.relation_id,relationRevisionId:relation.relation.relation_revision_id,relationVersion:1,digest,executionAuthorized:false});
  return json({objectId:source.resource_id,revisionId:source.revision_id,digest,record:{content:{name:'证据核对流程',purpose:'核对资料完整性',activities:[activity],source_materials:[]}}});
 });
 await page.route('**/api/workbench/v1/business-capabilities**',route=>{
  const path=new URL(route.request().url()).pathname;
  const json=(result:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result}});
  if(path.endsWith('/business-capabilities')&&route.request().method()==='POST'){const command=route.request().postDataJSON();capabilityWrites.push(command);saved={revision:command.revision,digest,state:'DRAFT',aggregateVersion:1,headRevisionId:command.revision.revision_id,publishedRevisionId:null,currentDraftRevisionId:command.revision.revision_id,executionAuthorized:false};if(mode==='capability-lost')return route.abort('failed');return json({accepted:true})}
  if(saved&&path.includes('/revisions/'))return json(saved);
  return route.fallback();
 });
 await page.goto('/capabilities?'+new URLSearchParams({processDesign:sourceUrl}));
 await expect(page.getByLabel('需要提供哪些资料',{exact:true})).toHaveValue('原始说明');
 await expect(page.getByLabel('将交付什么',{exact:true})).toHaveValue('缺项清单');
 if(mode.startsWith('draft-')){
  const notes='  原始边界\n第二行\n\n';
  if(mode==='draft-storage-failure')await page.evaluate(()=>{const set=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k.startsWith('capability-process-design:'))throw Error('Quota');return set.call(this,k,v)}});
  await page.getByLabel('适用范围',{exact:true}).fill(notes);await page.getByLabel('完成标准（每行一项）',{exact:true}).fill(notes);
  if(mode==='draft-storage-failure'){await expect(page.getByRole('alert')).toContainText('编辑内容暂时无法保留');await page.getByRole('link',{name:'返回原流程活动',exact:true}).click();await expect(page).toHaveURL(/processDesign=/)}
  else{
   if(mode==='draft-isolation')await page.route('**/api/workbench/v1/session',route=>route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:other',tenantId:'tenant',securityDomain:'domain'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'other-csrf'}}));
   await page.reload();await expect(page.getByLabel('适用范围',{exact:true})).toHaveValue(mode==='draft-isolation'?'':notes);
   if(mode==='draft-return'){await expect(page.getByLabel('完成标准（每行一项）',{exact:true})).toHaveValue(notes);await page.goto('/capabilities');await page.goto('/capabilities?'+new URLSearchParams({processDesign:sourceUrl}));await expect(page.getByLabel('适用范围',{exact:true})).toHaveValue(notes)}
  }
  expect(capabilityWrites).toHaveLength(0);expect(relationWrites).toHaveLength(0);return;
 }
 for(const [name,value] of [['适用范围','仅合成资料'],['不包含哪些操作','不部署'],['当前已知限制','未验证执行效果']])await page.getByLabel(name,{exact:true}).fill(value);
 await page.getByRole('button',{name:'保存草稿',exact:true}).click();
 if(mode==='capability-lost'){await expect(page.getByRole('alert')).toContainText('保存结果尚未核实');await page.reload();await page.getByRole('button',{name:'核实并重试本次保存',exact:true}).click()}
 if(mode==='source-lost'){await expect(page.getByRole('alert')).toContainText('来源登记未完成');await page.reload();await page.getByRole('button',{name:'核实原来源登记',exact:true}).click()}
 await expect(page.getByRole('status').filter({hasText:'设计来源已登记'})).toBeVisible();
 expect(capabilityWrites).toHaveLength(1);expect(relationWrites).toHaveLength(1);
 expect(relation.relation.process).toEqual(source);expect(relation.relation.activity_ids).toEqual(['activity-one']);expect(relation.relation.relation_type).toBe('DERIVED_FROM_PROCESS');
 expect(relation.relation.capability).toEqual({resource_id:saved.revision.capability_id,revision_id:saved.revision.revision_id,digest});
 await page.screenshot({path:test.info().outputPath('process-design-controlled.png'),fullPage:true});
});

for(const mode of ['return','isolation','cancel'])test(`independent draft restores safely ${mode}`,async({page})=>{
 const state=await fixture(page);await page.goto('/capabilities');await page.getByRole('button',{name:'创建独立能力',exact:true}).click();
 const raw='  未提交的独立草稿\n保留末尾空行\n\n';await page.getByLabel('适用范围',{exact:true}).fill(raw);await page.getByLabel('能力名称',{exact:true}).fill('独立草稿恢复测试');await page.getByLabel('本次承担什么职责',{exact:true}).fill('  尚未加入的职责  ');await expect(page).toHaveURL(/create=independent/);
 if(mode==='isolation')await page.route('**/api/workbench/v1/session',route=>route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:other',tenantId:'tenant',securityDomain:'domain'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'other-csrf'}}));
 await page.reload();await expect(page.getByLabel('适用范围',{exact:true})).toHaveValue(mode==='isolation'?'':raw);
 if(mode==='return'){await expect(page.getByLabel('本次承担什么职责',{exact:true})).toHaveValue('  尚未加入的职责  ');await page.goto('/capabilities');await page.getByRole('button',{name:'创建独立能力',exact:true}).click();await expect(page.getByLabel('适用范围',{exact:true})).toHaveValue(raw)}
 if(mode==='cancel'){await page.getByRole('button',{name:'取消编辑',exact:true}).click();await page.getByRole('button',{name:'创建独立能力',exact:true}).click();await expect(page.getByLabel('适用范围',{exact:true})).toHaveValue('')}
 expect(state.saves).toHaveLength(0);
});

test('independent pending save survives reload without duplicate creation',async({page})=>{
 const state=await fixture(page);await page.route('**/business-capabilities',route=>{if(route.request().method()!=='POST')return route.fallback();state.saves.push(route.request().postDataJSON());return route.abort('failed')});
 await page.goto('/capabilities');await page.getByRole('button',{name:'创建独立能力',exact:true}).click();const form=page.getByRole('form',{name:'业务能力编辑'});
 for(const label of ['能力名称','希望完成什么','需要提供哪些资料','将交付什么','适用范围','不包含哪些操作','需要人工参与什么','当前已知限制'])await form.getByLabel(label,{exact:true}).fill(label==='能力名称'?'原提交续接测试':label+'说明');
 await form.getByLabel('完成标准（每行一项）').fill('核对依据');await form.getByLabel('已发布资源',{exact:true}).selectOption({label:'交接核对助手'});await form.getByLabel('本次承担什么职责').fill('核对依据');await form.getByRole('button',{name:'加入能力组成'}).click();await form.getByRole('button',{name:'保存草稿',exact:true}).click();await expect(page.getByText('保存结果尚未核实。再次核实会沿用同一份内容和提交记录。',{exact:true})).toBeVisible();
 await page.reload();await page.getByRole('button',{name:'核实并重试本次保存',exact:true}).click();await expect(page.getByRole('heading',{name:'原提交续接测试',exact:true})).toBeVisible();expect(state.saves).toHaveLength(1);
});

test('independent local storage failure preserves form and blocks silent cancellation',async({page})=>{
 const state=await fixture(page);await page.goto('/capabilities?create=independent');await expect(page.getByLabel('能力名称',{exact:true})).toBeVisible();
 await page.evaluate(()=>{const original=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k.startsWith('capability-independent-draft:'))throw Error('Quota');return original.call(this,k,v)}});
 await page.getByLabel('能力名称',{exact:true}).fill('仍保留在页面的填写');await expect(page.getByText('本地草稿暂存失败，请保留此页并恢复浏览器存储后继续。',{exact:true})).toBeVisible();await page.getByRole('button',{name:'取消编辑',exact:true}).click();await expect(page.getByLabel('能力名称',{exact:true})).toHaveValue('仍保留在页面的填写');expect(state.saves).toHaveLength(0);
});

 test('independent cancel after directory settles restores usable directory',async({page})=>{await fixture(page);await page.goto('/capabilities');await page.getByRole('button',{name:'创建独立能力',exact:true}).click();await expect(page.getByText('正在读取业务能力…',{exact:true})).toBeHidden();await page.getByRole('button',{name:'取消编辑',exact:true}).click();await expect(page.getByRole('button',{name:'创建独立能力',exact:true})).toBeEnabled();await expect(page.getByText('正在读取业务能力…',{exact:true})).toBeHidden();});
