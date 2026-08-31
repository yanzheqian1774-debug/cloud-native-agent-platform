import {expect,test} from "@playwright/test";

async function publish(page: import("@playwright/test").Page, path: string, create: string) {
  await page.goto(path);
  await page.getByRole("button", {name:create}).click();
  await page.getByRole("button", {name:"Validate draft"}).click();
  await page.getByRole("button", {name:"Human review exact digest"}).click();
  await page.getByRole("button", {name:"Publish immutable revision"}).click();
  await expect(page.getByText("PUBLISHED · Enabled")).toBeVisible();
}

test("publishes, binds and authorizes one bounded real capability test",async({page})=>{
  await publish(page,"/mcp","Create governed MCP");
  await publish(page,"/skills","Create governed SKILL");
  await page.getByRole("button",{name:"Bind exact MCP capability"}).click();
  await page.getByRole("button",{name:"Authorize bounded capability test"}).click();
  await expect(page.getByRole("status")).toContainText("Invocation SUCCEEDED");
  await expect(page.getByRole("status")).toContainText("Evidence redacted: true");
  await page.getByText("Technical sibling projection").click();
  await expect(page.getByText("Canonical identity")).toBeVisible();
});
