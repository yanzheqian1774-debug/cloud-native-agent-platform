import {expect,test} from "@playwright/test";

const problem={scope:{namespace:"tenant-a",security_domain:"quality"},business_problem_id:"problem:w3-1",revision_id:"problem-revision:w3-1:1",revision:1,predecessor_revision_id:null,title:"供应商交付恢复",description:"关键零部件延期影响客户交付。",owner_id:"human:owner",created_by:"human:owner",created_at:"2026-09-14T00:20:00Z",digest:"c".repeat(64)};
const detail={problem:{scope:problem.scope,business_problem_id:problem.business_problem_id,owner_id:problem.owner_id,current_state:"DRAFT",aggregate_version:1,current_revision_id:problem.revision_id,created_by:problem.created_by,created_at:problem.created_at,updated_at:problem.created_at},revisions:[problem],lifecycle:[]};
const envelope=(result:unknown)=>({schemaVersion:"workbench-operation.v1",result,continuationIds:[]});

async function installReadRoutes(page:import("@playwright/test").Page){
  await page.route("**/api/workbench/v1/session",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({schemaVersion:"workbench-session.v1",principal:{principalId:"human:owner",tenantId:"tenant-a",securityDomain:"quality"},session:{expiresAt:"2026-09-15T00:00:00Z",idleExpiresAt:"2026-09-14T01:00:00Z"},csrfToken:"csrf-test"})}));
  await page.route("**/api/workbench/v1/problems",route=>route.fulfill({contentType:"application/json",body:JSON.stringify(envelope({problems:[problem]}))}));
  await page.route("**/api/workbench/v1/problems/problem%3Aw3-1",route=>route.fulfill({contentType:"application/json",body:JSON.stringify(envelope(detail))}));
  await page.route("**/api/workbench/v1/problems/problem%3Aw3-1/criteria-sets",route=>route.fulfill({contentType:"application/json",body:JSON.stringify(envelope({revisions:[]}))}));
  await page.route("**/api/workbench/v1/problems/problem%3Aw3-1/criteria",route=>route.fulfill({contentType:"application/json",body:JSON.stringify(envelope({revisions:[]}))}));
}

test("success criterion stays local until explicit type selection and confirmation",async({page},testInfo)=>{
  const writes:string[]=[];page.on("request",request=>{if(request.method()!=="GET")writes.push(`${request.method()} ${request.url()}`)});
  await installReadRoutes(page);await page.goto("/work?problem=problem%3Aw3-1");
  await page.getByRole("button",{name:"定义成功标准",exact:true}).click();
  const composer=page.getByLabel("怎样才算解决？");
  await expect(composer).toBeFocused();
  await expect(page.getByText("当前针对：供应商交付恢复 · 成功标准",{exact:true})).toBeVisible();
  await composer.fill("客户确认未来三批均能按承诺日期交付。");
  await composer.press("Enter");
  const card=page.getByLabel("成功标准待确认卡片");
  await expect(card).toContainText("客户确认未来三批均能按承诺日期交付。");
  await expect(card.getByRole("button",{name:"确认成功标准"})).toBeDisabled();
  await card.getByLabel("人工验收标准").check();
  await card.getByRole("button",{name:"修改原文"}).click();
  await page.getByLabel("修改成功标准原文").fill("业务负责人确认未来三批均能按承诺日期交付。");
  await page.getByRole("button",{name:"采用标准原文"}).click();
  await expect(card).toContainText("业务负责人确认未来三批均能按承诺日期交付。");
  await card.getByRole("button",{name:"确认成功标准"}).click();
  await expect(card).toContainText("已确认，尚未保存");
  expect(writes).toEqual([]);
  await page.screenshot({path:testInfo.outputPath("w3-criterion-confirmed-local-1440.png"),fullPage:true});
});
