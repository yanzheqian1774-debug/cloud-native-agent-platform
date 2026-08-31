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
  await expect(page.getByText("Validation required")).toBeVisible();
  await page.getByRole("button", {name:"Validate draft"}).click();
  await expect(page.getByText("Validation passed — exact review required")).toBeVisible();
  await page.getByRole("button", {name:"Human review exact digest"}).click();
  await expect(page.getByText("Exact digest reviewed — ready to publish")).toBeVisible();
  await page.getByRole("button", {name:"Publish immutable revision"}).click();
  await expect(page.locator(".agent-detail").getByText("PUBLISHED", {exact:true}).first()).toBeVisible();
  await expect(page.getByText("Enabled", {exact:true})).toBeVisible();
}

test("publishes, binds and authorizes one bounded real capability test",async({page})=>{
  await publish(page,"/mcp","Create governed MCP");
  await page.getByRole("button",{name:"Test connection"}).click();
  await expect(page.getByText(/HEALTHY/).first()).toBeVisible();
  await page.getByRole("button",{name:"Discover Tools, Resources and Prompts"}).click();
  await expect(page.getByText("1 Tool(s) · 1 Resource(s) · 1 Prompt(s)")).toBeVisible();
  await page.getByRole("button",{name:"Govern Tool selection"}).click();
  await page.getByRole("button",{name:"Authorize real bounded invocation"}).click();
  await expect(page.getByRole("status")).toContainText("Invocation Evidence recorded");
  await expect(page.getByRole("status")).toContainText("credential values redacted: true");
  await publish(page,"/skills","Create governed SKILL");
  await page.getByLabel("Search catalog").fill("Supplier Quality");
  await page.getByLabel("Lifecycle filter").selectOption("PUBLISHED");
  await expect(page.getByRole("button",{name:/Supplier Quality Skill/})).toBeVisible();
  await page.getByRole("button",{name:"Save test case"}).click();
  await page.getByRole("button",{name:"Run saved test"}).click();
  await expect(page.getByText(/expected equals actual/)).toBeVisible();
  await page.getByRole("button",{name:"Bind exact MCP capability"}).click();
  await page.getByRole("button",{name:"Authorize bounded capability test"}).click();
  await expect(page.getByRole("status")).toContainText("Invocation Evidence recorded");
  await expect(page.getByRole("status")).toContainText("credential values redacted: true");
  await page.getByRole("tab", {name:"Technical View"}).click();
  await expect(page.getByText("Canonical identity")).toBeVisible();
  await expect(page.getByRole("tab", {name:"Technical View"})).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Governed lifecycle")).not.toBeVisible();
  await page.getByRole("tab", {name:"Product View"}).click();
  await expect(page.getByText("Governed lifecycle")).toBeVisible();
  const design = await page.locator(".agent-workbench").evaluate((element) => {
    const style = getComputedStyle(element);
    return {background:style.backgroundColor,color:style.color};
  });
  expect(design).toEqual({background:"rgb(246, 247, 249)",color:"rgb(23, 32, 42)"});
});
