import { expect, test } from "@playwright/test";

const pages = [
  ["/applications", "应用市场"],
  ["/agent-center", "Agent Center"],
  ["/permissions", "权限中心"],
  ["/security", "安全中心"],
  ["/operations", "运维监控"],
  ["/models", "模型中心"],
  ["/usage", "费用与使用量"],
  ["/settings", "系统设置"],
  ["/help", "帮助中心"],
] as const;

test("exposes nine truthful Chinese-first platform support surfaces", async ({ page }) => {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    for (const [route, heading] of pages) {
      await page.goto(route);
      await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
      await expect(page.getByRole("tab", { name: "产品视图" })).toBeVisible();
      await expect(page.getByRole("tab", { name: "技术视图" })).toBeVisible();
      await expect(page.getByRole("status").first()).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
  }
});

test("keeps unsupported actions disabled and preserves real navigation", async ({ page }) => {
  await page.goto("/applications");
  await expect(page.getByRole("button", { name: "操作不可用" })).toBeDisabled();
  await page.getByRole("link", { name: /真实资源目录/ }).click();
  await expect(page.getByRole("heading", { name: "Resource Catalog" })).toBeVisible();
  await page.goto("/operations");
  const relatedProducts = page.locator(".px-support-links");
  for (const name of ["Runtime Profile", "Workflow", "Evidence", "Outcome"]) {
    await expect(relatedProducts.getByRole("link", { name: new RegExp(name) })).toBeVisible();
  }
  await page.goto("/usage");
  await expect(page.getByText("NOT_COLLECTED · 尚未采集", { exact: true })).toBeVisible();
  await expect(page.getByText("NOT_MEASURABLE · 数据来源缺失", { exact: true })).toBeVisible();
});

test("keeps all support pages reachable from the mobile navigation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/dashboard");
  const navigation = page.getByRole("navigation", { name: "移动端产品导航" });
  for (const [, heading] of pages) await expect(navigation.getByRole("link", { name: heading })).toBeVisible();
  await navigation.getByRole("link", { name: "帮助中心" }).focus();
  await expect(navigation.getByRole("link", { name: "帮助中心" })).toBeFocused();
  expect(await navigation.getByRole("link", { name: "帮助中心" }).evaluate((element) => getComputedStyle(element).outlineStyle)).not.toBe("none");
});
