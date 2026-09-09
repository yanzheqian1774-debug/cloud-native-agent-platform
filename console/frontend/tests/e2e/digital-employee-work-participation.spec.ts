import { expect, test, type Page, type Route } from "@playwright/test";

const digest = (value: string) => value.repeat(64);
const employee = {
  resourceKind: "DIGITAL_EMPLOYEE_DEFINITION",
  employeeDefinitionId: "employee:quality",
  employeeDefinitionRevisionId: "employee-revision:1",
  employeeDefinitionDigest: digest("e"),
  aggregateVersion: 4,
  role: "供应商质量负责人",
  responsibilities: ["审查供应商质量工作"],
  members: [
    { kind: "AGENT", resourceId: "agent:quality", revisionId: "agent-revision:1", digest: digest("a") },
    { kind: "RUNTIME_PROFILE", resourceId: "runtime-profile:native", revisionId: "runtime-profile-revision:1", digest: digest("b") },
  ],
  predecessorEmployeeRevisionId: null,
  published: true,
  matchable: false,
  facts: [{ action: "PUBLISH", decisionId: "decision:publish", ordinal: 1 }],
};
const agent = {
  definitionId: "agent:quality", name: "质量分析 Agent", aggregateVersion: 3,
  lifecycleState: "PUBLISHED", enabled: true, archived: false, currentDraftRevisionId: null,
  publishedRevisionId: "agent-revision:1", reviews: [], facts: [], relationships: [], limitations: [],
  revisions: [{ revisionId: "agent-revision:1", predecessorRevisionId: null, state: "PUBLISHED", digest: digest("a"), createdAt: "2026-09-09T00:00:00Z", content: { title: "质量分析员", duties: ["分析质量异常"], data: [], knowledge: [], skills: [], capabilities: ["supplier-quality-analysis"], runtimes: [], businessPurpose: "形成可核对的质量分析", bindings: { skills: [], mcpTools: [], knowledge: [] } } }],
};
const instance = (id: string) => ({
  instanceId: id, version: 1,
  employeeDefinition: { authorityKind: "DIGITAL_EMPLOYEE_DEFINITION_V1", employeeDefinitionId: employee.employeeDefinitionId, employeeDefinitionRevisionId: employee.employeeDefinitionRevisionId, digest: employee.employeeDefinitionDigest },
  ownerId: "owner:quality", organizationId: "tenant-a", lifecycle: "ENABLED",
  workspaceReference: null, modelReference: null, policyReferences: [], relationships: {},
  createdAt: "2026-09-09T00:00:00Z", updatedAt: "2026-09-09T00:00:00Z",
  execution: { state: "UNAVAILABLE", reasonCode: "EXECUTION_NOT_ASSEMBLED" },
  health: { state: "UNAVAILABLE", reasonCode: "HEALTH_NOT_OBSERVED" },
});
const assignment = { assignmentId: "assignment:quality", instanceId: "instance:quality", assigneeId: "team:quality", businessRole: "质量工作分配", lifecycle: "ACTIVE", effectiveFrom: "2026-09-09T00:00:00Z", effectiveUntil: null, version: 1, binding: { state: "UNAVAILABLE", reasonCode: "WORKFLOW_BINDING_NOT_ASSEMBLED" } };
const placement = { placementId: "placement:quality", requestId: "placement-request:quality", decision: "PLACED", runtimeInstanceId: "runtime-instance:quality", policyVersion: "policy:1", compatibilityFacts: ["native-compatible"], limitationCodes: [], decidedAt: "2026-09-09T00:00:00Z", digest: digest("c"), observation: { freshness: "UNOBSERVED", observationId: null }, execution: { state: "UNAVAILABLE", reasonCode: "RUNTIME_EXECUTION_NOT_STARTED" }, outcome: { state: "UNAVAILABLE", reasonCode: "OUTCOME_NOT_RECORDED" } };

async function installAdapter(page: Page, onInstance?: (route: Route, id: string) => Promise<void>) {
  await page.route("**/api/internal/**", async route => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path.endsWith("/digital-employees/definitions")) return route.fulfill({ json: [employee] });
    if (path.endsWith("/agent-definitions")) return route.fulfill({ json: [agent] });
    if (path.endsWith("/agent-definitions/agent%3Aquality")) return route.fulfill({ json: { definition: agent, productProjection: {}, technicalProjection: {} } });
    if (path.includes("/placements/")) return route.fulfill({ json: placement });
    if (path.includes("/assignments/")) return route.fulfill({ json: assignment });
    if (path.includes("/instances/")) {
      const id = decodeURIComponent(path.split("/instances/")[1]);
      if (onInstance) return onInstance(route, id);
      return route.fulfill({ json: instance(id) });
    }
    return route.fulfill({ status: 404, json: { detail: { reasonCode: "NOT_FOUND" } } });
  });
}

test("TEST_ADAPTER renders provenance and exact work facts after refresh at 390px", async ({ page }) => {
  let instanceReads = 0;
  await installAdapter(page, async (route, id) => { instanceReads += 1; await route.fulfill({ json: instance(id) }); });
  await page.setViewportSize({ width: 390, height: 844 });
  const query = new URLSearchParams({ panel: "work", instanceId: "instance:quality", assignmentId: "assignment:quality", placementId: "placement:quality", attemptId: "attempt:quality", agentInstanceId: "agent-instance:quality" });
  await page.goto(`/digital-employees?${query}`);
  await expect(page.getByLabel("Placement 权威详情")).toContainText("runtime-instance:quality");
  await expect(page.getByLabel("员工工作参与阶段")).toContainText("RUNTIME_EXECUTION_NOT_STARTED");
  await expect(page.getByText("不推导在线状态")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.reload();
  await expect(page.getByLabel("Placement 权威详情")).toBeVisible();
  expect(instanceReads).toBeGreaterThanOrEqual(2);
});

test("TEST_ADAPTER late Instance response cannot overwrite the new exact object", async ({ page }) => {
  await installAdapter(page, async (route, id) => {
    if (id === "instance:old") await new Promise(resolve => setTimeout(resolve, 250));
    await route.fulfill({ json: instance(id) });
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

test("TEST_ADAPTER requires exact identities and redacts a denied Placement read", async ({ page }) => {
  await installAdapter(page);
  await page.route("**/placements/**", route => route.fulfill({ status: 403, json: { detail: { reasonCode: "PLACEMENT_SCOPE_DENIED" } } }));
  const query = new URLSearchParams({ panel: "work", instanceId: "instance:quality", assignmentId: "assignment:quality" });
  await page.goto(`/digital-employees?${query}`);
  const read = page.getByRole("button", { name: "读取精确工作关联" });
  await expect(read).toBeDisabled();
  await page.getByLabel("Placement ID").fill("placement:denied");
  await page.getByLabel("Attempt ID").fill("attempt:denied");
  await page.getByLabel("Agent Instance ID").fill("agent-instance:denied");
  await read.click();
  const alert = page.getByRole("alert");
  await expect(alert).toContainText("denied");
  await expect(alert).toContainText("资源不可用或当前访问未获授权");
  await expect(alert).not.toContainText("PLACEMENT_SCOPE_DENIED");
});
