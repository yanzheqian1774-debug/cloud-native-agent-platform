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
  onInstance?: (route: Route, id: string) => Promise<void>;
  onDefinition?: (route: Route, id: string, revision: string) => Promise<void>;
  onPlacement?: (route: Route) => Promise<void>;
};

async function installAdapter(page: Page, options: AdapterOptions = {}) {
  await page.route("**/api/workbench/v1/**", async route => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path.endsWith("/employees")) {
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
  await expect(page.getByRole("alert").filter({ hasText: "not found" })).toContainText("资源不可用或当前访问未获授权");
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
  await expect(page.getByRole("alert").filter({ hasText: "conflict" })).toContainText("EMPLOYEE_DEFINITION_IDENTITY_MISMATCH");
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
