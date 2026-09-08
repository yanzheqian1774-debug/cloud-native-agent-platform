import {expect,test} from "@playwright/test";
import {createServer,type Server} from "node:http";

let mcp:Server;
test.beforeAll(async()=>{mcp=createServer((request,response)=>{let raw="";request.on("data",chunk=>{raw+=chunk});request.on("end",()=>{const message=JSON.parse(raw);const method=message.method;if(method==="notifications/initialized"){response.writeHead(202);response.end();return}const result=method==="initialize"?{protocolVersion:"2025-06-18",capabilities:{},serverInfo:{name:"browser-acceptance",version:"1"}}:method==="tools/list"?{tools:[{name:"quality.lookup",description:"Deterministic quality lookup",inputSchema:{type:"object"}}]}:method==="resources/list"?{resources:[{uri:"quality://guide",name:"Quality guide"}]}:method==="prompts/list"?{prompts:[{name:"quality-summary",description:"Quality summary"}]}:{content:[{type:"text",text:"healthy"}],structuredContent:{supplier:"ACME",token:"must-redact"}};const body=JSON.stringify({jsonrpc:"2.0",id:message.id,result});response.writeHead(200,{"Content-Type":"application/json","Mcp-Session-Id":"browser-session","Content-Length":Buffer.byteLength(body)});response.end(body)})});await new Promise<void>((resolve,reject)=>{mcp.once("error",reject);mcp.listen(8765,"127.0.0.1",resolve)})});
test.afterAll(async()=>{await new Promise<void>((resolve,reject)=>mcp.close(error=>error?reject(error):resolve()))});

async function publish(page: import("@playwright/test").Page, path: string, create: string) {
  await page.goto(path);
  await expect(page.locator(".demo-primary-nav")).toBeVisible();
  await expect(page.getByRole("region", {name:"Resource metrics"})).toBeVisible();
  await page.getByRole("button", {name:create}).click();
  if (path === "/skills") {
    await page.getByLabel("Skill 名称").fill("Supplier Quality Skill");
    await page.getByLabel("能力 / operation（逗号分隔）").fill("quality.lookup");
    await page.getByRole("button", {name:"保存 Skill Draft"}).click();
  }
  await expect(page.getByText("Validation required")).toBeVisible();
  await page.getByRole("button", {name:"Validate draft"}).click();
  await expect(page.getByText("Validation passed — exact review required")).toBeVisible();
  await page.getByRole("button", {name:"Human review exact digest"}).click();
  await expect(page.getByText("Exact digest reviewed — ready to publish")).toBeVisible();
  await page.getByRole("button", {name:"Publish immutable revision"}).click();
  await expect(page.locator(".agent-detail").getByText("PUBLISHED", {exact:true}).first()).toBeVisible();
  await expect(page.getByText("Enabled", {exact:true})).toBeVisible();
}

test("editing an operation-backed Skill through the UI preserves exact operations",async({page})=>{
  await page.goto("/skills");
  const operation={
    name:"quality.ui-preservation",
    inputSchema:{type:"object",properties:{supplier:{type:"string"}}},
    outputSchema:{type:"object",properties:{status:{type:"string"}}},
    sideEffectClass:"READ_ONLY",
    executorId:"ui-preservation-readonly",
    executorRevision:"1.0.0",
    executorConfigurationDigest:"a".repeat(64),
    sideEffectPolicy:{policyId:"ui-preservation",policyRevision:"1",policyDigest:"b".repeat(64)},
    ioLimits:{policyId:"ui-bounds",policyRevision:"1",maxInputBytes:4096,maxOutputBytes:4096,maxObjectDepth:8,maxProperties:64,timeoutMs:1000},
  };
  const created=await page.evaluate(async({name,operation})=>{
    const response=await fetch("/api/internal/v0.2.2/resources/skill",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({name,content:{description:"Operation-backed Skill before UI edit",capabilities:[operation.name],instructions:"Perform the exact bounded read-only operation.",operations:[operation]}}),
    });
    return {status:response.status,body:await response.json()};
  },{name:`UI preservation Skill ${Date.now()}`,operation});
  expect(created.status).toBe(201);
  const resourceId=created.body.resource.resourceId as string;
  const before=await page.evaluate(async id=>(await(await fetch(`/api/internal/v0.2.2/resources/skill/${encodeURIComponent(id)}`)).json()),resourceId);
  const beforeDraft=before.resource.revisions.find((item:{revisionId:string})=>item.revisionId===before.resource.currentDraftRevisionId);
  const authoritativeOperations=beforeDraft.content.operations;

  await page.goto(`/skills?resourceId=${encodeURIComponent(resourceId)}`);
  await expect(page.locator(".agent-detail").getByRole("heading",{name:created.body.resource.name,exact:true})).toBeVisible();
  await page.getByRole("button",{name:"编辑当前 Skill Draft"}).click();
  const editedDescription="Operation-backed Skill after normal UI edit";
  await page.getByLabel("说明",{exact:true}).fill(editedDescription);
  const draftPath=`/api/internal/v0.2.2/resources/skill/${resourceId}/draft`;
  const requestPromise=page.waitForRequest(request=>request.method()==="PUT");
  const responsePromise=page.waitForResponse(response=>response.request().method()==="PUT");
  await page.getByRole("button",{name:"保存 Skill Draft"}).click();
  const [actualRequest,actualResponse]=await Promise.all([requestPromise,responsePromise]);
  expect(decodeURIComponent(new URL(actualRequest.url()).pathname)).toBe(draftPath);
  expect(decodeURIComponent(new URL(actualResponse.url()).pathname)).toBe(draftPath);
  expect(actualRequest.postDataJSON().content.operations).toEqual(authoritativeOperations);
  expect(actualResponse.status()).toBe(200);

  const after=await page.evaluate(async id=>(await(await fetch(`/api/internal/v0.2.2/resources/skill/${encodeURIComponent(id)}`)).json()),resourceId);
  const afterDraft=after.resource.revisions.find((item:{revisionId:string})=>item.revisionId===after.resource.currentDraftRevisionId);
  expect(after.resource.resourceId).toBe(resourceId);
  expect(afterDraft.content.description).toBe(editedDescription);
  expect(afterDraft.content.operations).toEqual(authoritativeOperations);
});

test("publishes, binds and authorizes one bounded real capability test",async({page})=>{
  await page.setViewportSize({width:1440,height:900});
  await publish(page,"/mcp","Create governed MCP");
  await page.getByRole("button",{name:"Test connection"}).click();
  await expect(page.getByText(/HEALTHY/).first()).toBeVisible();
  await page.getByRole("button",{name:"Discover Tools, Resources and Prompts"}).click();
  await expect(page.getByText("1 Tool(s) · 1 Resource(s) · 1 Prompt(s)")).toBeVisible();
  await page.getByRole("button",{name:"Govern Tool selection"}).click();
  await page.getByRole("button",{name:"Authorize real bounded invocation"}).click();
  const mcpInvocationStatus=page.getByRole("region",{name:"MCP professional operations"}).getByRole("status",{name:"Invocation Evidence status"});
  await expect(mcpInvocationStatus).toContainText("Invocation Evidence recorded");
  await expect(mcpInvocationStatus).toContainText("credential values redacted: true");
  const publishedMcpId=await page.locator(".agent-detail > header code").textContent();
  await publish(page,"/skills","Create governed SKILL");
  await page.getByLabel("Search catalog").fill("Supplier Quality");
  await page.getByLabel("Lifecycle filter").selectOption("PUBLISHED");
  await expect(page.locator(".agent-detail").getByRole("heading",{name:"Supplier Quality Skill"})).toBeVisible();
  expect(new URL(page.url()).searchParams.get("query")).toBe("Supplier Quality");
  expect(new URL(page.url()).searchParams.get("lifecycle")).toBe("PUBLISHED");
  expect(new URL(page.url()).searchParams.get("resourceId")).toBeTruthy();
  await page.getByLabel("测试名称").fill("Supplier quality regression");
  await page.getByLabel("测试输入（JSON）").fill(JSON.stringify({supplier:"ACME"}));
  await page.getByLabel("期望输出（JSON）").fill(JSON.stringify({status:"healthy"}));
  await page.getByRole("button",{name:"Save test case"}).click();
  await page.getByRole("button",{name:"Run saved test"}).click();
  await expect(page.getByText(/expected equals actual/)).toBeVisible();
  await page.getByLabel("选择精确 MCP").selectOption(publishedMcpId!);
  await page.getByLabel("选择共同能力").selectOption("quality.lookup");
  await page.getByRole("button",{name:"Bind exact MCP capability"}).click();
  await page.getByLabel("管理测试输入（JSON）").fill(JSON.stringify({supplier:"ACME"}));
  await page.getByRole("button",{name:"Authorize bounded capability test"}).click();
  const skillInvocationStatus=page.getByRole("region",{name:"SKILL professional operations"}).getByRole("status",{name:"Invocation Evidence status"});
  await expect(skillInvocationStatus).toContainText("Invocation Evidence recorded");
  await expect(skillInvocationStatus).toContainText("credential values redacted: true");
  await page.getByRole("tab", {name:"Technical View"}).click();
  await expect(page.getByText("Canonical identity")).toBeVisible();
  await expect(page.getByRole("tab", {name:"Technical View"})).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Governed lifecycle")).not.toBeVisible();
  await page.getByRole("tab", {name:"Product View"}).click();
  await expect(page.getByText("Governed lifecycle")).toBeVisible();
  const skillId = await page.locator(".agent-detail > header code").textContent();
  const publishedSkill = await page.evaluate(async (id:string) => (await fetch(`/api/internal/v0.2.2/resources/skill/${encodeURIComponent(id)}`)).json(), skillId!);
  const publishedDigest = publishedSkill.resource.revisions.find((item:{revisionId:string})=>item.revisionId===publishedSkill.resource.publishedRevisionId).digest;
  await page.getByRole("button", {name:"Create successor Draft"}).click();
  const editDraft=page.getByRole("button", {name:"编辑当前 Skill Draft"});
  await expect(editDraft).toBeEnabled();
  await editDraft.click();
  await page.getByLabel("说明", {exact:true}).fill("Edited governed supplier quality contract");
  const saveDraft=page.getByRole("button", {name:"保存 Skill Draft"});
  await expect(saveDraft).toBeEnabled();
  await saveDraft.click();
  await expect(page.getByRole("region", {name:"Skill Draft authoring"})).toHaveCount(0);
  await expect(page.getByText("Edited governed supplier quality contract")).toBeVisible();
  await expect(page.getByLabel("Exact revision digest")).not.toHaveValue(publishedDigest);
  await page.setViewportSize({width:390,height:844});
  await page.reload();
  await expect(page.getByText("Edited governed supplier quality contract")).toBeVisible();
  await page.getByLabel("Search catalog").focus();
  await expect(page.getByLabel("Search catalog")).toBeFocused();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBe(true);
  const design = await page.locator(".agent-workbench").evaluate((element) => {
    const style = getComputedStyle(element);
    return {background:style.backgroundColor,color:style.color};
  });
  expect(design).toEqual({background:"rgb(246, 247, 249)",color:"rgb(23, 32, 42)"});

  const alternate = await page.evaluate(async (resource: {name:string;content:Record<string,unknown>}) => {
    const response = await fetch("/api/internal/v0.2.2/resources/skill", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({name:resource.name,content:resource.content}),
    });
    return response.json();
  }, {name:"Alternate Supplier Skill",content:publishedSkill.resource.revisions.at(-1).content});
  await page.reload();
  await page.getByLabel("Search catalog").fill("");
  await page.getByLabel("Lifecycle filter").selectOption("ALL");

  let releaseFirst!:()=>void,markFirstStarted!:()=>void;
  const firstStarted=new Promise<void>(resolve=>{markFirstStarted=resolve});
  const firstRelease=new Promise<void>(resolve=>{releaseFirst=resolve});
  const delayedPath=`/api/internal/v0.2.2/resources/skill/${encodeURIComponent(skillId!)}`;
  await page.route("**/api/internal/v0.2.2/resources/skill/*",async route=>{
    if(route.request().method()==="GET"&&new URL(route.request().url()).pathname===delayedPath){
      markFirstStarted();
      await firstRelease;
    }
    await route.continue();
  });
  const firstButton=page.locator(".agent-list button").filter({hasText:"Supplier Quality Skill"});
  const alternateButton=page.locator(".agent-list button").filter({hasText:"Alternate Supplier Skill"});
  await firstButton.click();
  await firstStarted;
  await alternateButton.click();
  await expect(page.locator(".agent-detail").getByRole("heading",{name:"Alternate Supplier Skill"})).toBeVisible();
  await expect(alternateButton).toHaveClass(/selected/);
  expect(new URL(page.url()).searchParams.get("resourceId")).toBe(alternate.resource.resourceId);
  const delayedResponse=page.waitForResponse(response=>new URL(response.url()).pathname===delayedPath&&response.request().method()==="GET");
  releaseFirst();
  await delayedResponse;
  await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
  await expect(page.locator(".agent-detail").getByRole("heading",{name:"Alternate Supplier Skill"})).toBeVisible();
  await expect(alternateButton).toHaveClass(/selected/);
  expect(new URL(page.url()).searchParams.get("resourceId")).toBe(alternate.resource.resourceId);
});
