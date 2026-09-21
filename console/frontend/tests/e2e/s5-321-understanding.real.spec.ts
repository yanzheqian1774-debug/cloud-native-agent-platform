import {expect,test,type Page,type BrowserContext} from '@playwright/test';
import {readFileSync,writeFileSync} from 'node:fs';
const runtime=process.env.S5_321_RUNTIME_DIR;
if(!runtime)throw new Error('S5_321_RUNTIME_DIR_REQUIRED');
const credentials=JSON.parse(readFileSync(`${runtime}/credentials.json`,'utf8')) as {full:string;admin:string};
async function login(context:BrowserContext,credential:string){const page=await context.newPage();await page.goto('/api/workbench/v1/login');await page.locator('input[name="bootstrapCredential"]').fill(credential);await page.getByRole('button',{name:'登录并返回工作台',exact:true}).click();await page.goto('/work');await expect(page.locator('#problem-composer')).toBeVisible();return page;}
async function fact(page:Page,label:string){const card=page.getByLabel('AI 问题理解与草稿辅助');const details=card.locator('details').last();if(await details.getAttribute('open')===null)await details.locator('summary').click();return (await details.locator('dt',{hasText:label}).locator('xpath=following-sibling::dd[1]').textContent())!.trim();}
async function decide(admin:Page,id:string,approve=true){await admin.goto(`/authorization-admin?request=${encodeURIComponent(id)}`);await admin.getByRole('button',{name:'检查授权申请',exact:true}).click();await expect(admin.getByText('等待决定',{exact:true})).toBeVisible();await admin.getByRole('button',{name:approve?'批准精确权限':'拒绝申请',exact:true}).click();await expect(admin.getByText(approve?'已批准':'已拒绝',{exact:true})).toBeVisible();}
async function authorize(page:Page,admin:Page){const card=page.getByLabel('AI 问题理解与草稿辅助');await expect(card).toContainText('AUTHORIZATION_PENDING');await decide(admin,await fact(page,'辅助授权申请'));await card.getByRole('button',{name:'重交正文并刷新授权',exact:true}).click();await expect.poll(()=>fact(page,'模型授权申请')).not.toBe('尚未提交');await decide(admin,await fact(page,'模型授权申请'));await card.getByRole('button',{name:'重交正文并刷新授权',exact:true}).click();await expect(page.getByLabel('问题草稿卡片').getByRole('button',{name:'确认创建',exact:true})).toBeEnabled();}

test('real HTTPS + PG: governed v2 correction, one create, independent READ, refresh and no replay',async({browser},info)=>{
 const userContext=await browser.newContext({ignoreHTTPSErrors:true}),adminContext=await browser.newContext({ignoreHTTPSErrors:true});
 const page=await login(userContext,credentials.full),admin=await login(adminContext,credentials.admin);
 const commands:Record<string,unknown>[]=[];
 page.on('request',request=>{if(new URL(request.url()).pathname==='/api/workbench/v1/problems'&&request.method()==='POST')commands.push(request.postDataJSON());});
 const text='321合成验收：只看A供应商，缺陷率低于2%，禁止更换设备；具体季度和基线未知。';
 await page.locator('#problem-composer').fill(text);await page.locator('#problem-composer').press('Enter');await authorize(page,admin);
 await expect(page.getByLabel('问题草稿卡片')).toContainText(text);
 await page.screenshot({path:info.outputPath('real-understanding.png')});
 const corrected='321合成验收：只看A供应商，缺陷率低于1%，禁止更换设备；具体季度和基线未知。';
 await page.locator('#problem-composer').fill(corrected);await expect(page.getByLabel('问题草稿卡片').getByRole('button',{name:'确认创建',exact:true})).toBeDisabled();await page.locator('#problem-composer').press('Enter');await authorize(page,admin);
 await expect(page.getByLabel('问题草稿卡片')).toContainText(corrected);await expect(page.getByLabel('问题草稿卡片').getByRole('button',{name:'确认创建',exact:true})).not.toBeFocused();
 await page.getByLabel('问题草稿卡片').getByRole('button',{name:'确认创建',exact:true}).dblclick();
 await expect(page.getByRole('heading',{name:'业务问题已创建',exact:true})).toBeVisible();expect(commands).toHaveLength(1);expect(commands[0].description).toBe(corrected);
 await expect(page.getByRole('heading',{name:'问题详情已读取',exact:true})).toHaveCount(0);
 const problemId=new URL(page.url()).searchParams.get('problem');expect(problemId).toBeTruthy();
 const denied=await page.request.get(`/api/workbench/v1/problems/${encodeURIComponent(problemId!)}`);expect(denied.status()).toBe(404);expect(await denied.text()).not.toContain(corrected);
 await page.getByRole('button',{name:'申请查看权限',exact:true}).click();
 const auth=page.locator('#authorization-message');const id=(await auth.locator('dt',{hasText:'申请编号'}).locator('xpath=following-sibling::dd[1]').textContent())!.trim();await decide(admin,id);await auth.getByRole('button',{name:'刷新授权状态',exact:true}).click();
 await expect(page.getByRole('heading',{name:'问题详情已读取',exact:true})).toBeVisible();await expect(page.locator('#formal-problem-message')).toContainText(corrected);
 await page.reload();await expect(page.locator('#formal-problem-message')).toContainText(corrected);expect(commands).toHaveLength(1);
 await expect(page.getByText('读取成功标准',{exact:false}).first()).toBeVisible();
 await page.screenshot({path:info.outputPath('real-readback-criteria-independent.png')});
 const storage=await page.evaluate(()=>JSON.stringify({local:{...localStorage},session:{...sessionStorage}}));expect(storage).not.toContain(corrected);
 writeFileSync(info.outputPath('receipt.json'),JSON.stringify({kind:'REAL_BACKEND_LOCAL_HTTPS_PROVIDER_FIXTURE',modelQuality:'NOT_MEASURED',problemId,createCommands:commands.length,independentRead:true,refreshRead:true,uiModelCalls:2},null,2));
 await userContext.close();await adminContext.close();
});

test('real authority denial prevents local provider dispatch',async({browser,request})=>{
 const userContext=await browser.newContext({ignoreHTTPSErrors:true}),adminContext=await browser.newContext({ignoreHTTPSErrors:true});const page=await login(userContext,credentials.full),admin=await login(adminContext,credentials.admin);
 const before=await (await request.get('https://127.0.0.1:19323/stats')).json();
 await page.locator('#problem-composer').fill('321授权拒绝，不应dispatch');await page.locator('#problem-composer').press('Enter');const card=page.getByLabel('AI 问题理解与草稿辅助');await expect(card).toContainText('AUTHORIZATION_PENDING');await decide(admin,await fact(page,'辅助授权申请'),false);await card.getByRole('button',{name:'重交正文并刷新授权',exact:true}).click();await expect(page.getByRole('alert')).toContainText('DRAFT_ASSISTANCE_NOT_FOUND');
 const after=await (await request.get('https://127.0.0.1:19323/stats')).json();expect(after.calls).toBe(before.calls);await expect(page.getByLabel('问题草稿卡片')).toHaveCount(0);await userContext.close();await adminContext.close();
});
