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
const primaryRoutes = ["/dashboard", "/work", "/digital-employees", "/agent-center", "/skills", "/mcp", "/knowledge", "/workflow-definitions", "/runtime-profiles", "/evidence", "/outcomes", ...pages.filter(([route]) => route !== "/agent-center").map(([route]) => route)] as const;
const journeys = [
  { launch: "业务闭环", name: "业务闭环总览演示路径", steps: ["业务问题", "成功标准", "已批准 Plan", "数字员工", "Skill", "MCP", "Knowledge", "Workflow", "Runtime / Attempt", "Evidence", "Outcome"] },
  { launch: "数字员工装配", name: "数字员工装配演示路径", steps: ["数字员工", "Agent Definition", "Skill 绑定", "MCP 端点边界", "Knowledge 绑定", "Workflow 定义", "Runtime 配置", "Evidence 入口"] },
  { launch: "平台治理", name: "平台治理与运营演示路径", steps: ["首页", "权限中心", "安全中心", "运维监控", "模型中心", "费用与使用量", "系统设置", "帮助中心"] },
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

test("keeps all nineteen primary surfaces responsive and restores heading focus", async ({ page }) => {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    for (const route of primaryRoutes) {
      await page.goto(route);
      await expect(page.locator("main h1").first()).toBeVisible();
      await expect(page.locator("main h1").first()).toBeFocused();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
  }
});

for (const journey of journeys) test(`navigates the repeatable ${journey.launch} journey with browser history`, async ({ page }) => {
  await page.goto("/dashboard");
  await page.getByRole("navigation", { name: "可重复演示路径" }).getByRole("link", { name: journey.launch, exact: true }).click();
  const rail = page.getByRole("navigation", { name: journey.name });
  for (let index = 0; index < journey.steps.length; index += 1) {
    await expect(rail.getByText(`第 ${index + 1} / ${journey.steps.length} 步`, { exact: false })).toBeVisible();
    await expect(rail.getByRole("link", { name: journey.steps[index], exact: true })).toHaveAttribute("aria-current", "step");
    if (index < journey.steps.length - 1) await rail.getByRole("link", { name: "下一步", exact: true }).click();
  }
  await page.goBack();
  await expect(rail.getByText(`第 ${journey.steps.length - 1} / ${journey.steps.length} 步`, { exact: false })).toBeVisible();
  await rail.getByRole("link", { name: "上一步", exact: true }).click();
  await expect(page.locator("main h1").first()).toBeFocused();
});
