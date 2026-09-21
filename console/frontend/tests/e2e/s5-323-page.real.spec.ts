import {execFileSync} from 'node:child_process';
import {expect,test,type Page,type BrowserContext} from '@playwright/test';
import {readFileSync,writeFileSync} from 'node:fs';
const runtime=process.env.S5_323_PAGE_RUNTIME_DIR;
if(!runtime)throw new Error('S5_323_PAGE_RUNTIME_DIR_REQUIRED');
const credentials=JSON.parse(readFileSync(`${runtime}/credentials.json`,'utf8')) as {full:string;admin:string};
async function login(context:BrowserContext,credential:string){const page=await context.newPage();await page.goto('/api/workbench/v1/login');await page.locator('input[name="bootstrapCredential"]').fill(credential);await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.goto('/work');await expect(page.locator('#problem-composer')).toBeVisible();return page;}
async function fact(page:Page,label:string){const card=page.getByLabel('AI 问题理解与草稿辅助');const details=card.locator('details').last();if(await details.getAttribute('open')===null)await details.locator('summary').click();return (await details.locator('dt',{hasText:label}).locator('xpath=following-sibling::dd[1]').textContent())!.trim();}
async function decide(admin:Page,id:string,approve=true){await admin.goto(`/authorization-admin?request=${encodeURIComponent(id)}`);await admin.getByRole('button',{name:'检查授权申请',exact:true}).click();await expect(admin.getByText('等待决定',{exact:true})).toBeVisible();await admin.getByRole('button',{name:approve?'批准精确权限':'拒绝申请',exact:true}).click();await expect(admin.getByText(approve?'已批准':'已拒绝',{exact:true})).toBeVisible();}
async function authorize(page:Page,admin:Page){const card=page.getByLabel('AI 问题理解与草稿辅助');await expect(card).toContainText('AUTHORIZATION_PENDING');await decide(admin,await fact(page,'辅助授权申请'));await card.getByRole('button',{name:'重交正文并刷新授权',exact:true}).click();await expect.poll(()=>fact(page,'模型授权申请')).not.toBe('尚未提交');await decide(admin,await fact(page,'模型授权申请'));await card.getByRole('button',{name:'重交正文并刷新授权',exact:true}).click();await expect(page.getByLabel('问题草稿卡片').getByRole('button',{name:'确认创建',exact:true})).toBeEnabled();}

test('323 same-case controlled understanding to durable plan',async({browser},info)=>{
 const userContext=await browser.newContext({ignoreHTTPSErrors:true,viewport:{width:1500,height:1050}}),adminContext=await browser.newContext({ignoreHTTPSErrors:true});
 const page=await login(userContext,credentials.full),admin=await login(adminContext,credentials.admin);
 if(process.env.S5_323_PAGE_READBACK){
  const receipt=JSON.parse(readFileSync(process.env.S5_323_PAGE_READBACK,'utf8'));
  await page.goto(`/work?problem=${encodeURIComponent(receipt.problemId)}`);
  await expect(page.getByRole('link',{name:'制定建议计划'})).toBeVisible();
  await page.getByLabel('问题与完成标准确认').scrollIntoViewIfNeeded();
  await page.screenshot({path:info.outputPath('323-final-problem-active.png'),fullPage:true});
  await page.goto(`/work/planning/${encodeURIComponent(receipt.proposalId)}`);
  await expect(page.getByRole('heading',{name:'计划已确认，资源待准备，尚未开始执行',exact:true})).toBeVisible();
  const history=await (await page.request.get(`/api/workbench/v1/planning-v2/${receipt.proposalId}/history`)).json();expect(history.result).toEqual(receipt.history);
  await page.screenshot({path:info.outputPath('323-final-plan-readback.png'),fullPage:true});
  await userContext.close();await adminContext.close();return;
 }
 const initial='[SYNTHETIC-323] 公司A采购延期报告，2026-09-18 Asia/Shanghai，只读分析，不修改订单、不催交、不执行。';
 await page.locator('#problem-composer').fill(initial);await page.locator('#problem-composer').press('Enter');await authorize(page,admin);
 const corrected='[SYNTHETIC-323] 纠正：仅公司B，2026-09-19 Asia/Shanghai；公司A和旧日期作废。按承诺日严格早于判定日识别延期，缺失和冲突单列，按供应商与单位汇总，不跨单位相加，只读报告，不启动执行。';
 await page.locator('#problem-composer').fill(corrected);await page.locator('#problem-composer').press('Enter');await authorize(page,admin);
 await page.screenshot({path:info.outputPath('323-understanding-corrected.png'),fullPage:true});
 await page.getByLabel('问题草稿卡片').getByRole('button',{name:'确认创建',exact:true}).click();
 await expect(page.getByRole('heading',{name:'业务问题已创建',exact:true})).toBeVisible();
 const problemId=new URL(page.url()).searchParams.get('problem')!;
 await page.getByRole('button',{name:'申请查看权限',exact:true}).click();
 const auth=page.locator('#authorization-message');await decide(admin,(await auth.locator('dt',{hasText:'申请编号'}).locator('xpath=following-sibling::dd[1]').textContent())!.trim());
 await auth.getByRole('button',{name:'刷新授权状态',exact:true}).click();await expect(page.locator('#formal-problem-message')).toContainText(corrected);
 execFileSync(process.env.S5_323_PYTHON!,[`${runtime}/../grant.py`,problemId],{env:{...process.env,PYTHONPATH:process.env.S5_323_PYTHONPATH}});
 await page.getByRole('button',{name:'申请定义与读取权限',exact:true}).click();
 const access=page.locator('section').filter({has:page.getByRole('heading',{name:'尚未读取成功标准',exact:true})}).last();
 await decide(admin,(await access.locator('dt',{hasText:'申请编号'}).locator('xpath=following-sibling::dd[1]').textContent())!.trim());
 await access.getByRole('button',{name:'刷新权限状态并继续',exact:true}).click();
 await page.getByRole('button',{name:'定义成功标准',exact:true}).click();await page.getByLabel('怎样才算解决？').fill('人工核对公司B延期报告、三阶段五任务，两职责，缺失资源明确列示，不执行。');await page.getByLabel('怎样才算解决？').press('Enter');
 const card=page.getByLabel('成功标准待确认卡片');await card.getByLabel('人工验收标准').check();await card.getByRole('button',{name:'确认并保存',exact:true}).click();
 await card.getByRole('button',{name:'申请所需精确权限',exact:true}).click();
 const request=card.getByLabel('成功标准权限申请');await decide(admin,(await request.locator('dt',{hasText:'申请编号'}).locator('xpath=following-sibling::dd[1]').textContent())!.trim());
 await request.getByRole('button',{name:'刷新权限状态并继续',exact:true}).click();await expect(card).toContainText('已保存并完成正式关联');
 const before=await (await page.request.get(`/api/workbench/v1/problems/${encodeURIComponent(problemId)}`)).json();expect(before.result.problem.current_state).toBe('DRAFT');
 await page.screenshot({path:info.outputPath('323-before-activation.png'),fullPage:true});
 await page.getByRole('button',{name:'确认问题与完成标准',exact:true}).click();await expect(page.getByRole('link',{name:'制定建议计划'})).toBeVisible();
 await page.screenshot({path:info.outputPath('323-after-activation.png'),fullPage:true});
 await page.getByRole('link',{name:'制定建议计划'}).click();await page.getByRole('button',{name:'依据已确认目标生成建议',exact:true}).click();
 await expect(page.locator('.planning-stage')).toHaveCount(3);await expect(page.locator('.planning-task')).toHaveCount(5);
 await page.screenshot({path:info.outputPath('323-plan-proposal.png'),fullPage:true});
 await page.getByRole('button',{name:'确认计划',exact:true}).click();await expect(page.getByRole('heading',{name:'计划已确认，资源待准备，尚未开始执行',exact:true})).toBeVisible();
 const proposalId=decodeURIComponent(new URL(page.url()).pathname.split('/').pop()!);
 const history=await (await page.request.get(`/api/workbench/v1/planning-v2/${proposalId}/history`)).json();expect(history.result.plans).toHaveLength(1);
 await page.reload();await expect(page.getByRole('heading',{name:'计划已确认，资源待准备，尚未开始执行',exact:true})).toBeVisible();
 const again=await (await page.request.get(`/api/workbench/v1/planning-v2/${proposalId}/history`)).json();expect(again).toEqual(history);
 await page.screenshot({path:info.outputPath('323-plan-refreshed.png'),fullPage:true});
 writeFileSync(info.outputPath('same-case-receipt.json'),JSON.stringify({source:'LOCAL_HTTPS_UNDERSTANDING_AND_CONTROLLED_PLANNING_REAL_PG',modelQuality:'NOT_MEASURED',problemId,proposalId,before:before.result,history:history.result,corrected},null,2));
 await userContext.close();await adminContext.close();
});
