import {expect,test} from "@playwright/test";
import type {WorkflowProjection} from "../../src/api/workflowDefinitions";

const workflow:WorkflowProjection={definition:{workflowDefinitionId:"synthetic-workflow",name:"采购资料整理（合成界面验证）",aggregateVersion:1,lifecycleState:"DRAFT",currentDraftRevisionId:"revision-1",publishedRevisionId:null,revisions:[{revisionId:"revision-1",predecessorRevisionId:null,state:"DRAFT",digest:"a".repeat(64),createdAt:"2026-11-03T00:00:00Z",content:{description:"仅验证表单、目录、详情和状态，不代表真实业务执行。",inputs:[],outputs:[],runtimeProfile:{kind:"RUNTIME_PROFILE",resourceId:"runtime-synthetic",revisionId:"runtime-revision-1"},tasks:[]}}],reviews:[],relationships:[],consumers:[]},productProjection:{},technicalProjection:{}};

test("grouped navigation exposes active resource, all technical routes and mobile keyboard access",async({page})=>{
 await page.route("**/api/**",route=>route.fulfill({status:404,json:{}}));
 await page.setViewportSize({width:1536,height:1024});await page.goto("/skills");
 const navigation=page.getByRole("navigation",{name:"P1 核心产品导航",exact:true});
 for(const group of ["工作与协同","人员与资源","运营与治理"])await expect(navigation.getByRole("heading",{name:group})).toBeVisible();
 await expect(navigation.locator('a[href="/skills"]')).toHaveAttribute("aria-current","page");
 await expect(navigation.getByRole("link",{name:"MCP 服务"})).toBeVisible();
 await expect(navigation.locator("summary").filter({hasText:"问题工作台"})).not.toHaveClass(/active/);
 const work=navigation.locator("summary").filter({hasText:"问题工作台"});await work.focus();await page.keyboard.press("Enter");
 const advanced=navigation.locator("summary").filter({hasText:"管理与技术"});await advanced.focus();await page.keyboard.press("Enter");
 for(const route of ["runtime-profiles","evidence","outcomes","authorization-admin","agents","catalog","relationships","attention","applications","agent-center","permissions","security","models","help"])await expect(navigation.locator(`a[href="/${route}"]`)).toBeVisible();
 await navigation.locator('a[href="/evidence"]').click();
 await expect(page.getByRole("navigation",{name:"页面位置"})).toContainText("证据记录");
 await page.setViewportSize({width:390,height:844});
 await page.locator(".px-mobile-menu>summary").focus();await page.keyboard.press("Enter");
 await expect(page.getByRole("navigation",{name:"移动端全部产品导航"}).locator('a[href="/evidence"]')).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

for(const config of [{route:"workflow-definitions",dashboard:"Workflow dashboard",create:"新建 Workflow Definition",empty:"没有匹配的 Workflow Definition。"},{route:"runtime-profiles",dashboard:"Runtime Profile dashboard",create:"Create Native Kubernetes Profile",empty:"No Runtime Profiles yet."}]){
 test(`${config.route}: failed reads are unknown, disable writes, and explicit GET recovery restores empty`,async({page},info)=>{
  let status=403;const writes:string[]=[];
  await page.route("**/api/**",route=>route.fulfill({status:404,json:{}}));
  await page.route(`**/api/internal/v0.2.2/${config.route}`,async route=>{
   if(route.request().method()!=="GET")writes.push(route.request().method());
   await route.fulfill(status===200?{json:[]}:{status,json:{detail:{reasonCode:"ACCESS_DENIED_PRIVATE_DIAGNOSTIC"}}});
  });
  await page.goto(`/${config.route}`);
  await expect(page.getByRole("alert")).toContainText("不可用或当前访问未获授权");
  await expect(page.getByRole("alert")).not.toContainText("PRIVATE_DIAGNOSTIC");
  await expect(page.getByRole("button",{name:config.create,exact:true})).toBeDisabled();
  await expect(page.getByText(config.empty,{exact:true})).toHaveCount(0);
  await expect(page.getByLabel(config.dashboard).locator("strong")).toHaveText(["—","—","—"]);
  status=503;await page.getByRole("button",{name:"重新读取权威数据",exact:true}).click();
  await expect(page.getByRole("alert")).toContainText("当前数量未知");
  await expect(page.getByRole("button",{name:config.create,exact:true})).toBeDisabled();
  await page.screenshot({path:info.outputPath(`${config.route}-unavailable-mock.png`),fullPage:true});
  status=200;await page.getByRole("button",{name:"重新读取权威数据",exact:true}).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByLabel(config.dashboard).locator("strong")).toHaveText(["0","0","0"]);
  await expect(page.getByRole("button",{name:config.create,exact:true})).toBeEnabled();
  await expect(page.getByText(config.empty,{exact:true})).toBeVisible();expect(writes).toEqual([]);
 });
}

test("representative workflow shared form, list, detail and zoom have no overflow",async({page},info)=>{
 const writes:string[]=[];
 await page.route("**/api/**",route=>route.fulfill({status:404,json:{}}));
 await page.route("**/api/internal/v0.2.2/resources/skill",route=>route.fulfill({json:[]}));
 await page.route("**/api/internal/v0.2.2/workflow-definitions**",async route=>{
  if(route.request().method()!=="GET")writes.push(route.request().method());
  await route.fulfill({json:new URL(route.request().url()).pathname.endsWith("synthetic-workflow")?workflow:[workflow]});
 });
 for(const viewport of [{width:1536,height:1100},{width:1229,height:880},{width:390,height:844}]){
  await page.setViewportSize(viewport);await page.goto("/workflow-definitions?resourceId=synthetic-workflow");
  await expect(page.getByRole("heading",{name:workflow.definition.name,exact:true})).toBeVisible();
  await expect(page.getByLabel("Exact revision digest")).toHaveValue("a".repeat(64));
  const search=page.getByLabel("搜索 Workflow Definition");await search.fill("采购");await expect(search).toBeFocused();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.evaluate(()=>window.scrollTo(0,0));
  if(viewport.width===1536)await page.screenshot({path:info.outputPath("workflow-native-viewport-mock.png")});
  await page.screenshot({path:info.outputPath(`workflow-detail-mock-${viewport.width}.png`),fullPage:true});
  await page.getByRole("button",{name:"编辑当前 Draft",exact:true}).click();
  await expect(page.getByLabel("Workflow 名称")).toHaveValue(workflow.definition.name);
  await page.getByLabel("用途说明").fill("仅页内编写验证，不提交写入");
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:info.outputPath(`workflow-form-mock-${viewport.width}.png`),fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 }
 expect(writes).toEqual([]);
});

for(const config of [{route:"skills",api:"resources/skill",create:"Create governed SKILL",metrics:"Resource metrics"},{route:"mcp",api:"resources/mcp",create:"Create governed MCP",metrics:"Resource metrics"},{route:"agents",api:"agent-definitions",create:"创建 Agent Draft",metrics:"Agent metrics"},{route:"knowledge",api:"knowledge",create:"创建知识源",metrics:"Knowledge quality dashboard"}]){
 test(`${config.route}: unavailable collection cannot imply empty or enable creation`,async({page})=>{
  await page.route("**/api/**",route=>route.fulfill({status:503,json:{detail:{reasonCode:"UNAVAILABLE"}}}));
  await page.goto(`/${config.route}`);await expect(page.getByRole("alert").first()).toBeVisible();
  await expect(page.getByRole("button",{name:config.create,exact:true})).toBeDisabled();
  await expect(page.getByText(/^(No matching resources|没有符合条件的授权知识包。)$/)).toHaveCount(0);
  await expect(page.getByLabel(config.metrics).locator("strong").first()).toHaveText("—");
 });
}
