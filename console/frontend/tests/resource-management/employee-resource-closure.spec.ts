import {expect,test,type Page} from '@playwright/test';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {fixture as maintenance,skillId,employeeId,principal,reportText,source} from '../helpers/resourceMaintenanceFixture';
import type {EmployeeDefinition,EmployeeCreateCommand} from '../../src/api/digitalEmployees';
const old='employee-revision:consumer',agent={kind:'AGENT' as const,resourceId:'agent:consumer',revisionId:'agent-revision:1',digest:'e'.repeat(64)};
const envelope=(result:unknown)=>({schemaVersion:'workbench-operation.v1',result,continuationIds:[]});
const canonical=(value:unknown):unknown=>typeof value==='string'?value.normalize('NFC'):Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.entries(value).sort(([a],[b])=>a<b?-1:1).map(([k,v])=>[k,canonical(v)])):value;
function ownerDigest(c:EmployeeCreateCommand){
 const record:Record<string,unknown>={schemaVersion:'digital-employee-composition.v1',namespace:principal.tenantId,securityDomain:principal.securityDomain,definitionId:c.employeeDefinitionId,revisionId:c.employeeDefinitionRevisionId,role:c.role,responsibilities:c.responsibilities,members:[...c.members].sort((a,b)=>a.kind<b.kind?-1:a.kind>b.kind?1:a.resourceId<b.resourceId?-1:1).map(m=>({kind:m.kind,resource_id:m.resourceId,revision_id:m.revisionId,digest:m.digest})),predecessorRevisionId:c.predecessorEmployeeRevisionId??null};
 if(c.responsibilityBindings?.length){record.schemaVersion='digital-employee-composition.v2';record.responsibilityBindings=[...c.responsibilityBindings].sort((a,b)=>c.responsibilities.indexOf(a.responsibility)-c.responsibilities.indexOf(b.responsibility)||(a.member.kind<b.member.kind?-1:a.member.kind>b.member.kind?1:a.member.resourceId<b.member.resourceId?-1:1)).map(b=>({responsibility:b.responsibility,member:{kind:b.member.kind,resource_id:b.member.resourceId,revision_id:b.member.revisionId,digest:b.member.digest}}))}
 return createHash('sha256').update(JSON.stringify(canonical(record))).digest('hex');
}
async function fixture(page:Page){
 const state=await maintenance(page,true);state.resource.aggregateVersion=8;state.resource.publishedRevisionId='revision:2';state.resource.currentDraftRevisionId=null;state.resource.lifecycleState='PUBLISHED';state.resource.revisions[0].state='PUBLISHED';state.resource.revisions.push({...structuredClone(state.resource.revisions[0]),revisionId:'revision:2',predecessorRevisionId:'revision:1',digest:'b'.repeat(64),state:'PUBLISHED'});
 state.resource.testResults=[{resultId:'test:old',revisionId:'revision:1',revisionDigest:'a'.repeat(64),operation:'READ_DATA',caseName:'旧维护用例',status:'PASSED',actualExecution:true,verificationLevel:'ISOLATED_SYNTHETIC_EXECUTOR',actual:{oldRevision:true}},{resultId:'test:current',revisionId:'revision:2',revisionDigest:'b'.repeat(64),operation:'READ_DATA',caseName:'新维护用例',status:'PASSED',actualExecution:true,verificationLevel:'ISOLATED_SYNTHETIC_EXECUTOR',actual:{newRevision:true}},{resultId:'test:unverified',revisionId:'unknown',revisionDigest:'0'.repeat(64),status:'PASSED',actualExecution:true}];
 const original:EmployeeDefinition={resourceKind:'DIGITAL_EMPLOYEE_DEFINITION',employeeDefinitionId:employeeId,employeeDefinitionRevisionId:old,employeeDefinitionDigest:'d'.repeat(64),role:'准确资源引用员工',responsibilities:['维护旧修订'],publicationState:'NOT_PUBLISHED',lifecycleState:'DRAFT',aggregateVersion:1,members:[agent,{kind:'MCP',resourceId:'mcp:disabled',revisionId:'mcp-revision:old',digest:'9'.repeat(64)},{kind:'SKILL',resourceId:skillId,revisionId:'revision:1',digest:'a'.repeat(64)}]};
 const extra={records:new Map([[old,original]]),posts:[] as {path:string;body:Record<string,unknown>}[],readable:true,rejectNext:"",loseNext:false,wrongReceipt:false,hold:false,release:()=>{}};
 await page.route('**/api/workbench/v1/employees**',async route=>{
  const req=route.request(),path=decodeURIComponent(new URL(req.url()).pathname),parts=path.split('/'),rev=parts[parts.indexOf('revisions')+1];
  if(req.method()==='GET'){
   state.gets.push(path);
   if(path.endsWith('/employees'))return route.fulfill({json:envelope({items:[...extra.records.values()]})});
   if(path.endsWith('/work-records'))return route.fulfill({json:envelope({schemaVersion:'employee-work-records.v1',subject:principal.principalId,scope:{tenantId:principal.tenantId,securityDomain:principal.securityDomain},employeeDefinition:extra.records.get(rev),items:[],scanLimited:false,visibility:'AUTHORIZED_ONLY',executionStarted:false})});
   if(path.endsWith('/authoring')){
    const values=[...extra.records.values()],head=values.at(-1)!,publication=[...values].reverse().find(x=>x.publicationState==='PUBLISHED');
    const version=Math.max(...values.map(x=>x.aggregateVersion??0));
    const available=(d:EmployeeDefinition)=>({status:'AVAILABLE',definition:{...d,aggregateVersion:version}});
    return route.fulfill({json:envelope({basis:'OWNER_FACT_ORDER',parent:extra.records.get(rev),aggregateVersion:version,head:available(head),draft:['DRAFT','VALIDATED','APPROVED'].includes(head.lifecycleState??'')?available(head):{status:'NONE'},publication:publication?available(publication):{status:'NOT_AVAILABLE'},executionStarted:false})});
   }
   if(path.endsWith('/history'))return route.fulfill({json:envelope({items:[...extra.records.values()],visibility:'AUTHORIZED_ONLY',nextCursor:null,executionStarted:false})});
   const record=extra.records.get(rev);return record&&(extra.readable||rev===old)?route.fulfill({json:envelope(record)}):route.fulfill({status:403,json:{reasonCode:'EXACT_READ_REQUIRED'}});
  }
  const body=req.postDataJSON();extra.posts.push({path,body});expect(req.headers()['x-csrf-token']).toBe('fixture-csrf');
  let result:EmployeeDefinition;
  if(path.endsWith('/employees')){
   if(extra.rejectNext){const reasonCode=extra.rejectNext;extra.rejectNext='';return route.fulfill({status:409,json:{reasonCode}})}
   const command=body as EmployeeCreateCommand;expect(command.employeeDefinitionId).toBe(employeeId);expect(command.predecessorEmployeeRevisionId).toBe(old);expect(command.expectedVersion).toBe(1);
   original.aggregateVersion=2;result={...structuredClone(original),employeeDefinitionRevisionId:command.employeeDefinitionRevisionId,employeeDefinitionDigest:ownerDigest(command),responsibilities:command.responsibilities,responsibilityBindings:command.responsibilityBindings,members:command.members,aggregateVersion:2};extra.records.set(result.employeeDefinitionRevisionId,result);
  }else{
   result=extra.records.get(rev)!;expect(body.employeeDefinitionDigest).toBe(result.employeeDefinitionDigest);expect(body.expectedVersion).toBe(result.aggregateVersion);
   result.aggregateVersion!++;result.lifecycleState=path.endsWith('/validation')?'VALIDATED':path.endsWith('/approvals')?'APPROVED':'PUBLISHED';result.publicationState=result.lifecycleState==='PUBLISHED'?'PUBLISHED':'NOT_PUBLISHED';
  }
  if(extra.hold)await new Promise<void>(resolve=>{extra.release=resolve});
  if(extra.loseNext){extra.loseNext=false;return route.abort('failed')}
  return route.fulfill({json:envelope({...result,...(extra.wrongReceipt?{employeeDefinitionDigest:'0'.repeat(64)}:{})})});
 });
 return {state,extra,original};
}
const href=()=>'/employees?'+new URLSearchParams({employeeView:'professional',employeeDefinitionId:employeeId,employeeDefinitionRevisionId:old,detail:'1',section:'overview'});
async function prepare(page:Page){await page.getByRole('button',{name:'准备员工后继',exact:true}).click();await page.getByLabel('后继职责',{exact:true}).fill('维护发布后的准确资源\n保留旧记录，不启动业务运行');await page.getByRole('checkbox',{name:'保留 MCP mcp:disabled',exact:true}).uncheck();await page.getByRole('region',{name:'组合业务资源'}).getByRole('checkbox').check();await page.getByRole('button',{name:'核对后继草稿',exact:true}).click();await expect(page.getByRole('region',{name:'员工后继确认'})).toBeVisible()}
async function save(page:Page){await page.getByRole('button',{name:'确认保存后继草稿',exact:true}).click()}
test('same Employee successor selects current published Skill and preserves original draft through publication',async({page},info)=>{
 const {state,extra,original}=await fixture(page);await page.goto(href());await prepare(page);await save(page);await expect.poll(()=>extra.posts.length).toBe(1);const command=extra.posts[0].body as EmployeeCreateCommand;expect(command.members).toEqual([agent,{kind:'SKILL',resourceId:skillId,revisionId:'revision:2',digest:'b'.repeat(64)}]);expect(command.employeeDefinitionRevisionId).not.toBe(old);await expect.poll(()=>new URL(page.url()).searchParams.get('employeeDefinitionRevisionId')).toBe(command.employeeDefinitionRevisionId);
 for(const action of ['校验修订','批准修订','发布修订']){await page.getByRole('button',{name:new RegExp('^'+action)}).click();await page.getByRole('button',{name:'确认提交',exact:true}).click();await expect(page.getByRole('button',{name:'确认提交',exact:true})).toHaveCount(0)}
 await expect.poll(()=>extra.posts.length).toBe(4);await expect.poll(()=>extra.records.get(command.employeeDefinitionRevisionId)?.lifecycleState).toBe('PUBLISHED');expect(extra.records.get(command.employeeDefinitionRevisionId)?.lifecycleState).toBe('PUBLISHED');expect(original.lifecycleState).toBe('DRAFT');expect(original.members.find(m=>m.kind==='SKILL')?.revisionId).toBe('revision:1');expect(state.posts).toEqual([]);
 for(const width of [1280,390]){await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.screenshot({path:info.outputPath('employee-successor-'+width+'.png')})}
});
test('lost successor response reload recovers only its original revision via GET',async({page})=>{
 const {extra}=await fixture(page);await page.goto(href());await prepare(page);extra.loseNext=true;extra.readable=false;await save(page);await expect(page.getByRole('button',{name:'读取原后继修订',exact:true})).toBeEnabled();const rev=String(extra.posts[0].body.employeeDefinitionRevisionId);await page.reload();await expect(page.getByRole('button',{name:'读取原后继修订',exact:true})).toBeEnabled();extra.readable=true;await page.getByRole('button',{name:'读取原后继修订',exact:true}).click();await expect.poll(()=>new URL(page.url()).searchParams.get('employeeDefinitionRevisionId')).toBe(rev);expect(extra.posts).toHaveLength(1);
});
test('stale aggregate or changed identity cannot create a successor',async({page})=>{
 const {state,extra,original}=await fixture(page);await page.goto(href());await prepare(page);original.aggregateVersion=9;await save(page);await expect(page.getByRole('status').filter({hasText:'原员工版本已变化'})).toBeVisible();expect(extra.posts).toEqual([]);state.otherIdentity=true;await save(page);expect(extra.posts).toEqual([]);
});
test('wrong receipt and unreadable result retains UNKNOWN without resubmission',async({page})=>{
 const {extra}=await fixture(page);await page.goto(href());await prepare(page);extra.wrongReceipt=true;extra.readable=false;await save(page);await expect(page.getByRole('button',{name:'读取原后继修订',exact:true})).toBeEnabled();await page.getByRole('button',{name:'读取原后继修订',exact:true}).click();await expect(page.getByRole('button',{name:'确认保存后继草稿',exact:true})).toHaveCount(0);expect(extra.posts).toHaveLength(1);
});
test('late response from another identity cannot replace selected Employee',async({page})=>{
 const {state,extra}=await fixture(page);await page.goto(href());await prepare(page);extra.hold=true;await save(page);await expect.poll(()=>extra.posts.length).toBe(1);state.otherIdentity=true;extra.release();await expect(page.getByRole('button',{name:'读取原后继修订',exact:true})).toBeEnabled();expect(new URL(page.url()).searchParams.get('employeeDefinitionRevisionId')).toBe(old);expect(extra.posts).toHaveLength(1);
});
test('lost lifecycle response survives reload and reads state without replaying POST',async({page})=>{
 const {extra}=await fixture(page);await page.goto(href());await page.getByRole('button',{name:/^校验修订/}).click();extra.loseNext=true;await page.getByRole('button',{name:'确认提交',exact:true}).click();await expect(page.getByRole('button',{name:'读取原修订状态',exact:true})).toBeEnabled();await page.reload();await expect(page.getByRole('button',{name:'读取原修订状态',exact:true})).toBeEnabled();await page.getByRole('button',{name:'读取原修订状态',exact:true}).click();await expect(page.getByRole('button',{name:/^批准修订/})).toBeEnabled();expect(extra.posts).toHaveLength(1);
});
test('selected historical maintenance result remains separate from current publication evidence',async({page})=>{
 const {state}=await fixture(page);await page.goto('/skills?'+new URLSearchParams({managedResource:skillId,resourceTab:'使用追溯'}));const records=page.getByRole('article',{name:'维护测试使用记录'});await expect(records.getByRole('button',{name:'查看维护测试结果',exact:true})).toHaveCount(2);await records.getByRole('row').filter({hasText:'旧维护用例'}).getByRole('button').click();await expect(page.getByRole('tab',{name:'测试',exact:true})).toHaveAttribute('aria-selected','true');await expect(page.getByText('正在查看历史修订的维护测试结果，不计入当前版本发布依据。',{exact:true})).toBeVisible();await expect(page.getByLabel('本次真实测试结果')).toContainText('旧维护用例');expect(state.posts).toEqual([]);
});
for(const mode of ['valid','overview','professional','invalid-section','duplicate-section','wrong-member','external-back','duplicate-ref'])test('exact referring Employee resource return '+mode,async({page})=>{
 const {state,original}=await fixture(page);original.members=original.members.filter(m=>m.kind!=='MCP');original.members.find(m=>m.kind==='SKILL')!.revisionId='revision:2';original.members.find(m=>m.kind==='SKILL')!.digest='b'.repeat(64);if(mode==='wrong-member')original.members.find(m=>m.kind==='SKILL')!.revisionId='revision:foreign';
 const params=new URLSearchParams({kind:'skill',query:skillId,selected:skillId,resourceRevision:'revision:2',resourceDigest:'b'.repeat(64),employeeRef:employeeId,employeeRev:old,employeeDigest:'d'.repeat(64),employeeResourceBack:'/skills?'+new URLSearchParams({managedResource:skillId,resourceTab:'使用追溯'})});if(mode==='external-back')params.set('employeeResourceBack','https://foreign.invalid/skills');if(mode==='duplicate-ref')params.append('employeeRef',employeeId);
 if(mode==='overview'||mode==='professional')params.set('employeeSection','overview');if(mode==='professional')params.set('employeeViewReturn','professional');if(mode==='invalid-section')params.set('employeeSection','other');if(mode==='duplicate-section'){params.append('employeeSection','overview');params.append('employeeSection','capabilities')}
 await page.goto('/skills?'+params);if(['valid','overview','professional'].includes(mode)){await page.getByRole('link',{name:'返回引用员工',exact:true}).click();await expect(page.getByRole('heading',{name:'准确资源引用员工',exact:true})).toBeVisible();expect(new URL(page.url()).searchParams.get('section')).toBe(mode==='valid'?'capabilities':'overview');if(mode==='professional')expect(new URL(page.url()).searchParams.get('employeeView')).toBe('professional');await page.getByRole('link',{name:/返回资源维护/}).click();await expect(page.getByRole('tab',{name:'使用追溯',exact:true})).toHaveAttribute('aria-selected','true')}else{await expect(page.getByRole('link',{name:'返回引用员工',exact:true})).toHaveCount(0)}expect(state.posts).toEqual([]);
});

const plan=JSON.parse(readFileSync(new URL('../e2e/fixtures/delivery-plan.json',import.meta.url),'utf8'));
test('Employee Agent saved result and same-resource return retain exact referring Employee and maintenance tab',async({page})=>{
 const {state,original,extra}=await fixture(page),scope={tenantId:principal.tenantId,securityDomain:principal.securityDomain};
 const item={kind:'agent',identity:agent.resourceId,revisionId:agent.revisionId,digest:agent.digest,name:'已保存引用的Agent',enabled:true,isCurrentPublished:true,isCurrentDraft:false,state:'PUBLISHED',executionReady:false,createdAt:'2026-11-08'};
 await page.route('**/api/workbench/v1/resource-directory**',async route=>{
  const path=decodeURIComponent(new URL(route.request().url()).pathname),kind=new URL(route.request().url()).searchParams.get('kind');
  if(path.endsWith('/resource-directory')&&kind==='agent')return route.fulfill({json:{result:{subject:principal.principalId,scope,items:[item],nextCursor:null,executionAuthority:'NONE'}}});
  if(path.includes('/resource-directory/agent/'))return route.fulfill({json:{result:{...item,subject:principal.principalId,scope,revision:{revisionId:item.revisionId,digest:item.digest,state:'PUBLISHED',createdAt:'2026-11-08',content:{title:'核对原保存引用',duties:['核对来源']}},usage:[{digest:'c'.repeat(64),title:'原Agent已保存结果',planVersion:4,state:'SUCCEEDED',problemId:'maintenance-problem'}]}}});
  return route.fallback();
 });
 await page.route('**/api/workbench/v1/prepared-executions/**',route=>{
  const ref={resource_id:employeeId,revision_id:old,digest:original.employeeDefinitionDigest},skill={resource_id:skillId,revision_id:'revision:1',digest:'a'.repeat(64)};
  return route.fulfill({json:{result:{digest:'c'.repeat(64),executionStarted:true,preparation:{plan_id:'maintenance-plan',plan_version:4,plan_digest:'9'.repeat(64),approval_id:'fixture-only',source_snapshot:source,semantics:{...plan.semantics,title:'原Agent已保存结果',target:{problem:{resource_id:'maintenance-problem',revision_id:'1',digest:'8'.repeat(64)}}},participants:plan.semantics.tasks.map((t:{task_id:string;operation:string})=>({task_id:t.task_id,instance_id:'fixture-instance',assignment_id:'fixture-assignment',definition:ref,skill:{reference:skill,operation:t.operation},profile:ref}))},progress:{state:'SUCCEEDED',version:10,cancellation_request_id:null,tasks:plan.semantics.tasks.map((t:{task_id:string})=>({task_id:t.task_id,state:'SUCCEEDED',attempt_ordinal:1,reason:null}))},admission:{state:'NOT_ADMITTED',reason:'READ_ONLY_FIXTURE'},resourceUses:[],artifacts:[{artifact_id:'saved-report',task_id:plan.semantics.tasks.at(-1).task_id,digest:'7'.repeat(64),bytes:reportText.length,created_at:'2026-11-08',contentAccess:'AUTHORIZED',content:reportText}],events:[],outcome:null}}});
 });
 await page.goto(href()+'&resourceBack='+encodeURIComponent('/skills?'+new URLSearchParams({managedResource:skillId,resourceTab:'使用追溯'})));
 await page.getByRole('button',{name:'职责与能力',exact:true}).click();await page.getByRole('table').getByRole('link').filter({hasText:agent.resourceId}).click();await expect(page.getByRole('link',{name:'返回引用员工',exact:true})).toBeVisible();
 await page.getByRole('tab',{name:'引用与影响',exact:true}).click();await page.getByRole('button',{name:'原Agent已保存结果',exact:true}).click();await expect(page.getByRole('region',{name:'销售诊断关键数据'})).toBeVisible();await page.reload();await page.getByRole('link',{name:'返回同一准确资源',exact:true}).click();await page.getByRole('link',{name:'返回引用员工',exact:true}).click();await page.getByRole('link',{name:/返回资源维护/}).click();await expect(page.getByRole('tab',{name:'使用追溯',exact:true})).toHaveAttribute('aria-selected','true');expect(extra.posts).toEqual([]);expect(state.posts).toEqual([]);
});

test('explicit published Agent selection replaces only the primary member in same Employee successor',async({page})=>{
 const {extra,original}=await fixture(page);const replacement={kind:'AGENT',resourceId:'agent:replacement',revisionId:'agent-revision:published',digest:'6'.repeat(64)};
 await page.route('**/api/workbench/v1/resource-directory?**',route=>{if(new URL(route.request().url()).searchParams.get('kind')!=='agent')return route.fallback();return route.fulfill({json:{result:{subject:principal.principalId,scope:{tenantId:principal.tenantId,securityDomain:principal.securityDomain},items:[{kind:'agent',identity:replacement.resourceId,revisionId:replacement.revisionId,digest:replacement.digest,name:'明确选择的已发布Agent',enabled:true,isCurrentPublished:true},{kind:'agent',identity:'agent:another',revisionId:'agent-revision:another',digest:'5'.repeat(64),name:'另一个已发布Agent',enabled:true,isCurrentPublished:true},{kind:'agent',identity:'agent:draft',revisionId:'draft',digest:'4'.repeat(64),name:'不可选择的Agent草稿',enabled:true,isCurrentPublished:false}],nextCursor:null}}})});
 await page.goto(href());await page.getByRole('button',{name:'准备员工后继',exact:true}).click();await page.getByRole('checkbox',{name:'保留 MCP mcp:disabled',exact:true}).uncheck();const picker=page.getByRole('region',{name:'组合业务资源'});await picker.getByRole('checkbox').check();await picker.getByRole('button',{name:/^Agent职责/}).click();await picker.getByRole('checkbox',{name:/明确选择的已发布Agent/}).check();await picker.getByRole('checkbox',{name:/另一个已发布Agent/}).click();await expect(picker.getByRole('alert')).toContainText('只能选择一个Agent职责');await expect(picker.getByText('不可选择的Agent草稿',{exact:true})).toHaveCount(0);await page.getByRole('button',{name:'核对后继草稿',exact:true}).click();await save(page);await expect.poll(()=>extra.posts.length).toBe(1);expect((extra.posts[0].body as EmployeeCreateCommand).members).toEqual([{kind:'SKILL',resourceId:skillId,revisionId:'revision:2',digest:'b'.repeat(64)},replacement]);expect(original.members.find(m=>m.kind==='AGENT')).toEqual(agent);await expect.poll(()=>new URL(page.url()).searchParams.get('employeeDefinitionRevisionId')).not.toBe(old);
});

for(const mode of ['exact','historical','mismatch','denied'])test('F3 named employee resources '+mode+' preserve fixed references without writes',async({page},info)=>{
 const {state,extra}=await fixture(page);
 await page.route('**/api/workbench/v1/resource-directory?**',async route=>{
  const url=new URL(route.request().url());if(url.searchParams.get('kind')!=='skill'||url.searchParams.get('query')!==skillId)return route.fallback();
  if(mode==='denied')return route.fulfill({status:403,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
  const item={kind:'skill',identity:skillId,revisionId:mode==='mismatch'?'revision:2':'revision:1',digest:'a'.repeat(64),name:'采购交付核对技能',state:'PUBLISHED',enabled:true,isCurrentPublished:mode==='exact',isCurrentDraft:false,createdAt:null,executionReady:false,policyReviewed:false};
  return route.fulfill({json:{result:{subject:principal.principalId,scope:{tenantId:principal.tenantId,securityDomain:principal.securityDomain},items:[item],nextCursor:null,executionAuthority:'NONE'}}});
 });
 await page.goto(href().replace('employeeView=professional&',''));const card=page.getByRole('article',{name:'技能绑定资源',exact:true});
 if(mode==='exact'||mode==='historical'){
  await expect(card.getByText('采购交付核对技能',{exact:true})).toBeVisible();
  await expect(card.getByText('本次绑定版本',{exact:true})).toBeVisible();
 }else {await expect(card.getByText('已绑定技能 · 名称暂未核对',{exact:true})).toBeVisible();await expect(page.getByText('采购交付核对技能',{exact:true})).toHaveCount(0)}
 await expect(card.getByRole('link',{name:'查看详情',exact:true})).toHaveAttribute('href',/resourceRevision=revision%3A1/);
 await expect(card.getByText(skillId,{exact:true})).toBeHidden();await card.getByText('版本依据',{exact:true}).click();await expect(card.getByText(skillId,{exact:true})).toBeVisible();
 if(mode==='exact'){await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.screenshot({path:info.outputPath('employee-named-resources-mobile.png')});await page.evaluate(()=>window.dispatchEvent(new Event('workbench-session-expired')));await expect(page.getByText('采购交付核对技能',{exact:true})).toHaveCount(0)}
 expect(extra.posts).toEqual([]);expect(state.posts).toEqual([]);
});


test('F3 employee full-page business frame retains professional operations and team filters',async({page},info)=>{
 const {state,extra}=await fixture(page);await page.goto(href().replace('employeeView=professional&','')+'&q='+encodeURIComponent('准确资源'));
 const main=page.locator('.f3-employee-detail');await expect(main).toBeVisible();await expect(page.getByRole('region',{name:'员工集合',exact:true})).toBeHidden();
 const nav=page.getByRole('navigation',{name:'选中员工详情分类'});await expect(nav.getByRole('button')).toHaveText(['资源组成','职责与资源','工作记录']);
 await expect(page.getByRole('button',{name:'准备员工后继',exact:true})).toHaveCount(0);
 await expect(page.locator('.employee-detail-context code').first()).toBeHidden();await expect(page.getByText('2 项业务资源 · 已有任务保持原快照',{exact:true})).toBeVisible();await expect(page.getByRole('article',{name:'职责定义绑定资源',exact:true})).toHaveCount(0);expect(await page.locator('.employee-composition-duties li').first().evaluate(n=>getComputedStyle(n).fontSize)).toBe('14px');
 await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:info.outputPath('f3-employee-desktop.png')});
 await nav.getByRole('button',{name:'职责与资源',exact:true}).click();await page.reload();await expect(nav.getByRole('button',{name:'职责与资源',exact:true})).toHaveClass('active');
 await page.getByRole('button',{name:'查看专业管理',exact:true}).click();await expect(page.getByRole('button',{name:'职责与能力',exact:true})).toHaveClass('active');await page.getByRole('button',{name:'返回业务详情',exact:true}).click();
 await nav.getByRole('button',{name:'工作记录',exact:true}).click();await expect(page.getByRole('region',{name:'员工工作记录',exact:true})).toBeVisible();await expect(page.getByText('当前可读范围内未返回这个版本的工作记录。',{exact:true})).toBeVisible();await expect(nav.getByRole('button',{name:'工作记录',exact:true})).toHaveClass('active');
 await nav.getByRole('button',{name:'资源组成',exact:true}).click();await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.screenshot({path:info.outputPath('f3-employee-mobile.png')});
 await page.getByRole('button',{name:'← 返回员工集合',exact:true}).click();await expect(page.getByLabel('搜索当前结果')).toHaveValue('准确资源');await expect(page.getByRole('region',{name:'员工集合',exact:true})).toBeVisible();expect(extra.posts).toEqual([]);expect(state.posts).toEqual([]);
});

test('F3 business editor saves then validates and publishes exact successor in the same page',async({page},info)=>{
 const {state,extra,original}=await fixture(page);await page.goto(href().replace('employeeView=professional&',''));
 await page.getByRole('button',{name:'修改职责与资源',exact:true}).click();const editor=page.getByRole('region',{name:'职责与资源修改',exact:true});await expect(editor).toBeVisible();
 await page.getByLabel('职能职责',{exact:true}).fill('核对采购交付并形成可追溯报告');
 await page.getByLabel('保留已绑定资源 1',{exact:true}).uncheck();
 await page.getByRole('region',{name:'组合业务资源'}).getByRole('checkbox').check();
 await page.getByRole('button',{name:'核对修改',exact:true}).click();await page.getByRole('button',{name:'保存修改草稿',exact:true}).click();
 await expect.poll(()=>extra.posts.length).toBe(1);const command=extra.posts[0].body as EmployeeCreateCommand;
 await expect.poll(()=>new URL(page.url()).searchParams.get('employeeDefinitionRevisionId')).toBe(command.employeeDefinitionRevisionId);expect(new URL(page.url()).searchParams.get('employeeView')).toBeNull();
 await page.reload();await expect(page.getByRole('heading',{name:'已保存的职责与资源',exact:true})).toBeVisible();expect(extra.posts).toHaveLength(1);await expect(page.locator('.employee-detail-context .employee-state-chip')).toHaveText('修改草稿 · 待验证');
 await expect(editor.getByRole('heading',{name:'已保存的职责与资源',exact:true})).toBeVisible();await expect(editor.getByText('核对采购交付并形成可追溯报告',{exact:true})).toBeVisible();await expect(editor.getByRole('article',{name:'技能绑定资源',exact:true})).toHaveCount(1);await expect(editor.getByRole('button',{name:'继续修改职责与资源',exact:true})).toBeVisible();expect(extra.posts).toHaveLength(1);
 await page.screenshot({path:info.outputPath('f3-business-saved-draft.png')});
 for(const action of ['验证草稿','确认发布资格','发布定义']){await page.getByRole('button',{name:new RegExp('^'+action)}).click();await page.getByRole('button',{name:'确认提交',exact:true}).click();await expect(page.getByRole('button',{name:'确认提交',exact:true})).toHaveCount(0)}
 await expect(page.locator('.employee-detail-context .employee-state-chip')).toHaveText('当前发布版本');expect(extra.posts).toHaveLength(4);expect(original.members.find(m=>m.kind==='SKILL')?.revisionId).toBe('revision:1');expect(original.lifecycleState).toBe('DRAFT');
 await page.getByRole('button',{name:'返回原查看版本',exact:true}).click();await expect(page.getByRole('region',{name:'员工资源组成',exact:true})).toBeVisible();expect(state.posts).toEqual([]);expect(new URL(page.url()).searchParams.get('employeeView')).toBeNull();
});


test('occupied predecessor gives definite guidance without unknown recovery or automatic resubmit',async({page})=>{
 const {extra}=await fixture(page);extra.rejectNext='EMPLOYEE_SUCCESSOR_ALREADY_EXISTS';await page.goto(href().replace('employeeView=professional&',''));await page.getByRole('button',{name:'修改职责与资源',exact:true}).click();await page.getByLabel('职能职责',{exact:true}).fill('保留旧版本并核对后继');await page.getByRole('button',{name:'核对修改',exact:true}).click();await page.getByRole('button',{name:'保存修改草稿',exact:true}).click();await expect(page.getByText('该版本已有后继记录。请从员工版本记录打开已有后继后继续修改；本次没有保存新草稿。',{exact:true})).toBeVisible();await expect(page.getByLabel('职能职责',{exact:true})).toBeEnabled();await expect(page.getByRole('button',{name:'读取原后继修订',exact:true})).toHaveCount(0);expect(extra.posts).toHaveLength(1);expect(extra.records.size).toBe(1);await page.reload();expect(extra.posts).toHaveLength(1);
});


test('business confirmation includes retained resources, replacements and removals before submission',async({page})=>{
 const {original,extra}=await fixture(page);
 original.members.push({kind:'KNOWLEDGE',resourceId:'knowledge:retained',revisionId:'knowledge-revision:retained',digest:'7'.repeat(64)});
 await page.goto(href().replace('employeeView=professional&',''));
 await page.getByRole('button',{name:'修改职责与资源',exact:true}).click();
 await page.getByRole('checkbox',{name:'保留已绑定资源 1',exact:true}).uncheck();
 await page.getByRole('region',{name:'组合业务资源'}).getByRole('checkbox').check();
 await page.getByRole('button',{name:'核对修改',exact:true}).click();
 const summary=page.getByRole('region',{name:'本次保存的完整资源摘要',exact:true});
 await expect(summary.getByRole('heading',{name:'保存后共 2 项业务资源',exact:true})).toBeVisible();
 await expect(summary.getByText('保留',{exact:true})).toBeVisible();
 await expect(summary.getByText('替换版本',{exact:true})).toBeVisible();
 await expect(summary.getByText('移除',{exact:true})).toBeVisible();
 await expect(summary.getByText('另有 1 项内部依赖，保留固定引用。',{exact:true})).toBeVisible();
 await summary.getByText('版本依据',{exact:true}).nth(1).click();
 await expect(summary.getByText('knowledge-revision:retained',{exact:true})).toBeVisible();
 expect(extra.posts).toHaveLength(0);
 await page.getByRole('button',{name:'保存修改草稿',exact:true}).click();
 await expect.poll(()=>extra.posts.length).toBe(1);
 expect((extra.posts[0].body as EmployeeCreateCommand).members).toEqual([agent,{kind:'SKILL',resourceId:skillId,revisionId:'revision:2',digest:'b'.repeat(64)},original.members[3]]);
});


test('historical employee edit resumes authoritative draft and refresh keeps its identity',async({page})=>{
 const {original,extra}=await fixture(page);
 original.publicationState='PUBLISHED';original.lifecycleState='PUBLISHED';original.aggregateVersion=2;
 const draft={...structuredClone(original),employeeDefinitionRevisionId:'revision:aaa-current-draft',employeeDefinitionDigest:'8'.repeat(64),publicationState:'NOT_PUBLISHED' as const,lifecycleState:'VALIDATED' as const,responsibilities:['当前草稿职责']};
 extra.records.set(draft.employeeDefinitionRevisionId,draft);
 await page.goto(href().replace('employeeView=professional&','').replace('section=overview','section=capabilities'));
 await expect(page.getByRole('region',{name:'当前发布与修改草稿'}).getByText('修改草稿：已有草稿',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'修改职责与资源',exact:true}).click();
 await expect(page.getByLabel('职能职责',{exact:true})).toHaveValue('当前草稿职责');
 expect(new URL(page.url()).searchParams.get('employeeDefinitionRevisionId')).toBe(draft.employeeDefinitionRevisionId);
 await page.reload();await expect(page.getByLabel('职能职责',{exact:true})).toHaveValue('当前草稿职责');await expect(page.locator('.employee-edit-basis')).toContainText('原先查看的历史版本保持不变');
 await page.getByRole('button',{name:'返回原查看版本',exact:true}).click();
 await expect.poll(()=>new URL(page.url()).searchParams.get('employeeDefinitionRevisionId')).toBe(old);
 await expect(page.getByRole('region',{name:'当前发布与修改草稿'}).getByText('修改草稿：已有草稿',{exact:true})).toBeVisible();
 expect(new URL(page.url()).searchParams.get('section')).toBe('capabilities');
 await expect(page.getByRole('button',{name:'职责与资源',exact:true})).toHaveClass(/active/);
 expect(extra.posts).toHaveLength(0);
});

for(const mode of ['denied','wrong-parent','withdrawn'])test('authoring '+mode+' cannot silently choose a historical publication',async({page})=>{
 const {extra,original}=await fixture(page);
 original.publicationState='PUBLISHED';original.lifecycleState='PUBLISHED';
 await page.route('**/authoring',async route=>{
  const target={status:'AVAILABLE',definition:original};
  return route.fulfill({json:envelope({basis:'OWNER_FACT_ORDER',parent:{...original,...(mode==='wrong-parent'?{employeeDefinitionDigest:'0'.repeat(64)}:{})},aggregateVersion:1,head:mode==='denied'?{status:'NOT_AVAILABLE'}:target,draft:{status:'NONE'},publication:{status:mode==='withdrawn'?'WITHDRAWN':'NOT_AVAILABLE'},executionStarted:false})});
 });
 await page.goto(href().replace('employeeView=professional&','')+'&employeeEdit=edit');
 if(mode==='withdrawn')await expect(page.getByText('当前发布：已撤销',{exact:true})).toBeVisible();
 else {await expect(page.getByRole('button',{name:'修改职责与资源',exact:true})).toBeDisabled();await expect(page.getByLabel('职能职责',{exact:true})).toHaveCount(0)}
 expect(extra.posts).toHaveLength(0);
});


for(const mode of ['ready','denied','wrong-parent','partial','origin'])test('business work records '+mode+' use saved exact participation directly',async({page},info)=>{
 const {original,extra}=await fixture(page);let reads=0;await page.setViewportSize({width:1406,height:818});
 await page.route('**/work-records',async route=>{
  reads++;if(mode==='denied')return route.fulfill({status:403,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
  return route.fulfill({json:envelope({schemaVersion:'employee-work-records.v1',subject:principal.principalId,scope:{tenantId:principal.tenantId,securityDomain:principal.securityDomain},employeeDefinition:{...original,...(mode==='wrong-parent'?{employeeDefinitionRevisionId:'revision:other'}:{})},items:[{executionDigest:'6'.repeat(64),...(mode==='origin'?{originConversationId:'original-document-chat',originVerified:true}:{}),participation:'COORDINATION',title:'平台交接文档缺口核对',planVersion:2,state:'SUCCEEDED',tasks:[{taskId:'review',title:'核对缺失章节'}]}],scanLimited:mode==='partial',visibility:'AUTHORIZED_ONLY',executionStarted:false})});
 });
 await page.goto(href().replace('employeeView=professional&',''));
 expect(reads).toBe(0);
 await page.getByRole('button',{name:'工作记录',exact:true}).click();
 const records=page.getByRole('region',{name:'员工工作记录',exact:true});
 if(mode==='denied'||mode==='wrong-parent'){await expect(records.getByRole('alert')).toBeVisible();await expect(records.getByRole('link',{name:'查看任务',exact:true})).toHaveCount(0)}
 else {await expect(records.getByText('平台交接文档缺口核对',{exact:true})).toBeVisible();await expect(page.locator('.skill-frame-navigation').getByRole('link',{name:process.env.VITE_TEAM_DEFINITIONS_ENABLED==='true'?'数字人团队':'数字员工',exact:true})).toHaveAttribute('aria-current','page');const firstRow=await records.locator('tbody tr').first().boundingBox();expect(firstRow!.y).toBeLessThan(760);await expect(page.locator('.employee-composition-summary').getByRole('region',{name:'当前发布与修改草稿'})).toBeVisible();await expect(records.getByRole('link',{name:'查看任务',exact:true})).toHaveAttribute('href','/tasks?work='+'6'.repeat(64)+(mode==='origin'?'&origin=original-document-chat':'')+'&workView=result');if(mode==='partial')await expect(records.getByText('本次达到核对上限，列表可能不完整。',{exact:true})).toBeVisible();await page.reload();await expect(records.getByText('核对缺失章节',{exact:true})).toBeVisible();await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.screenshot({path:info.outputPath('employee-work-records-'+mode+'.png')});await page.evaluate(()=>window.dispatchEvent(new Event('workbench-session-expired')));await expect(page.getByText('平台交接文档缺口核对',{exact:true})).toHaveCount(0)}
 expect(extra.posts).toHaveLength(0);
});


test('work return restores exact employee tab scroll and focus after authorized read',async({page})=>{
 const {original,extra}=await fixture(page);
 await page.setViewportSize({width:1406,height:818});
 await page.route('**/work-records',route=>route.fulfill({json:envelope({schemaVersion:'employee-work-records.v1',subject:principal.principalId,scope:{tenantId:principal.tenantId,securityDomain:principal.securityDomain},employeeDefinition:original,items:Array.from({length:12},(_,i)=>({executionDigest:i.toString(16).padStart(64,'0'),participation:'TASK_EXECUTION',title:'已有任务 '+i,planVersion:1,state:'SUCCEEDED',tasks:[{taskId:'read',title:'核对已有资料'}]})),scanLimited:false,visibility:'AUTHORIZED_ONLY',executionStarted:false})}));
 await page.goto(href().replace('employeeView=professional&',''));
 await page.getByRole('button',{name:'工作记录',exact:true}).click();
 const link=page.getByRole('region',{name:'员工工作记录'}).getByRole('link',{name:'查看任务',exact:true}).nth(7);
 await link.scrollIntoViewIfNeeded();const originalUrl=page.url();const top=await page.locator('.employee-detail-body').evaluate(n=>n.scrollTop);expect(top).toBeGreaterThan(100);
 await link.click();await expect(page).toHaveURL(/\/tasks\?work=/);
 await page.goBack();await expect(page).toHaveURL(originalUrl);await expect(link).toBeFocused();
 await expect.poll(()=>page.locator('.employee-detail-body').evaluate(n=>n.scrollTop)).toBe(top);
 await expect(page.getByRole('button',{name:'工作记录',exact:true})).toHaveClass(/active/);
 expect(extra.posts).toHaveLength(0);
});


test('explicit duty resource association survives save and reload without publishing or executing',async({page})=>{
 const {extra,original}=await fixture(page);await page.goto(href().replace('employeeView=professional&',''));
 await page.getByRole('button',{name:'修改职责与资源',exact:true}).click();
 const mapping=page.getByRole('group',{name:'设置职责与资源关联',exact:true});
 await mapping.locator('summary').filter({hasText:'维护旧修订'}).click();
 await mapping.getByRole('checkbox',{name:'维护旧修订：关联资源 2',exact:true}).check();
 await page.getByRole('button',{name:'核对修改',exact:true}).click();
 await expect(page.getByText('本次保存 1 项职责资源关联。',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'保存修改草稿',exact:true}).click();
 await expect.poll(()=>extra.posts.length).toBe(1);const command=extra.posts[0].body as EmployeeCreateCommand;
 expect(command.responsibilityBindings).toEqual([{responsibility:'维护旧修订',member:original.members[2]}]);
 await expect.poll(()=>new URL(page.url()).searchParams.get('employeeDefinitionRevisionId')).toBe(command.employeeDefinitionRevisionId);
 await page.getByRole('navigation',{name:'选中员工详情分类'}).getByRole('button',{name:'职责与资源',exact:true}).click();await page.reload();
 await expect(page.getByRole('region',{name:'职责与资源关联',exact:true}).getByRole('article',{name:'技能绑定资源',exact:true})).toHaveCount(1);
 expect(extra.posts).toHaveLength(1);expect(original.responsibilityBindings).toBeUndefined();expect(original.employeeDefinitionRevisionId).toBe(old);
});

test('editing a mapped duty requires explicit stale association removal before saving',async({page})=>{
 const {extra,original}=await fixture(page);original.responsibilityBindings=[{responsibility:original.responsibilities[0],member:original.members[2]}];
 await page.goto(href().replace('employeeView=professional&',''));await page.getByRole('button',{name:'修改职责与资源',exact:true}).click();
 await page.getByLabel('职能职责',{exact:true}).fill('新的职责');await page.getByRole('button',{name:'核对修改',exact:true}).click();
 await expect(page.getByText('请先处理职责与资源的失效关联。',{exact:true})).toBeVisible();expect(extra.posts).toHaveLength(0);
 await page.getByRole('button',{name:'移除此失效关联',exact:true}).click();await page.getByRole('button',{name:'核对修改',exact:true}).click();
 await expect(page.getByRole('button',{name:'保存修改草稿',exact:true})).toBeVisible();expect(extra.posts).toHaveLength(0);
});

test('business collection preserves filters and scroll through exact employee detail',async({page})=>{
 const {extra,original}=await fixture(page);
 extra.records.clear();
 for(let i=0;i<18;i++)extra.records.set('employee-revision:list-'+i,{...structuredClone(original),employeeDefinitionId:'employee:list-'+i,employeeDefinitionRevisionId:'employee-revision:list-'+i,role:'检查员 '+i});
 await page.goto('/employees');
 await expect(page.locator('.employee-collection-row')).toHaveCount(18);
 await expect(page.getByRole('region',{name:'选中员工详情',exact:true})).toBeHidden();
 await page.getByLabel('搜索当前结果',{exact:true}).fill('检查员');
 await page.getByRole('combobox',{name:'发布状态',exact:true}).selectOption('NOT_PUBLISHED');
 const row=page.locator('.employee-row-main').filter({hasText:'检查员 16'});
 await row.scrollIntoViewIfNeeded();
 const position=await page.locator('.employee-collection-rows').evaluate(n=>n.scrollTop);
 expect(position).toBeGreaterThan(0);
 await row.click();
 await expect(page.locator('.employee-detail-context h2')).toHaveText('检查员 16');
 expect(new URL(page.url()).searchParams.get('employeeDefinitionRevisionId')).toBe('employee-revision:list-16');
 await page.getByRole('button',{name:'← 返回员工集合',exact:true}).click();
 await expect(page.getByLabel('搜索当前结果',{exact:true})).toHaveValue('检查员');
 await expect(page.getByRole('combobox',{name:'发布状态',exact:true})).toHaveValue('NOT_PUBLISHED');
 await expect.poll(()=>page.locator('.employee-collection-rows').evaluate(n=>n.scrollTop)).toBe(position);
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
 expect(extra.posts).toHaveLength(0);
});

for(const mode of ['current','historical','unavailable','withdrawn','digest-mismatch'] as const)test('selected publication label remains evidence based: '+mode,async({page})=>{
 const {extra,original}=await fixture(page);original.publicationState='PUBLISHED';original.lifecycleState='PUBLISHED';
 const current={...structuredClone(original),employeeDefinitionRevisionId:mode==='historical'?'employee-revision:current':old,employeeDefinitionDigest:mode==='historical'||mode==='digest-mismatch'?'f'.repeat(64):original.employeeDefinitionDigest};
 await page.route('**/authoring',route=>route.fulfill({json:envelope({basis:'OWNER_FACT_ORDER',parent:original,aggregateVersion:1,head:{status:'AVAILABLE',definition:current},draft:{status:'NONE'},publication:mode==='unavailable'?{status:'NOT_AVAILABLE'}:mode==='withdrawn'?{status:'WITHDRAWN'}:{status:'AVAILABLE',definition:current},executionStarted:false})}));
 await page.goto(href().replace('employeeView=professional&',''));
 const label={current:'当前发布版本',historical:'历史发布版本',unavailable:'已发布记录 · 当前版本待核实',withdrawn:'已发布记录 · 当前发布已撤销','digest-mismatch':'已发布记录 · 当前状态暂不可核实'}[mode];
 await expect(page.locator('.employee-detail-context .employee-state-chip')).toHaveText(label);
 await expect(page.locator('.employee-composition-summary h3')).toHaveText(label);
 expect(new URL(page.url()).searchParams.get('employeeDefinitionRevisionId')).toBe(old);
 if(mode==='historical')await expect(page.getByText('当前发布：另有发布版本',{exact:true})).toBeVisible();
 await expect(page.locator('.employee-detail-context h2')).toHaveCSS('font-size','28px');
 await expect(page.getByRole('button',{name:'资源组成',exact:true})).toHaveCSS('font-size','15px');
 expect(extra.posts).toHaveLength(0);
});

test('collection separates authoritative publication and draft from listed history',async({page})=>{
 const {extra,original}=await fixture(page);original.publicationState='PUBLISHED';original.lifecycleState='PUBLISHED';
 const current={...structuredClone(original),employeeDefinitionRevisionId:'employee-revision:published',employeeDefinitionDigest:'f'.repeat(64),responsibilities:['当前发布职责'],aggregateVersion:2};
 const draft={...structuredClone(original),employeeDefinitionRevisionId:'employee-revision:draft',employeeDefinitionDigest:'a'.repeat(64),publicationState:'NOT_PUBLISHED' as const,lifecycleState:'DRAFT' as const,responsibilities:['新草稿职责'],aggregateVersion:3};
 extra.records.set(current.employeeDefinitionRevisionId,current);extra.records.set(draft.employeeDefinitionRevisionId,draft);
 await page.goto('/employees');const card=page.locator('.employee-version-card');await expect(card).toHaveCount(1);
 await expect(card.getByText('当前发布职责',{exact:true})).toBeVisible();await expect(card.getByText('新草稿职责',{exact:true})).toBeVisible();
 await card.getByRole('button',{name:'查看当前发布',exact:true}).click();await expect(page.locator('.employee-detail-context .employee-state-chip')).toHaveText('当前发布版本');expect(new URL(page.url()).searchParams.get('employeeDefinitionRevisionId')).toBe(current.employeeDefinitionRevisionId);
 await page.getByRole('button',{name:'← 返回员工集合',exact:true}).click();await card.getByRole('button',{name:'查看修改草稿',exact:true}).click();await expect(page.locator('.employee-detail-context .employee-state-chip')).toHaveText('修改草稿 · 待验证');
 await page.getByRole('button',{name:'← 返回员工集合',exact:true}).click();await card.locator('summary').click();await card.getByRole('combobox').selectOption(old);await expect(page.locator('.employee-detail-context .employee-state-chip')).toHaveText('历史发布版本');expect(new URL(page.url()).searchParams.get('employeeDefinitionRevisionId')).toBe(old);expect(extra.posts).toHaveLength(0);
});

for(const mode of ['unavailable','withdrawn','wrong-parent','identity-change'] as const)test('collection never invents current versions: '+mode,async({page})=>{
 const {state,extra,original}=await fixture(page);
 await page.route('**/authoring',async route=>{
  if(mode==='identity-change')state.otherIdentity=true;
  return route.fulfill({json:envelope({basis:'OWNER_FACT_ORDER',parent:{...original,...(mode==='wrong-parent'?{employeeDefinitionDigest:'0'.repeat(64)}:{})},aggregateVersion:1,head:{status:'NOT_AVAILABLE'},publication:{status:mode==='withdrawn'?'WITHDRAWN':'NOT_AVAILABLE'},draft:{status:'NOT_AVAILABLE'},executionStarted:false})});
 });
 await page.goto('/employees');const card=page.locator('.employee-version-card');await expect(card.getByText(mode==='withdrawn'?'当前发布已撤销':'当前发布暂未核实',{exact:true})).toBeVisible();await expect(card.getByText('修改草稿暂未核实',{exact:true})).toBeVisible();await expect(card.getByRole('button',{name:'查看当前发布',exact:true})).toHaveCount(0);await expect(card.getByRole('button',{name:'查看修改草稿',exact:true})).toHaveCount(0);expect(extra.posts).toHaveLength(0);
});

for(const mode of ['published','validated'] as const)test('fresh authoring lifecycle overrides stale selected metadata: '+mode,async({page})=>{
 const {extra,original}=await fixture(page);const fresh={...structuredClone(original),publicationState:mode==='published'?'PUBLISHED':'NOT_PUBLISHED',lifecycleState:mode==='published'?'PUBLISHED':'VALIDATED'};
 await page.route('**/authoring',route=>route.fulfill({json:envelope({basis:'OWNER_FACT_ORDER',parent:original,aggregateVersion:1,head:{status:'AVAILABLE',definition:fresh},publication:mode==='published'?{status:'AVAILABLE',definition:fresh}:{status:'NOT_AVAILABLE'},draft:mode==='validated'?{status:'AVAILABLE',definition:fresh}:{status:'NONE'},executionStarted:false})}));
 await page.goto(href().replace('employeeView=professional&','')+'&employeeEdit=review');await expect(page.locator('.employee-detail-context .employee-state-chip')).toHaveText(mode==='published'?'当前发布版本':'修改草稿 · 已验证');if(mode==='published')await expect(page.getByRole('button',{name:/^验证草稿/})).toHaveCount(0);expect(new URL(page.url()).searchParams.get('employeeDefinitionRevisionId')).toBe(old);expect(extra.posts).toHaveLength(0);
});

test('collection bounds version reads and does not repeat them for local filters',async({page})=>{
 const {extra,original}=await fixture(page);extra.records.clear();for(let i=0;i<7;i++)extra.records.set('revision:'+i,{...structuredClone(original),employeeDefinitionId:'employee:'+i,employeeDefinitionRevisionId:'revision:'+i,role:'核验员 '+i});
 let active=0,maximum=0,calls=0;
 await page.route('**/authoring',async route=>{calls++;active++;maximum=Math.max(maximum,active);const revision=decodeURIComponent(new URL(route.request().url()).pathname).split('/revisions/')[1].split('/')[0],item=extra.records.get(revision)!;await new Promise(resolve=>setTimeout(resolve,30));active--;return route.fulfill({json:envelope({basis:'OWNER_FACT_ORDER',parent:item,aggregateVersion:1,head:{status:'AVAILABLE',definition:item},publication:{status:'NOT_AVAILABLE'},draft:{status:'AVAILABLE',definition:item},executionStarted:false})})});
 await page.goto('/employees');await expect(page.locator('.employee-version-card').getByRole('button',{name:'查看修改草稿',exact:true})).toHaveCount(7);expect(calls).toBe(7);expect(maximum).toBeLessThanOrEqual(3);
 await page.getByLabel('搜索当前结果',{exact:true}).fill('核验员 1');await expect(page.locator('.employee-version-card')).toHaveCount(1);expect(calls).toBe(7);expect(extra.posts).toHaveLength(0);
});

for(const mode of ['immediate','expanded-refresh','identity-change'])test('bound resource return restores scoped position '+mode,async({page})=>{
 const {original,extra,state}=await fixture(page);original.responsibilities=Array.from({length:20},(_,i)=>'核对第 '+(i+1)+' 项已保存资料与来源。');
 original.members=original.members.filter(m=>m.kind!=='MCP');const skill=original.members.find(m=>m.kind==='SKILL')!;skill.revisionId='revision:2';skill.digest='b'.repeat(64);
 await page.setViewportSize({width:1406,height:550});await page.goto(href().replace('employeeView=professional&',''));
 const card=page.locator('.employee-resource-card').filter({has:page.locator('a[href*="kind=skill"]')}),link=card.getByRole('link',{name:'查看详情',exact:true});if(mode==='expanded-refresh')await card.locator('summary').click();await link.scrollIntoViewIfNeeded();
 await expect.poll(()=>page.evaluate(()=>document.querySelector('.employee-detail-body')!.scrollTop)).toBeGreaterThan(0);
 const before=await page.locator('.employee-detail-body').evaluate(n=>n.scrollTop);await link.click();await page.getByRole('link',{name:'返回引用员工',exact:true}).waitFor();if(mode==='expanded-refresh')await page.reload();if(mode==='identity-change')state.otherIdentity=true;await page.getByRole('link',{name:'返回引用员工',exact:true}).click();
 await expect(page.getByRole('button',{name:'资源组成',exact:true})).toHaveClass(/active/);
 if(mode==='identity-change'){await expect(link).not.toBeFocused();await expect.poll(()=>page.locator('.employee-detail-body').evaluate(n=>n.scrollTop)).toBe(0)}else{await expect.poll(()=>page.locator('.employee-detail-body').evaluate(n=>n.scrollTop)).toBeCloseTo(before,0);await expect(link).toBeFocused();if(mode==='expanded-refresh')await expect(card.locator('details')).toHaveAttribute('open','')}expect(extra.posts).toHaveLength(0);
});
