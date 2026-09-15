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

const createdProblem = {
  scope: { namespace: "tenant-a", security_domain: "quality" },
  business_problem_id: "problem:conversation-1",
  revision_id: "problem-revision:conversation-1:1",
  revision: 1,
  predecessor_revision_id: null,
  title: "供应商交付恢复",
  description: "关键零部件延期影响客户交付，需要明确恢复责任和时间。",
  owner_id: "human:applicant",
  created_by: "human:applicant",
  created_at: "2026-09-14T00:20:00Z",
  digest: "sha256:" + "c".repeat(64),
};

const applicantContextKey = "human:applicant\u0000tenant-a\u0000quality";

type TestIdentity = { value: string | null; tenantId?: string; securityDomain?: string };

async function installRoutes(page: import("@playwright/test").Page, identity: TestIdentity) {
  await page.route("**/api/workbench/v1/session", route => identity.value
    ? route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-session.v1", principal: { principalId: identity.value, tenantId: identity.tenantId ?? "tenant-a", securityDomain: identity.securityDomain ?? "quality" }, session: { expiresAt: "2026-09-14T00:00:00Z", idleExpiresAt: "2026-09-14T00:00:00Z" }, csrfToken: "redacted-test-value" }) })
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
  await page.screenshot({ path: testInfo.outputPath("w2c-new-conversation-1440.png"), fullPage: true });
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
  await expect(draft.getByText("供应商交付延期", { exact: true })).toBeVisible();
  await expect(draft.getByLabel("建议名称")).toHaveCount(0);
  expect(createAttempts).toBe(0);
  await page.screenshot({ path: testInfo.outputPath("w2c-draft-confirm-1440.png"), fullPage: true });

  await draft.getByRole("button", { name: "修改", exact: true }).click();
  await expect(draft.getByLabel("建议名称")).toHaveValue("供应商交付延期");
  await expect(draft.getByLabel("完整描述")).toHaveValue(original);
  const independentSupplement = page.getByLabel("待处理补充（仅本页）");
  await expect(independentSupplement).toBeEnabled();
  await independentSupplement.fill("字段编辑期间准备的独立补充不得被描述替换覆盖。");
  await draft.getByLabel("建议名称").fill("字段编辑先保留");
  await draft.getByRole("button", { name: "使用输入框完整修改", exact: true }).click();
  await expect(draft.getByLabel("完整描述")).toHaveCount(0);
  await expect(draft.getByRole("button", { name: "确认创建", exact: true })).toHaveCount(0);
  const replacement = page.getByLabel("完整替换草稿描述");
  await expect(replacement).toHaveValue(original);
  await replacement.fill("这次替换应当取消，不得覆盖卡片字段。");
  await page.getByRole("button", { name: "取消修改", exact: true }).click();
  await expect(independentSupplement).toHaveValue("字段编辑期间准备的独立补充不得被描述替换覆盖。");
  await draft.getByRole("button", { name: "修改", exact: true }).click();
  await expect(draft.getByLabel("建议名称")).toHaveValue("字段编辑先保留");
  await expect(draft.getByLabel("完整描述")).toHaveValue(original);
  await draft.getByRole("button", { name: "使用输入框完整修改", exact: true }).click();
  await replacement.fill("关键零部件延期影响客户交付，需要明确恢复责任和时间。");
  await page.getByRole("button", { name: "采用草稿描述", exact: true }).click();
  await expect(independentSupplement).toHaveValue("字段编辑期间准备的独立补充不得被描述替换覆盖。");
  await draft.getByRole("button", { name: "修改", exact: true }).click();
  await expect(draft.getByLabel("建议名称")).toHaveValue("字段编辑先保留");
  await expect(draft.getByLabel("完整描述")).toHaveValue("关键零部件延期影响客户交付，需要明确恢复责任和时间。");
  await draft.getByLabel("建议名称").fill("供应商交付恢复");
  await page.screenshot({ path: testInfo.outputPath("w2c-draft-modified-1440.png"), fullPage: true });
  await draft.getByRole("button", { name: "采用字段修改", exact: true }).click();
  await draft.getByRole("button", { name: "确认创建", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("创建业务问题的结果暂时无法确认");
  await expect(page.getByText("diagnostic:fixture", { exact: true })).not.toBeVisible();
  await page.getByRole("alert").getByText("技术详情", { exact: true }).click();
  await expect(page.getByText("诊断 ID", { exact: true })).toBeVisible();
  await expect(page.getByText("diagnostic:fixture", { exact: true })).toBeVisible();
  await expect(draft.getByText("供应商交付恢复", { exact: true })).toBeVisible();
  await expect(draft.getByText("关键零部件延期影响客户交付，需要明确恢复责任和时间。", { exact: true })).toBeVisible();
  await expect(independentSupplement).toBeEnabled();
  await expect(independentSupplement).toHaveValue("字段编辑期间准备的独立补充不得被描述替换覆盖。");
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
  const cancelDraft = page.getByRole("button", { name: "取消草稿", exact: true });
  await expect(cancelDraft).toBeInViewport();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("w2b-create-form-390.png") });
  await cancelDraft.click();
  await expect(page.getByText("已取消本地草稿", { exact: false })).toBeVisible();
});

test("unknown create replays the exact payload and key while double activation stays single", async ({ page }, testInfo) => {
  const identity = { value: "human:applicant" as string | null };
  await installRoutes(page, identity);
  const attempts: Array<Record<string, unknown>> = [];
  await page.route("**/api/workbench/v1/problems", async route => {
    if (route.request().method() !== "POST") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { problems: [] }, continuationIds: [] }) });
      return;
    }
    attempts.push(route.request().postDataJSON());
    if (attempts.length === 1) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ reasonCode: "WORKBENCH_UNAVAILABLE", requestId: "diagnostic:unknown" }) });
      return;
    }
    await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { revision: createdProblem, creatorContinuation: { schemaVersion: "problem-creator-continuation.v1", relation: "PROBLEM_CREATOR", purpose: "CONTINUE_PROBLEM_READ", state: "AVAILABLE", expiresAt: "2026-09-14T01:20:00Z", continuationId: "continuation-ref." + "a".repeat(64) } }, continuationIds: [] }) });
  });

  await page.goto("/work");
  await page.getByLabel("你希望解决什么问题？").fill(createdProblem.description);
  await page.getByRole("button", { name: "发送", exact: true }).click();
  const draft = page.getByLabel("问题草稿卡片");
  await draft.getByRole("button", { name: "修改", exact: true }).click();
  await draft.getByLabel("建议名称").fill(createdProblem.title);
  await draft.getByRole("button", { name: "采用字段修改", exact: true }).click();
  const confirm = draft.getByRole("button", { name: "确认创建", exact: true });
  await confirm.evaluate((button: HTMLButtonElement) => { button.click(); button.click(); });
  await expect(draft.getByText("结果不确定", { exact: true })).toBeVisible();
  expect(attempts).toHaveLength(1);
  const unknownSupplement = page.getByLabel("待处理补充（仅本页）");
  await expect(unknownSupplement).toBeEnabled();
  await unknownSupplement.fill("结果未知期间新增的约束，只能页内保留。");
  await page.getByRole("button", { name: "保留补充", exact: true }).click();
  await expect(page.getByText("结果未知期间新增的约束，只能页内保留。", { exact: true })).toBeVisible();
  await expect(page.getByText("已保留，尚未采用", { exact: true })).toBeVisible();
  await draft.getByRole("button", { name: "恢复原创建结果", exact: true }).click();
  await expect(page.getByRole("heading", { name: "业务问题已创建", exact: true })).toBeVisible();
  await expect(draft.getByRole("button", { name: "确认创建", exact: true })).toHaveCount(0);
  expect(attempts).toHaveLength(2);
  expect(attempts[1]).toEqual(attempts[0]);
  await expect(page.getByText("结果未知期间新增的约束，只能页内保留。", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("w2c-created-after-recovery-1440.png"), fullPage: true });
});

test("an in-flight create keeps the independent composer and late success does not steal focus", async ({ page }, testInfo) => {
  const identity = { value: "human:applicant" as string | null };
  let releaseCreate!: () => void;
  const createGate = new Promise<void>(resolve => { releaseCreate = resolve; });
  const attempts: Array<Record<string, unknown>> = [];
  await installRoutes(page, identity);
  await page.route("**/api/workbench/v1/problems", async route => {
    if (route.request().method() !== "POST") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { problems: [] }, continuationIds: [] }) });
      return;
    }
    attempts.push(route.request().postDataJSON());
    await createGate;
    await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { revision: createdProblem, creatorContinuation: { schemaVersion: "problem-creator-continuation.v1", relation: "PROBLEM_CREATOR", purpose: "CONTINUE_PROBLEM_READ", state: "AVAILABLE", expiresAt: "2026-09-14T01:20:00Z", continuationId: "continuation-ref." + "e".repeat(64) } }, continuationIds: [] }) });
  });

  await page.goto("/work");
  await page.getByLabel("你希望解决什么问题？").fill(createdProblem.description);
  await page.getByRole("button", { name: "发送", exact: true }).click();
  await page.getByRole("button", { name: "确认创建", exact: true }).click();
  await expect(page.getByText("正在创建", { exact: true })).toBeVisible();
  const composer = page.getByLabel("待处理补充（仅本页）");
  await expect(composer).toBeEnabled();
  await composer.fill("创建响应到达前输入的新约束必须保留。");
  await composer.focus();
  releaseCreate();
  await expect(page.getByRole("heading", { name: "业务问题已创建", exact: true })).toBeVisible();
  await expect(composer).toHaveValue("创建响应到达前输入的新约束必须保留。");
  await expect(composer).toBeFocused();
  expect(attempts).toHaveLength(1);
  await page.screenshot({ path: testInfo.outputPath("w2e-create-late-response-preserves-supplement-1440.png"), fullPage: true });
});

test("cancel remains local and an upward reader receives a new-message affordance", async ({ page }) => {
  const identity = { value: "human:applicant" as string | null };
  let writes = 0;
  await installRoutes(page, identity);
  page.on("request", request => { if (request.method() !== "GET") writes += 1; });
  await page.goto("/work");
  const composer = page.getByLabel("你希望解决什么问题？");
  await composer.fill("取消的草稿不应写入正式 Problem。");
  await page.getByRole("button", { name: "发送", exact: true }).click();
  await page.getByLabel("问题草稿卡片").getByRole("button", { name: "取消草稿", exact: true }).click();
  await expect(page.getByText("已取消本地草稿，没有提交 Problem，也没有撤销任何服务器事实。", { exact: true })).toBeVisible();
  expect(writes).toBe(0);

  await composer.fill("长内容：" + "用于验证用户上滚阅读时不被卡片更新强制拉到底。".repeat(75));
  await page.getByRole("button", { name: "发送", exact: true }).click();
  const stream = page.locator(".px-message-stream");
  await stream.evaluate(element => { (element as HTMLElement).style.maxHeight = "200px"; element.scrollTop = 0; element.dispatchEvent(new Event("scroll")); });
  expect(await stream.evaluate(element => element.scrollHeight > element.clientHeight)).toBe(true);
  await page.getByLabel("问题草稿卡片").getByRole("button", { name: "修改", exact: true }).evaluate((button: HTMLButtonElement) => button.click());
  await expect(page.getByRole("button", { name: "有新消息，回到最新", exact: true })).toBeVisible();
  expect(await stream.evaluate(element => element.scrollTop)).toBe(0);
  expect(writes).toBe(0);
});

test("a changed principal, tenant, or security domain isolates local input and ignores an old create response", async ({ page }) => {
  const identity: TestIdentity = { value: "human:applicant-a", tenantId: "tenant-a", securityDomain: "quality" };
  let releaseCreate!: () => void;
  const createGate = new Promise<void>(resolve => { releaseCreate = resolve; });
  await installRoutes(page, identity);
  await page.route("**/api/workbench/v1/problems", async route => {
    if (route.request().method() !== "POST") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { problems: [] }, continuationIds: [] }) });
      return;
    }
    await createGate;
    await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { revision: { ...createdProblem, owner_id: "human:applicant-a", created_by: "human:applicant-a" }, creatorContinuation: { schemaVersion: "problem-creator-continuation.v1", relation: "PROBLEM_CREATOR", purpose: "CONTINUE_PROBLEM_READ", state: "AVAILABLE", expiresAt: "2026-09-14T01:20:00Z", continuationId: "continuation-ref." + "b".repeat(64) } }, continuationIds: [] }) });
  });

  await page.goto("/work");
  await page.getByLabel("你希望解决什么问题？").fill("旧主体的在途创建不得写入新主体对话。");
  await page.getByRole("button", { name: "发送", exact: true }).click();
  await page.getByRole("button", { name: "确认创建", exact: true }).click();
  await expect(page.getByText("正在创建", { exact: true })).toBeVisible();
  identity.securityDomain = "restricted";
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.getByRole("heading", { name: "请在当前可信会话重新开始", exact: true })).toBeVisible();
  await expect(page.locator(".px-task-summary-panel").getByText(createdProblem.title, { exact: true })).toHaveCount(0);
  releaseCreate();
  await page.waitForTimeout(100);
  await expect(page.getByRole("heading", { name: "业务问题已创建", exact: true })).toHaveCount(0);
  await expect(page.getByText("problem:conversation-1", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("你希望解决什么问题？")).toBeEnabled();
  await page.getByLabel("你希望解决什么问题？").fill("新安全域中的本地草稿。");
  await page.getByRole("button", { name: "发送", exact: true }).click();
  identity.tenantId = "tenant-b";
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.getByText("新安全域中的本地草稿。", { exact: true })).toHaveCount(0);
  await page.getByLabel("你希望解决什么问题？").fill("新租户中的本地草稿。");
  await page.getByRole("button", { name: "发送", exact: true }).click();
  identity.value = "human:applicant-b";
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.getByText("新租户中的本地草稿。", { exact: true })).toHaveCount(0);
});

test("switching Problems requires confirmation and does not carry page-only supplements", async ({ page }) => {
  const identity = { value: "human:applicant" as string | null };
  const secondProblem = { ...createdProblem, business_problem_id: "problem:conversation-2", revision_id: "problem-revision:conversation-2:1", title: "第二个正式问题", description: "第二个问题的权威描述。", digest: "sha256:" + "d".repeat(64) };
  await installRoutes(page, identity);
  await page.route("**/api/workbench/v1/problems", route => route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { problems: [createdProblem, secondProblem] }, continuationIds: [] }) }));
  await page.route(/\/api\/workbench\/v1\/problems\/problem%3Aconversation-(1|2)$/, route => {
    const revision = route.request().url().includes("conversation-2") ? secondProblem : createdProblem;
    return route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { problem: { scope: revision.scope, business_problem_id: revision.business_problem_id, owner_id: revision.owner_id, current_state: "OPEN", aggregate_version: 1, current_revision_id: revision.revision_id, created_by: revision.created_by, created_at: revision.created_at, updated_at: revision.created_at }, revisions: [revision], lifecycle: [] }, continuationIds: [] }) });
  });
  await page.route("**/api/workbench/v1/problems/*/criteria-sets", route => route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { revisions: [] }, continuationIds: [] }) }));
  await page.route("**/api/workbench/v1/problems/*/criteria", route => route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { revisions: [] }, continuationIds: [] }) }));

  await page.goto("/work?problem=problem%3Aconversation-1");
  const composer = page.getByLabel("待处理补充（仅本页）");
  await composer.fill("只属于第一个问题的页内补充。");
  await page.getByText("业务问题与新建入口", { exact: true }).click();
  page.once("dialog", async dialog => {
    expect(dialog.message()).toContain("未保存修改或页内补充");
    await dialog.accept();
  });
  await page.getByRole("button", { name: /第二个正式问题/ }).click();
  await expect(page).toHaveURL(/problem%3Aconversation-2/);
  await expect(page.getByRole("heading", { name: "读取成功", exact: true })).toBeVisible();
  await expect(page.locator("#formal-problem-message").getByText(secondProblem.description, { exact: true })).toBeVisible();
  await expect(composer).toHaveValue("");
  await expect(page.getByText("只属于第一个问题的页内补充。", { exact: true })).toHaveCount(0);
});

test("created problem continues through pending approval to a fresh exact read", async ({ page }, testInfo) => {
  const identity = { value: "human:applicant" as string | null };
  let grantState: "PENDING" | "APPROVED" = "PENDING";
  let exactReadFails = false;
  let exactReads = 0;
  let delayGrantInspect = false;
  let releaseGrantInspect!: () => void;
  let grantInspectStarted!: () => void;
  const grantInspectGate = new Promise<void>(resolve => { releaseGrantInspect = resolve; });
  const grantInspectInFlight = new Promise<void>(resolve => { grantInspectStarted = resolve; });
  await installRoutes(page, identity);
  await page.route("**/api/workbench/v1/problems", async route => {
    if (route.request().method() === "POST") {
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { revision: createdProblem, creatorContinuation: { schemaVersion: "problem-creator-continuation.v1", relation: "PROBLEM_CREATOR", purpose: "CONTINUE_PROBLEM_READ", state: "AVAILABLE", expiresAt: "2026-09-14T01:20:00Z", continuationId: "continuation-ref." + "d".repeat(64) } }, continuationIds: [] }) });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { problems: [createdProblem] }, continuationIds: [] }) });
  });
  await page.route("**/api/workbench/v1/problems/problem%3Aconversation-1", async route => {
    exactReads += 1;
    if (exactReadFails) {
      await route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ reasonCode: "AUTHORIZATION_DENIED" }) });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { problem: { scope: createdProblem.scope, business_problem_id: createdProblem.business_problem_id, owner_id: createdProblem.owner_id, current_state: "OPEN", aggregate_version: 1, current_revision_id: createdProblem.revision_id, created_by: createdProblem.created_by, created_at: createdProblem.created_at, updated_at: createdProblem.created_at }, revisions: [createdProblem], lifecycle: [] }, continuationIds: [] }) });
  });
  await page.route("**/api/workbench/v1/authorization/grant-requests", async route => {
    await route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ requestId: "grant-request:conversation-1", state: "PENDING", aggregateVersion: 1, submittedAt: "2026-09-14T00:22:00Z", purpose: "CONTINUE_PROBLEM_READ", requestedActions: ["READ"] }) });
  });
  await page.route("**/api/workbench/v1/authorization/grant-requests/grant-request%3Aconversation-1", async route => {
    if(delayGrantInspect){grantInspectStarted();await grantInspectGate}
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ requestId: "grant-request:conversation-1", state: grantState, aggregateVersion: grantState === "PENDING" ? 1 : 2, submittedAt: "2026-09-14T00:22:00Z", purpose: "CONTINUE_PROBLEM_READ", requestedActions: ["READ"] }) });
  });

  await page.goto("/work");
  await page.getByLabel("你希望解决什么问题？").fill(createdProblem.description);
  await page.getByRole("button", { name: "发送", exact: true }).click();
  await page.getByRole("button", { name: "确认创建", exact: true }).click();
  await page.getByRole("button", { name: "申请查看权限", exact: true }).click();
  await expect(page.getByText("等待管理员处理", { exact: true })).toBeVisible();
  const waitingComposer = page.getByLabel("待处理补充（仅本页）");
  await expect(waitingComposer).toBeEnabled();
  await expect(page.getByText("尚未修改正式问题，管理员不会自动收到", { exact: false })).toBeVisible();
  const pendingText = "等待审批期间补充：同时核对恢复责任与日期。";
  await waitingComposer.fill(pendingText);
  expect(exactReads).toBe(0);
  const desktopSummary = page.locator(".px-task-summary-panel");
  await expect(desktopSummary.getByRole("heading", { name: createdProblem.title, exact: true })).toBeVisible();
  await expect(desktopSummary.getByText("获得查看权限后显示问题详情。", { exact: true })).toBeVisible();
  await expect(desktopSummary.getByText("授权状态", { exact: true })).toBeVisible();
  await expect(desktopSummary.getByText("内容读取", { exact: true })).toBeVisible();
  await expect(desktopSummary.getByText("尚未读取", { exact: true })).toBeVisible();
  await expect(desktopSummary.getByRole("heading", { name: "等待审批", exact: true })).toBeVisible();
  await expect(desktopSummary.getByText("grant-request:conversation-1", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("w2c-waiting-authorization-1440.png"), fullPage: true });
  const stream = page.locator(".px-message-stream");
  await stream.evaluate(element => { (element as HTMLElement).style.maxHeight = "180px"; element.scrollTop = 0; element.dispatchEvent(new Event("scroll")); });
  await waitingComposer.focus();
  grantState = "APPROVED";
  delayGrantInspect = true;
  const refreshButton = page.getByRole("button", { name: "刷新授权状态", exact: true });
  await refreshButton.click();
  await grantInspectInFlight;
  const userFocusTarget = page.locator(".px-problem-switcher > summary");
  await userFocusTarget.click();
  await expect(userFocusTarget).toBeFocused();
  const scrollAfterDispatch = await stream.evaluate(element => element.scrollTop);
  releaseGrantInspect();
  await expect(page.getByRole("heading", { name: "读取成功", exact: true })).toBeVisible();
  await expect(page.locator("#authorization-message").getByText("问题详情已读取成功", { exact: false })).toBeVisible();
  await expect(waitingComposer).toHaveValue(pendingText);
  await expect(userFocusTarget).toBeFocused();
  expect(await stream.evaluate(element => element.scrollTop)).toBe(scrollAfterDispatch);
  await expect(desktopSummary.getByText(pendingText, { exact: true })).toHaveCount(0);
  expect(exactReads).toBe(1);
  const formalProblem = page.locator("#formal-problem-message");
  await expect(formalProblem.getByText("修改此问题需要另行授权", { exact: false })).toBeVisible();
  await expect(formalProblem.getByText("READ 不隐含 REVISE。", { exact: false })).toBeHidden();
  await formalProblem.getByText("技术详情", { exact: true }).click();
  await expect(formalProblem.getByText("READ 不隐含 REVISE。", { exact: false })).toBeVisible();
  await expect(desktopSummary.getByText(createdProblem.description, { exact: true })).toBeVisible();
  await expect(desktopSummary.getByText("读取成功", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "保留补充", exact: true }).click();
  await expect(page.getByText(pendingText, { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("w2c-approved-exact-read-1440.png"), fullPage: true });
  await page.reload();
  await expect(page.getByRole("heading", { name: "已恢复正式业务记录", exact: true })).toBeVisible();
  await page.getByText("查看创建事实", { exact: true }).click();
  await expect(page.getByText("不是恢复的聊天历史", { exact: false })).toBeVisible();
  expect(exactReads).toBe(2);
  await page.setViewportSize({ width: 390, height: 844 });
  const summaryTrigger = page.getByRole("button", { name: "本任务", exact: true });
  const triggerBox = await summaryTrigger.boundingBox();
  expect(triggerBox?.width).toBeGreaterThanOrEqual(350);
  expect(triggerBox?.height).toBeGreaterThanOrEqual(48);
  await summaryTrigger.click();
  const drawer = page.getByRole("dialog", { name: "本任务" });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByText(createdProblem.description, { exact: true })).toBeVisible();
  await expect(drawer.getByRole("button", { name: "关闭本任务", exact: true })).toBeFocused();
  expect(await drawer.evaluate(node => node.matches(":modal"))).toBe(true);
  await page.getByRole("button", { name: "刷新授权状态", exact: true }).evaluate(button => (button as HTMLButtonElement).focus());
  await expect(drawer.getByRole("button", { name: "关闭本任务", exact: true })).toBeFocused();
  await page.keyboard.press("Tab");
  expect(await drawer.evaluate(node => node.contains(document.activeElement))).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("w2d-task-summary-drawer-390x844.png") });
  await drawer.getByRole("button", { name: "关闭本任务", exact: true }).click();
  await expect(summaryTrigger).toBeFocused();
  exactReadFails = true;
  await page.getByRole("button", { name: "刷新授权状态", exact: true }).click();
  await summaryTrigger.click();
  await expect(drawer.getByText("暂时无法读取", { exact: true })).toBeVisible();
  await expect(drawer.getByText(createdProblem.description, { exact: true })).toHaveCount(0);
  expect(exactReads).toBe(3);
});

test("a rejected authorization card does not perform an exact read", async ({ page }) => {
  const identity = { value: "human:applicant" as string | null };
  let exactReads = 0;
  await installRoutes(page, identity);
  await page.addInitScript(({ problemId, contextKey }) => {
    sessionStorage.setItem(`impl299.authorization.${problemId}`, JSON.stringify({ contextKey, state: { request: { requestId: "grant-request:rejected", state: "REJECTED", aggregateVersion: 2, submittedAt: "2026-09-14T00:22:00Z", purpose: "CONTINUE_PROBLEM_READ", requestedActions: ["READ"] } } }));
  }, { problemId: createdProblem.business_problem_id, contextKey: applicantContextKey });
  await page.route("**/api/workbench/v1/problems", route => route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { problems: [createdProblem] }, continuationIds: [] }) }));
  await page.route("**/api/workbench/v1/problems/problem%3Aconversation-1", route => { exactReads += 1; return route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ reasonCode: "AUTHORIZATION_DENIED" }) }); });
  await page.route("**/api/workbench/v1/authorization/grant-requests/grant-request%3Arejected", route => route.fulfill({ contentType: "application/json", body: JSON.stringify({ requestId: "grant-request:rejected", state: "REJECTED", aggregateVersion: 2, submittedAt: "2026-09-14T00:22:00Z", purpose: "CONTINUE_PROBLEM_READ", requestedActions: ["READ"] }) }));
  await page.goto("/work?problem=problem%3Aconversation-1&request=grant-request%3Arejected");
  await expect(page.getByLabel("业务问题对话").getByText("已拒绝", { exact: true })).toBeVisible();
  await expect(page.getByLabel("业务问题对话").getByText("页面不会读取问题详情", { exact: false })).toBeVisible();
  expect(exactReads).toBe(0);
});

test("an expired creator continuation is explicit and does not read protected content", async ({ page }) => {
  const identity = { value: "human:applicant" as string | null };
  let exactReads = 0;
  await installRoutes(page, identity);
  await page.addInitScript(({ problemId, contextKey }) => { sessionStorage.setItem(`impl299.authorization.${problemId}`, JSON.stringify({ contextKey, state: { continuation: { schemaVersion: "problem-creator-continuation.v1", relation: "PROBLEM_CREATOR", purpose: "CONTINUE_PROBLEM_READ", state: "EXPIRED", expiresAt: "2026-09-13T23:00:00Z" } } })); }, { problemId: createdProblem.business_problem_id, contextKey: applicantContextKey });
  await page.route("**/api/workbench/v1/problems", route => route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { problems: [createdProblem] }, continuationIds: [] }) }));
  await page.route("**/api/workbench/v1/problems/problem%3Aconversation-1", route => { exactReads += 1; return route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ reasonCode: "AUTHORIZATION_DENIED" }) }); });
  await page.goto("/work?problem=problem%3Aconversation-1");
  await expect(page.getByLabel("业务问题对话").getByText("申请窗口已过期", { exact: true })).toBeVisible();
  await expect(page.getByText("不会自动延长窗口、撤销创建或换新标识重建", { exact: false })).toBeVisible();
  expect(exactReads).toBe(0);
});

test("a hidden Problem 404 preserves the non-disclosure boundary", async ({ page }) => {
  const identity = { value: "human:applicant" as string | null };
  await installRoutes(page, identity);
  await page.route("**/api/workbench/v1/problems/problem%3Ahidden**", route => route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ reasonCode: "RESOURCE_NOT_FOUND", requestId: "diagnostic:hidden" }) }));
  await page.goto("/work?problem=problem%3Ahidden");
  await expect(page.getByRole("alert")).toContainText("该内容可能不存在，也可能对当前会话不可见");
  await expect(page.getByText("diagnostic:hidden", { exact: true })).not.toBeVisible();
});

test("an unbound request id is ignored for the current session and Problem", async ({ page }) => {
  const identity = { value: "human:applicant" as string | null };
  let requestInspections = 0;
  await installRoutes(page, identity);
  await page.route("**/api/workbench/v1/problems", route => route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { problems: [createdProblem] }, continuationIds: [] }) }));
  await page.route("**/api/workbench/v1/problems/problem%3Aconversation-1", route => route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ reasonCode: "AUTHORIZATION_DENIED" }) }));
  await page.route("**/api/workbench/v1/problems/problem%3Aconversation-1/criteria-sets", route => route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { revisions: [] }, continuationIds: [] }) }));
  await page.route("**/api/workbench/v1/problems/problem%3Aconversation-1/criteria", route => route.fulfill({ contentType: "application/json", body: JSON.stringify({ schemaVersion: "workbench-operation.v1", result: { revisions: [] }, continuationIds: [] }) }));
  await page.route("**/api/workbench/v1/authorization/grant-requests/grant-request%3Aforeign", route => { requestInspections += 1; return route.fulfill({ contentType: "application/json", body: JSON.stringify({ requestId: "grant-request:foreign", state: "APPROVED", aggregateVersion: 9, submittedAt: "2026-09-14T00:22:00Z", purpose: "CONTINUE_PROBLEM_READ", requestedActions: ["READ"] }) }); });
  await page.goto("/work?problem=problem%3Aconversation-1&request=grant-request%3Aforeign");
  await expect(page.getByText("链接中的申请编号不属于当前会话与问题", { exact: false })).toBeVisible();
  expect(requestInspections).toBe(0);
  await expect(page.getByText("grant-request:foreign", { exact: true })).toHaveCount(0);
});
