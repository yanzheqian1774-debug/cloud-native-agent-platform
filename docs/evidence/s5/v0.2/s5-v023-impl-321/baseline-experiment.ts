import {expect,test} from '@playwright/test';
import {writeFileSync} from 'node:fs';

test('fixed legacy UI baseline (mock, not model quality)',async({page},info)=>{
  test.skip(process.env.S5_321_BASELINE!=='1','Only run against fixed legacy source before product edits');
  let assistanceCalls=0; const writes:unknown[]=[];
  await page.route('**/api/workbench/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    let result:unknown={};
    if(path.endsWith('/session')){await route.fulfill({json:{principal:{principalId:'human:321',tenantId:'321',securityDomain:'quality'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'synthetic-321'}});return}
    if(path.endsWith('/draft-assistance/invocations')){assistanceCalls++; result={contextId:'ctx',turnId:'turn',turnVersion:1,invocationId:'inv',state:'SUCCEEDED',resultKind:'DRAFT_READY',transport:'SYNTHETIC',draft:{title:'来料改善',description:'A供应商，缺陷率低于2%，不能更换供应商。'},contentDisposition:'CONTENT_NOT_RETAINED'};}
    else if(path.endsWith('/problems')&&route.request().method()==='GET')result={problems:[]};
    else if(path.endsWith('/problems')){writes.push(route.request().postDataJSON());await route.fulfill({status:403,json:{reasonCode:'AUTHORIZATION_DENIED'}});return}
    await route.fulfill({json:{result}});
  });
  await page.goto('/work'); const input=page.locator('#problem-composer');
  await input.fill('A供应商，缺陷率低于2%，不能更换供应商。');await input.press('Enter');
  const card=page.getByLabel('问题草稿卡片');await expect(card.getByRole('button',{name:'确认创建',exact:true})).toBeVisible();
  await input.fill('只把阈值改成低于1%，其他保持。');await input.press('Enter');
  await expect(input).toHaveValue('');await expect(card).toContainText('低于2%');
  await card.getByRole('button',{name:'确认创建',exact:true}).click();expect(writes).toHaveLength(1);expect(assistanceCalls).toBe(1);
  const result={source:'e51334aa9780291b3d077a1edb698dca630a6b3f',kind:'MOCK_UI_BASELINE',modelQuality:'NOT_MEASURED',directConfirmAvailable:true,forcedEditVisits:0,naturalCorrectionAdopted:false,initialSend:1,correctionSend:1,businessConfirmClicks:1,assistanceRequests:assistanceCalls,problemCommands:writes.length};
  writeFileSync(info.outputPath('baseline.json'),JSON.stringify(result,null,2));await page.screenshot({path:info.outputPath('baseline.png')});
});
