import {expect,test} from '@playwright/test';
import {readFileSync} from 'node:fs';
import type {ExecutionView} from '../../src/api/preparedExecution';
const original=JSON.parse(readFileSync(new URL('./fixtures/cost323.json',import.meta.url),'utf8'));
const ref={resource_id:'fixture-resource',revision_id:'fixture-revision',digest:'a'.repeat(64)};
const problem={scope:{namespace:'fixture-324',security_domain:'isolated'},business_problem_id:'fixture-problem',revision_id:'fixture-revision',revision:1,predecessor_revision_id:null,title:'隔离合成成本案例（视图测试）',description:'仅用于页面行为验证，不代表实际执行。',owner_id:'human:fixture',created_by:'human:fixture',created_at:'2026-09-21T00:00:00Z',digest:'b'.repeat(64)};
function view():ExecutionView{return {digest:'c'.repeat(64),executionStarted:false,preparation:{plan_id:'fixture-plan',plan_version:3,plan_digest:'d'.repeat(64),approval_id:'fixture-approval',source_snapshot:ref,semantics:{...original.semantics,title:problem.title,target:{problem:{...ref,resource_id:problem.business_problem_id}}},participants:original.semantics.tasks.map((t:{task_id:string;operation:string})=>({task_id:t.task_id,instance_id:'fixture-instance',assignment_id:`fixture-assignment-${t.task_id}`,definition:ref,skill:{reference:ref,operation:t.operation},profile:ref}))},progress:null,admission:{state:'NOT_ADMITTED',reason:'AUTHORIZATION_NOT_FOUND'},resourceUses:[],artifacts:[],events:[],outcome:null}}

test('324 real-data panel separates binding from admission and reload sends no mutation',async({page},info)=>{
 let writes=0;const state=view();
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;if(route.request().method()!=='GET')writes++;
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:fixture',tenantId:'fixture-324',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  const result=path.includes('/prepared-executions/')?state:path.endsWith('/criteria')||path.endsWith('/criteria-sets')?{revisions:[]}:path.endsWith('/problems')?{problems:[problem]}:{problem:{...problem,current_state:'ACTIVE',aggregate_version:1,current_revision_id:problem.revision_id},revisions:[problem],lifecycle:[]};
  return route.fulfill({json:{result}});
 });
 await page.setViewportSize({width:1536,height:1024});await page.goto(`/work?problem=${problem.business_problem_id}&execution=${state.digest}`);
 const panel=page.getByRole('region',{name:'Native 执行与成果验收'});await expect(panel).toBeAttached();await expect(panel.getByRole('button',{name:'启动本次只读执行'})).toBeDisabled();await expect(panel).toContainText('资源已绑定');await expect(panel).toContainText('待独立准入');
 await panel.scrollIntoViewIfNeeded();await page.screenshot({path:info.outputPath('H05-P08-prepared-not-admitted.png')});
 for(const scale of [1,1.25]){await page.setViewportSize({width:Math.floor(1536/scale),height:Math.floor(1024/scale)});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();const send=page.locator('.px-composer button[type="submit"]');await expect(send).toBeInViewport()}
 await page.reload();await expect(panel).toBeAttached();expect(writes).toBe(0);
 state.executionStarted=true;state.admission.state='ADMITTED';state.progress={state:'SUCCEEDED',version:18,cancellation_request_id:null,tasks:state.preparation.semantics.tasks.map(t=>({task_id:t.task_id,state:'SUCCEEDED',attempt_ordinal:1,reason:null}))};state.outcome={outcomeId:'fixture-outcome',version:1,evaluationDigest:'e'.repeat(64),businessResolution:'UNDETERMINED',confirmationId:null,evaluation:{evaluationId:'fixture-evaluation',results:[{criterionRevisionId:'fixture-criterion',criterionDigest:'f'.repeat(64),result:'UNKNOWN',reason:'HUMAN_REVIEW_REQUIRED',artifactIds:['fixture-artifact']}]}};state.artifacts=[{artifact_id:'fixture-artifact',task_id:'t6-report',digest:'1'.repeat(64),bytes:500,created_at:'2026-09-21T01:00:00Z',contentAccess:'AUTHORIZED',content:'明确标注的合成页面产物，不是实际执行证据。'.repeat(20)}];
 await panel.getByRole('button',{name:'刷新正式状态'}).click();await expect(panel).toContainText('业务结果：尚无法确定');await expect(panel.getByRole('button',{name:'确认限制与待解决事项'})).toBeDisabled();await panel.getByRole('textbox',{name:'验收意见'}).fill('视图测试意见');await expect(panel.getByRole('button',{name:'确认限制与待解决事项'})).toBeEnabled();expect(writes).toBe(0);await panel.getByRole('heading',{name:'标准评价与人工决定'}).scrollIntoViewIfNeeded();await page.screenshot({path:info.outputPath('H06-undetermined-fixture.png')});
});

test('324 resource review preserves partial publication and reload never repeats Human commands',async({page},info)=>{
 let writes=0;const resources=['skill','runtime','knowledge','agent'].map(kind=>({kind,identity:`fixture-${kind}`,name:`隔离合成${kind}（视图测试）`,aggregateVersion:1,revision:{revisionId:'fixture-revision',digest:(kind==='runtime'?'sha256:':'')+'a'.repeat(64),state:'DRAFT',content:{synthetic:true,description:'仅用于页面交互验证，不是正式资源发布。',operations:[{name:'fixture-read',sideEffectClass:'READ_ONLY',inputSchema:{type:'object',required:['source'],properties:{source:{type:'string',description:'精确合成来源，保留长中文说明。'.repeat(8)}}},outputSchema:{type:'object',properties:{result:{type:'string'}}}}]}},publishedRevisionId:null as string|null}));
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:fixture',tenantId:'fixture-324',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(path.includes('/prepared-resources/')){const resource=resources.find(r=>path.includes('/'+r.kind+'/'))!;if(route.request().method()==='POST'){writes++;if(resource.kind==='runtime')return route.fulfill({status:409,json:{reasonCode:'FIXTURE_PUBLICATION_CONFLICT'}});resource.publishedRevisionId=resource.revision.revisionId;resource.revision.state='PUBLISHED';resource.aggregateVersion=4;return route.fulfill({json:{result:{state:'PUBLISHED'}}})}return route.fulfill({json:{result:resource}})}
  const result=path.endsWith('/criteria')||path.endsWith('/criteria-sets')?{revisions:[]}:path.endsWith('/problems')?{problems:[problem]}:{problem:{...problem,current_state:'ACTIVE',aggregate_version:1,current_revision_id:problem.revision_id},revisions:[problem],lifecycle:[]};return route.fulfill({json:{result}});
 });
 const query=new URLSearchParams({problem:problem.business_problem_id});resources.forEach(r=>query.append('resource',[r.kind,r.identity,r.revision.revisionId].join('|')));
 await page.setViewportSize({width:1536,height:1024});await page.goto('/work?'+query.toString());const panel=page.getByRole('region',{name:'本次执行必要资源审核'});
 await expect(panel.getByRole('button',{name:'审核并发布待处理的 4 项资源'})).toBeDisabled();await panel.getByRole('textbox').fill('视图测试：已核对合成范围和精确修订');await panel.getByRole('checkbox').check();await panel.getByRole('button',{name:'审核并发布待处理的 4 项资源'}).click();await expect(panel.getByRole('alert')).toContainText('已保存记录保留');await expect(panel.getByRole('button',{name:'审核并发布待处理的 3 项资源'})).toBeVisible();expect(writes).toBe(2);await page.reload();await expect(panel).toContainText('已发布');expect(writes).toBe(2);await panel.scrollIntoViewIfNeeded();await panel.locator('.prepared-resource-card').first().locator('summary').first().click();await panel.getByText('fixture-read · 只读',{exact:true}).click();await expect(panel.getByRole('region',{name:'操作输入字段'})).toContainText('精确合成来源');await page.screenshot({path:info.outputPath('S04-R04-K05-D09-resource-review.png')});for(const scale of [1,1.25]){await page.setViewportSize({width:Math.floor(1536/scale),height:Math.floor(1024/scale)});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await expect(page.locator('.px-composer button[type="submit"]')).toBeInViewport();await panel.getByRole('region',{name:'操作输入字段'}).scrollIntoViewIfNeeded();await page.screenshot({path:info.outputPath(`resource-long-zh-${scale}.png`)})};expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await expect(page.locator('.px-composer button[type="submit"]')).toBeInViewport();
});

test('324 expired session preserves exact return object and re-entry never replays business writes',async({page})=>{
 let expired=false,writes=0;
 const state=view();
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(route.request().method()!=='GET')writes++;
  if(path.endsWith('/session'))return route.fulfill(expired?{status:401,json:{reasonCode:'AUTHENTICATION_REQUIRED'}}:{json:{principal:{principalId:'human:fixture',tenantId:'fixture-324',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  const result=path.includes('/prepared-executions/')?state:path.endsWith('/criteria')||path.endsWith('/criteria-sets')?{revisions:[]}:path.endsWith('/problems')?{problems:[problem]}:{problem:{...problem,current_state:'ACTIVE',aggregate_version:1,current_revision_id:problem.revision_id},revisions:[problem],lifecycle:[]};
  return route.fulfill({json:{result}});
 });
 const originalUrl=`/work?problem=${problem.business_problem_id}&execution=${state.digest}`;
 await page.goto(originalUrl);
 await expect(page.getByRole('region',{name:'Native 执行与成果验收'})).toBeAttached();
 await page.locator('#problem-composer').fill('尚未发送的中文补充，不得重新登录后自动提交。');
 expired=true;
 await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
 const login=page.getByRole('link',{name:'重新登录并读回'});
 await expect(login).toBeVisible();
 await expect(login).toHaveAttribute('href',`/api/workbench/v1/login?returnTo=${encodeURIComponent(originalUrl)}`);
 await expect(page.locator('#problem-composer')).toHaveCount(0);
 expect(new URL(page.url()).search).toBe(new URL(originalUrl,'http://fixture').search);
 // Simulate the successful server login redirect; this is UI behavior, not authentication proof.
 expired=false;
 await page.goto(originalUrl);
 await expect(page.getByRole('region',{name:'Native 执行与成果验收'})).toBeAttached();
 await expect(page.locator('#problem-composer')).toHaveValue('');
 expect(writes).toBe(0);
});
