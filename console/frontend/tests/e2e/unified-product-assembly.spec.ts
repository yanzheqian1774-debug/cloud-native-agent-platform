import { expect, test } from "@playwright/test";

test("assembles six durable domains into one truthful product journey", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByText("Authorized resources")).toBeVisible();
  await expect(page.getByText("NO EXECUTION AUTHORITY")).toBeVisible();
  await page.getByRole("link", { name: "Resource Catalog" }).click();
  await expect(page.getByRole("heading", { name: "Resource Catalog" })).toBeVisible();
  await page.getByLabel("Resource kind").selectOption("AGENT");
  await expect(page.locator(".resource-list a, .state-panel").first()).toBeVisible();
  await page.getByLabel("Resource kind").selectOption("");
  await page.getByLabel("Search").fill("not-a-fabricated-resource");
  await expect(page.getByRole("heading", { name: "No authorized resources match" })).toBeVisible();
  for (const [link, heading] of [["Digital Employees", "Digital Employees"], ["Attention", "Attention"], ["Relationships", "Resource Relationships"]] as const) {
    await page.getByRole("link", { name: link, exact: true }).click();
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  }
  await page.getByRole("link", { name: "Digital Employees", exact: true }).click();
  const template = page.locator(".template-grid article").first();
  if (await template.count()) {
    await expect(template).toContainText("Execution authority");
    await expect(template).toContainText("NONE");
    await expect(template).toContainText("NO EXECUTION AUTHORITY");
    const identity = await template.locator("dd code").nth(0).textContent();
    const revision = await template.locator("dd code").nth(1).textContent();
    const digest = await template.locator("dd code").nth(2).textContent();
    await page.goto(`/catalog?kind=AGENT&selected=${encodeURIComponent(`AGENT:${identity}`)}`);
    await expect(page.locator(".resource-detail")).toContainText(identity!);
    await expect(page.locator(".resource-detail")).toContainText(revision!);
    await expect(page.locator(".resource-detail")).toContainText(digest!);
  }
});

test("keeps denial disclosure-safe and responsive navigation accessible", async ({ page }) => {
  await page.route("**/api/internal/v0.2.2/product/catalog**", route => route.fulfill({status:403,contentType:"application/json",body:JSON.stringify({detail:{reasonCode:"PRODUCT_ASSEMBLY_ACCESS_DENIED"}})}));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/catalog");
  await expect(page.getByRole("alert")).toContainText("PRODUCT_ASSEMBLY_ACCESS_DENIED");
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
  await expect(page.locator("main")).toBeVisible();
});
