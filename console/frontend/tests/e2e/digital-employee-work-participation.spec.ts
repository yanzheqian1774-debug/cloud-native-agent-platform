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
  lifecycleState: "DRAFT",
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
    instanceId: "instance:quality",
    assignmentId: "assignment:quality",
    placementId: "placement:quality",
    attemptId: "attempt:quality",
    agentInstanceId: "agent-instance:quality",
  });
  await page.goto(`/digital-employees?${query}`);
  await expect(page.getByLabel("Placement 权威详情")).toContainText("runtime-instance:quality");
  await expect(page.getByLabel("员工工作参与阶段")).toContainText("正式 Execution READ 尚未接通");
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
  await page.goto("/digital-employees?panel=instance");
  await page.getByLabel("Instance ID").fill("instance:old");
  await page.getByRole("button", { name: "按精确 ID 读取" }).click();
  await page.getByLabel("Instance ID").fill("instance:new");
  await page.getByRole("button", { name: "按精确 ID 读取" }).click();
  await expect(page.locator(".employee-facts")).toContainText("instance:new");
  await page.waitForTimeout(300);
  await expect(page.locator(".employee-facts")).not.toContainText("instance:old");
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
  await page.getByRole("button", { name: "Agent 候选", exact: true }).click();
  await page.getByRole("button", { name: "加载更多 Agent" }).click();
  await expect(page.getByText("第二页 Agent")).toBeVisible();
  expect(agentCursor).toBe("agent-page-2");
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
  await expect(page.locator(".employee-facts")).toContainText("employee-revision:history");
  await expect(page.locator(".employee-facts")).toContainText("允许合法历史发布版本");
});

async function fillCreateForm(page: Page) {
  await page.getByRole("button", { name: "Agent 候选", exact: true }).click();
  await page.getByLabel(/质量分析 Agent/).check();
  await page.getByLabel("职责角色").fill("供应商质量负责人");
  await page.getByLabel(/职责清单/).fill("审查供应商质量异常\n协调整改与复核");
  await page.getByText("技术身份与版本").click();
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
  await page.getByRole("button", { name: "确认并提交正式命令" }).click();
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
  await page.getByRole("button", { name: "确认并提交正式命令" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "结果未知" })).toBeVisible();
  await page.getByRole("button", { name: "重放原命令" }).click();
  await expect(page.getByRole("status").filter({ hasText: "创建命令已确认" })).toBeVisible();
  expect(attempts).toHaveLength(2);
  expect(attempts[1]).toBe(attempts[0]);
});

test("TEST_ADAPTER 503 keeps the frozen CREATE command in UNKNOWN", async ({ page }) => {
  await installAdapter(page, {
    onCreate: async route => route.fulfill({ status: 503, json: { reasonCode: "EMPLOYEE_STORE_UNAVAILABLE" } }),
  });
  await page.goto("/digital-employees");
  await fillCreateForm(page);
  await page.getByRole("button", { name: "确认并提交正式命令" }).click();
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
  await page.getByRole("button", { name: "确认并提交正式命令" }).click();
  await expect(page.getByRole("alert")).toContainText("可信会话已切换；原命令未发送");
  expect(creates).toBe(0);

  sessionReads = 0;
  await page.reload();
  await fillCreateForm(page);
  sessionReads = 1;
  await page.route("**/api/workbench/v1/session", route => route.fulfill({ status: 401, json: { reasonCode: "AUTHENTICATION_REQUIRED" } }));
  await page.getByRole("button", { name: "确认并提交正式命令" }).click();
  await expect(page.getByRole("alert")).toContainText("可信会话已失效");
  expect(creates).toBe(0);
});

test("TEST_ADAPTER revoked CREATE is a controlled rejection", async ({ page }) => {
  await installAdapter(page, {
    onCreate: async route => route.fulfill({ status: 404, json: { reasonCode: "EMPLOYEE_NOT_FOUND" } }),
  });
  await page.goto("/digital-employees");
  await fillCreateForm(page);
  await page.getByRole("button", { name: "确认并提交正式命令" }).click();
  await expect(page.getByRole("alert")).toContainText("当前身份没有创建权限，或依赖资源不可用");
  await expect(page.getByRole("button", { name: "确认并提交正式命令" })).toBeEnabled();
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
  await page.getByRole("button", { name: "确认并提交正式命令" }).dblclick();
  await expect(page.getByRole("status").filter({ hasText: "创建命令已确认" })).toBeVisible();
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
  await page.getByRole("button", { name: "确认并提交正式命令" }).click();
  await page.getByRole("button", { name: "员工档案" }).click();
  await page.waitForTimeout(350);
  await expect(page.getByText("创建命令已确认", { exact: false })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "供应商质量负责人" })).toBeVisible();
});

test("TEST_ADAPTER lifecycle command requires explicit version and confirmation", async ({ page }) => {
  const actions: string[] = [];
  await installAdapter(page, {
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
  await installAdapter(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/digital-employees");
  await expect(page.getByRole("heading", { name: "数字员工管理" })).toBeVisible();
  await page.evaluate(() => {
    const label = document.createElement("div");
    label.dataset.testEvidence = "true";
    label.textContent = "TEST_ADAPTER 模拟数据 · 非真实业务记录";
    Object.assign(label.style, {
      position: "fixed", top: "68px", right: "18px", zIndex: "9999",
      padding: "8px 12px", borderRadius: "8px", color: "#7c2d12",
      background: "#ffedd5", border: "1px solid #fdba74", font: "600 12px system-ui",
    });
    document.body.append(label);
    (document.activeElement as HTMLElement | null)?.blur();
  });
  await page.screenshot({ path: testInfo.outputPath("digital-employees-desktop-test-adapter.png") });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "＋ 创建数字员工" }).click();
  await page.evaluate(() => {
    const section = document.querySelector(".employee-assembly");
    const label = document.querySelector<HTMLElement>("[data-test-evidence]");
    if (section) window.scrollTo(0, section.getBoundingClientRect().top + window.scrollY - 68);
    if (label) { label.style.top = "auto"; label.style.right = "12px"; label.style.bottom = "64px"; }
    (document.activeElement as HTMLElement | null)?.blur();
  });
  await expect(page.getByText("部分实现 · 权限取得待 305")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("digital-employees-390x844-test-adapter.png") });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const roleInput = page.getByLabel("职责角色");
  await roleInput.focus();
  await expect(roleInput).toBeFocused();
  expect(await roleInput.evaluate(element => parseFloat(getComputedStyle(element).outlineWidth))).toBeGreaterThanOrEqual(2);
  await page.keyboard.press("Tab");
  await expect(page.getByLabel(/职责清单/)).toBeFocused();
});
