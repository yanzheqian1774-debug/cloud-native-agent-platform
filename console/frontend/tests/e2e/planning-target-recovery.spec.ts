import {expect,test} from "@playwright/test";

const session={principal:{principalId:"synthetic-requester",tenantId:"synthetic",securityDomain:"isolated"},session:{expiresAt:"2099-01-01",idleExpiresAt:"2099-01-01"},csrfToken:"synthetic"};
const target=(id:string)=>({target:{problem:{resource_id:id,revision_id:`${id}:1`,digest:"a".repeat(64)}},title:`已确认目标 ${id}`,description:`仅界面验证 ${id}，不代表真实数据或执行。`});

test("failed target blocks generation and admitted continuation; explicit read recovery and reload never dispatch",async({page},info)=>{
 let unavailable=true;const writes:string[]=[];
 await page.route("**/api/workbench/v1/**",async route=>{
  const path=new URL(route.request().url()).pathname;if(route.request().method()!=="GET")writes.push(path);
  if(path.endsWith("/session"))return route.fulfill({json:session});
  if(path.includes("/planning-input/"))return route.fulfill(unavailable?{status:503,json:{reasonCode:"PLANNING_INPUT_UNAVAILABLE"}}:{json:{result:target("case-A")}});
  if(path.includes("/planning-v2/requests/"))return route.fulfill({json:{result:{admission:{context_id:"synthetic",ready:true,maximum_new_calls:1,cumulative_call_cap:20},invocation:{target:{invocation_id:"opaque"},request:{answers:[]}},result:{technical_status:"PREPARED",kind:null},facts_status:"NOT_DISPATCHED"}}});
  return route.fulfill({status:404,json:{}});
 });
 await page.setViewportSize({width:1536,height:1024});await page.goto("/work/plan?problem=case-A&request=opaque");
 await expect(page.getByRole("heading",{name:"已确认目标暂时无法读取"})).toBeVisible();
 await expect(page.getByRole("button",{name:"继续本次规划调用",exact:true})).toBeDisabled();
 await expect(page.getByRole("button",{name:"提交规划补充",exact:true})).toBeDisabled();expect(writes).toEqual([]);
 await page.screenshot({path:info.outputPath("planning-target-unavailable-mock.png"),fullPage:true});
 unavailable=false;await page.getByRole("button",{name:"重新读取已确认目标",exact:true}).click();
 await expect(page.getByRole("heading",{name:"已确认目标 case-A",exact:true})).toBeVisible();
 await expect(page.getByRole("button",{name:"继续本次规划调用",exact:true})).toBeEnabled();
 await expect(page.getByRole("link",{name:"查看原问题与成功标准",exact:true})).toHaveAttribute("href","/work?problem=case-A");
 await page.reload();await expect(page.getByLabel("当前已确认目标")).toContainText("case-A");expect(writes).toEqual([]);
 await page.screenshot({path:info.outputPath("planning-target-restored-mock.png"),fullPage:true});
});

test("switching problem immediately withdraws prior target and rejects a delayed response",async({page})=>{
 let release!:()=>void;const held=new Promise<void>(resolve=>release=resolve);const writes:string[]=[];
 await page.route("**/api/workbench/v1/**",async route=>{
  const path=new URL(route.request().url()).pathname;if(route.request().method()!=="GET")writes.push(path);
  if(path.endsWith("/session"))return route.fulfill({json:session});
  if(path.includes("/planning-input/")){const id=decodeURIComponent(path.split("/").at(-1)!);if(id==="case-B")await held;return route.fulfill({json:{result:target(id)}})}
  return route.fulfill({status:404,json:{}});
 });
 await page.goto("/work/plan?problem=case-A");await expect(page.getByLabel("当前已确认目标")).toContainText("case-A");
 const switchTo=async(id:string)=>page.evaluate(id=>{history.pushState({idx:1},"",`/work/plan?problem=${id}`);window.dispatchEvent(new PopStateEvent("popstate",{state:history.state}))},id);
 await switchTo("case-B");await expect(page.getByLabel("当前已确认目标")).toHaveCount(0);
 await expect(page.getByRole("button",{name:"依据已确认目标生成建议",exact:true})).toBeDisabled();
 await switchTo("case-C");await expect(page.getByLabel("当前已确认目标")).toContainText("case-C");const late=page.waitForResponse(r=>r.url().endsWith("/planning-input/case-B"));release();await (await late).finished();await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
 await expect(page.getByLabel("当前已确认目标")).not.toContainText("case-B");expect(writes).toEqual([]);
});

test("missing problem offers source navigation and never reads an empty target",async({page})=>{
 const targetReads:string[]=[];
 await page.route("**/api/**",route=>{if(route.request().url().includes("planning-input"))targetReads.push(route.request().url());return route.fulfill({status:404,json:{}})});
 await page.route("**/api/workbench/v1/session",route=>route.fulfill({json:session}));
 await page.goto("/work/plan");await expect(page.getByRole("heading",{name:"请先选择业务问题",exact:true})).toBeVisible();
 await expect(page.getByRole("link",{name:"返回问题工作台",exact:true})).toHaveAttribute("href","/work");
 await expect(page.getByRole("button",{name:"依据已确认目标生成建议",exact:true})).toBeDisabled();expect(targetReads).toEqual([]);
});
