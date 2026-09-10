import { expect, request, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name}_REQUIRED`);
  return value;
}

const baseURL = required("S5_310_WORKBENCH_URL");
const controlURL = required("S5_310_CONTROL_URL");
const controlToken = required("S5_310_CONTROL_TOKEN");
const credentials = {
  full: required("S5_310_FULL_CREDENTIAL"),
  list: required("S5_310_LIST_CREDENTIAL"),
  wrongScope: required("S5_310_WRONG_SCOPE_CREDENTIAL"),
  wrongGrant: required("S5_310_WRONG_GRANT_CREDENTIAL"),
};

type BrowserObservations = { identityHeaders: string[]; privateRequests: string[] };

async function login(
  browser: Browser,
  credential: string,
  observations: BrowserObservations,
): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  context.on("request", value => {
    const headers = value.headers();
    for (const name of ["x-principal-id", "x-tenant-id", "x-security-domain"])
      if (headers[name]) observations.identityHeaders.push(name);
    if (new URL(value.url()).pathname.startsWith("/api/internal/")) observations.privateRequests.push(value.url());
  });
  const page = await context.newPage();
  await page.goto(`${baseURL}/api/workbench/v1/login`);
  await page.locator('input[name="bootstrapCredential"]').fill(credential);
  await Promise.all([
    page.waitForURL(/\/workbench$/),
    page.getByRole("button", { name: "Sign in" }).click(),
  ]);
  return { context, page };
}

async function browserFetch(page: Page, path: string) {
  return page.evaluate(async value => {
    const response = await fetch(value, { credentials: "same-origin", headers: { Accept: "application/json" } });
    return { status: response.status, body: await response.json() };
  }, path);
}

test("REAL_SERVICE trusted Digital Employee reads preserve authorization and identity", async ({ browser }) => {
  const observations: BrowserObservations = { identityHeaders: [], privateRequests: [] };
  const full = await login(browser, credentials.full, observations);

  await full.page.goto(`${baseURL}/digital-employees`);
  await expect(full.page.getByRole("button", { name: /Supplier quality owner/ })).toBeVisible();
  await full.page.getByRole("button", { name: /Supplier quality owner/ }).click();
  await expect(full.page.getByText("Quality analysis Agent", { exact: true })).toBeVisible();
  const employee = await browserFetch(
    full.page,
    "/api/workbench/v1/employees/employee-definition%3Aquality/revisions/employee-revision%3A1",
  );
  expect(employee.status).toBe(200);
  expect(employee.body.result).toMatchObject({
    employeeDefinitionId: "employee-definition:quality",
    employeeDefinitionRevisionId: "employee-revision:1",
    publicationState: "PUBLISHED",
  });
  expect(employee.body.result.employeeDefinitionDigest).toMatch(/^(?:sha256:)?[a-f0-9]{64}$/);
  expect(employee.body.result.members.map((value: { kind: string }) => value.kind).sort()).toEqual([
    "AGENT",
    "KNOWLEDGE",
    "MCP",
    "RUNTIME_PROFILE",
    "SKILL",
    "WORKFLOW",
  ]);
  for (const member of employee.body.result.members) {
    expect(member.resourceId).toBeTruthy();
    expect(member.revisionId).toBeTruthy();
    expect(member.digest).toMatch(/^(?:sha256:)?[a-f0-9]{64}$/);
  }
  const agentMember = employee.body.result.members.find((value: { kind: string }) => value.kind === "AGENT");
  expect(agentMember).toMatchObject({ kind: "AGENT" });
  expect(agentMember.revisionId).toBeTruthy();
  expect(agentMember.digest).toMatch(/^(?:sha256:)?[a-f0-9]{64}$/);
  const agent = await browserFetch(
    full.page,
    `/api/workbench/v1/agents/${encodeURIComponent(agentMember.resourceId)}/revisions/${encodeURIComponent(agentMember.revisionId)}`,
  );
  expect(agent).toMatchObject({
    status: 200,
    body: { result: {
      definitionId: agentMember.resourceId,
      revisionId: agentMember.revisionId,
      digest: agentMember.digest,
      name: "Quality analysis Agent",
    } },
  });
  const employeeDetail = full.page.locator(".px-object-detail");
  await expect(employeeDetail).toContainText("PUBLISHED");
  await expect(employeeDetail).toContainText(employee.body.result.employeeDefinitionRevisionId);
  await expect(employeeDetail).toContainText(employee.body.result.employeeDefinitionDigest);
  for (const member of employee.body.result.members) {
    const binding = employeeDetail.getByRole("listitem").filter({ hasText: member.resourceId });
    await expect(binding).toContainText(member.kind);
    await expect(binding).toContainText(member.revisionId);
    await expect(binding).toContainText(member.digest);
  }

  const firstEmployees = await browserFetch(full.page, "/api/workbench/v1/employees?pageSize=1");
  expect(firstEmployees.status).toBe(200);
  expect(firstEmployees.body.result.items).toHaveLength(1);
  expect(firstEmployees.body.result.totalCount).toBeUndefined();
  const nextEmployees = await browserFetch(
    full.page,
    `/api/workbench/v1/employees?pageSize=1&cursor=${encodeURIComponent(firstEmployees.body.result.nextCursor)}`,
  );
  expect(nextEmployees.status).toBe(200);
  expect(nextEmployees.body.result.items[0].employeeDefinitionId).not.toBe(
    firstEmployees.body.result.items[0].employeeDefinitionId,
  );

  const firstAgents = await browserFetch(full.page, "/api/workbench/v1/agents?pageSize=1");
  expect(firstAgents.status).toBe(200);
  const nextAgents = await browserFetch(
    full.page,
    `/api/workbench/v1/agents?pageSize=1&cursor=${encodeURIComponent(firstAgents.body.result.nextCursor)}`,
  );
  expect(nextAgents.status).toBe(200);
  expect(nextAgents.body.result.items[0].definitionId).not.toBe(firstAgents.body.result.items[0].definitionId);

  const workQuery = new URLSearchParams({
    panel: "work",
    instanceId: "employee-instance:quality",
    assignmentId: "employee-assignment:quality",
    placementId: "placement:quality",
    attemptId: "attempt:quality",
    agentInstanceId: "agent-instance:quality",
  });
  await full.page.goto(`${baseURL}/digital-employees?${workQuery}`);
  await expect(full.page.getByLabel("Placement 权威详情")).toContainText("runtime-instance:quality");
  await full.page.reload();
  await expect(full.page.getByLabel("Placement 权威详情")).toContainText("runtime-instance:quality");

  const wrongParent = await browserFetch(
    full.page,
    "/api/workbench/v1/instances/employee-instance%3Aquality/assignments/employee-assignment%3Aother/placements/placement%3Aquality?attemptId=attempt%3Aquality&agentInstanceId=agent-instance%3Aquality",
  );
  expect(wrongParent).toMatchObject({ status: 404, body: { reasonCode: "PLACEMENT_NOT_FOUND" } });
  const wrongAttempt = await browserFetch(
    full.page,
    "/api/workbench/v1/instances/employee-instance%3Aquality/assignments/employee-assignment%3Aquality/placements/placement%3Aquality?attemptId=attempt%3Aother&agentInstanceId=agent-instance%3Aquality",
  );
  expect(wrongAttempt).toMatchObject({ status: 404, body: { reasonCode: "PLACEMENT_NOT_FOUND" } });
  const wrongAgent = await browserFetch(
    full.page,
    "/api/workbench/v1/instances/employee-instance%3Aquality/assignments/employee-assignment%3Aquality/placements/placement%3Aquality?attemptId=attempt%3Aquality&agentInstanceId=agent-instance%3Aother",
  );
  expect(wrongAgent).toMatchObject({ status: 404, body: { reasonCode: "PLACEMENT_NOT_FOUND" } });

  const control = await request.newContext({ baseURL: controlURL });
  const revoked = await control.post("/revoke-placement", { headers: { "x-control-token": controlToken } });
  expect(revoked.ok()).toBe(true);
  const afterGrantRevoke = await browserFetch(
    full.page,
    "/api/workbench/v1/instances/employee-instance%3Aquality/assignments/employee-assignment%3Aquality/placements/placement%3Aquality?attemptId=attempt%3Aquality&agentInstanceId=agent-instance%3Aquality",
  );
  expect(afterGrantRevoke).toMatchObject({ status: 404, body: { reasonCode: "AUTHORIZATION_NOT_FOUND" } });
  await control.dispose();

  const session = await browserFetch(full.page, "/api/workbench/v1/session");
  expect(session.status).toBe(200);
  const logout = await full.context.request.delete(`${baseURL}/api/workbench/v1/session`, {
    headers: { "x-csrf-token": session.body.csrfToken, origin: baseURL },
  });
  expect(logout.status()).toBe(204);
  expect((await browserFetch(full.page, "/api/workbench/v1/employees?pageSize=1")).status).toBe(401);
  await full.context.close();

  const lister = await login(browser, credentials.list, observations);
  expect((await browserFetch(lister.page, "/api/workbench/v1/employees?pageSize=1")).status).toBe(200);
  expect(
    await browserFetch(
      lister.page,
      "/api/workbench/v1/employees/employee-definition%3Aquality/revisions/employee-revision%3A1",
    ),
  ).toMatchObject({ status: 404, body: { reasonCode: "AUTHORIZATION_NOT_FOUND" } });
  await lister.context.close();

  const wrongScope = await login(browser, credentials.wrongScope, observations);
  expect(
    await browserFetch(
      wrongScope.page,
      "/api/workbench/v1/employees/employee-definition%3Aquality/revisions/employee-revision%3A1",
    ),
  ).toMatchObject({ status: 404, body: { reasonCode: "EMPLOYEE_NOT_FOUND" } });
  await wrongScope.context.close();

  const wrongGrant = await login(browser, credentials.wrongGrant, observations);
  expect(
    await browserFetch(
      wrongGrant.page,
      "/api/workbench/v1/employees/employee-definition%3Aquality/revisions/employee-revision%3A1",
    ),
  ).toMatchObject({ status: 404, body: { reasonCode: "AUTHORIZATION_NOT_FOUND" } });
  await wrongGrant.context.close();
  expect(observations.identityHeaders).toEqual([]);
  expect(observations.privateRequests).toEqual([]);
});
