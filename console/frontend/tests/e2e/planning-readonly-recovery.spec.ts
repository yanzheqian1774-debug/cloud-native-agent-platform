import {test,expect,type Page} from "@playwright/test";
const session={principal:{principalId:"synthetic-only",tenantId:"synthetic",securityDomain:"isolated"},session:{expiresAt:"2099-01-01",idleExpiresAt:"2099-01-01"},csrfToken:"synthetic"};
const invocation=(id:string,problem="synthetic-case",reason="PROVIDER_OUTCOME_UNKNOWN")=>({invocation:{target:{invocation_id:id,problem:{problem:{resource_id:problem}}},request:{answers:[]},bounded_new_calls:1},result:{technical_status:"OUTCOME_UNKNOWN",reason,kind:null},facts_status:"NOT_VERIFIED"});
async function base(page:Page){await page.route("**/api/**",route=>route.fulfill({status:404,json:{}}));await page.route("**/api/workbench/v1/session",route=>route.fulfill({json:session}));await page.route("**/api/workbench/v1/planning-input/**",route=>route.fulfill({json:{result:{target:{},title:"隔离合成目标",description:"仅界面验证，不代表真实同案业务。"}}}));}
for(const reason of ["PROVIDER_OUTCOME_UNKNOWN","NO_DURABLE_TERMINAL_RESULT_DO_NOT_REDISPATCH"]){
 test(`UNKNOWN recovery ${reason} remains GET only across repeated reads and reload`,async({page},info)=>{
  await base(page);const methods:string[]=[];
  await page.route("**/api/workbench/v1/planning-v2/**",route=>{methods.push(route.request().method());return route.fulfill({json:{result:invocation("synthetic-original","synthetic-case",reason)}})});
  await page.setViewportSize({width:1536,height:1100});await page.goto("/work/plan?problem=synthetic-case&invocation=synthetic-original");
  const card=page.getByLabel("原规划调用只读恢复");await expect(card).toContainText(reason==="PROVIDER_OUTCOME_UNKNOWN"?"本次规划调用结果未知":"原调用尚无持久终态");
  await expect(card).toContainText("零费用");await expect(card).toContainText("synthetic-original");
  await expect(page.getByRole("button",{name:"依据已确认目标生成建议",exact:true})).toBeDisabled();
  for(let i=0;i<2;i++){await card.getByRole("button",{name:"读取原调用状态（不重试）",exact:true}).click();await expect(card.getByRole("button",{name:"读取原调用状态（不重试）",exact:true})).toBeEnabled()}
  await page.screenshot({path:info.outputPath(`${reason}-mock-1536.png`),fullPage:true});
  await page.reload();await expect(card).toContainText("UNKNOWN");expect(methods).toEqual(["GET","GET","GET","GET"]);
  await page.setViewportSize({width:390,height:844});await card.getByRole("button",{name:"读取原调用状态（不重试）",exact:true}).focus();await page.keyboard.press("Enter");await expect(card.getByRole("button",{name:"读取原调用状态（不重试）",exact:true})).toBeEnabled();
  await page.screenshot({path:info.outputPath(`${reason}-mock-390.png`)});
  expect(methods.every(m=>m==="GET")).toBe(true);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 });
}
test("initial record read failure offers explicit GET recovery, never generation",async({page})=>{
 await base(page);let unavailable=true;const methods:string[]=[];
 await page.route("**/api/workbench/v1/planning-v2/**",route=>{methods.push(route.request().method());return route.fulfill(unavailable?{status:503,json:{reasonCode:"UNAVAILABLE"}}:{json:{result:invocation("synthetic-original")}})});
 await page.goto("/work/plan?problem=synthetic-case&invocation=synthetic-original");const card=page.getByLabel("原规划调用只读恢复");
 await expect(card.getByRole("button",{name:"读取原调用状态（不重试）",exact:true})).toBeEnabled();await expect(page.getByRole("button",{name:"依据已确认目标生成建议",exact:true})).toBeDisabled();
 unavailable=false;await card.getByRole("button",{name:"读取原调用状态（不重试）",exact:true}).click();await expect(card).toContainText("本次规划调用结果未知");expect(methods).toEqual(["GET","GET"]);
});
test("same-problem locator change withdraws old record and rejects mismatched target",async({page})=>{
 await base(page);let release!:()=>void;const held=new Promise<void>(resolve=>release=resolve),methods:string[]=[];
 await page.route("**/api/workbench/v1/planning-v2/**",async route=>{methods.push(route.request().method());if(route.request().url().endsWith("second"))await held;return route.fulfill({json:{result:route.request().url().endsWith("first")?{...invocation("first"),admission:{ready:true,context_id:"synthetic",cumulative_call_cap:21}}:invocation("second","another-problem")}})});
 await page.goto("/work/plan?problem=synthetic-case&request=first");await expect(page.getByRole("button",{name:"继续本次规划调用",exact:true})).toBeEnabled();
 await page.evaluate(()=>{history.pushState({idx:1},"","/work/plan?problem=synthetic-case&invocation=second");window.dispatchEvent(new PopStateEvent("popstate",{state:history.state}))});
 await expect(page.getByRole("button",{name:"继续本次规划调用",exact:true})).toHaveCount(0);
 await expect(page.getByRole("button",{name:"依据已确认目标生成建议",exact:true})).toBeDisabled();
 const arrived=page.waitForResponse(r=>r.url().endsWith("/invocations/second"));release();await arrived;
 await expect(page.getByLabel("原规划调用只读恢复")).toContainText("原调用与当前问题不一致");await expect(page.getByRole("button",{name:"依据已确认目标生成建议",exact:true})).toBeDisabled();expect(methods).toEqual(["GET","GET"]);
});

test("late explicit recovery cannot redirect the newly selected record",async({page})=>{
 await base(page);let hold=false,release!:()=>void;const held=new Promise<void>(resolve=>release=resolve);const methods:string[]=[];
 await page.route("**/api/workbench/v1/planning-v2/**",async route=>{
  methods.push(route.request().method());const first=route.request().url().endsWith("first");if(first&&hold)await held;
  const value=invocation(first?"first":"second");
  return route.fulfill({json:{result:first&&hold?{...value,result:{technical_status:"SUCCEEDED",kind:"VALID_SUGGESTION",proposal:{proposal_id:"stale-proposal",revision:1}}}:value}});
 });
 await page.goto("/work/plan?problem=synthetic-case&invocation=first");const card=page.getByLabel("原规划调用只读恢复");await expect(card).toContainText("本次规划调用结果未知");await expect(card.getByRole("button",{name:"读取原调用状态（不重试）",exact:true})).toBeEnabled();hold=true;
 const started=page.waitForRequest(r=>r.url().endsWith("/invocations/first"));
 await card.getByRole("button",{name:"读取原调用状态（不重试）",exact:true}).click();await started;
 await page.evaluate(()=>{history.pushState({idx:1},"","/work/plan?problem=synthetic-case&invocation=second");window.dispatchEvent(new PopStateEvent("popstate",{state:history.state}))});
 await expect(card).toContainText("second");const late=page.waitForResponse(r=>r.url().endsWith("/invocations/first"));release();await (await late).finished();
 await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
 await expect(page).toHaveURL(/invocation=second$/);await expect(card).toContainText("second");expect(methods.every(x=>x==="GET")).toBe(true);
});
