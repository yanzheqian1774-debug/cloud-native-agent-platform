import { expect, test } from "@playwright/test";

const legacyProblem = {
  problemId: "legacy-problem:planning-only",
  displayCode: "OLD-001",
  name: "旧规划供应商质量问题",
  description: "仅属于 v0.2.1 规划来源",
  revision: 1,
  status: "PLAN_REVIEW",
  provenance: "v0.2.1 planning service",
  createdAt: "2026-09-01T00:00:00Z",
  updatedAt: "2026-09-01T00:00:00Z",
  tenantId: "legacy-tenant",
  securityDomain: "legacy-domain",
  principalId: "legacy-principal",
  currentPlanRevisionId: "legacy-plan-revision:1",
  planRevisions: [{
    planId: "legacy-plan:1",
    planRevisionId: "legacy-plan-revision:1",
    displayCode: "PLAN-OLD-001",
    revision: 1,
    status: "READY",
    approvalState: "PENDING",
    createdAt: "2026-09-01T00:00:00Z",
    updatedAt: "2026-09-01T00:00:00Z",
    knowledgeSnapshotId: "legacy-snapshot:1",
    capabilityGapCount: 0,
    canonicalDigest: "sha256:" + "a".repeat(64),
    summary: "旧规划计划",
    classification: "FORMAL",
    tasks: [],
    capabilityGaps: [],
    limitations: [],
    provenance: { provider: "fixture", model: "none", promptTemplateRevision: "1", schemaValidation: "PASS", ruleValidation: "PASS" },
  }],
  planningAttempts: [{ attemptId: "legacy-attempt:1", displayCode: "ATT-OLD-001", state: "SUCCEEDED", createdAt: "2026-09-01T00:00:00Z", knowledgeMode: "FIXED" }],
  clarificationAttempts: [],
  interpretations: [],
  humanDecisions: [],
  knowledge: { knowledgeBaseId: "legacy-kb:1", indexSnapshotId: "legacy-snapshot:1", indexManifestDigest: "sha256:" + "b".repeat(64), retrievalState: "READY", selectedCitationIds: [], citations: [] },
  selectedBlueprintId: null,
  blueprints: [],
  events: [],
  approval: null,
  timings: { problemAcceptanceMs: 1, retrievalMs: 1, controlledModelPlanningMs: 1, schemaAndRuleValidationMs: 1, comparisonAssemblyMs: 1, totalMs: 5 },
};

async function installRoutes(page: import("@playwright/test").Page, identity: { value: string | null }) {
  await page.route("**/api/workbench/v1/session", route => identity.value
    ? route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-session.v1", principal: { principalId: identity.value, tenantId: "tenant-a", securityDomain: "quality" }, session: { expiresAt: "2026-09-14T00:00:00Z", idleExpiresAt: "2026-09-14T00:00:00Z" }, csrfToken: "redacted-test-value" }) })
    : route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ reasonCode: "WORKBENCH_LOGIN_REQUIRED" }) }));
  await page.route("**/api/workbench/v1/problems", route => route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { problems: [] }, continuationIds: [] }) }));
  await page.route("**/api/internal/v0.2.1/problems", route => route.fulfill({ contentType: "application/json", body: JSON.stringify([legacyProblem]) }));
  await page.route("**/api/internal/v0.2.2/product/dashboard", route => route.fulfill({ contentType: "application/json", body: JSON.stringify({ resourceCount: 0, countsByKind: {}, countsByLifecycle: {}, attentionCount: 0, capabilityGapCount: 0, authority: "fixture", limitations: [] }) }));
  await page.route("**/api/internal/v0.2.2/product/digital-employee-templates", route => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.route("**/api/internal/v0.2.2/product/attention", route => route.fulfill({ contentType: "application/json", body: "[]" }));
}

test("uses only current session identity and keeps legacy planning out of trusted Problem reads", async ({ page }, testInfo) => {
  const identity = { value: "human:applicant" as string | null };
  const exactProblemReads: string[] = [];
  page.on("request", request => {
    if (/\/api\/workbench\/v1\/problems\//.test(request.url())) exactProblemReads.push(request.url());
  });
  await installRoutes(page, identity);
  await page.goto("/dashboard");
  await expect(page.getByLabel("当前可信身份 human:applicant")).toBeVisible();
  await expect(page.getByText("审核人员", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("全局搜索（暂未接线）")).toBeDisabled();
  await expect(page.getByText("⌘ K", { exact: true })).toHaveCount(0);
  await expect(page.locator(".px-notification")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "待处理事项", exact: true })).toBeVisible();

  const currentEntry = page.getByRole("link", { name: "提出业务问题", exact: true }).first();
  await expect(currentEntry).toHaveAttribute("href", "/work");
  const legacyEntry = page.getByRole("link", { name: "打开旧规划来源" });
  await expect(legacyEntry).toHaveAttribute("href", "/problems");
  await legacyEntry.click();
  await expect(page).toHaveURL(/\/problems$/);
  expect(exactProblemReads).toEqual([]);

  await page.goto("/dashboard");
  await expect(page.getByLabel("当前可信身份 human:applicant")).toBeVisible();
  identity.value = null;
  await Promise.all([
    page.waitForResponse(response => response.url().endsWith("/api/workbench/v1/session") && response.status() === 401),
    page.evaluate(() => document.dispatchEvent(new Event("visibilitychange"))),
  ]);
  await expect(page.getByText("未显示可信身份", { exact: true })).toBeVisible();
  await expect(page.getByText("human:applicant", { exact: true })).toHaveCount(0);
  identity.value = "human:applicant-refocused";
  await Promise.all([
    page.waitForResponse(response => response.url().endsWith("/api/workbench/v1/session") && response.status() === 200),
    page.evaluate(() => window.dispatchEvent(new Event("focus"))),
  ]);
  await expect(page.getByLabel("当前可信身份 human:applicant-refocused")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("w2a-session-failure-desktop.png"), fullPage: true });
});

test("shows honest controls with keyboard access and no overflow at 390px", async ({ page }, testInfo) => {
  const identity = { value: "human:independent-admin" as string | null };
  const writes: string[] = [];
  page.on("request", request => {
    if (request.method() !== "GET") writes.push(`${request.method()} ${request.url()}`);
  });
  await installRoutes(page, identity);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/tasks");
  await expect(page.getByLabel("当前可信身份 human:independent-admin")).toBeVisible();
  await expect(page.getByText("搜索、状态、业务问题和排序筛选暂未接线；上方状态页签可用。")).toBeVisible();
  for (const name of ["搜索计划（暂未接线）", "状态筛选（暂未接线）", "业务问题筛选（暂未接线）", "排序（暂未接线）"]) {
    await expect(page.getByLabel(name)).toBeDisabled();
  }
  const availableTab = page.getByRole("button", { name: "等待人工处理", exact: true });
  await availableTab.focus();
  await expect(availableTab).toBeFocused();
  expect(await availableTab.evaluate(element => getComputedStyle(element).outlineStyle)).not.toBe("none");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(writes).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("w2a-honest-controls-390.png"), fullPage: true });
});

test("business workbench creates a message draft before any write and supports complete replacement", async ({ page }, testInfo) => {
  const identity = { value: "human:applicant" as string | null };
  await installRoutes(page, identity);
  let createAttempts = 0;
  await page.route("**/api/workbench/v1/problems", async route => {
    if (route.request().method() === "POST") {
      createAttempts += 1;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ reasonCode: "WORKBENCH_UNAVAILABLE", requestId: "diagnostic:fixture" }) });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { problems: [] }, continuationIds: [] }) });
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/work");
  await expect(page.getByRole("heading", { name: "你希望解决什么问题？" })).toBeVisible();
  const composer = page.getByLabel("你希望解决什么问题？");
  await composer.fill("组合输入不应发送");
  await composer.dispatchEvent("keydown", { key: "Enter", code: "Enter", isComposing: true, keyCode: 229 });
  await expect(page.getByLabel("问题草稿卡片")).toHaveCount(0);
  expect(createAttempts).toBe(0);

  const original = "供应商交付延期。关键零部件连续延期，影响本季度客户交付。";
  await composer.fill(original);
  await composer.press("Enter");
  const draft = page.getByLabel("问题草稿卡片");
  await expect(draft).toBeVisible();
  await expect(draft.getByLabel("建议名称")).toHaveValue("供应商交付延期");
  await expect(draft.getByLabel("完整描述")).toHaveValue(original);
  expect(createAttempts).toBe(0);

  await draft.getByRole("button", { name: "修改", exact: true }).click();
  const replacement = page.getByLabel("完整替换草稿描述");
  await replacement.fill("关键零部件延期影响客户交付，需要明确恢复责任和时间。");
  await page.getByRole("button", { name: "更新草稿", exact: true }).click();
  await expect(draft.getByLabel("完整描述")).toHaveValue("关键零部件延期影响客户交付，需要明确恢复责任和时间。");
  await draft.getByRole("button", { name: "修改", exact: true }).click();
  await draft.getByLabel("建议名称").fill("供应商交付恢复");
  await draft.getByRole("button", { name: "确认创建", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("创建业务问题的结果暂时无法确认");
  await expect(page.getByText("diagnostic:fixture", { exact: true })).not.toBeVisible();
  await page.getByRole("alert").getByText("技术详情", { exact: true }).click();
  await expect(page.getByText("诊断 ID", { exact: true })).toBeVisible();
  await expect(page.getByText("diagnostic:fixture", { exact: true })).toBeVisible();
  await expect(draft.getByLabel("建议名称")).toHaveValue("供应商交付恢复");
  await expect(draft.getByLabel("完整描述")).toContainText("需要明确恢复责任和时间");
  expect(createAttempts).toBe(1);
  await page.screenshot({ path: testInfo.outputPath("w2b-create-error-preserves-input-1440.png"), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  const mobileComposer = page.getByLabel("你希望解决什么问题？");
  await mobileComposer.fill("移动端问题需要确认底部输入、确认与取消均可达。");
  await page.getByRole("button", { name: "发送", exact: true }).click();
  const submit = page.getByRole("button", { name: "确认创建", exact: true });
  await submit.focus();
  await expect(submit).toBeFocused();
  await expect(submit).toBeInViewport();
  await expect(page.getByRole("button", { name: "取消", exact: true })).toBeInViewport();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("w2b-create-form-390.png"), fullPage: true });
});
