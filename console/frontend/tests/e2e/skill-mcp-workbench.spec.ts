import {expect,test} from "@playwright/test";

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
  await expect(page.getByText("PUBLISHED", {exact:true}).first()).toBeVisible();
  await expect(page.getByText("Enabled", {exact:true})).toBeVisible();
}

test("publishes, binds and authorizes one bounded real capability test",async({page})=>{
  await publish(page,"/mcp","Create governed MCP");
  await publish(page,"/skills","Create governed SKILL");
  await page.getByRole("button",{name:"Bind exact MCP capability"}).click();
  await page.getByRole("button",{name:"Authorize bounded capability test"}).click();
  await expect(page.getByRole("status")).toContainText("Invocation SUCCEEDED");
  await expect(page.getByRole("status")).toContainText("Evidence redacted: true");
  await page.getByRole("tab", {name:"Technical View"}).click();
  await expect(page.getByText("Canonical identity")).toBeVisible();
  await expect(page.getByRole("tab", {name:"Technical View"})).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Removal impact")).not.toBeVisible();
  await page.getByRole("tab", {name:"Product View"}).click();
  await expect(page.getByText("Removal impact")).toBeVisible();
  const design = await page.locator(".agent-workbench").evaluate((element) => {
    const style = getComputedStyle(element);
    return {background:style.backgroundColor,color:style.color};
  });
  expect(design).toEqual({background:"rgb(246, 247, 249)",color:"rgb(23, 32, 42)"});
});
