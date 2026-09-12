import {expect,test,type Response} from "@playwright/test";
import {createServer,type Server} from "node:http";
import {recordSkillMcpOperationResult} from "../harness/structuredSkillMcpReporter";

let mcp:Server;
const responsePath=(response:Response)=>decodeURIComponent(new URL(response.url()).pathname);
test.beforeAll(async()=>{mcp=createServer((request,response)=>{let raw="";request.on("data",chunk=>{raw+=chunk});request.on("end",()=>{const message=JSON.parse(raw);const method=message.method;if(method==="notifications/initialized"){response.writeHead(202);response.end();return}const result=method==="initialize"?{protocolVersion:"2025-06-18",capabilities:{},serverInfo:{name:"browser-acceptance",version:"1"}}:method==="tools/list"?{tools:[{name:"quality.lookup",description:"Deterministic quality lookup",inputSchema:{type:"object"}}]}:method==="resources/list"?{resources:[{uri:"quality://guide",name:"Quality guide"}]}:method==="prompts/list"?{prompts:[{name:"quality-summary",description:"Quality summary"}]}:{content:[{type:"text",text:"healthy"}],structuredContent:{supplier:"ACME",token:"must-redact"}};const body=JSON.stringify({jsonrpc:"2.0",id:message.id,result});response.writeHead(200,{"Content-Type":"application/json","Mcp-Session-Id":"browser-session","Content-Length":Buffer.byteLength(body)});response.end(body)})});await new Promise<void>((resolve,reject)=>{mcp.once("error",reject);mcp.listen(8765,"127.0.0.1",resolve)})});
test.afterAll(async()=>{await new Promise<void>((resolve,reject)=>mcp.close(error=>error?reject(error):resolve()))});

test.afterEach(async({page},info)=>{
  if(info.status===info.expectedStatus)return;
  const codes=(await page.getByRole("alert").allTextContents()).flatMap(text=>text.match(/\b[A-Z][A-Z0-9_]{4,}\b/g)??[]);
  info.annotations.push({type:"controlled-state-codes",description:JSON.stringify(codes)});
});

async function publish(page: import("@playwright/test").Page, path: string, create: string) {
  await page.goto(path);
  await expect(page.locator(".demo-primary-nav")).toBeVisible();
  await expect(page.getByRole("region", {name:"Resource metrics"})).toBeVisible();
  await page.getByRole("button", {name:create}).click();
  const kind=path==="/skills"?"skill":"mcp";
  const createResponse=page.waitForResponse(response=>new URL(response.url()).pathname===`/api/internal/v0.2.2/resources/${kind}`&&response.request().method()==="POST");
  if (path === "/skills") {
    await page.getByLabel("Skill 名称").fill("Supplier Quality Skill");
    await page.getByLabel("能力 / operation（逗号分隔）").fill("quality.lookup");
    await page.getByRole("button", {name:"保存 Skill Draft"}).click();
  } else {
    await page.getByLabel("MCP 名称").fill("Local Acceptance MCP");
    await page.getByLabel("说明", {exact:true}).fill("Local deterministic MCP acceptance server");
    await page.getByLabel("能力 / operation（逗号分隔）").fill("quality.lookup");
    await page.getByLabel("Streamable HTTP endpoint").fill("http://127.0.0.1:8765/mcp");
    await page.getByLabel("Credential reference").fill("secret-ref:supplier-quality/mcp");
    await page.getByRole("button", {name:"保存 MCP Draft"}).click();
  }
  expect((await createResponse).status()).toBe(201);
  await expect(page.getByText("Validation required")).toBeVisible();
  const validationResponse=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith("/validation")&&response.request().method()==="POST");
  await page.getByRole("button", {name:"Validate draft"}).click();
  expect((await validationResponse).status()).toBe(200);
  await expect(page.getByText("Validation passed — exact review required")).toBeVisible();
  const reviewResponse=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith("/reviews")&&response.request().method()==="POST");
  await page.getByRole("button", {name:"Human review exact digest"}).click();
  expect((await reviewResponse).status()).toBe(200);
  await expect(page.getByText("Exact digest reviewed — ready to publish")).toBeVisible();
  const publicationResponse=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith("/publications")&&response.request().method()==="POST");
  await page.getByRole("button", {name:"Publish immutable revision"}).click();
  expect((await publicationResponse).status()).toBe(200);
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
  const identity=page.getByRole("region",{name:"正式资源身份与能力"});
  await expect(identity).toContainText(resourceId);
  await expect(identity).toContainText(beforeDraft.revisionId);
  await expect(identity).toContainText(beforeDraft.digest);
  await expect(identity.getByRole("region",{name:"Skill capabilities"})).toContainText(operation.name);
  await expect(identity.getByRole("region",{name:"Skill operations"})).toContainText(operation.executorId);
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

test("capability directory switches views, searches Chinese content and paginates the full list response",async({page})=>{
  const suffix=Date.now();
  const resources=Array.from({length:7},(_,index)=>({resourceId:`skill-directory-${suffix}-${index}`,kind:"skill",name:`分页能力 ${suffix}-${index}`,aggregateVersion:1,lifecycleState:"DRAFT",enabled:true,archived:false,currentDraftRevisionId:`revision-${index}`,publishedRevisionId:null,revisions:[{revisionId:`revision-${index}`,predecessorRevisionId:null,state:"DRAFT",digest:`sha256:${String(index).repeat(64)}`,content:{description:index===6?"中文供应商巡检":"目录分页样例",capabilities:[`catalog.sample.${index}`],instructions:"Read-only catalog sample."},createdAt:"2026-09-09T00:00:00Z"}],reviews:[],relationships:[],bindings:[],invocations:[],savedTests:[],testResults:[],discoverySnapshots:[],toolSelections:[],healthObservations:[],driftRecords:[],limitations:[]}));
  await page.route("**/api/internal/v0.2.2/resources/skill",route=>route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(resources)}));
  await page.route("**/api/internal/v0.2.2/resources/mcp",route=>route.fulfill({status:200,contentType:"application/json",body:"[]"}));
  await page.goto("/skills");
  const directory=page.getByRole("complementary",{name:"SKILL 能力目录"});
  await expect(directory.getByText(/当前完整响应共 \d+ 项/)).toBeVisible();
  await directory.getByRole("button",{name:"紧凑列表"}).click();
  await expect(directory.getByRole("button",{name:"紧凑列表"})).toHaveAttribute("aria-pressed","true");
  await expect(directory.getByRole("navigation",{name:"能力目录分页"})).toBeVisible();
  await directory.getByRole("button",{name:"下一页"}).click();
  await expect(directory.getByText(/第 2 \/ \d+ 页/)).toBeVisible();
  await page.getByLabel("Search catalog").fill("中文供应商巡检");
  await expect(directory.getByText(`分页能力 ${suffix}-6`,{exact:true})).toBeVisible();
  await expect(directory.getByText("筛选后 1 项",{exact:false})).toBeVisible();
  await expect(directory.getByRole("navigation",{name:"能力目录分页"})).toHaveCount(0);
});

test("publishes, binds and authorizes one bounded real capability test",async({page},testInfo)=>{
  await page.setViewportSize({width:1440,height:900});
  await test.step("SKILL_MCP_BACKEND_READY",async()=>{
    const response=await page.request.get("/api/internal/v0.2.2/resources/mcp");
    await recordSkillMcpOperationResult(testInfo,{operationId:"SKILL_MCP_BACKEND_READY",resultState:response.status()===200?"EXPECTED":"UNEXPECTED",structuredHttpStatus:response.status()});
    expect(response.status()).toBe(200);
  });
  await test.step("SKILL_MCP_MCP_PUBLISHED",()=>publish(page,"/mcp","Create governed MCP"));
  const resourceId=(await page.locator(".agent-detail > header code").textContent())!.trim();
  const healthPath=`/api/internal/v0.2.2/resources/mcp/${resourceId}/health`;
  let healthResponse!:Promise<Response>;
  await test.step("SKILL_MCP_HEALTH_SUBMIT",async()=>{
    healthResponse=page.waitForResponse(response=>responsePath(response)===healthPath&&response.request().method()==="POST");
    await page.getByRole("button",{name:"Test connection"}).click();
  });
  await test.step("SKILL_MCP_HEALTH_HTTP_COMPLETION",async()=>{
    const response=await healthResponse;
    await recordSkillMcpOperationResult(testInfo,{operationId:"SKILL_MCP_HEALTH_HTTP_COMPLETION",resultState:response.status()===200?"EXPECTED":"UNEXPECTED",structuredHttpStatus:response.status()});
    expect(response.status()).toBe(200);
  });
  await test.step("SKILL_MCP_HEALTH_UI_RENDERED",async()=>{
    await expect(page.getByText(/HEALTHY/).first()).toBeVisible();
  });
  const discoveryPath=`/api/internal/v0.2.2/resources/mcp/${resourceId}/discovery`;
  let discoveryResponse!:Promise<Response>,discoveryReadback!:Promise<Response>;
  let firstSnapshot="";
  await test.step("SKILL_MCP_DISCOVERY_SUBMIT",async()=>{
    discoveryResponse=page.waitForResponse(response=>responsePath(response)===discoveryPath&&response.request().method()==="POST");
    discoveryReadback=page.waitForResponse(async response=>{
      if(new URL(response.url()).pathname!=="/api/internal/v0.2.2/resources/mcp"||response.request().method()!=="GET")return false;
      const discoveryHttp=await discoveryResponse;
      if(discoveryHttp.status()!==200||response.status()!==200)return false;
      const discoveryBody=await discoveryHttp.json() as {resource:{resourceId:string;discoverySnapshots:Array<{snapshotId:string}>}};
      const snapshotId=discoveryBody.resource.discoverySnapshots.at(-1)?.snapshotId;
      const directoryBody=await response.json() as Array<{resourceId:string;discoverySnapshots:Array<{snapshotId:string}>}>;
      return discoveryBody.resource.resourceId===resourceId&&Boolean(snapshotId&&directoryBody.find(item=>item.resourceId===resourceId)?.discoverySnapshots.at(-1)?.snapshotId===snapshotId);
    });
    await page.getByRole("button",{name:"Discover Tools, Resources and Prompts"}).click();
  });
  await test.step("SKILL_MCP_DISCOVERY_HTTP_COMPLETION",async()=>{
    const response=await discoveryResponse;
    await recordSkillMcpOperationResult(testInfo,{operationId:"SKILL_MCP_DISCOVERY_HTTP_COMPLETION",resultState:response.status()===200?"EXPECTED":"UNEXPECTED",structuredHttpStatus:response.status()});
    expect(response.status()).toBe(200);
    const body=await response.json();firstSnapshot=body.resource.discoverySnapshots.at(-1).snapshotId;
  });
  await test.step("SKILL_MCP_DISCOVERY_SNAPSHOT_READBACK",async()=>{
    const response=await discoveryReadback;
    await recordSkillMcpOperationResult(testInfo,{operationId:"SKILL_MCP_DISCOVERY_SNAPSHOT_READBACK",resultState:response.status()===200?"EXPECTED":"UNEXPECTED",structuredHttpStatus:response.status()});
    expect(response.status()).toBe(200);
  });
  await test.step("SKILL_MCP_DISCOVERY_UI_RENDERED",async()=>{
    await expect(page.getByText("1 Tool(s) · 1 Resource(s) · 1 Prompt(s)")).toBeVisible();
    const mcpIdentity=page.getByRole("region",{name:"正式资源身份与能力"});
    await expect(mcpIdentity.getByRole("region",{name:"MCP capabilities"})).toContainText("quality.lookup");
    await expect(mcpIdentity.getByRole("region",{name:"MCP tools"})).toContainText("quality.lookup");
  });
  const selectionPath=`/api/internal/v0.2.2/resources/mcp/${resourceId}/tool-selections`;
  let selectionResponse!:Promise<Response>,selectionReadback!:Promise<Response>;
  let firstSelectionId="";
  await test.step("SKILL_MCP_TOOL_SELECTION_SUBMIT",async()=>{
    selectionResponse=page.waitForResponse(response=>responsePath(response)===selectionPath&&response.request().method()==="POST");
    selectionReadback=page.waitForResponse(async response=>{
      if(new URL(response.url()).pathname!=="/api/internal/v0.2.2/resources/mcp"||response.request().method()!=="GET")return false;
      const selectionHttp=await selectionResponse;
      if(selectionHttp.status()!==200||response.status()!==200)return false;
      const selectionBody=await selectionHttp.json() as {resource:{resourceId:string;toolSelections:Array<{selectionId:string;snapshotId:string}>}};
      const selected=selectionBody.resource.toolSelections.at(-1);
      const directoryBody=await response.json() as Array<{resourceId:string;toolSelections:Array<{selectionId:string;snapshotId:string}>}>;
      return selectionBody.resource.resourceId===resourceId&&Boolean(selected&&directoryBody.find(item=>item.resourceId===resourceId)?.toolSelections.some(item=>item.selectionId===selected.selectionId&&item.snapshotId===firstSnapshot));
    });
    await page.getByRole("checkbox",{name:/quality.lookup/}).check();
    await page.getByRole("button",{name:"Govern explicit Tool selection"}).click();
  });
  await test.step("SKILL_MCP_TOOL_SELECTION_HTTP_COMPLETION",async()=>{
    const response=await selectionResponse;
    await recordSkillMcpOperationResult(testInfo,{operationId:"SKILL_MCP_TOOL_SELECTION_HTTP_COMPLETION",resultState:response.status()===200?"EXPECTED":"UNEXPECTED",structuredHttpStatus:response.status()});
    expect(response.status()).toBe(200);
    const body=await response.json();firstSelectionId=body.resource.toolSelections.at(-1).selectionId;
  });
  await test.step("SKILL_MCP_TOOL_SELECTION_READBACK",async()=>{
    const response=await selectionReadback;
    await recordSkillMcpOperationResult(testInfo,{operationId:"SKILL_MCP_TOOL_SELECTION_READBACK",resultState:response.status()===200?"EXPECTED":"UNEXPECTED",structuredHttpStatus:response.status()});
    expect(response.status()).toBe(200);
    await expect(page.getByLabel("管理调用 Tool")).toBeVisible();
  });
  const rediscoveryPath=`/api/internal/v0.2.2/resources/mcp/${encodeURIComponent(resourceId)}/discovery`;
  let rediscoveryResponse!:Promise<Response>,rediscoveryReadback!:Promise<Response>;
  let secondSnapshot="";
  await test.step("SKILL_MCP_REDISCOVERY_SUBMIT",async()=>{
    rediscoveryResponse=page.waitForResponse(response=>responsePath(response)===rediscoveryPath&&response.request().method()==="POST");
    rediscoveryReadback=page.waitForResponse(async response=>{
      if(new URL(response.url()).pathname!=="/api/internal/v0.2.2/resources/mcp"||response.request().method()!=="GET")return false;
      const discoveryHttp=await rediscoveryResponse;
      if(discoveryHttp.status()!==200||response.status()!==200)return false;
      const discoveryBody=await discoveryHttp.json() as {resource:{resourceId:string;discoverySnapshots:Array<{snapshotId:string}>}};
      const snapshotId=discoveryBody.resource.discoverySnapshots.at(-1)?.snapshotId;
      const directoryBody=await response.json() as Array<{resourceId:string;discoverySnapshots:Array<{snapshotId:string}>}>;
      return discoveryBody.resource.resourceId===resourceId&&Boolean(snapshotId&&directoryBody.find(item=>item.resourceId===resourceId)?.discoverySnapshots.at(-1)?.snapshotId===snapshotId);
    });
    await page.getByRole("button",{name:"Discover Tools, Resources and Prompts"}).click();
  });
  await test.step("SKILL_MCP_REDISCOVERY_HTTP_COMPLETION",async()=>{
    const response=await rediscoveryResponse;
    await recordSkillMcpOperationResult(testInfo,{operationId:"SKILL_MCP_REDISCOVERY_HTTP_COMPLETION",resultState:response.status()===200?"EXPECTED":"UNEXPECTED",structuredHttpStatus:response.status()});
    expect(response.status()).toBe(200);
    const body=await response.json();secondSnapshot=body.resource.discoverySnapshots.at(-1).snapshotId;
    expect(secondSnapshot).not.toBe(firstSnapshot);
    expect(body.resource.toolSelections.some((item:{snapshotId:string})=>item.snapshotId===secondSnapshot)).toBe(false);
  });
  await test.step("SKILL_MCP_REDISCOVERY_SNAPSHOT_READBACK",async()=>{
    const response=await rediscoveryReadback;
    await recordSkillMcpOperationResult(testInfo,{operationId:"SKILL_MCP_REDISCOVERY_SNAPSHOT_READBACK",resultState:response.status()===200?"EXPECTED":"UNEXPECTED",structuredHttpStatus:response.status()});
    expect(response.status()).toBe(200);
  });
  await test.step("SKILL_MCP_REDISCOVERY_UI_RENDERED",async()=>{
    await expect(page.getByRole("status").filter({hasText:"当前 snapshot 尚无"})).toBeVisible();
    await expect(page.getByRole("checkbox",{name:/quality.lookup/})).not.toBeChecked();
    await expect(page.getByLabel("管理调用 Tool")).toHaveCount(0);
    await expect(page.getByRole("region",{name:"MCP snapshot and selection history"})).toContainText(firstSnapshot);
    await expect(page.getByRole("region",{name:"MCP snapshot and selection history"})).toContainText(secondSnapshot);
  });
  let reselectionResponse!:Promise<Response>,reselectionReadback!:Promise<Response>;
  let secondSelectionId="";
  await test.step("SKILL_MCP_RESELECTION_SUBMIT",async()=>{
    reselectionResponse=page.waitForResponse(response=>responsePath(response)===selectionPath&&response.request().method()==="POST");
    reselectionReadback=page.waitForResponse(async response=>{
      if(new URL(response.url()).pathname!=="/api/internal/v0.2.2/resources/mcp"||response.request().method()!=="GET")return false;
      const selectionHttp=await reselectionResponse;
      if(selectionHttp.status()!==200||response.status()!==200)return false;
      const selectionBody=await selectionHttp.json() as {resource:{resourceId:string;toolSelections:Array<{selectionId:string;snapshotId:string}>}};
      const selected=selectionBody.resource.toolSelections.at(-1);
      const directoryBody=await response.json() as Array<{resourceId:string;toolSelections:Array<{selectionId:string;snapshotId:string}>}>;
      return selectionBody.resource.resourceId===resourceId&&Boolean(selected&&selected.snapshotId===secondSnapshot&&directoryBody.find(item=>item.resourceId===resourceId)?.toolSelections.some(item=>item.selectionId===selected.selectionId));
    });
    await page.getByRole("checkbox",{name:/quality.lookup/}).check();
    await page.getByRole("button",{name:"Govern explicit Tool selection"}).click();
  });
  await test.step("SKILL_MCP_RESELECTION_HTTP_COMPLETION",async()=>{
    const response=await reselectionResponse;
    await recordSkillMcpOperationResult(testInfo,{operationId:"SKILL_MCP_RESELECTION_HTTP_COMPLETION",resultState:response.status()===200?"EXPECTED":"UNEXPECTED",structuredHttpStatus:response.status()});
    expect(response.status()).toBe(200);
    const body=await response.json();secondSelectionId=body.resource.toolSelections.at(-1).selectionId;
  });
  await test.step("SKILL_MCP_RESELECTION_READBACK",async()=>{
    const response=await reselectionReadback;
    await recordSkillMcpOperationResult(testInfo,{operationId:"SKILL_MCP_RESELECTION_READBACK",resultState:response.status()===200?"EXPECTED":"UNEXPECTED",structuredHttpStatus:response.status()});
    expect(response.status()).toBe(200);
    expect(secondSelectionId).not.toBe(firstSelectionId);
    await expect(page.getByLabel("管理调用 Tool")).toBeVisible();
  });
  let invocationResponse!:Promise<Response>;
  await test.step("SKILL_MCP_MCP_INVOCATION_SUBMIT",async()=>{
    await page.getByLabel("管理调用 Tool").selectOption("quality.lookup");
    await page.getByLabel("管理调用输入（JSON）").fill(JSON.stringify({supplier:"ACME"}));
    invocationResponse=page.waitForResponse(response=>responsePath(response)===`/api/internal/v0.2.2/resources/mcp/${resourceId}/tool-invocations`&&response.request().method()==="POST");
    await page.getByRole("button",{name:"Authorize bounded management invocation"}).click();
  });
  await test.step("SKILL_MCP_MCP_INVOCATION_HTTP_COMPLETION",async()=>{
    const response=await invocationResponse;
    await recordSkillMcpOperationResult(testInfo,{operationId:"SKILL_MCP_MCP_INVOCATION_HTTP_COMPLETION",resultState:response.status()===200?"EXPECTED":"UNEXPECTED",structuredHttpStatus:response.status()});
    expect(response.status()).toBe(200);
    const body=await response.json();expect(body.invocation.status).toBe("SUCCEEDED");
  });
  await test.step("SKILL_MCP_MCP_INVOCATION_UI_RENDERED",async()=>{
    const status=page.getByRole("region",{name:"MCP professional operations"}).getByRole("status",{name:"Invocation Evidence status"});
    await expect(status).toContainText("管理调用即时结果已保留");
    await expect(status).toContainText("credential values redacted: true");
    const current=await page.evaluate(async id=>(await(await fetch(`/api/internal/v0.2.2/resources/mcp/${encodeURIComponent(id)}`)).json()).resource,resourceId);
    expect(current.discoverySnapshots).toHaveLength(2);expect(current.toolSelections).toHaveLength(2);
    expect(current.toolSelections[0].snapshotId).toBe(firstSnapshot);
    expect(current.toolSelections[1].snapshotId).toBe(current.discoverySnapshots[1].snapshotId);
    expect(current.invocations.at(-1).selectionId).toBe(current.toolSelections[1].selectionId);
  });
  const publishedMcpId=await page.locator(".agent-detail > header code").textContent();
  await test.step("SKILL_MCP_SKILL_PUBLISHED",()=>publish(page,"/skills","Create governed SKILL"));
  const skillId=(await page.locator(".agent-detail > header code").textContent())!.trim();
  await test.step("SKILL_MCP_SKILL_TEST_UI_RENDERED",async()=>{
    const realDirectory=page.getByRole("complementary",{name:"SKILL 能力目录"});
    await expect(realDirectory.getByRole("button",{name:"卡片"})).toHaveAttribute("aria-pressed","true");
    await realDirectory.getByRole("button",{name:"紧凑列表"}).click();
    await expect(realDirectory.getByRole("button",{name:"紧凑列表"})).toHaveAttribute("aria-pressed","true");
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
  });
  const bindingPath=`/api/internal/v0.2.2/resources/skill/${skillId}/bindings`;
  let bindingResponse!:Promise<Response>,bindingReadback!:Promise<Response>;
  let bindingId="";
  await test.step("SKILL_MCP_BIND_SUBMIT",async()=>{
    bindingResponse=page.waitForResponse(response=>responsePath(response)===bindingPath&&response.request().method()==="POST");
    bindingReadback=page.waitForResponse(async response=>{
      if(new URL(response.url()).pathname!=="/api/internal/v0.2.2/resources/skill"||response.request().method()!=="GET")return false;
      const bindingHttp=await bindingResponse;
      if(bindingHttp.status()!==200||response.status()!==200)return false;
      const bindingBody=await bindingHttp.json() as {resource:{resourceId:string;bindings:Array<{bindingId:string}>}};
      const currentBinding=bindingBody.resource.bindings.at(-1);
      const directoryBody=await response.json() as Array<{resourceId:string;bindings:Array<{bindingId:string}>}>;
      return bindingBody.resource.resourceId===skillId&&Boolean(currentBinding&&directoryBody.find(item=>item.resourceId===skillId)?.bindings.some(item=>item.bindingId===currentBinding.bindingId));
    });
    await page.getByLabel("选择精确 MCP").selectOption(publishedMcpId!);
    await page.getByLabel("选择共同能力").selectOption("quality.lookup");
    await page.getByRole("button",{name:"Bind exact MCP capability"}).click();
  });
  await test.step("SKILL_MCP_BIND_HTTP_COMPLETION",async()=>{
    const response=await bindingResponse;
    await recordSkillMcpOperationResult(testInfo,{operationId:"SKILL_MCP_BIND_HTTP_COMPLETION",resultState:response.status()===200?"EXPECTED":"UNEXPECTED",structuredHttpStatus:response.status()});
    expect(response.status()).toBe(200);
    const body=await response.json();bindingId=body.resource.bindings.at(-1).bindingId;
  });
  await test.step("SKILL_MCP_BIND_READBACK",async()=>{
    const response=await bindingReadback;
    await recordSkillMcpOperationResult(testInfo,{operationId:"SKILL_MCP_BIND_READBACK",resultState:response.status()===200?"EXPECTED":"UNEXPECTED",structuredHttpStatus:response.status()});
    expect(response.status()).toBe(200);expect(bindingId).toBeTruthy();
    await expect(page.getByRole("button",{name:"Authorize bounded capability test"})).toBeEnabled();
  });
  let skillInvocationResponse!:Promise<Response>;
  await test.step("SKILL_MCP_SKILL_INVOCATION_SUBMIT",async()=>{
    skillInvocationResponse=page.waitForResponse(response=>responsePath(response)===`/api/internal/v0.2.2/resources/skill/${skillId}/invocations`&&response.request().method()==="POST");
    await page.getByLabel("管理测试输入（JSON）").fill(JSON.stringify({supplier:"ACME"}));
    await page.getByRole("button",{name:"Authorize bounded capability test"}).click();
  });
  await test.step("SKILL_MCP_SKILL_INVOCATION_HTTP_COMPLETION",async()=>{
    const response=await skillInvocationResponse;
    await recordSkillMcpOperationResult(testInfo,{operationId:"SKILL_MCP_SKILL_INVOCATION_HTTP_COMPLETION",resultState:response.status()===200?"EXPECTED":"UNEXPECTED",structuredHttpStatus:response.status()});
    expect(response.status()).toBe(200);
  });
  await test.step("SKILL_MCP_SKILL_INVOCATION_UI_RENDERED",async()=>{
    const status=page.getByRole("region",{name:"SKILL professional operations"}).getByRole("status",{name:"Invocation Evidence status"});
    await expect(status).toContainText("Invocation Evidence recorded");
    await expect(status).toContainText("credential values redacted: true");
  });
  await test.step("SKILL_MCP_FINAL_UI_INTERACTION",async()=>{
    await page.getByRole("tab", {name:"Technical View"}).click();
  await expect(page.getByText("Canonical identity")).toBeVisible();
  await expect(page.getByRole("tab", {name:"Technical View"})).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Governed lifecycle")).not.toBeVisible();
  await page.getByRole("tab", {name:"Product View"}).click();
  await expect(page.getByText("Governed lifecycle")).toBeVisible();
  const publishedSkill = await page.evaluate(async (id:string) => (await fetch(`/api/internal/v0.2.2/resources/skill/${encodeURIComponent(id)}`)).json(), skillId);
  const publishedDigest = publishedSkill.resource.revisions.find((item:{revisionId:string})=>item.revisionId===publishedSkill.resource.publishedRevisionId).digest;
  await page.getByRole("button", {name:"Create successor Draft"}).click();
  const editDraft=page.getByRole("button", {name:"编辑当前 Skill Draft"});
  await expect(editDraft).toBeEnabled();
  await editDraft.click();
  await expect(page.getByLabel("Skill 名称")).toHaveAttribute("readonly","");
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
  const delayedPath=`/api/internal/v0.2.2/resources/skill/${encodeURIComponent(skillId)}`;
  await page.route("**/api/internal/v0.2.2/resources/skill/*",async route=>{
    if(route.request().method()==="GET"&&new URL(route.request().url()).pathname===delayedPath){
      markFirstStarted();
      await firstRelease;
    }
    await route.continue();
  });
  const firstButton=page.locator(".agent-list button").filter({hasText:"Supplier Quality Skill"}).last();
  const alternateButton=page.locator(".agent-list button").filter({hasText:"Alternate Supplier Skill"}).last();
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
});

for(const operation of ["edit","lifecycle"] as const)test("skill write directory readback cannot own later selection or write: "+operation,async({page})=>{
  await page.goto("/skills");
  const suffix=Date.now(),names=[`race A skill ${suffix}`, `race B skill ${suffix}`];const ids:string[]=[];
  for(const name of names){await page.getByRole("button",{name:"Create governed SKILL"}).click();await page.getByLabel("Skill 名称").fill(name);const created=page.waitForResponse(response=>new URL(response.url()).pathname==="/api/internal/v0.2.2/resources/skill"&&response.request().method()==="POST");await page.getByRole("button",{name:"保存 SKILL Draft"}).click();expect((await created).status()).toBe(201);await expect(page.getByRole("heading",{name,exact:true})).toBeVisible();ids.push((await page.locator(".agent-detail > header code").textContent())!.trim())}
  const read=()=>page.evaluate(async root=>(await(await fetch(root)).json()),"/api/internal/v0.2.2/resources/skill");const before=await read();
  await page.getByLabel("Search catalog").fill(names[0]);await page.locator(".agent-list button").filter({hasText:names[0]}).click();await expect(page.getByRole("heading",{name:names[0],exact:true})).toBeVisible();
  let release!:()=>void,started!:()=>void;const held=new Promise<void>(resolve=>release=resolve),waiting=new Promise<void>(resolve=>started=resolve);let delayed=false;
  await page.route("**/api/internal/**",async route=>{if(route.request().method()==="GET"&&new URL(route.request().url()).pathname==="/api/internal/v0.2.2/resources/skill"&&!delayed){delayed=true;const response=await route.fetch();started();await held;await route.fulfill({response})}else await route.continue()});
  if(operation==="edit"){await page.getByRole("button",{name:"编辑当前 SKILL Draft"}).click();await expect(page.getByLabel("Skill 名称")).toHaveAttribute("readonly","");await page.getByLabel("说明",{exact:true}).fill("directory race saved content");await page.getByRole("button",{name:"保存 SKILL Draft"}).click()}else await page.getByRole("button",{name:"Disable",exact:true}).click();
  await waiting;await page.getByLabel("Search catalog").fill(names[1]);await page.locator(".agent-list button").filter({hasText:names[1]}).click();await expect(page.getByRole("heading",{name:names[1],exact:true})).toBeVisible();
  let releaseB!:()=>void,startedB!:()=>void;const heldB=new Promise<void>(resolve=>releaseB=resolve),waitingB=new Promise<void>(resolve=>startedB=resolve);
  await page.route("**/disable",async route=>{startedB();await heldB;await route.continue()});
  await page.getByRole("button",{name:"Disable",exact:true}).click();await waitingB;
  const responseA=page.waitForResponse(response=>new URL(response.url()).pathname==="/api/internal/v0.2.2/resources/skill"&&response.request().method()==="GET");release();await responseA;await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
  await expect(page.getByRole("heading",{name:names[1],exact:true})).toBeVisible();expect(new URL(page.url()).searchParams.get("resourceId")).toBe(ids[1]);
  await expect(page.getByRole("status",{name:"Workbench save status"})).toBeVisible();await expect(page.getByRole("button",{name:"Disable",exact:true})).toBeDisabled();
  releaseB();await expect(page.getByRole("button",{name:"Enable",exact:true})).toBeEnabled();await expect(page.getByRole("alert")).toHaveCount(0);
  const after=await read();expect(after).toHaveLength(before.length);expect(after.some((item:{resourceId:string})=>item.resourceId===ids[0])).toBe(true);
});

for(const operation of ["edit","lifecycle"] as const)test("mcp write directory readback cannot own later selection or write: "+operation,async({page})=>{
  await page.goto("/mcp");
  const suffix=Date.now(),names=[`race A mcp ${suffix}`, `race B mcp ${suffix}`];const ids:string[]=[];
  for(const name of names){await page.getByRole("button",{name:"Create governed MCP"}).click();await page.getByLabel("MCP 名称").fill(name);await page.getByRole("button",{name:"保存 MCP Draft"}).click();await expect(page.getByRole("heading",{name,exact:true})).toBeVisible();ids.push((await page.locator(".agent-detail > header code").textContent())!.trim())}
  const read=()=>page.evaluate(async root=>(await(await fetch(root)).json()),"/api/internal/v0.2.2/resources/mcp");const before=await read();
  await page.getByLabel("Search catalog").fill(names[0]);await page.locator(".agent-list button").filter({hasText:names[0]}).click();await expect(page.getByRole("heading",{name:names[0],exact:true})).toBeVisible();
  let release!:()=>void,started!:()=>void;const held=new Promise<void>(resolve=>release=resolve),waiting=new Promise<void>(resolve=>started=resolve);let delayed=false;
  await page.route("**/api/internal/**",async route=>{if(route.request().method()==="GET"&&new URL(route.request().url()).pathname==="/api/internal/v0.2.2/resources/mcp"&&!delayed){delayed=true;const response=await route.fetch();started();await held;await route.fulfill({response})}else await route.continue()});
  if(operation==="edit"){await page.getByRole("button",{name:"编辑当前 MCP Draft"}).click();await expect(page.getByLabel("MCP 名称")).toHaveAttribute("readonly","");await page.getByLabel("说明",{exact:true}).fill("directory race saved content");await page.getByRole("button",{name:"保存 MCP Draft"}).click()}else await page.getByRole("button",{name:"Disable",exact:true}).click();
  await waiting;await page.getByLabel("Search catalog").fill(names[1]);await page.locator(".agent-list button").filter({hasText:names[1]}).click();await expect(page.getByRole("heading",{name:names[1],exact:true})).toBeVisible();
  let releaseB!:()=>void,startedB!:()=>void;const heldB=new Promise<void>(resolve=>releaseB=resolve),waitingB=new Promise<void>(resolve=>startedB=resolve);
  await page.route("**/disable",async route=>{startedB();await heldB;await route.continue()});
  await page.getByRole("button",{name:"Disable",exact:true}).click();await waitingB;
  const responseA=page.waitForResponse(response=>new URL(response.url()).pathname==="/api/internal/v0.2.2/resources/mcp"&&response.request().method()==="GET");release();await responseA;await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
  await expect(page.getByRole("heading",{name:names[1],exact:true})).toBeVisible();expect(new URL(page.url()).searchParams.get("resourceId")).toBe(ids[1]);
  await expect(page.getByRole("status",{name:"Workbench save status"})).toBeVisible();await expect(page.getByRole("button",{name:"Disable",exact:true})).toBeDisabled();
  releaseB();await expect(page.getByRole("button",{name:"Enable",exact:true})).toBeEnabled();await expect(page.getByRole("alert")).toHaveCount(0);
  const after=await read();expect(after).toHaveLength(before.length);expect(after.some((item:{resourceId:string})=>item.resourceId===ids[0])).toBe(true);
});
