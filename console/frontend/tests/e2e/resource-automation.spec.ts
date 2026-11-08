import {expect,test,type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
const semantics=JSON.parse(readFileSync(new URL('./fixtures/source-change-plan.json',import.meta.url),'utf8'));
const id='automatic-resource-case',digest='b'.repeat(64),subject='human:resource-fixture';
const principal={principalId:subject,tenantId:'resource-fixture',securityDomain:'isolated'};
async function setup(page:Page,mode:'ready'|'lost'|'partial'|'denied'|'identity'='ready',linked?:string){
 let stored:Record<string,unknown>|null=null,posts=0,gets=0,sessionReads=0;const keys:string[]=[];const paths:string[]=[];
 const record=(key:string)=>({schemaVersion:'resource-preparation.v1',requestKey:key,planId:id,planVersion:2,planDigest:digest,subject,state:mode==='partial'?'PARTIALLY_READY':'READY',policy:{id:'isolated-policy',version:'1',digest:'d'.repeat(64),actor:'service:resource-preparation-policy'},resources:['agent','knowledge','runtime','skill'].map(kind=>({kind,reference:{resource_id:'fixture-'+kind,revision_id:'1',digest:'a'.repeat(64)},name:'隔离资源 '+kind,state:mode==='partial'&&kind==='skill'?'BLOCKED':'READY',case:'NEW',reason:kind==='skill'&&mode==='partial'?'RESOURCE_EXECUTOR_SCHEMA_MISMATCH':undefined,decisionId:'isolated-policy-decision',checks:[],publication:null})),assembly:{state:mode==='partial'?'BLOCKED':'ASSEMBLED',definition:{resource_id:'fixture-employee',revision_id:'1',digest:'c'.repeat(64)},reused:false},executionStarted:false,createdAt:'2026-11-04T06:00:00Z',nextStep:'EXISTING_EXECUTION_ADMISSION',resourceSnapshot:{proposal_digest:digest,checked_at:'2026-11-04T06:00:00Z',observations:semantics.requirements.map((r:{requirement_id:string})=>({requirement_id:r.requirement_id,status:mode==='partial'?'UNAVAILABLE':'MATCHED',reason:'ISOLATED_OWNER_STATE'}))}});
 await page.route('**/api/workbench/v1/**',async route=>{
  const req=route.request(),url=new URL(req.url()),path=url.pathname;
  if(req.method()!=='GET')paths.push(path);
  if(path.endsWith('/session')){sessionReads++;return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:mode==='identity'&&stored&&sessionReads>2?{...principal,securityDomain:'other-domain'}:principal,session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}})}
  if(path.endsWith('/resource-preparation')){
   if(req.method()==='POST'){posts++;const body=req.postDataJSON();expect(Object.keys(body).sort()).toEqual(['idempotencyKey','version']);keys.push(body.idempotencyKey);stored=record(body.idempotencyKey);if(mode==='lost')return route.fulfill({status:503,json:{reasonCode:'RESPONSE_LOST_AFTER_FIXTURE_COMMIT'}})}else gets++;
   if(mode==='denied')return route.fulfill({status:403,json:{reasonCode:'RESOURCE_PERMISSION_REVOKED'}});
   return route.fulfill(stored?{json:{result:stored}}:{status:404,json:{reasonCode:'RESOURCE_PREPARATION_NOT_FOUND'}});
  }
  if(path.endsWith('/history'))return route.fulfill({json:{result:{resourceAutomation:{enabled:true,policyVersion:'1'},proposals:[{proposal_id:id,revision:2,semantics}],plans:[{plan:{plan_id:id,version:2,source_proposal_revision:2,semantics},digest,approval:{approval_decision_id:'fixture-approval',decided_at:'2026-11-04T05:00:00Z'},execution_summary:{state:'NOT_STARTED',basis:'ISOLATED_FIXTURE'}}]}}});
  if(path===`/api/workbench/v1/planning-v2/${id}`)return route.fulfill({json:{result:{proposal:{proposal_id:id,revision:2,semantics},digest,snapshot:null,validation:{status:'DECLARED_CONTRACT_VALID'}}}});
  return route.fulfill({status:404,json:{reasonCode:'UNEXPECTED_FIXTURE_ROUTE'}});
 });
 await page.goto(`/work/planning/${id}?revision=2${linked?'&resourcePreparation='+encodeURIComponent(linked):''}`);
 if(!linked)await page.getByRole('button',{name:'按当前计划继续办理',exact:true}).click();
 return {get posts(){return posts},get gets(){return gets},keys,paths};
}

test('D11 prepares automatically, shows key resource states inline and sends no approval or invocation command',async({page},info)=>{
 const state=await setup(page);const panel=page.getByRole('region',{name:'平台自动准备资源'});
 await expect(panel).toContainText('资源已备齐，角色装配完成');await expect(panel.getByRole('table',{name:'本次必要资源与核验结果'})).toBeVisible();await expect(panel.getByRole('row')).toHaveCount(5);expect(state.posts).toBe(1);expect(state.paths.every(p=>p.endsWith('/resource-preparation'))).toBe(true);
 await page.setViewportSize({width:1536,height:1056});await panel.scrollIntoViewIfNeeded();await page.screenshot({path:info.outputPath('P08-P10-automatic-preparation-1536.png')});
 await page.reload();await expect(panel).toContainText('角色装配完成');expect(state.posts).toBe(1);
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:info.outputPath('P08-P10-automatic-preparation-390.png')});
});

test('D11 response loss recovers original receipt without repeated publication or manual refresh',async({page})=>{
 const state=await setup(page,'lost');await expect(page.getByRole('region',{name:'平台自动准备资源'})).toContainText('角色装配完成',{timeout:12000});expect(state.posts).toBe(1);expect(state.gets).toBeGreaterThan(0);await page.reload();await expect(page.getByRole('region',{name:'平台自动准备资源'})).toContainText('角色装配完成');expect(state.posts).toBe(1);
});

test('D11 partial batch retains successful resources and exposes one grouped gap without approval controls',async({page})=>{
 const state=await setup(page,'partial');const panel=page.getByRole('region',{name:'平台自动准备资源'});await expect(panel).toContainText('部分资源已备齐');await expect(panel).toContainText('技能输入输出契约不匹配');await expect(panel.getByRole('button',{name:'重新核对已知缺口',exact:true})).toBeVisible();expect(state.posts).toBe(1);
});

test('D11 denied preparation never exposes success and stops original receipt polling',async({page})=>{
 const state=await setup(page,'denied');const panel=page.getByRole('region',{name:'平台自动准备资源'});await expect(panel.getByRole('alert')).toBeVisible();await page.waitForTimeout(3000);const reads=state.gets;await page.waitForTimeout(3000);expect(state.gets).toBe(reads);await expect(panel.getByRole('table')).toHaveCount(0);expect(state.posts).toBe(1);
});

test('D11 account scope change withdraws a late preparation receipt',async({page})=>{
 await setup(page,'identity');const panel=page.getByRole('region',{name:'平台自动准备资源'});await expect(panel.getByRole('alert')).toBeVisible();await expect(panel.getByRole('table')).toHaveCount(0);
});


test('known gaps use one fresh verification key and linked history never creates absent work',async({page})=>{
 const state=await setup(page,'partial');const panel=page.getByRole('region',{name:'平台自动准备资源'});await expect(panel).toContainText('部分资源已备齐');const first=state.keys[0];await panel.getByRole('button',{name:'重新核对已知缺口',exact:true}).click();await expect(panel).toContainText('部分资源已备齐');expect(state.posts).toBe(2);expect(state.keys[1]).not.toBe(first);expect(state.paths.every(p=>p.endsWith('/resource-preparation'))).toBe(true);await page.reload();await expect(panel).toContainText('部分资源已备齐');expect(state.posts).toBe(2);
});

test('a missing linked preparation is read only and cannot submit or execute',async({page})=>{
 const state=await setup(page,'ready','missing-record');await expect(page.getByRole('region',{name:'平台自动准备资源'}).getByRole('alert')).toBeVisible();expect(state.posts).toBe(0);expect(state.gets).toBeGreaterThan(0);expect(state.paths).toEqual([]);
});

for(const mode of ['ready','lost-selection','wrong-predecessor'] as const)test('all-selected Human supplement selects a policy preparation successor before preparing '+mode,async({page})=>{
 const oldSemantics=structuredClone(semantics);for(const [i,r]of oldSemantics.requirements.entries())r.selected??={resource_id:'selected-'+r.kind,revision_id:'revision-'+i,digest:'a'.repeat(64)};
 const employee=oldSemantics.requirements.find((r:{kind:string})=>r.kind==='EMPLOYEE').selected;
 const oldProposal={proposal_id:id,revision:5,semantics:oldSemantics,origin:{kind:'HUMAN_RESOURCE_SUPPLEMENT',predecessor_plan:{resource_id:id,revision_id:'4',digest:'4'.repeat(64)}}};
 const oldPlan={plan:{plan_id:id,version:5,source_proposal_revision:5,semantics:oldSemantics},digest,approval:{approval_decision_id:'human-supplement-confirmation',decided_at:'2026-11-08'},execution_summary:{state:'NOT_STARTED'}};
 const nextDigest='6'.repeat(64),nextSemantics={...structuredClone(oldSemantics),business_rules:[...oldSemantics.business_rules,'本轮只规划与确认，由原策略owner重新准备；旧执行映射保留在历史版本。']};
 const nextProposal={proposal_id:id,revision:6,semantics:nextSemantics,origin:{kind:'POLICY_RESOURCE_PREPARATION',predecessor_plan:{resource_id:id,revision_id:mode==='wrong-predecessor'?'3':'5',digest}}};
 const nextPlan={plan:{plan_id:id,version:6,source_proposal_revision:6,source_proposal_digest:nextDigest,semantics:nextSemantics},digest:nextDigest,approval:{approval_decision_id:'policy-preparation-confirmation',decided_at:'2026-11-08'},execution_summary:{state:'NOT_STARTED'}};
 const coverage={planId:id,planVersion:5,planDigest:digest,subject,scope:{tenantId:principal.tenantId,securityDomain:principal.securityDomain},state:'SELECTION_AVAILABLE',candidates:[],selection:employee};
 const selection={automaticCoverage:coverage,confirmation:nextPlan,proposal:nextProposal,digest:nextDigest,executionStarted:false};
 const state={selected:false,selectionPosts:0,selectionGets:0,preparationPosts:[] as Record<string,unknown>[],stored:null as Record<string,unknown>|null,otherWrites:[] as string[]};
 await page.route('**/api/workbench/v1/**',async route=>{
  const req=route.request(),u=new URL(req.url()),p=u.pathname;
  if(p.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal,session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(p.endsWith('/history'))return route.fulfill({json:{result:{resourceAutomation:{enabled:true,policyVersion:'current-owner'},proposals:state.selected?[oldProposal,nextProposal]:[oldProposal],plans:state.selected?[oldPlan,nextPlan]:[oldPlan]}}});
  if(p===`/api/workbench/v1/planning-v2/${id}`)return route.fulfill({json:{result:{proposal:state.selected?nextProposal:oldProposal,digest:state.selected?nextDigest:digest,snapshot:null}}});
  if(p.endsWith('/resource-coverage'))return route.fulfill({json:{result:coverage}});
  if(p.endsWith('/resource-selection/automatic')){
   if(req.method()==='GET'){state.selectionGets++;return state.selected?route.fulfill({json:{result:selection}}):route.fulfill({status:404,json:{reasonCode:'RESOURCE_SELECTION_NOT_FOUND'}})}
   state.selectionPosts++;expect(req.postDataJSON()).toMatchObject({version:5,digest,expectedProposalRevision:5});expect(req.headers()['x-csrf-token']).toBe('fixture');state.selected=true;return route.fulfill(mode==='lost-selection'?{status:503,json:{reasonCode:'LOST_AFTER_COMMIT'}}:{json:{result:selection}});
  }
  if(p.endsWith('/resource-preparation')){
   if(req.method()==='POST'){const b=req.postDataJSON();state.preparationPosts.push(b);expect(b.version).toBe(6);state.stored={schemaVersion:'resource-preparation.v1',requestKey:b.idempotencyKey,planId:id,planVersion:6,planDigest:nextDigest,subject,state:'READY',policy:{id:'same-current-owner',version:'1',digest:'d'.repeat(64),actor:'service:resource-preparation-policy'},resources:[],assembly:{state:'ASSEMBLED',definition:employee,reused:true},executionStarted:false,createdAt:'2026-11-08',nextStep:'EXISTING_EXECUTION_ADMISSION'};}
   return state.stored?route.fulfill({json:{result:state.stored}}):route.fulfill({status:404,json:{reasonCode:'RESOURCE_PREPARATION_NOT_FOUND'}});
  }
  if(req.method()!=='GET')state.otherWrites.push(p);
  return route.fulfill({status:404,json:{reasonCode:'UNEXPECTED_FIXTURE_READ'}});
 });
 await page.goto(`/work/planning/${id}?revision=5`);await page.getByRole('button',{name:'按当前计划继续办理',exact:true}).click();
 if(mode==='wrong-predecessor'){await expect(page.getByRole('region',{name:'平台自动选择能力'})).toContainText('RESOURCE_SELECTION_CONTEXT_MISMATCH');expect(state.preparationPosts).toEqual([]);expect(state.selectionPosts).toBe(1)}
 else{await expect(page).toHaveURL(/revision=6/,{timeout:15000});await expect(page.getByRole('region',{name:'平台自动准备资源'})).toContainText('资源已备齐，角色装配完成');expect(state.selectionPosts).toBe(1);expect(state.preparationPosts).toHaveLength(1);await page.reload();await expect(page.getByRole('region',{name:'平台自动准备资源'})).toContainText('角色装配完成');expect(state.selectionPosts).toBe(1);expect(state.preparationPosts).toHaveLength(1)}
 expect(state.otherWrites).toEqual([]);expect(oldProposal.origin.kind).toBe('HUMAN_RESOURCE_SUPPLEMENT');expect(oldProposal.revision).toBe(5);
});
