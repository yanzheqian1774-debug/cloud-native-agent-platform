import { expect, test, type Page, type Route } from "@playwright/test";

const digest = (value: string) => value.repeat(64);
const employeeSummary = {
  employeeDefinitionId: "employee:quality",
  employeeDefinitionRevisionId: "employee-revision:1",
  employeeDefinitionDigest: digest("e"),
  role: "供应商质量负责人",
  publicationState: "PUBLISHED",
};
const employee = {
  ...employeeSummary,
  resourceKind: "DIGITAL_EMPLOYEE_DEFINITION",
  responsibilities: ["审查供应商质量工作"],
  members: [
    { kind: "AGENT", resourceId: "agent:quality", revisionId: "agent-revision:1", digest: digest("a") },
    { kind: "RUNTIME_PROFILE", resourceId: "runtime-profile:native", revisionId: "runtime-profile-revision:1", digest: digest("b") },
  ],
};
const agentSummary = {
  definitionId: "agent:quality",
  name: "质量分析 Agent",
  revisionId: "agent-revision:1",
  digest: digest("a"),
  title: "质量分析员",
  enabled: true,
  archived: false,
};
const agent = {
  definitionId: "agent:quality",
  revisionId: "agent-revision:1",
  digest: digest("a"),
  name: "质量分析 Agent",
  role: {
    title: "质量分析员",
    duties: ["分析质量异常"],
    businessPurpose: "形成可核对的质量分析",
    capabilities: ["supplier-quality-analysis"],
  },
};
const instance = (id: string, definition = employee) => ({
  instanceId: id,
  employeeDefinition: {
    authorityKind: "DIGITAL_EMPLOYEE_DEFINITION_V1",
    employeeDefinitionId: definition.employeeDefinitionId,
    employeeDefinitionRevisionId: definition.employeeDefinitionRevisionId,
    digest: definition.employeeDefinitionDigest,
  },
  ownerId: "owner:quality",
  organizationId: "tenant-a",
  lifecycle: "ENABLED",
  execution: { state: "UNAVAILABLE", reasonCode: "EXECUTION_NOT_ASSEMBLED" },
  health: { state: "UNAVAILABLE", reasonCode: "HEALTH_NOT_ASSEMBLED" },
});
const assignment = {
  assignmentId: "assignment:quality",
  instanceId: "instance:quality",
  assigneeId: "team:quality",
  businessRole: "质量工作分配",
  lifecycle: "ACTIVE",
  effectiveFrom: "2026-09-09T00:00:00Z",
  effectiveUntil: null,
  binding: { state: "UNAVAILABLE", reasonCode: "WORKFLOW_BINDING_NOT_ASSEMBLED" },
};
const placement = {
  placementId: "placement:quality",
  requestId: "placement-request:quality",
  decision: "PLACED",
  runtimeInstanceId: "runtime-instance:quality",
  policyVersion: "policy:1",
  compatibilityFacts: ["native-compatible"],
  limitationCodes: [],
  decidedAt: "2026-09-09T00:00:00Z",
  digest: digest("c"),
  binding: {
    instanceId: "instance:quality",
    assignmentId: "assignment:quality",
    attemptId: "attempt:quality",
    agentInstanceId: "agent-instance:quality",
  },
};

const envelope = (result: unknown) => ({
  schemaVersion: "workbench-operation.v1",
  result,
  continuationIds: [],
});

type AdapterOptions = {
  onSession?: (route: Route) => Promise<void>;
  onInstance?: (route: Route, id: string) => Promise<void>;
  onDefinition?: (route: Route, id: string, revision: string) => Promise<void>;
  onPlacement?: (route: Route) => Promise<void>;
  onCreate?: (route: Route) => Promise<void>;
  onLifecycle?: (route: Route, action: "VALIDATE" | "APPROVE" | "PUBLISH") => Promise<void>;
};

async function installAdapter(page: Page, options: AdapterOptions = {}) {
  await page.route("**/api/workbench/v1/**", async route => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path.endsWith("/session")) {
      if (options.onSession) return options.onSession(route);
      return route.fulfill({ json: {
        schemaVersion: "workbench-session.v1",
        principal: { principalId: "human:quality", tenantId: "tenant-a", securityDomain: "quality" },
        session: { expiresAt: "2026-09-15T00:00:00Z", idleExpiresAt: "2026-09-14T23:00:00Z" },
        csrfToken: "csrf-test-token",
      } });
    }
    if (path.endsWith("/employees") && route.request().method() === "POST") {
      if (options.onCreate) return options.onCreate(route);
      const body = route.request().postDataJSON();
      return route.fulfill({ status: 201, json: envelope({
        resourceKind: "DIGITAL_EMPLOYEE_DEFINITION",
        employeeDefinitionId: body.employeeDefinitionId,
        employeeDefinitionRevisionId: body.employeeDefinitionRevisionId,
        employeeDefinitionDigest: digest("e"),
        aggregateVersion: 1,
        lifecycleState: "DRAFT",
      }) });
    }
    if (route.request().method() === "POST" && /\/(validation|approvals|publication)$/.test(path)) {
      const action = path.endsWith("/validation") ? "VALIDATE" : path.endsWith("/approvals") ? "APPROVE" : "PUBLISH";
      if (options.onLifecycle) return options.onLifecycle(route, action);
      const state = action === "VALIDATE" ? "VALIDATED" : action === "APPROVE" ? "APPROVED" : "PUBLISHED";
      return route.fulfill({ json: envelope({
        resourceKind: "DIGITAL_EMPLOYEE_DEFINITION",
        employeeDefinitionId: employee.employeeDefinitionId,
        employeeDefinitionRevisionId: employee.employeeDefinitionRevisionId,
        employeeDefinitionDigest: employee.employeeDefinitionDigest,
        aggregateVersion: action === "VALIDATE" ? 2 : action === "APPROVE" ? 3 : 4,
        lifecycleState: state,
      }) });
    }
    if (path.endsWith("/employees") && route.request().method() === "GET") {
      return route.fulfill({ json: envelope({ items: [employeeSummary], nextCursor: "employee-page-2" }) });
    }
    if (path.includes("/employees/") && path.includes("/revisions/")) {
      const [, id = "", revision = ""] = path.match(/\/employees\/(.+)\/revisions\/(.+)$/) ?? [];
      if (options.onDefinition) return options.onDefinition(route, decodeURIComponent(id), decodeURIComponent(revision));
      return route.fulfill({ json: envelope(employee) });
    }
    if (path.endsWith("/agents")) {
      return route.fulfill({ json: envelope({ items: [agentSummary], nextCursor: "agent-page-2" }) });
    }
    if (path.includes("/agents/") && path.includes("/revisions/")) {
      return route.fulfill({ json: envelope(agent) });
    }
    if (path.includes("/placements/")) {
      if (options.onPlacement) return options.onPlacement(route);
      return route.fulfill({ json: envelope(placement) });
    }
    if (path.includes("/assignments/")) return route.fulfill({ json: envelope(assignment) });
    if (path.includes("/instances/")) {
      const id = decodeURIComponent(path.split("/instances/")[1]);
      if (options.onInstance) return options.onInstance(route, id);
      return route.fulfill({ json: envelope(instance(id)) });
    }
    return route.fulfill({ status: 404, json: { reasonCode: "WORKBENCH_ROUTE_NOT_FOUND" } });
  });
}

test("TEST_ADAPTER uses trusted BFF reads and restores the exact work chain at 390px", async ({ page }) => {
  let instanceReads = 0;
  const privateRequests: string[] = [];
  page.on("request", request => {
    if (request.url().includes("/api/internal/")) privateRequests.push(request.url());
  });
  await installAdapter(page, {
    onInstance: async (route, id) => {
      instanceReads += 1;
      await route.fulfill({ json: envelope(instance(id)) });
    },
  });
  await page.setViewportSize({ width: 390, height: 844 });
  const query = new URLSearchParams({
    panel: "work",
    detail: "open",
    instanceId: "instance:quality",
    assignmentId: "assignment:quality",
    placementId: "placement:quality",
    attemptId: "attempt:quality",
    agentInstanceId: "agent-instance:quality",
  });
  await page.goto(`/digital-employees?${query}`);
  await expect(page.getByLabel("Placement 权威详情")).toContainText("runtime-instance:quality");
  await expect(page.getByLabel("分别核实的工作对象")).toContainText("placement:quality");
  await expect(page.getByText("执行、证据与结果尚未接通")).toBeVisible();
  await expect(page.getByText("不推导在线状态")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.reload();
  await expect(page.getByLabel("Placement 权威详情")).toBeVisible();
  expect(instanceReads).toBeGreaterThanOrEqual(2);
  expect(privateRequests).toEqual([]);
});

test("TEST_ADAPTER late Instance response cannot overwrite the new exact object", async ({ page }) => {
  await installAdapter(page, {
    onInstance: async (route, id) => {
      if (id === "instance:old") await new Promise(resolve => setTimeout(resolve, 250));
      await route.fulfill({ json: envelope(instance(id)) });
    },
  });
  await page.goto("/digital-employees");
  await page.getByRole("button", { name: /供应商质量负责人/ }).click();
  await page.getByRole("button", { name: "实例", exact: true }).click();
  await page.getByText("使用已知实例 ID 查询", { exact: true }).click();
  await page.getByLabel("实例 ID").fill("instance:old");
  await page.getByRole("button", { name: "读取并验证归属" }).click();
  await page.getByLabel("实例 ID").fill("instance:new");
  await page.getByRole("button", { name: "读取并验证归属" }).click();
  await expect(page.locator(".employee-read-result")).toContainText("instance:new");
  await page.waitForTimeout(300);
  await expect(page.locator(".employee-read-result")).not.toContainText("instance:old");
});

test("TEST_ADAPTER LIST discovery does not bypass denied exact READ", async ({ page }) => {
  await installAdapter(page, {
    onDefinition: async route => {
      await route.fulfill({ status: 404, json: { reasonCode: "EMPLOYEE_NOT_FOUND" } });
    },
  });
  await page.goto("/digital-employees");
  await expect(page.getByRole("button", { name: /供应商质量负责人/ })).toBeVisible();
  await page.getByRole("button", { name: /供应商质量负责人/ }).click();
  await expect(page.getByRole("alert").filter({ hasText: "详情读取未完成" })).toContainText("资源不可用或当前访问未获授权");
  await expect(page.locator(".employee-profile")).toHaveCount(0);
});

test("TEST_ADAPTER reports missing trusted session without private fallback", async ({ page }) => {
  await page.route("**/api/workbench/v1/**", route => route.fulfill({
    status: 401,
    json: { reasonCode: "AUTHENTICATION_REQUIRED" },
  }));
  await page.goto("/digital-employees");
  await expect(page.getByRole("alert").first()).toContainText("需要可信 Workbench session");
});

test("TEST_ADAPTER rejects a Placement response with mismatched parent coordinates", async ({ page }) => {
  await installAdapter(page, {
    onPlacement: async route => {
      await route.fulfill({ json: envelope({
        ...placement,
        binding: { ...placement.binding, attemptId: "attempt:other" },
      }) });
    },
  });
  const query = new URLSearchParams({
    panel: "work",
    instanceId: "instance:quality",
    assignmentId: "assignment:quality",
    placementId: "placement:quality",
    attemptId: "attempt:quality",
    agentInstanceId: "agent-instance:quality",
  });
  await page.goto(`/digital-employees?${query}`);
  await expect(page.getByRole("alert")).toContainText("PLACEMENT_BINDING_IDENTITY_MISMATCH");
  await expect(page.getByLabel("Placement 权威详情")).toHaveCount(0);
});

test("TEST_ADAPTER rejects the same Definition ID with a different revision digest", async ({ page }) => {
  const wrong = { ...employee, employeeDefinitionDigest: digest("f") };
  await installAdapter(page, {
    onDefinition: async route => route.fulfill({ json: envelope(wrong) }),
  });
  await page.goto("/digital-employees");
  await page.getByRole("button", { name: /供应商质量负责人/ }).click();
  await expect(page.getByRole("alert").filter({ hasText: "详情读取未完成" })).toContainText("EMPLOYEE_DEFINITION_IDENTITY_MISMATCH");
  await expect(page.locator(".employee-profile")).toHaveCount(0);
});

test("TEST_ADAPTER consumes Employee and Agent nextCursor without treating a page as complete", async ({ page }) => {
  let employeeCursor = "";
  let agentCursor = "";
  await installAdapter(page);
  await page.route("**/api/workbench/v1/employees?*", async route => {
    const url = new URL(route.request().url());
    employeeCursor = url.searchParams.get("cursor") ?? employeeCursor;
    const second = { ...employeeSummary, employeeDefinitionId: "employee:second", role: "第二页员工" };
    await route.fulfill({ json: envelope(url.searchParams.has("cursor")
      ? { items: [second] }
      : { items: [employeeSummary], nextCursor: "employee-page-2" }) });
  });
  await page.route("**/api/workbench/v1/agents?*", async route => {
    const url = new URL(route.request().url());
    agentCursor = url.searchParams.get("cursor") ?? agentCursor;
    const second = { ...agentSummary, definitionId: "agent:second", name: "第二页 Agent" };
    await route.fulfill({ json: envelope(url.searchParams.has("cursor")
      ? { items: [second] }
      : { items: [agentSummary], nextCursor: "agent-page-2" }) });
  });
  await page.goto("/digital-employees");
  await page.getByRole("button", { name: "加载下一页" }).click();
  await expect(page.getByRole("button", { name: /第二页员工/ })).toBeVisible();
  expect(employeeCursor).toBe("employee-page-2");
  await page.getByRole("button", { name: "＋ 创建数字员工" }).click();
  await page.getByRole("button", { name: "加载更多 Agent" }).click();
  await expect(page.getByText("第二页 Agent")).toBeVisible();
  expect(agentCursor).toBe("agent-page-2");
});

test("TEST_ADAPTER groups 50 records by employee, selects revisions explicitly, and clears hidden detail", async ({ page }) => {
  const summaries = Array.from({ length: 50 }, (_, index) => ({
    ...employeeSummary,
    employeeDefinitionId: index < 2 ? "employee:multi-version" : `employee:record:${String(index).padStart(2, "0")}`,
    employeeDefinitionRevisionId: index < 2 ? `employee-revision:multi:${index + 1}` : `employee-revision:${index}`,
    employeeDefinitionDigest: digest(index % 10 === 0 ? "a" : index % 10 === 1 ? "b" : "e"),
    role: index === 2 ? "负责超长中文供应链质量异常复核与跨部门协同跟进的数字员工角色" : index < 2 ? "同一员工的多版本角色" : index < 4 ? "同名员工角色" : `数字员工角色 ${index}`,
    publicationState: index % 2 === 0 ? "PUBLISHED" : "NOT_PUBLISHED",
  }));
  await installAdapter(page, {
    onDefinition: async (route, id, revision) => {
      const summary = summaries.find(item => item.employeeDefinitionId === id && item.employeeDefinitionRevisionId === revision) ?? employeeSummary;
      await route.fulfill({ json: envelope({ ...employee, ...summary, responsibilities: ["保持长中文职责摘要清晰可读"] }) });
    },
  });
  await page.route("**/api/workbench/v1/employees?*", route => {
    const next = new URL(route.request().url()).searchParams.has("cursor");
    return route.fulfill({ json: envelope(next
      ? { items: summaries.map((item, index) => ({ ...item, employeeDefinitionId: `employee:page-two:${index}` })) }
      : { items: summaries, nextCursor: "employee-page-2" }) });
  });
  await page.goto("/digital-employees");
  await expect(page.getByLabel("当前加载范围")).toContainText("49 个已加载员工");
  await expect(page.getByLabel("当前加载范围")).toContainText("50 个已加载修订");
  await expect(page.getByLabel("同一员工的多版本角色 选择版本")).toHaveCount(1);
  await expect(page.locator(".employee-collection-row").filter({ hasText: "负责超长中文供应链" }).getByRole("combobox")).toHaveCount(0);
  await page.getByLabel("同一员工的多版本角色 选择版本").selectOption("employee-revision:multi:2");
  await expect(page.getByRole("region", { name: "选中员工详情" })).toContainText("employee-revision:multi:2");
  await page.getByLabel("发布状态").selectOption("PUBLISHED");
  await expect(page.getByText("选择一个数字员工")).toBeVisible();
  await page.getByRole("button", { name: "加载下一页 →" }).click();
  await expect(page.getByText("第 2 批", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "← 上一页" })).toBeEnabled();
});

test("TEST_ADAPTER mobile detail returns to the retained filtered list", async ({ page }) => {
  await installAdapter(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/digital-employees?q=供应商");
  await page.getByRole("button", { name: /供应商质量负责人/ }).click();
  await expect(page.getByRole("region", { name: "选中员工详情" })).toBeVisible();
  await page.getByRole("button", { name: "← 返回员工集合" }).click();
  await expect(page.getByLabel("员工集合")).toBeVisible();
  await expect(page.getByPlaceholder("职责角色或技术 ID")).toHaveValue("供应商");
});

test("TEST_ADAPTER preserves a valid historical Instance revision", async ({ page }) => {
  const historical = {
    ...employee,
    employeeDefinitionRevisionId: "employee-revision:history",
    employeeDefinitionDigest: digest("h"),
    members: [
      employee.members[0],
      { kind: "RUNTIME_PROFILE", resourceId: "runtime-profile:history", revisionId: "runtime-profile-revision:history", digest: digest("d") },
    ],
  };
  await installAdapter(page, {
    onInstance: async (route, id) => route.fulfill({ json: envelope(instance(id, historical)) }),
    onDefinition: async route => route.fulfill({ json: envelope(historical) }),
  });
  await page.goto("/digital-employees?panel=instance&instanceId=instance%3Aquality");
  await page.getByText("实例技术身份与原始状态").click();
  await expect(page.locator(".employee-read-result")).toContainText("employee-revision:history");
  await expect(page.locator(".employee-read-result")).toContainText("与所选精确修订一致");
});

async function fillCreateForm(page: Page) {
  const createButton = page.getByRole("button", { name: "＋ 创建数字员工" });
  if (await createButton.isVisible()) await createButton.click();
  await page.getByLabel(/质量分析 Agent/).check();
  await page.getByLabel("职责角色").fill("供应商质量负责人");
  await page.getByLabel(/职责清单/).fill("审查供应商质量异常\n协调整改与复核");
  await page.getByText("高级设置 · 技术身份需配置").click();
  await page.getByLabel("Employee Definition ID").fill("employee:new-quality");
  await page.getByLabel("Revision ID", { exact: true }).fill("employee-revision:new-quality:1");
  await page.getByRole("button", { name: "检查并进入确认" }).click();
  await expect(page.getByLabel("创建命令确认")).toBeVisible();
}

test("TEST_ADAPTER submits one exact Agent CREATE and preserves confirmed-but-hidden success", async ({ page }) => {
  let submitted: Record<string, unknown> | null = null;
  await installAdapter(page, {
    onCreate: async route => {
      submitted = route.request().postDataJSON();
      await route.fulfill({ status: 201, json: envelope({
        resourceKind: "DIGITAL_EMPLOYEE_DEFINITION",
        employeeDefinitionId: "employee:new-quality",
        employeeDefinitionRevisionId: "employee-revision:new-quality:1",
        employeeDefinitionDigest: digest("n"),
        aggregateVersion: 1,
        lifecycleState: "DRAFT",
      }) });
    },
    onDefinition: async route => route.fulfill({ status: 404, json: { reasonCode: "EMPLOYEE_NOT_FOUND" } }),
  });
  await page.goto("/digital-employees");
  await fillCreateForm(page);
  await page.getByRole("button", { name: "确认创建" }).click();
  await expect(page.getByRole("status").filter({ hasText: "创建命令已确认" })).toContainText("当前无权读取详情");
  expect(submitted).toMatchObject({
    employeeDefinitionId: "employee:new-quality",
    employeeDefinitionRevisionId: "employee-revision:new-quality:1",
    expectedVersion: 0,
    members: [{ kind: "AGENT", resourceId: "agent:quality", revisionId: "agent-revision:1" }],
  });
  expect((submitted as { responsibilities: string[] }).responsibilities).toHaveLength(2);
});

test("TEST_ADAPTER UNKNOWN replays the byte-equivalent frozen CREATE command", async ({ page }) => {
  const attempts: string[] = [];
  await installAdapter(page, {
    onCreate: async route => {
      attempts.push(route.request().postData() ?? "");
      if (attempts.length === 1) return route.abort("connectionreset");
      return route.fulfill({ status: 201, json: envelope({
        resourceKind: "DIGITAL_EMPLOYEE_DEFINITION",
        employeeDefinitionId: "employee:new-quality",
        employeeDefinitionRevisionId: "employee-revision:new-quality:1",
        employeeDefinitionDigest: digest("n"),
        aggregateVersion: 1,
        lifecycleState: "DRAFT",
      }) });
    },
  });
  await page.goto("/digital-employees");
  await fillCreateForm(page);
  await page.getByRole("button", { name: "确认创建" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "结果未知" })).toBeVisible();
  await page.getByRole("button", { name: "重放原命令" }).click();
  await expect(page.getByRole("region", { name: "选中员工详情" })).toContainText("供应商质量负责人");
  expect(attempts).toHaveLength(2);
  expect(attempts[1]).toBe(attempts[0]);
});

test("TEST_ADAPTER 503 keeps the frozen CREATE command in UNKNOWN", async ({ page }) => {
  await installAdapter(page, {
    onCreate: async route => route.fulfill({ status: 503, json: { reasonCode: "EMPLOYEE_STORE_UNAVAILABLE" } }),
  });
  await page.goto("/digital-employees");
  await fillCreateForm(page);
  await page.getByRole("button", { name: "确认创建" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "结果未知" })).toContainText("原 commandId 与语义 payload 已冻结");
  await expect(page.getByRole("button", { name: "重放原命令" })).toBeEnabled();
});

test("TEST_ADAPTER principal switch and logout stop CREATE before POST", async ({ page }) => {
  let sessionReads = 0;
  let creates = 0;
  await installAdapter(page, {
    onSession: async route => {
      sessionReads += 1;
      if (sessionReads === 1) return route.fulfill({ json: {
        schemaVersion: "workbench-session.v1",
        principal: { principalId: "human:quality", tenantId: "tenant-a", securityDomain: "quality" },
        session: { expiresAt: "2026-09-15T00:00:00Z", idleExpiresAt: "2026-09-14T23:00:00Z" },
        csrfToken: "csrf-first",
      } });
      return route.fulfill({ json: {
        schemaVersion: "workbench-session.v1",
        principal: { principalId: "human:other", tenantId: "tenant-a", securityDomain: "quality" },
        session: { expiresAt: "2026-09-15T00:00:00Z", idleExpiresAt: "2026-09-14T23:00:00Z" },
        csrfToken: "csrf-second",
      } });
    },
    onCreate: async route => { creates += 1; return route.fulfill({ status: 500 }); },
  });
  await page.goto("/digital-employees");
  await fillCreateForm(page);
  await page.getByRole("button", { name: "确认创建" }).click();
  await expect(page.getByRole("alert")).toContainText("可信会话已切换；原命令未发送");
  expect(creates).toBe(0);

  sessionReads = 0;
  await page.reload();
  await fillCreateForm(page);
  sessionReads = 1;
  await page.route("**/api/workbench/v1/session", route => route.fulfill({ status: 401, json: { reasonCode: "AUTHENTICATION_REQUIRED" } }));
  await page.getByRole("button", { name: "确认创建" }).click();
  await expect(page.getByRole("alert")).toContainText("可信会话已失效");
  expect(creates).toBe(0);
});

test("TEST_ADAPTER revoked CREATE is a controlled rejection", async ({ page }) => {
  await installAdapter(page, {
    onCreate: async route => route.fulfill({ status: 404, json: { reasonCode: "EMPLOYEE_NOT_FOUND" } }),
  });
  await page.goto("/digital-employees");
  await fillCreateForm(page);
  await page.getByRole("button", { name: "确认创建" }).click();
  await expect(page.getByRole("alert")).toContainText("当前身份没有创建权限，或依赖资源不可用");
  await expect(page.getByRole("button", { name: "确认创建" })).toBeEnabled();
});

test("TEST_ADAPTER double click emits only one CREATE command", async ({ page }) => {
  let creates = 0;
  await installAdapter(page, {
    onCreate: async route => {
      creates += 1;
      await new Promise(resolve => setTimeout(resolve, 150));
      await route.fulfill({ status: 201, json: envelope({
        resourceKind: "DIGITAL_EMPLOYEE_DEFINITION",
        employeeDefinitionId: "employee:new-quality",
        employeeDefinitionRevisionId: "employee-revision:new-quality:1",
        employeeDefinitionDigest: digest("n"),
        aggregateVersion: 1,
        lifecycleState: "DRAFT",
      }) });
    },
  });
  await page.goto("/digital-employees");
  await fillCreateForm(page);
  await page.getByRole("button", { name: "确认创建" }).dblclick();
  await expect(page.getByRole("region", { name: "选中员工详情" })).toContainText("供应商质量负责人");
  expect(creates).toBe(1);
});

test("TEST_ADAPTER late CREATE response cannot update an abandoned panel", async ({ page }) => {
  await installAdapter(page, {
    onCreate: async route => {
      await new Promise(resolve => setTimeout(resolve, 250));
      await route.fulfill({ status: 201, json: envelope({
        resourceKind: "DIGITAL_EMPLOYEE_DEFINITION",
        employeeDefinitionId: "employee:new-quality",
        employeeDefinitionRevisionId: "employee-revision:new-quality:1",
        employeeDefinitionDigest: digest("n"),
        aggregateVersion: 1,
        lifecycleState: "DRAFT",
      }) });
    },
  });
  await page.goto("/digital-employees");
  await fillCreateForm(page);
  await page.getByRole("button", { name: "确认创建" }).click();
  await page.getByRole("button", { name: "← 返回员工集合" }).click();
  await page.waitForTimeout(350);
  await expect(page.getByText("创建命令已确认", { exact: false })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /供应商质量负责人/ })).toBeVisible();
});

test("TEST_ADAPTER lifecycle command requires explicit version and confirmation", async ({ page }) => {
  const actions: string[] = [];
  await installAdapter(page, {
    onDefinition: async route => route.fulfill({ json: envelope({ ...employee, publicationState: "NOT_PUBLISHED", lifecycleState: "DRAFT" }) }),
    onLifecycle: async (route, action) => {
      actions.push(action);
      const body = route.request().postDataJSON();
      return route.fulfill({ json: envelope({
        resourceKind: "DIGITAL_EMPLOYEE_DEFINITION",
        employeeDefinitionId: employee.employeeDefinitionId,
        employeeDefinitionRevisionId: employee.employeeDefinitionRevisionId,
        employeeDefinitionDigest: employee.employeeDefinitionDigest,
        aggregateVersion: body.expectedVersion + 1,
        lifecycleState: "VALIDATED",
      }) });
    },
  });
  await page.goto("/digital-employees");
  await page.getByRole("button", { name: /供应商质量负责人/ }).click();
  await expect(page.getByRole("heading", { name: "生命周期操作" })).toBeVisible();
  await expect(page.getByRole("button", { name: /校验修订/ })).toBeDisabled();
  await page.getByLabel("期望聚合版本").fill("1");
  await page.getByRole("button", { name: /校验修订/ }).click();
  await expect(page.getByText("等待用户明确确认")).toBeVisible();
  await page.getByRole("button", { name: "确认提交" }).click();
  await expect(page.getByRole("status").filter({ hasText: "校验修订已确认" })).toBeVisible();
  expect(actions).toEqual(["VALIDATE"]);
});

test("TEST_ADAPTER captures labeled desktop and 390x844 visual evidence", async ({ page }, testInfo) => {
  const visualSummaries = Array.from({ length: 50 }, (_, index) => ({
    ...employeeSummary,
    employeeDefinitionId: `employee:visual:${String(index + 1).padStart(2, "0")}`,
    employeeDefinitionRevisionId: `employee-revision:visual:${index + 1}:1`,
    role: index === 0 ? "负责供应商质量异常复核与跨部门协同跟进的数字员工" : ["客户问题协调员", "合同风险复核员", "采购交付跟进员", "知识质量管理员"][index % 4],
    publicationState: index % 4 === 3 ? "NOT_PUBLISHED" : "PUBLISHED",
  }));
  await installAdapter(page, {
    onDefinition: async (route, id, revision) => {
      const summary = visualSummaries.find(item => item.employeeDefinitionId === id && item.employeeDefinitionRevisionId === revision) ?? employeeSummary;
      await route.fulfill({ json: envelope({ ...employee, ...summary, responsibilities: ["核对业务异常并形成可追溯结论", "协调相关团队完成复核与跟进"] }) });
    },
    onInstance: async (route, id) => route.fulfill({ json: envelope(instance(id, { ...employee, ...visualSummaries[0] })) }),
  });
  await page.route("**/api/workbench/v1/employees?*", route => route.fulfill({ json: envelope({ items: visualSummaries }) }));

  const placeBadge = async (target: ".employee-management" | ".employee-assembly" | ".employee-selected-detail" | ".employee-command-confirmation") => page.evaluate(selector => {
    let label = document.querySelector<HTMLElement>("[data-test-evidence]");
    if (!label) {
      label = document.createElement("div");
      label.dataset.testEvidence = "true";
      label.textContent = "TEST_ADAPTER 模拟数据 · 非真实业务记录";
      Object.assign(label.style, { margin: "0 0 8px auto", width: "fit-content", padding: "8px 12px", borderRadius: "8px", color: "#7c2d12", background: "#ffedd5", border: "1px solid #fdba74", font: "600 12px system-ui" });
    }
    document.querySelector(selector)?.prepend(label);
    const detailBody = document.querySelector<HTMLElement>(".employee-detail-body");
    if (detailBody) detailBody.scrollTop = 0;
    label.scrollIntoView({ block: "start" });
    window.scrollBy(0, -64);
    (document.activeElement as HTMLElement | null)?.blur();
  }, target);

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/digital-employees");
  await expect(page.getByRole("heading", { name: "数字员工", exact: true })).toBeVisible();
  const hierarchy = await page.evaluate(() => ({
    pageTitle: getComputedStyle(document.querySelector<HTMLElement>(".employee-page-title h1")!).fontSize,
    sectionTitle: getComputedStyle(document.querySelector<HTMLElement>(".employee-collection-toolbar h2")!).fontSize,
    rowRole: getComputedStyle(document.querySelector<HTMLElement>(".employee-row-copy strong")!).fontSize,
    rowId: getComputedStyle(document.querySelector<HTMLElement>(".employee-row-copy small")!).fontSize,
  }));
  expect(hierarchy).toEqual({ pageTitle: "28px", sectionTitle: "18px", rowRole: "15px", rowId: "12px" });
  await placeBadge(".employee-management");
  await page.screenshot({ path: testInfo.outputPath("desktop-list-test-adapter.png") });
  await page.getByRole("button", { name: /负责供应商质量异常复核/ }).click();
  await placeBadge(".employee-management");
  await page.screenshot({ path: testInfo.outputPath("desktop-detail-test-adapter.png") });
  await page.getByRole("button", { name: "职责与能力", exact: true }).click();
  await expect(page.getByRole("heading", { name: "职责与能力", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前员工职责" })).toBeVisible();
  await expect(page.getByText("核对业务异常并形成可追溯结论")).toBeVisible();
  await expect(page.getByRole("heading", { name: "已绑定 Agent 的职责与能力" })).toBeVisible();
  await expect(page.getByText("质量分析 Agent", { exact: true })).toBeVisible();
  await expect(page.getByText("Runtime Profile exact 详情尚未接通")).toBeVisible();
  const detailHierarchy = await page.evaluate(() => ({
    sectionTitle: getComputedStyle(document.querySelector<HTMLElement>(".employee-capability-profile > header h3")!).fontSize,
    body: getComputedStyle(document.querySelector<HTMLElement>(".employee-current-responsibilities li")!).fontSize,
    fieldLabel: getComputedStyle(document.querySelector<HTMLElement>(".employee-profile-grid dt")!).fontSize,
    fieldValue: getComputedStyle(document.querySelector<HTMLElement>(".employee-profile-grid dd")!).fontSize,
    capability: getComputedStyle(document.querySelector<HTMLElement>(".employee-capabilities li")!).fontSize,
  }));
  expect(detailHierarchy).toEqual({ sectionTitle: "18px", body: "14px", fieldLabel: "12px", fieldValue: "14px", capability: "13px" });
  await placeBadge(".employee-selected-detail");
  await page.screenshot({ path: testInfo.outputPath("desktop-capabilities-test-adapter.png") });
  await page.getByText("当前员工修订身份", { exact: true }).click();
  await expect(page.locator(".employee-technical-details").filter({ hasText: "当前员工修订身份" })).toContainText(employee.employeeDefinitionDigest);
  await page.getByText("成员技术身份与摘要", { exact: true }).click();
  const agentBinding = page.getByRole("listitem").filter({ hasText: "agent:quality" });
  await agentBinding.getByText("摘要与目录", { exact: true }).click();
  await expect(agentBinding).toContainText("agent-revision:1");
  await expect(agentBinding).toContainText(digest("a"));

  const detailBody = page.locator(".employee-detail-body");
  await detailBody.evaluate(element => { element.scrollTop = 400; });
  expect(await detailBody.evaluate(element => element.scrollTop)).toBeGreaterThan(0);
  await expect(page.getByRole("button", { name: "实例", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "实例", exact: true }).click();
  await expect.poll(() => detailBody.evaluate(element => element.scrollTop)).toBe(0);
  await expect(page.getByText("暂不支持按员工浏览实例列表；可使用已知实例 ID 查询。")).toBeVisible();
  await page.getByText("使用已知实例 ID 查询", { exact: true }).click();
  await page.getByLabel("实例 ID").fill("instance:quality");
  await page.getByRole("button", { name: "读取并验证归属" }).click();
  await expect(page.getByRole("heading", { name: "已读取实例摘要" })).toBeVisible();
  await expect(page.locator(".employee-read-result")).toContainText("已启用");
  await expect(page.locator(".employee-read-result")).toContainText("执行信息未接通");
  await expect(page.locator(".employee-read-result")).toContainText("健康信息未接通");
  await expect(page.locator(".employee-read-result")).not.toContainText("运行中");
  await placeBadge(".employee-selected-detail");
  await page.screenshot({ path: testInfo.outputPath("desktop-instance-test-adapter.png") });

  await page.getByRole("button", { name: "工作分配", exact: true }).click();
  await expect(page.getByText("暂不支持按员工或实例浏览工作分配列表")).toBeVisible();
  await page.getByText("使用已知 Assignment ID 查询", { exact: true }).click();
  await page.getByLabel("Assignment ID").fill("assignment:quality");
  await page.getByRole("button", { name: "读取并验证父链" }).click();
  await expect(page.getByRole("heading", { name: "当前查询的实例与工作分配" })).toBeVisible();
  await expect(page.locator(".employee-read-result")).toContainText("assignment:quality");
  await expect(page.locator(".employee-read-result")).toContainText("instance:quality");
  await page.getByText("技术操作：按精确坐标读取 Placement").click();
  await page.getByLabel("Placement ID").fill("placement:quality");
  await page.getByLabel("Attempt ID").fill("attempt:quality");
  await page.getByLabel("Agent Instance ID").fill("agent-instance:quality");
  await page.getByRole("button", { name: "读取精确工作关联" }).click();
  await expect(page.getByLabel("Placement 权威详情")).toContainText("runtime-instance:quality");
  await expect(page.getByLabel("Placement 权威详情")).toContainText("已放置（不代表执行成功）");
  await placeBadge(".employee-selected-detail");
  await page.screenshot({ path: testInfo.outputPath("desktop-assignments-test-adapter.png") });
  await page.getByLabel("Placement 权威详情").scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("desktop-assignments-placement-test-adapter.png") });

  await page.getByRole("button", { name: "＋ 创建数字员工" }).click();
  await expect(page.getByLabel("当前加载范围")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "＋ 创建数字员工" })).toHaveCount(0);
  await expect(page.getByText("高级设置 · 技术身份需配置（2 项必填）")).toBeVisible();
  await placeBadge(".employee-assembly");
  await page.screenshot({ path: testInfo.outputPath("desktop-create-test-adapter.png") });
  await fillCreateForm(page);
  await placeBadge(".employee-command-confirmation");
  await page.screenshot({ path: testInfo.outputPath("desktop-create-actions-test-adapter.png") });

  await page.getByRole("button", { name: "← 返回员工集合" }).click();
  await page.route("**/api/workbench/v1/employees/*/revisions/*", route => route.fulfill({ status: 404, json: { reasonCode: "EMPLOYEE_NOT_FOUND" } }));
  await page.getByRole("button", { name: /客户问题协调员/ }).first().click();
  await expect(page.getByRole("alert").filter({ hasText: "详情读取未完成" })).toBeVisible();
  await expect(page.getByLabel("所选员工列表摘要")).toContainText("客户问题协调员");
  await expect(page.getByRole("button", { name: "重试" })).toBeVisible();
  await placeBadge(".employee-management");
  await page.screenshot({ path: testInfo.outputPath("desktop-exception-test-adapter.png") });

  await page.unroute("**/api/workbench/v1/employees/*/revisions/*");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/digital-employees");
  await placeBadge(".employee-management");
  await page.screenshot({ path: testInfo.outputPath("mobile-list-test-adapter.png") });
  await page.getByRole("button", { name: /负责供应商质量异常复核/ }).click();
  await placeBadge(".employee-selected-detail");
  await page.screenshot({ path: testInfo.outputPath("mobile-detail-test-adapter.png") });
  await page.getByRole("button", { name: "＋ 创建数字员工" }).click();
  await fillCreateForm(page);
  await placeBadge(".employee-assembly");
  await expect(page.getByText("部分实现 · 正式权限路径待接通")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("mobile-create-test-adapter.png") });
  await placeBadge(".employee-command-confirmation");
  await page.screenshot({ path: testInfo.outputPath("mobile-create-actions-test-adapter.png") });

  await page.getByRole("button", { name: "← 返回员工集合" }).click();
  await page.route("**/api/workbench/v1/employees/*/revisions/*", route => route.fulfill({ status: 404, json: { reasonCode: "EMPLOYEE_NOT_FOUND" } }));
  await page.getByRole("button", { name: /客户问题协调员/ }).first().click();
  await expect(page.getByRole("alert").filter({ hasText: "详情读取未完成" })).toBeVisible();
  await placeBadge(".employee-selected-detail");
  await page.screenshot({ path: testInfo.outputPath("mobile-exception-test-adapter.png") });

  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.unroute("**/api/workbench/v1/employees/*/revisions/*");
  await page.getByRole("button", { name: "← 返回员工集合" }).click();
  await page.getByRole("button", { name: "＋ 创建数字员工" }).click();
  const roleInput = page.getByLabel("职责角色");
  await roleInput.focus();
  await expect(roleInput).toBeFocused();
  expect(await roleInput.evaluate(element => parseFloat(getComputedStyle(element).outlineWidth))).toBeGreaterThanOrEqual(2);
  await page.keyboard.press("Tab");
  await expect(page.getByLabel(/职责清单/)).toBeFocused();
});
