import {expect,test} from '@playwright/test';
import {readFileSync} from 'node:fs';
const proposal=JSON.parse(readFileSync(new URL('./fixtures/cost323.json',import.meta.url),'utf8'));
const translation=JSON.parse(readFileSync(new URL('../../../backend/src/agent_console/cost_plan_translation.json',import.meta.url),'utf8'));

test('historical cost Chinese display preserves original and bottom composer at desktop and zoom',async({page},info)=>{
 const translated=structuredClone(proposal.semantics) as unknown as Record<string,unknown>;
 for(const [path,text] of Object.entries(translation.fields)){
  const keys=path.split('/');let node=translated;
  for(const key of keys.slice(0,-1))node=node[key] as Record<string,unknown>;
  node[keys.at(-1)!]=text;
 }
 let writes=0;
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(route.request().method()!=='GET')writes++;
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:controlled-view',tenantId:'synthetic-323',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'controlled'}});
  const result=path.endsWith('/history')?{proposals:[proposal],plans:[{plan:{plan_id:proposal.proposal_id,version:1,source_proposal_revision:1,semantics:proposal.semantics},digest:'controlled-plan-digest',approval:{approval_decision_id:'controlled-display-approval',decided_at:'2026-09-21T00:00:00Z'},execution_status:'NOT_STARTED'}],conversation:[]}:{proposal,digest:translation.source_digest,snapshot:null,generated_at:null,display_translation:{semantics:translated,metadata:translation}};
  return route.fulfill({json:{result}});
 });
 await page.setViewportSize({width:1536,height:1024});
 await page.goto(`/work/planning/${proposal.proposal_id}?revision=1`);
 await expect(page.getByRole('heading',{name:/计划已确认/})).toBeAttached();
 await expect(page.getByRole('heading',{name:/建议方案/})).toContainText('4阶段 / 6任务');
 await expect(page.locator('.planning-goal')).toContainText('8,000');
 await expect(page.getByText('Collect billing and usage data',{exact:true})).toHaveCount(0);
 await page.screenshot({path:info.outputPath('P06-cost-zh-1536x1024.png')});
 await page.getByRole('button',{name:'查看原文',exact:true}).click();
 await expect(page.locator('.planning-task-overview strong').filter({hasText:'Collect billing and usage data'})).toBeAttached();
 await page.screenshot({path:info.outputPath('P06-cost-original-1536x1024.png')});
 await page.getByRole('button',{name:'显示中文译文',exact:true}).click();
 const input=page.getByLabel('补充信息或提出方案修改');
 await input.fill('纠正：请保留8,000元预算，排除试验项目；缺少账单时先收集数据，不推断成本归因。'.repeat(4));
 for(const scale of [1,1.25]){
  // Browser zoom reduces the CSS layout viewport; CSS style.zoom does not.
  const height=Math.floor(1024/scale);
  await page.setViewportSize({width:Math.floor(1536/scale),height});
  const send=page.getByRole('button',{name:'提交规划补充',exact:true});
  const box=await send.boundingBox();expect(box).toBeTruthy();expect(box!.y+box!.height).toBeLessThanOrEqual(height);
  await expect(send).toBeInViewport();
  await page.locator('.px-message-stream').evaluate(el=>{el.scrollTop=el.scrollHeight});
  await expect(page.getByRole('heading',{name:/计划已确认/})).toBeAttached();
  await page.screenshot({path:info.outputPath(`P06-cost-long-zh-zoom-${scale}.png`)});
 }
 await page.reload();await expect(input).toHaveValue('');expect(writes).toBe(0);
 await expect(page.getByText('Collect billing and usage data',{exact:true})).toHaveCount(0);
});

test('explicit clarification choices fill editable composer without automatic submission',async({page})=>{
 let calls=0;
 await page.route('**/api/workbench/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:controlled',tenantId:'fixture',securityDomain:'fixture'},session:{},csrfToken:'fixture'}});
  if(path.endsWith('/invocations')||path.endsWith('/invocations/choice')){if(route.request().method()==='POST')calls++;return route.fulfill({json:{result:{invocation:{target:{invocation_id:'choice'},request:{answers:[]}},result:{technical_status:'SUCCEEDED',kind:'NEEDS_CLARIFICATION',questions:['下月建议采用哪一种预算情景？\nA. 仅按已确认8,000元预算\nB. 同时比较8,000元及更低预算，另行确认具体金额']}}}})}
  return route.fulfill({json:{result:path.includes('/planning-input/')?{target:proposal.semantics.target,title:'合成成本案例',description:'真实账单尚缺'}:{}}});
 });
 await page.goto('/work/plan?problem=controlled');
 await page.getByRole('button',{name:'依据已确认目标生成建议',exact:true}).click();
 await page.getByRole('button',{name:'A. 仅按已确认8,000元预算',exact:true}).click();
 await expect(page.getByLabel('补充信息或提出方案修改')).toHaveValue('下月建议采用哪一种预算情景？：A. 仅按已确认8,000元预算');
 expect(calls).toBe(1);
 await page.getByLabel('补充信息或提出方案修改').fill('自由补充：仅按已确认的8,000元预算，不比较其他情景。');
 expect(calls).toBe(1);
});

test('login presentation uses official nonce form and expiry hides business content',async({page},info)=>{
 await page.setViewportSize({width:1536,height:1024});
 const html=readFileSync(new URL('../../../backend/src/agent_console/workbench_login.html',import.meta.url),'utf8').replace('{{nonce}}','controlled-nonce').replace('{{return}}','/work').replace('{{error}}','');
 const css=readFileSync(new URL('../../../backend/src/agent_console/workbench_login.css',import.meta.url),'utf8');
 await page.route('**/api/workbench/v1/login',route=>route.fulfill({contentType:'text/html',body:html}));
 await page.route('**/api/workbench/v1/login-style',route=>route.fulfill({contentType:'text/css',body:css}));
 await page.route('**/api/workbench/v1/session',route=>route.fulfill({status:401,json:{reasonCode:'AUTHENTICATION_REQUIRED'}}));
 await page.goto('/api/workbench/v1/login');
 await expect(page.getByLabel('登录凭据')).toHaveAttribute('type','password');
 await expect(page.locator('form')).toHaveAttribute('action','/api/workbench/v1/session');
 await page.screenshot({path:info.outputPath('IAM01-login-1536x1024.png')});
 await page.goto('/work');
 await expect(page.getByRole('heading',{name:'当前登录已失效'})).toBeVisible();
 await expect(page.locator('#problem-composer')).toHaveCount(0);
 await expect(page.getByRole('link',{name:'重新登录并读回'})).toHaveAttribute('href','/api/workbench/v1/login?returnTo=%2Fwork');
 await page.screenshot({path:info.outputPath('IAM03-expired-1536x1024.png')});
});
