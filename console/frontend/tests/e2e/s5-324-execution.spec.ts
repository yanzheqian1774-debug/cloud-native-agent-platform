import {expect,test} from '@playwright/test';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import type {ExecutionView} from '../../src/api/preparedExecution';
const original=JSON.parse(readFileSync(new URL('./fixtures/delivery-plan.json',import.meta.url),'utf8'));
const ref={resource_id:'fixture-resource',revision_id:'fixture-revision',digest:'a'.repeat(64)};
const problem={scope:{namespace:'fixture-324',security_domain:'isolated'},business_problem_id:'fixture-problem',revision_id:'fixture-revision',revision:1,predecessor_revision_id:null,title:'隔离合成供应商交付案例（视图测试）',description:'仅用于页面行为验证，不代表实际执行。',owner_id:'human:fixture',created_by:'human:fixture',created_at:'2026-09-21T00:00:00Z',digest:'b'.repeat(64)};
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
 await panel.getByRole('button',{name:'刷新正式状态'}).click();await expect(page.getByRole('heading',{name:'成果已交付',exact:true})).toBeVisible();await expect(page.getByRole('complementary',{name:'执行与交付',exact:true}).locator('.px-execution-context')).toContainText(`任务完成 ${state.preparation.semantics.tasks.length}/${state.preparation.semantics.tasks.length}`);await expect(page.getByRole('list',{name:'当前阶段'}).locator('[aria-current=step]')).toContainText('验收结果');await panel.getByRole('button',{name:'查看验收摘要'}).click();await expect(panel).toContainText('业务结果：尚无法确定');await expect(panel.getByRole('button',{name:'确认限制与待解决事项'})).toBeDisabled();await panel.getByRole('textbox',{name:'验收意见'}).fill('视图测试意见');await expect(panel.getByRole('button',{name:'确认限制与待解决事项'})).toBeEnabled();expect(writes).toBe(0);await panel.getByRole('heading',{name:'标准评价与人工决定'}).scrollIntoViewIfNeeded();await page.screenshot({path:info.outputPath('H06-undetermined-fixture.png')});
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

for(const mismatch of ['identity','revision','digest','version'])test(`324 resource batch rejects ${mismatch} and never publishes`,async({page})=>{
 let writes=0;
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(route.request().method()!=='GET')writes++;
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:fixture',tenantId:'fixture-324',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(path.includes('/prepared-resources/'))return route.fulfill({json:{result:{kind:'skill',identity:mismatch==='identity'?'other':'fixture-skill',name:'测试技能',aggregateVersion:mismatch==='version'?0:1,revision:{revisionId:mismatch==='revision'?'other':'fixture-revision',digest:mismatch==='digest'?'invalid':'a'.repeat(64),state:'DRAFT',content:{}},publishedRevisionId:null}}});
  const result=path.endsWith('/criteria')||path.endsWith('/criteria-sets')?{revisions:[]}:path.endsWith('/problems')?{problems:[problem]}:{problem:{...problem,current_state:'ACTIVE',aggregate_version:1,current_revision_id:problem.revision_id},revisions:[problem],lifecycle:[]};return route.fulfill({json:{result}});
 });
 await page.goto(`/work?${new URLSearchParams({problem:problem.business_problem_id,resource:'skill|fixture-skill|fixture-revision'})}`);
 const panel=page.getByRole('region',{name:'本次执行必要资源审核'});
 await expect(panel.getByRole('alert')).toContainText(mismatch==='identity'||mismatch==='revision'?'RESOURCE_REFERENCE_MISMATCH':'RESOURCE_RECORD_INVALID');
 await expect(panel.getByRole('button',{name:/审核并发布待处理/})).toHaveCount(0);expect(writes).toBe(0);
});

test('324 failed resource refresh withdraws stale publication controls',async({page})=>{
 let unavailable=false,writes=0;
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;if(route.request().method()!=='GET')writes++;
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:fixture',tenantId:'fixture-324',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(path.includes('/prepared-resources/'))return route.fulfill(unavailable?{status:503,json:{reasonCode:'STORAGE_UNAVAILABLE'}}:{json:{result:{kind:'skill',identity:'fixture-skill',name:'测试技能',aggregateVersion:1,revision:{revisionId:'fixture-revision',digest:'a'.repeat(64),state:'DRAFT',content:{}},publishedRevisionId:null}}});
  const result=path.endsWith('/criteria')||path.endsWith('/criteria-sets')?{revisions:[]}:path.endsWith('/problems')?{problems:[problem]}:{problem:{...problem,current_state:'ACTIVE',aggregate_version:1,current_revision_id:problem.revision_id},revisions:[problem],lifecycle:[]};return route.fulfill({json:{result}});
 });
 await page.goto(`/work?${new URLSearchParams({problem:problem.business_problem_id,resource:'skill|fixture-skill|fixture-revision'})}`);const panel=page.getByRole('region',{name:'本次执行必要资源审核'});
 await expect(panel.getByRole('button',{name:'审核并发布待处理的 1 项资源'})).toBeVisible();
 await panel.getByRole('textbox',{name:'审核依据与限制'}).fill('测试');await panel.getByRole('checkbox').check();unavailable=true;
 await panel.getByRole('button',{name:'刷新资源状态'}).click();await expect(panel.getByRole('alert')).toBeVisible();await expect(panel.getByRole('button',{name:/审核并发布待处理/})).toHaveCount(0);
 unavailable=false;await panel.getByRole('button',{name:'刷新资源状态'}).click();await expect(panel.getByRole('checkbox')).not.toBeChecked();expect(writes).toBe(0);
});

test('324 changed resource version requires a new review without publishing',async({page})=>{
 let version=1,writes=0;
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;if(route.request().method()!=='GET')writes++;
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:fixture',tenantId:'fixture-324',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(path.includes('/prepared-resources/'))return route.fulfill({json:{result:{kind:'skill',identity:'fixture-skill',name:'测试技能',aggregateVersion:version,revision:{revisionId:'fixture-revision',digest:'a'.repeat(64),state:'DRAFT',content:{}},publishedRevisionId:null}}});
  const result=path.endsWith('/criteria')||path.endsWith('/criteria-sets')?{revisions:[]}:path.endsWith('/problems')?{problems:[problem]}:{problem:{...problem,current_state:'ACTIVE',aggregate_version:1,current_revision_id:problem.revision_id},revisions:[problem],lifecycle:[]};return route.fulfill({json:{result}});
 });
 await page.goto(`/work?${new URLSearchParams({problem:problem.business_problem_id,resource:'skill|fixture-skill|fixture-revision'})}`);const panel=page.getByRole('region',{name:'本次执行必要资源审核'});
 await panel.getByRole('textbox',{name:'审核依据与限制'}).fill('测试旧版本');await panel.getByRole('checkbox').check();version=2;
 await panel.getByRole('button',{name:'审核并发布待处理的 1 项资源'}).click();await expect(panel.getByRole('alert')).toContainText('RESOURCE_REVIEW_CHANGED_READ_AGAIN');await expect(panel.getByRole('checkbox')).not.toBeChecked();expect(writes).toBe(0);
});

test('324 new composer input during publication stops remaining resource writes',async({page})=>{
 let writes=0;let release!:()=>void;let started!:()=>void;
 const firstStarted=new Promise<void>(r=>{started=r}),gate=new Promise<void>(r=>{release=r});
 const resources=['skill','runtime'].map(kind=>({kind,identity:`fixture-${kind}`,name:'测试资源',aggregateVersion:1,revision:{revisionId:'fixture-revision',digest:'a'.repeat(64),state:'DRAFT',content:{}},publishedRevisionId:null as string|null}));
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:fixture',tenantId:'fixture-324',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(path.includes('/prepared-resources/')){const r=resources.find(r=>path.includes('/'+r.kind+'/'))!;if(route.request().method()==='POST'){writes++;started();await gate;r.publishedRevisionId=r.revision.revisionId;r.revision.state='PUBLISHED';return route.fulfill({json:{result:{state:'PUBLISHED'}}})}return route.fulfill({json:{result:r}})}
  const result=path.endsWith('/criteria')||path.endsWith('/criteria-sets')?{revisions:[]}:path.endsWith('/problems')?{problems:[problem]}:{problem:{...problem,current_state:'ACTIVE',aggregate_version:1,current_revision_id:problem.revision_id},revisions:[problem],lifecycle:[]};return route.fulfill({json:{result}});
 });
 const q=new URLSearchParams({problem:problem.business_problem_id});resources.forEach(r=>q.append('resource',`${r.kind}|${r.identity}|fixture-revision`));await page.goto('/work?'+q);
 const panel=page.getByRole('region',{name:'本次执行必要资源审核'});await panel.getByRole('textbox',{name:'审核依据与限制'}).fill('测试批量发布');await panel.getByRole('checkbox').check();await panel.getByRole('button',{name:'审核并发布待处理的 2 项资源'}).click();await firstStarted;
 await page.locator('#problem-composer').fill('新的业务补充，不得继续原批次。');release();await expect(panel.getByRole('alert')).toContainText('RESOURCE_REVIEW_CONTEXT_CHANGED');await expect(panel.getByRole('button',{name:/审核并发布待处理/})).toHaveCount(0);await expect(page.locator('#problem-composer')).toHaveValue('新的业务补充，不得继续原批次。');
 expect(writes).toBe(1);await page.locator('#problem-composer').fill('');await panel.getByRole('button',{name:'刷新资源状态'}).click();await expect(panel.getByRole('checkbox')).not.toBeChecked();expect(writes).toBe(1);
});

test('324 authorized delivery report renders unit-separated quantities, anomalies and source without writes',async({page},info)=>{
 const reportDocument=JSON.parse(readFileSync(new URL('./fixtures/delivery-report324.json',import.meta.url),'utf8'));reportDocument.sourceSnapshot=ref;let writes=0;const state=view();
 state.executionStarted=true;state.admission={state:'ADMITTED',reason:null};state.progress={state:'SUCCEEDED',version:18,cancellation_request_id:null,tasks:state.preparation.semantics.tasks.map(t=>({task_id:t.task_id,state:'SUCCEEDED',attempt_ordinal:1,reason:null}))};
 state.artifacts=state.preparation.semantics.tasks.map((t,i)=>{const content=JSON.stringify({...reportDocument,operation:state.preparation.participants[i].skill.operation});return {artifact_id:'fixture-delivery-'+i,task_id:t.task_id,digest:createHash('sha256').update(content).digest('hex'),bytes:Buffer.byteLength(content),created_at:'2026-11-03T17:00:00Z',contentAccess:'AUTHORIZED',content}});state.resourceUses=state.artifacts.map((_,i)=>({resourceUseId:'fixture-use-'+i,state:'SUCCEEDED'}));state.outcome={outcomeId:'fixture-outcome',version:1,evaluationDigest:'e'.repeat(64),businessResolution:'UNDETERMINED',confirmationId:null,evaluation:{evaluationId:'fixture-evaluation',results:['snapshot','eligibility','quantities','ranking','traceability','anomalies'].map((check,i)=>({check,criterionRevisionId:'fixture-criterion-'+(i+1),criterionDigest:'f'.repeat(64),result:'SATISFIED',reason:'SYNTHETIC_ONLY',artifactIds:state.artifacts.map(a=>a.artifact_id)}))}};
 const checks=['snapshot','eligibility','quantities','ranking','traceability','anomalies'];const criteria=checks.map((check,i)=>({scope:problem.scope,success_criterion_id:'fixture-criterion-'+(i+1),revision_id:'fixture-criterion-'+(i+1),revision:1,predecessor_revision_id:null,criterion_type:'DETERMINISTIC_BOOLEAN',measurement:{expected:true},evaluator_type:'SYNTHETIC_DELIVERY',evaluator_version:'1',required_evidence_kinds:['NATIVE_EXECUTION_ARTIFACT','PUBLISHED_SYNTHETIC_SOURCE'],applicability:{check,sourceContentDigest:reportDocument.sourceDigest},created_by:problem.created_by,created_at:problem.created_at,digest:'f'.repeat(64)}));const sets=[{scope:problem.scope,set_revision_id:'fixture-criteria-set',business_problem_id:problem.business_problem_id,problem_revision_id:problem.revision_id,revision:1,predecessor_set_revision_id:null,ordered_criterion_revision_ids:criteria.map(c=>c.revision_id),created_by:problem.created_by,created_at:problem.created_at,digest:'a'.repeat(64)}];
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;if(route.request().method()!=='GET')writes++;
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:fixture',tenantId:'fixture-324',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  const result=path.includes('/prepared-executions/')?state:path.endsWith('/criteria')?{revisions:criteria}:path.endsWith('/criteria-sets')?{revisions:sets}:path.endsWith('/problems')?{problems:[problem]}:{problem:{...problem,current_state:'ACTIVE',aggregate_version:1,current_revision_id:problem.revision_id},revisions:[problem],lifecycle:[]};return route.fulfill({json:{result}});
 });
 await page.goto(`/work?problem=${problem.business_problem_id}&execution=${state.digest}`);const panel=page.getByRole('region',{name:'Native 执行与成果验收'});await page.setViewportSize({width:1536,height:1056});const inline=page.getByRole('region',{name:'供应商交付关键数据'});await expect(inline.getByRole('table',{name:'供应商交付优先级'})).toBeVisible();await expect(inline).toContainText('60 件');await expect(inline).toContainText('15 箱');await inline.getByRole('button',{name:'SYN-A',exact:true}).click();await expect(inline.getByRole('table',{name:'订单明细与来源行'}).getByRole('cell',{name:'PO-S01',exact:true})).toBeVisible();await expect(inline.getByRole('table',{name:'订单明细与来源行'})).toBeInViewport();await page.screenshot({path:info.outputPath('inline-supplier-detail-fixture-1536.png')});await inline.getByRole('button',{name:'SYN-A',exact:true}).click();await page.locator('.px-message-stream').evaluate(node=>node.scrollTop=0);await page.screenshot({path:info.outputPath('P06.3-delivery-first-screen-fixture-1536.png')});await panel.getByRole('button',{name:'查看交付分析报告',exact:true}).click();const reportView=page.getByRole('dialog',{name:'成果文件详情'}).getByRole('region',{name:'供应商交付报告'});
 await expect(reportView).toBeVisible();
 await expect(reportView.locator('[aria-label=结果摘要]')).toContainText('4确定逾期订单');await expect(reportView).toContainText('60 件');await expect(reportView).toContainText('15 箱');await expect(reportView).not.toContainText('75 件');await expect(reportView).toContainText('承诺日期缺失或无效');await expect(reportView).toContainText('数量缺失或相互矛盾');
 await reportView.getByRole('button',{name:'SYN-A',exact:true}).click();await expect(reportView.getByRole('status')).toContainText('最长逾期10天');
 for(const size of [{width:1536,height:1100},{width:1229,height:880},{width:390,height:844}]){await page.setViewportSize(size);await reportView.scrollIntoViewIfNeeded();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.screenshot({path:info.outputPath(`delivery-report-${size.width}.png`)});}
 await reportView.getByText('来源版本与原始产物',{exact:true}).click();await expect(reportView.locator('pre')).toContainText('synthetic-delivery-output.v1');expect(writes).toBe(0);
 await page.setViewportSize({width:1536,height:1100});
 const downloading=page.waitForEvent('download');await reportView.getByRole('button',{name:'下载订单明细 CSV'}).click();const file=await downloading;expect(file.suggestedFilename()).toBe('supplier-delivery-details.csv');const downloaded=readFileSync((await file.path())!,'utf8');expect(downloaded).toContain('固定合成快照');expect(downloaded).toContain('PO-S01');expect(downloaded).toContain('来源');
 await page.getByRole('button',{name:'返回成果',exact:true}).click();await page.locator('#problem-composer').fill('PO-S09');await page.getByRole('button',{name:'查找报告',exact:true}).click();const lookup=page.getByRole('region',{name:'供应商交付关键数据'}).getByRole('region',{name:'订单明细检索'});await expect(lookup).toContainText('匹配 0 条订单、1 条异常');await expect(lookup).toContainText('承诺日期缺失或无效');await expect(page.getByRole('button',{name:'保存修改',exact:true})).toHaveCount(0);expect(writes).toBe(0);
 await expect(page.getByRole('dialog',{name:'成果文件详情'})).not.toBeVisible();await page.reload();await expect(panel).toBeAttached();expect(writes).toBe(0);
});

for(const mode of ['digest-mismatch','failed-refresh'])test(`324 execution ${mode} withdraws command controls and GET recovery never starts`,async({page})=>{
 let unavailable=false,writes=0;const state=view();if(mode==='failed-refresh'){state.executionStarted=true;state.admission={state:'ADMITTED',reason:null};state.progress={state:'SUCCEEDED',version:18,cancellation_request_id:null,tasks:state.preparation.semantics.tasks.map(t=>({task_id:t.task_id,state:'SUCCEEDED',attempt_ordinal:1,reason:null}))}}
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;if(route.request().method()!=='GET')writes++;
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:fixture',tenantId:'fixture-324',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(path.includes('/prepared-executions/'))return route.fulfill(unavailable?{status:503,json:{reasonCode:'STORAGE_UNAVAILABLE'}}:{json:{result:mode==='digest-mismatch'?{...state,digest:'wrong-digest'}:state}});
  const result=path.endsWith('/criteria')||path.endsWith('/criteria-sets')?{revisions:[]}:path.endsWith('/problems')?{problems:[problem]}:{problem:{...problem,current_state:'ACTIVE',aggregate_version:1,current_revision_id:problem.revision_id},revisions:[problem],lifecycle:[]};return route.fulfill({json:{result}});
 });
 await page.goto(`/work?problem=${problem.business_problem_id}&execution=${state.digest}`);const panel=page.getByRole('region',{name:'Native 执行与成果验收'});
 if(mode==='digest-mismatch'){await expect(panel.getByRole('alert')).toContainText('EXECUTION_DIGEST_MISMATCH')}
 else{await expect(page.getByRole('heading',{name:'成果已交付',exact:true})).toBeVisible();unavailable=true;await panel.getByRole('button',{name:'刷新正式状态'}).click();await expect(panel.getByRole('alert')).toBeVisible();await expect(page.getByRole('heading',{name:'执行进度',exact:true})).toBeVisible()}
 await expect(panel.getByRole('button',{name:'启动本次只读执行'})).toHaveCount(0);expect(writes).toBe(0);await panel.getByRole('button',{name:'刷新正式状态'}).click();expect(writes).toBe(0);
});

test('sales diagnostic exposes separated currencies and reusable report interactions without writes',async({page},info)=>{
 const content=readFileSync(new URL('./fixtures/sales-report.json',import.meta.url),'utf8');let writes=0;const state=view();
 state.executionStarted=true;state.admission={state:'ADMITTED',reason:null};state.progress={state:'SUCCEEDED',version:18,cancellation_request_id:null,tasks:state.preparation.semantics.tasks.map(t=>({task_id:t.task_id,state:'SUCCEEDED',attempt_ordinal:1,reason:null}))};state.artifacts=[{artifact_id:'fixture-sales-report',task_id:state.preparation.semantics.tasks.at(-1)!.task_id,digest:'1'.repeat(64),bytes:content.length,created_at:'2026-11-04T00:00:00Z',contentAccess:'AUTHORIZED',content}];
 state.preparation.semantics.title='销售变化诊断（合成视图测试）';state.preparation.source_snapshot=JSON.parse(content).sourceSnapshot;const displayedProblem={...problem,title:state.preparation.semantics.title};
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;if(route.request().method()!=='GET')writes++;
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:fixture',tenantId:'fixture-324',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  const result=path.includes('/prepared-executions/')?state:path.endsWith('/criteria')||path.endsWith('/criteria-sets')?{revisions:[]}:path.endsWith('/problems')?{problems:[displayedProblem]}:{problem:{...displayedProblem,current_state:'ACTIVE',aggregate_version:1,current_revision_id:problem.revision_id},revisions:[displayedProblem],lifecycle:[]};return route.fulfill({json:{result}});
 });
 state.preparation.semantics.title='销售变化诊断（合成视图测试）';await page.goto(`/work?problem=${problem.business_problem_id}&execution=${state.digest}`);await page.getByRole('button',{name:'查看销售变化诊断报告',exact:true}).click();const reportView=page.getByRole('dialog',{name:'成果文件详情'}).getByRole('region',{name:'销售诊断报告'});await expect(reportView).toBeVisible();await expect(reportView).toContainText('1000.00');await expect(reportView).toContainText('800.00');await expect(reportView).toContainText('-160.00');await expect(reportView).toContainText('基期为零，变化率不适用');await expect(reportView).toContainText('取消订单已排除');
 await reportView.getByRole('button',{name:'渠道',exact:true}).click();await expect(reportView.getByRole('status')).toContainText('渠道匹配');await reportView.getByRole('button',{name:'产品',exact:true}).click();await expect(reportView.getByRole('button',{name:'产品',exact:true})).toHaveAttribute('aria-pressed','true');
 await page.getByRole('button',{name:'返回成果',exact:true}).click();await page.locator('#problem-composer').fill('A');await page.getByRole('button',{name:'查找报告',exact:true}).click();const inlineSales=page.getByRole('region',{name:'销售诊断关键数据'});await inlineSales.getByRole('button',{name:'产品',exact:true}).click();await expect(inlineSales.getByRole('status')).toContainText('产品匹配 1 项');await expect(page.getByRole('dialog',{name:'成果文件详情'})).not.toBeVisible();expect(writes).toBe(0);
 await inlineSales.getByRole('button',{name:'A',exact:true}).click();const detail=inlineSales.getByRole('region',{name:'销售贡献来源明细'});await expect(detail).toContainText('S01');await expect(detail).toContainText('S03');await expect(detail).toContainText('CSV 第 4 行');await expect(detail).not.toContainText('S09');await expect(page.getByRole('dialog',{name:'成果文件详情'})).not.toBeVisible();await detail.scrollIntoViewIfNeeded();await page.screenshot({path:info.outputPath('sales-inline-source-drilldown-1536.png')});await detail.getByRole('button',{name:'收起来源明细'}).click();await expect(detail).toHaveCount(0);
 await inlineSales.getByRole('button',{name:'A',exact:true}).focus();await page.keyboard.press('Enter');await expect(detail).toBeVisible();await inlineSales.getByRole('button',{name:'渠道',exact:true}).click();await expect(detail).toHaveCount(0);expect(writes).toBe(0);await page.getByRole('button',{name:'查看销售变化诊断报告',exact:true}).click();
 const pending=page.waitForEvent('download');await reportView.getByRole('button',{name:'下载变化贡献 CSV'}).click();const file=await pending;expect(readFileSync((await file.path())!,'utf8')).toContain('不证明因果');
 for(const size of [{width:1536,height:1100},{width:1229,height:880},{width:390,height:844}]){await page.setViewportSize(size);await reportView.scrollIntoViewIfNeeded();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.screenshot({path:info.outputPath(`sales-report-fixture-${size.width}.png`)});}
 await page.getByRole('button',{name:'返回成果',exact:true}).click();await page.reload();await expect(page.getByRole('button',{name:'查看销售变化诊断报告',exact:true})).toBeVisible();expect(writes).toBe(0);
});

test('mismatched report source never becomes inline business data or an openable file',async({page})=>{
 const state=view();state.executionStarted=true;state.admission={state:'ADMITTED',reason:null};state.progress={state:'SUCCEEDED',version:18,cancellation_request_id:null,tasks:state.preparation.semantics.tasks.map(t=>({task_id:t.task_id,state:'SUCCEEDED',attempt_ordinal:1,reason:null}))};
 const content=readFileSync(new URL('./fixtures/delivery-report324.json',import.meta.url),'utf8');state.artifacts=[{artifact_id:'fixture-other-source',task_id:state.preparation.semantics.tasks.at(-1)!.task_id,digest:createHash('sha256').update(content).digest('hex'),bytes:Buffer.byteLength(content),created_at:'2026-11-04T00:00:00Z',contentAccess:'AUTHORIZED',content}];let writes=0;
 await page.route('**/api/workbench/v1/**',async route=>{const path=new URL(route.request().url()).pathname;if(route.request().method()!=='GET')writes++;if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:fixture',tenantId:'fixture-324',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});const result=path.includes('/prepared-executions/')?state:path.endsWith('/criteria')||path.endsWith('/criteria-sets')?{revisions:[]}:path.endsWith('/problems')?{problems:[problem]}:{problem:{...problem,current_state:'ACTIVE',aggregate_version:3,current_revision_id:problem.revision_id},revisions:[problem],lifecycle:[]};return route.fulfill({json:{result}})});
 await page.goto(`/work?problem=${problem.business_problem_id}&execution=${state.digest}`);await expect(page.getByRole('alert')).toContainText('报告来源版本与本次执行不一致');await expect(page.getByRole('region',{name:'供应商交付关键数据'})).toHaveCount(0);await expect(page.getByRole('button',{name:'查看交付分析报告',exact:true})).toBeDisabled();await expect(page.getByRole('button',{name:'下载交付分析报告',exact:true})).toBeDisabled();await page.reload();await expect(page.getByRole('alert')).toContainText('来源版本');expect(writes).toBe(0);
});

test('running same-case view shows real progress states and refresh remains GET only',async({page},info)=>{
 const state=view();state.executionStarted=true;state.admission={state:'ADMITTED',reason:null};state.progress={state:'RUNNING',version:6,cancellation_request_id:null,tasks:state.preparation.semantics.tasks.map((t,i)=>({task_id:t.task_id,state:i===0?'SUCCEEDED':i===1?'RUNNING':'WAITING',attempt_ordinal:i<2?1:0,reason:null}))};let writes=0;
 await page.route('**/api/workbench/v1/**',async route=>{const path=new URL(route.request().url()).pathname;if(route.request().method()!=='GET')writes++;if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:fixture',tenantId:'fixture-324',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});const result=path.includes('/prepared-executions/')?state:path.endsWith('/criteria')||path.endsWith('/criteria-sets')?{revisions:[]}:path.endsWith('/problems')?{problems:[problem]}:{problem:{...problem,current_state:'ACTIVE',aggregate_version:3,current_revision_id:problem.revision_id},revisions:[problem],lifecycle:[]};return route.fulfill({json:{result}})});
 await page.setViewportSize({width:1536,height:1056});await page.goto(`/work?problem=${problem.business_problem_id}&execution=${state.digest}`);const panel=page.getByRole('region',{name:'Native 执行与成果验收'});await expect(page.getByRole('heading',{name:'执行进度',exact:true})).toBeVisible();await expect(panel).toContainText('执行进度 1/3');await expect(panel).toContainText('运行中');await expect(page.getByRole('list',{name:'当前阶段'}).locator('[aria-current=step]')).toContainText('执行');await expect(panel).not.toContainText('执行准入存在缺口');await page.locator('.px-message-stream').evaluate(node=>node.scrollTop=0);await page.screenshot({path:info.outputPath('P06.2-running-first-screen-fixture-1536.png')});await panel.getByRole('button',{name:'刷新正式状态'}).click();await expect(panel).toContainText('执行进度 1/3');expect(writes).toBe(0);
});
