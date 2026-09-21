import {expect,test} from '@playwright/test';
import {procurement} from './fixtures/planning323';

test('planning dialogue preserves confirmed history and refresh never dispatches',async({page},info)=>{
 const first={proposal_id:'dialogue-case',revision:1,semantics:procurement};
 const proposals=[first];
 const plans=[{plan:{plan_id:'dialogue-case',version:1,source_proposal_revision:1,semantics:procurement},digest:'a'.repeat(64),approval:{approval_decision_id:'old-approval',decided_at:'2026-09-20T10:00:00Z'},execution_status:'NOT_STARTED'}];
 const old=JSON.stringify(plans[0]);const messages:object[]=[];const calls:Record<string,unknown>[]=[];
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:fixture',tenantId:'fixture',securityDomain:'fixture'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(path.includes('/planning-input/'))return route.fulfill({json:{result:{target:procurement.target,title:'合成案例',description:'仅规划，无业务执行'}}});
  if(path.endsWith('/preflight'))return route.fulfill({json:{result:{status:'EXPLICIT_CONSTRAINTS_VALID',dispatch_count:0}}});
  if(path.endsWith('/invocations')){
   const body=route.request().postDataJSON();calls.push(body);
   const next={...first,revision:2,semantics:{...procurement,title:'纠正后的方案',tasks:procurement.tasks.map((t,i)=>i===0?{...t,responsibility:'按最新信息准备数据'}:t)}};proposals.push(next);
   messages.push({invocation_id:'new-invocation',request:body,submitted_at:'2026-09-20T11:00:00Z',generated_at:'2026-09-20T11:00:10Z',questions:[]});
   return route.fulfill({json:{result:{invocation:{target:{invocation_id:'new-invocation'},request:body},result:{technical_status:'SUCCEEDED',kind:'VALID_SUGGESTION',proposal:next}}}});
  }
  if(path.endsWith('/confirm'))plans.push({plan:{plan_id:'dialogue-case',version:2,source_proposal_revision:2,semantics:proposals[1].semantics},digest:'b'.repeat(64),approval:{approval_decision_id:'new-approval',decided_at:'2026-09-20T11:01:00Z'},execution_status:'NOT_STARTED'});
  const revision=Number(new URL(route.request().url()).searchParams.get('version')??1);
  return route.fulfill({json:{result:path.endsWith('/history')?{proposals,plans,conversation:messages}:path.endsWith('/confirm')?plans[1]:{proposal:proposals.find(p=>p.revision===revision),digest:'c'.repeat(64),snapshot:null,generated_at:revision===1?null:'2026-09-20T11:00:10Z'}}});
 });
 await page.goto('/work/planning/dialogue-case?revision=1');
 await expect(page.getByRole('heading',{name:/计划已确认/})).toBeVisible();
 await page.getByLabel('补充信息或提出方案修改').fill('纠正：按最新确认信息准备数据，保留其他任务。');
 await page.getByRole('button',{name:'提交规划补充',exact:true}).click();
 await expect(page).toHaveURL(/revision=2/);
 await expect(page.getByRole('heading',{name:'本次修订影响'})).toBeVisible();
 expect(calls).toHaveLength(1);expect(calls[0].source_proposal).toEqual({resource_id:'dialogue-case',revision_id:'1',digest:'c'.repeat(64)});
 await page.getByRole('button',{name:'确认计划',exact:true}).click();
 await expect(page.getByRole('heading',{name:/计划已确认/})).toBeVisible();
 await page.reload();await expect(page.getByRole('heading',{name:/计划已确认/})).toBeVisible();
 await expect(page.getByText('纠正：按最新确认信息准备数据，保留其他任务。',{exact:true})).toBeVisible();
 expect(calls).toHaveLength(1);expect(JSON.stringify(plans[0])).toBe(old);expect(plans).toHaveLength(2);
 await page.screenshot({path:info.outputPath('dialogue-successor-confirmed.png'),fullPage:true});
});

test('lost response keeps opaque identity and refresh is read only',async({page})=>{
 let posts=0,reads=0;
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:fixture',tenantId:'fixture',securityDomain:'fixture'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(path.includes('/requests/')){reads++;return route.fulfill({status:404,json:{reasonCode:'PLANNING_NOT_FOUND'}})}
  if(path.endsWith('/invocations')){posts++;return route.abort('failed')}
  return route.fulfill({json:{result:path.includes('/planning-input/')?{target:procurement.target,title:'合成案例',description:'无业务执行'}:{status:'EXPLICIT_CONSTRAINTS_VALID'}}});
 });
 await page.goto('/work/plan?problem=fixture');await page.getByRole('button',{name:'依据已确认目标生成建议'}).click();
 await expect(page.getByRole('alert')).toBeVisible();const key=new URL(page.url()).searchParams.get('request');expect(key).toBeTruthy();
 await page.reload();await expect(page.getByRole('alert')).toContainText('不会重发');
 await expect(page.getByRole('button',{name:'依据已确认目标生成建议'})).toBeDisabled();expect(posts).toBe(1);expect(reads).toBe(1);expect(new URL(page.url()).searchParams.get('request')).toBe(key);
});
