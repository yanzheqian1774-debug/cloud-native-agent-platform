import {expect,test} from '@playwright/test';
import {readFileSync,writeFileSync} from 'node:fs';
const runtime=process.env.S5_323_RUNTIME_DIR;
if(!runtime)throw new Error('S5_323_RUNTIME_DIR_REQUIRED');
const credentials=JSON.parse(readFileSync(`${runtime}/credentials.json`,'utf8')) as {browser:string};
test('323 HTTPS planning, clarification, confirmation and durable readback',async({page},info)=>{
 const failures:string[]=[];page.on('pageerror',e=>failures.push(e.message));
 await page.goto('/api/workbench/v1/login');
 await page.locator('input[name="bootstrapCredential"]').fill(credentials.browser);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 if(process.env.S5_323_RESTART_READ==='1'){
  const saved=JSON.parse(readFileSync(`${runtime}/browser-receipt.json`,'utf8'));
  await page.goto(saved.url);
  await expect(page.getByRole('heading',{name:'计划已确认，资源待准备，尚未开始执行',exact:true})).toBeVisible();
  const history=await (await page.request.get(`/api/workbench/v1/planning-v2/${saved.proposalId}/history`)).json();
  expect(history.result).toEqual(saved.history);
  await page.screenshot({path:info.outputPath('323-restart.png'),fullPage:true});
  expect(failures).toEqual([]);return;
 }
 await page.goto('/work/plan?problem=problem%3A323-purchase');
 await expect(page.getByRole('heading',{name:'整理延期采购订单清单',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'依据已确认目标生成建议',exact:true}).click();
 await expect(page.getByRole('heading',{name:'需要补充的信息',exact:true})).toBeVisible();
 await page.reload();
 await expect(page.getByRole('heading',{name:'需要补充的信息',exact:true})).toBeVisible();
 await page.getByLabel('补充信息或提出方案修改').fill('2026年9月17日10:00，323五行合成采购样本，仅只读分析。');
 await page.getByRole('button',{name:'提交规划补充',exact:true}).click();
 await expect(page.getByRole('heading',{name:'建议方案',exact:false})).toBeVisible();
 await expect(page.locator('.planning-stage')).toHaveCount(3);
 await expect(page.locator('.planning-task')).toHaveCount(5);
 await page.getByRole('button',{name:'刷新资源状态',exact:true}).click();
 await expect(page.locator('.planning-counts')).toContainText('1已匹配');
 await page.screenshot({path:info.outputPath('323-proposal.png'),fullPage:true});
 await page.getByRole('button',{name:'确认计划',exact:true}).click();
 await expect(page.getByRole('heading',{name:'计划已确认，资源待准备，尚未开始执行',exact:true})).toBeVisible();
 const proposalId=decodeURIComponent(new URL(page.url()).pathname.split('/').pop()!);
 const history=await (await page.request.get(`/api/workbench/v1/planning-v2/${proposalId}/history`)).json();
 expect(history.result.plans).toHaveLength(1);
 await page.reload();await expect(page.getByRole('heading',{name:'计划已确认，资源待准备，尚未开始执行',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'刷新资源状态',exact:true}).click();
 const again=await (await page.request.get(`/api/workbench/v1/planning-v2/${proposalId}/history`)).json();
 expect(again.result).toEqual(history.result);
 await page.screenshot({path:info.outputPath('323-confirmed.png'),fullPage:true});
 writeFileSync(`${runtime}/browser-receipt.json`,JSON.stringify({url:page.url(),proposalId,history:history.result},null,2));
 expect(failures).toEqual([]);
});

test('opaque request identity survives a lost response and browser refresh',async({page})=>{
 await page.goto('/api/workbench/v1/login');
 await page.locator('input[name="bootstrapCredential"]').fill(credentials.browser);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 const requests:Record<string,unknown>[]=[];
 await page.route('**/api/workbench/v1/planning-v2/invocations',async route=>{
  requests.push(route.request().postDataJSON());await route.abort('failed');
 });
 await page.goto('/work/plan?problem=problem%3A323-purchase');
 await page.getByRole('button',{name:'依据已确认目标生成建议',exact:true}).click();
 await expect(page.getByRole('alert')).toBeVisible();
 await page.reload();
 await expect(page.getByRole('alert')).toBeVisible();
 await expect(page.getByRole('button',{name:'依据已确认目标生成建议',exact:true})).toBeDisabled();
 expect(requests).toHaveLength(1);
 expect(new URL(page.url()).searchParams.get('request')).toBe(requests[0].idempotency_key);
});
