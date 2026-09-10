import { expect, request, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

const baseURL = process.env.S5_310_WORKBENCH_URL ?? "";
const controlURL = process.env.S5_310_CONTROL_URL ?? "";
const controlToken = process.env.S5_310_CONTROL_TOKEN ?? "";

async function login(browser: Browser, credential: string): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
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
  test.skip(!baseURL || !controlURL || !controlToken, "310 real Workbench fixture is not configured");
  const full = await login(browser, "310-full-browser-credential");
  const identityHeaders: string[] = [];
  full.page.on("request", value => {
    const headers = value.headers();
    for (const name of ["x-principal-id", "x-tenant-id", "x-security-domain"])
      if (headers[name]) identityHeaders.push(name);
  });

  await full.page.goto(`${baseURL}/digital-employees`);
  await expect(full.page.getByRole("button", { name: /Supplier quality owner/ })).toBeVisible();
  await full.page.getByRole("button", { name: /Supplier quality owner/ }).click();
  await expect(full.page.getByText("Quality analysis Agent", { exact: true })).toBeVisible();

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
  expect(identityHeaders).toEqual([]);
  await full.context.close();

  const lister = await login(browser, "310-list-browser-credential");
  expect((await browserFetch(lister.page, "/api/workbench/v1/employees?pageSize=1")).status).toBe(200);
  expect(
    await browserFetch(
      lister.page,
      "/api/workbench/v1/employees/employee-definition%3Aquality/revisions/employee-revision%3A1",
    ),
  ).toMatchObject({ status: 404, body: { reasonCode: "AUTHORIZATION_NOT_FOUND" } });
  await lister.context.close();

  const wrongScope = await login(browser, "310-wrong-scope-credential");
  expect(
    await browserFetch(
      wrongScope.page,
      "/api/workbench/v1/employees/employee-definition%3Aquality/revisions/employee-revision%3A1",
    ),
  ).toMatchObject({ status: 404, body: { reasonCode: "EMPLOYEE_NOT_FOUND" } });
  await wrongScope.context.close();

  const wrongGrant = await login(browser, "310-wrong-grant-credential");
  expect(
    await browserFetch(
      wrongGrant.page,
      "/api/workbench/v1/employees/employee-definition%3Aquality/revisions/employee-revision%3A1",
    ),
  ).toMatchObject({ status: 404, body: { reasonCode: "AUTHORIZATION_NOT_FOUND" } });
  await wrongGrant.context.close();
});
