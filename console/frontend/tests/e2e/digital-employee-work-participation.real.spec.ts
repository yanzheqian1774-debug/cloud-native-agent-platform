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
type LoginKind = "FULL" | "LISTER" | "WRONG_SCOPE" | "WRONG_GRANT";
const sessionURL = new URL("/api/workbench/v1/session", baseURL);
const loginIdentities = {
  FULL: { principalId: "human:alice", tenantId: "tenant-a", securityDomain: "quality" },
  LISTER: { principalId: "human:lister", tenantId: "tenant-a", securityDomain: "quality" },
  WRONG_SCOPE: { principalId: "human:wrongscope", tenantId: "tenant-b", securityDomain: "quality" },
  WRONG_GRANT: { principalId: "human:wronggrant", tenantId: "tenant-a", securityDomain: "quality" },
} as const;
const fullLoginSubmitSteps = {
  click: "FULL_LOGIN_SUBMIT_CLICK",
  request: "FULL_LOGIN_POST_REQUEST_OBSERVED",
  response: "FULL_LOGIN_POST_RESPONSE_OBSERVED",
  status: "FULL_LOGIN_POST_STATUS_ASSERTION",
  location: "FULL_LOGIN_POST_LOCATION_ASSERTION",
} as const;
const employeeListSteps = {
  navigation: "EMPLOYEE_LIST_NAVIGATION",
  request: "EMPLOYEE_LIST_REQUEST_OBSERVED",
  response: "EMPLOYEE_LIST_RESPONSE_OBSERVED",
  status: "EMPLOYEE_LIST_STATUS_ASSERTION",
  count: "EMPLOYEE_LIST_BUTTON_COUNT",
  visible: "EMPLOYEE_LIST_BUTTON_VISIBLE",
} as const;
const loginSteps = {
  FULL: ["FULL_LOGIN_FORM", "FULL_LOGIN_SUBMIT_REDIRECT", "FULL_SESSION_READY"],
  LISTER: ["LISTER_LOGIN_FORM", "LISTER_LOGIN_SUBMIT_REDIRECT", "LISTER_SESSION_READY"],
  WRONG_SCOPE: ["WRONG_SCOPE_LOGIN_FORM", "WRONG_SCOPE_LOGIN_SUBMIT_REDIRECT", "WRONG_SCOPE_SESSION_READY"],
  WRONG_GRANT: ["WRONG_GRANT_LOGIN_FORM", "WRONG_GRANT_LOGIN_SUBMIT_REDIRECT", "WRONG_GRANT_SESSION_READY"],
} as const;

function isSessionPost(requestValue: { method(): string; url(): string }): boolean {
  const url = new URL(requestValue.url());
  return (
    requestValue.method() === "POST" &&
    url.origin === sessionURL.origin &&
    url.pathname === sessionURL.pathname &&
    url.search === ""
  );
}

function isEmployeeListRequest(requestValue: { method(): string; url(): string }): boolean {
  const url = new URL(requestValue.url());
  return (
    requestValue.method() === "GET" &&
    url.origin === sessionURL.origin &&
    url.pathname === "/api/workbench/v1/employees" &&
    url.searchParams.get("pageSize") === "50"
  );
}

function recordFullLoginDiagnostic(type: string, description: string): void {
  test.info().annotations.push({ type, description });
}

function classifyLocation(location: string | undefined): "EXPECTED_WORKBENCH" | "OTHER" | "MISSING" {
  if (location === undefined) return "MISSING";
  return location === "/workbench" ? "EXPECTED_WORKBENCH" : "OTHER";
}

async function login(
  browser: Browser,
  credential: string,
  observations: BrowserObservations,
  kind: LoginKind,
): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  context.on("request", value => {
    const headers = value.headers();
    for (const name of ["x-principal-id", "x-tenant-id", "x-security-domain"])
      if (headers[name]) observations.identityHeaders.push(name);
    if (new URL(value.url()).pathname.startsWith("/api/internal/")) observations.privateRequests.push(value.url());
  });
  const page = await context.newPage();
  const [formStep, submitStep, readyStep] = loginSteps[kind];
  await test.step(formStep, async () => {
    await page.goto(`${baseURL}/api/workbench/v1/login`);
    await expect(page.locator('input[name="bootstrapCredential"]')).toHaveCount(1);
    await page.locator('input[name="bootstrapCredential"]').fill(credential);
  });
  await test.step(submitStep, async () => {
    const submit = page.getByRole("button", { name: "Sign in", exact: true });
    await expect(submit).toHaveCount(1);
    if (kind === "FULL") {
      const requestPromise = page.waitForRequest(isSessionPost).then(
        value => {
          recordFullLoginDiagnostic("S5_310_LOGIN_REQUEST_OBSERVED", "true");
          return value;
        },
        () => {
          recordFullLoginDiagnostic("S5_310_LOGIN_REQUEST_OBSERVED", "false");
          return null;
        },
      );
      const responsePromise = page.waitForResponse(value => isSessionPost(value.request())).then(
        value => {
          recordFullLoginDiagnostic("S5_310_LOGIN_RESPONSE_OBSERVED", "true");
          recordFullLoginDiagnostic("S5_310_LOGIN_HTTP_STATUS", String(value.status()));
          recordFullLoginDiagnostic("S5_310_LOGIN_LOCATION_CLASS", classifyLocation(value.headers().location));
          return value;
        },
        () => {
          recordFullLoginDiagnostic("S5_310_LOGIN_RESPONSE_OBSERVED", "false");
          return null;
        },
      );
      await test.step(fullLoginSubmitSteps.click, async () => {
        await submit.click();
      });
      await test.step(fullLoginSubmitSteps.request, async () => {
        expect(await requestPromise).not.toBeNull();
      });
      const response = await test.step(fullLoginSubmitSteps.response, async () => {
        const value = await responsePromise;
        expect(value).not.toBeNull();
        if (!value) throw new Error("FULL_LOGIN_POST_RESPONSE_NOT_OBSERVED");
        return value;
      });
      await test.step(fullLoginSubmitSteps.status, async () => {
        expect(response.status()).toBe(303);
      });
      await test.step(fullLoginSubmitSteps.location, async () => {
        expect(classifyLocation(response.headers().location)).toBe("EXPECTED_WORKBENCH");
      });
      return;
    }
    const [response] = await Promise.all([
      page.waitForResponse(value => isSessionPost(value.request())),
      submit.click(),
    ]);
    expect(response.status()).toBe(303);
    expect(response.headers().location).toBe("/workbench");
  });
  await test.step(readyStep, async () => {
    const response = await context.request.get(`${baseURL}/api/workbench/v1/session`);
    expect(response.status()).toBe(200);
    expect(await response.json()).toMatchObject({
      principal: loginIdentities[kind],
    });
  });
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
  const full = await login(browser, credentials.full, observations, "FULL");

  const employeeButton = full.page.getByRole("button", { name: /Supplier quality owner/ });
  await test.step("EMPLOYEE_LIST_PAGE_READY", async () => {
    const requestPromise = full.page.waitForRequest(isEmployeeListRequest).then(
      value => {
        test.info().annotations.push({ type: "S5_310_EMPLOYEE_LIST_REQUEST_OBSERVED", description: "true" });
        return value;
      },
      () => {
        test.info().annotations.push({ type: "S5_310_EMPLOYEE_LIST_REQUEST_OBSERVED", description: "false" });
        return null;
      },
    );
    const responsePromise = full.page.waitForResponse(value => isEmployeeListRequest(value.request())).then(
      value => {
        test.info().annotations.push({ type: "S5_310_EMPLOYEE_LIST_RESPONSE_OBSERVED", description: "true" });
        test.info().annotations.push({ type: "S5_310_EMPLOYEE_LIST_HTTP_STATUS", description: String(value.status()) });
        return value;
      },
      () => {
        test.info().annotations.push({ type: "S5_310_EMPLOYEE_LIST_RESPONSE_OBSERVED", description: "false" });
        return null;
      },
    );
    await test.step(employeeListSteps.navigation, async () => {
      await full.page.goto(`${baseURL}/digital-employees`);
    });
    await test.step(employeeListSteps.request, async () => {
      expect(await requestPromise).not.toBeNull();
    });
    const response = await test.step(employeeListSteps.response, async () => {
      const value = await responsePromise;
      expect(value).not.toBeNull();
      if (!value) throw new Error("EMPLOYEE_LIST_RESPONSE_NOT_OBSERVED");
      return value;
    });
    await test.step(employeeListSteps.status, async () => {
      expect(response.status()).toBe(200);
    });
    await test.step(employeeListSteps.count, async () => {
      await expect(employeeButton).toHaveCount(1);
    });
    await test.step(employeeListSteps.visible, async () => {
      await expect(employeeButton).toBeVisible();
    });
  });
  await test.step("EMPLOYEE_EXACT_UI_READ", async () => {
    await employeeButton.click();
    const agentName = full.page.getByText("Quality analysis Agent", { exact: true });
    await expect(agentName).toHaveCount(1);
    await expect(agentName).toBeVisible();
  });
  const employee = await test.step("EMPLOYEE_EXACT_API_READ", async () => {
    const value = await browserFetch(
      full.page,
      "/api/workbench/v1/employees/employee-definition%3Aquality/revisions/employee-revision%3A1",
    );
    expect(value.status).toBe(200);
    expect(value.body.result).toMatchObject({
      employeeDefinitionId: "employee-definition:quality",
      employeeDefinitionRevisionId: "employee-revision:1",
      publicationState: "PUBLISHED",
    });
    expect(value.body.result.employeeDefinitionDigest).toMatch(/^(?:sha256:)?[a-f0-9]{64}$/);
    expect(value.body.result.members.map((member: { kind: string }) => member.kind).sort()).toEqual([
      "AGENT",
      "KNOWLEDGE",
      "MCP",
      "RUNTIME_PROFILE",
      "SKILL",
      "WORKFLOW",
    ]);
    for (const member of value.body.result.members) {
      expect(member.resourceId).toBeTruthy();
      expect(member.revisionId).toBeTruthy();
      expect(member.digest).toMatch(/^(?:sha256:)?[a-f0-9]{64}$/);
    }
    return value;
  });
  const agentMember = employee.body.result.members.find((value: { kind: string }) => value.kind === "AGENT");
  expect(agentMember).toMatchObject({ kind: "AGENT" });
  expect(agentMember.revisionId).toBeTruthy();
  expect(agentMember.digest).toMatch(/^(?:sha256:)?[a-f0-9]{64}$/);
  await test.step("AGENT_EXACT_API_READ", async () => {
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
  });
  await test.step("EMPLOYEE_DETAIL_RENDER", async () => {
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
  });

  const firstEmployees = await test.step("EMPLOYEE_PAGINATION_FIRST", async () => {
    const value = await browserFetch(full.page, "/api/workbench/v1/employees?pageSize=1");
    expect(value.status).toBe(200);
    expect(value.body.result.items).toHaveLength(1);
    expect(value.body.result.totalCount).toBeUndefined();
    return value;
  });
  await test.step("EMPLOYEE_PAGINATION_NEXT", async () => {
    const value = await browserFetch(
      full.page,
      `/api/workbench/v1/employees?pageSize=1&cursor=${encodeURIComponent(firstEmployees.body.result.nextCursor)}`,
    );
    expect(value.status).toBe(200);
    expect(value.body.result.items[0].employeeDefinitionId).not.toBe(
      firstEmployees.body.result.items[0].employeeDefinitionId,
    );
  });

  const firstAgents = await test.step("AGENT_PAGINATION_FIRST", async () => {
    const value = await browserFetch(full.page, "/api/workbench/v1/agents?pageSize=1");
    expect(value.status).toBe(200);
    return value;
  });
  await test.step("AGENT_PAGINATION_NEXT", async () => {
    const value = await browserFetch(
      full.page,
      `/api/workbench/v1/agents?pageSize=1&cursor=${encodeURIComponent(firstAgents.body.result.nextCursor)}`,
    );
    expect(value.status).toBe(200);
    expect(value.body.result.items[0].definitionId).not.toBe(firstAgents.body.result.items[0].definitionId);
  });

  const workQuery = new URLSearchParams({
    panel: "work",
    instanceId: "employee-instance:quality",
    assignmentId: "employee-assignment:quality",
    placementId: "placement:quality",
    attemptId: "attempt:quality",
    agentInstanceId: "agent-instance:quality",
  });
  await test.step("WORK_CHAIN_INITIAL_READ", async () => {
    await full.page.goto(`${baseURL}/digital-employees?${workQuery}`);
    const placement = full.page.getByLabel("Placement 权威详情", { exact: true });
    await expect(placement).toHaveCount(1);
    await expect(placement).toContainText("runtime-instance:quality");
  });
  await test.step("WORK_CHAIN_RELOAD_READ", async () => {
    await full.page.reload();
    await expect(full.page.getByLabel("Placement 权威详情", { exact: true })).toContainText("runtime-instance:quality");
  });

  await test.step("PARENT_ASSIGNMENT_DENIAL", async () => {
    const value = await browserFetch(
      full.page,
      "/api/workbench/v1/instances/employee-instance%3Aquality/assignments/employee-assignment%3Aother/placements/placement%3Aquality?attemptId=attempt%3Aquality&agentInstanceId=agent-instance%3Aquality",
    );
    expect(value).toMatchObject({ status: 404, body: { reasonCode: "PLACEMENT_NOT_FOUND" } });
  });
  await test.step("PARENT_ATTEMPT_DENIAL", async () => {
    const value = await browserFetch(
      full.page,
      "/api/workbench/v1/instances/employee-instance%3Aquality/assignments/employee-assignment%3Aquality/placements/placement%3Aquality?attemptId=attempt%3Aother&agentInstanceId=agent-instance%3Aquality",
    );
    expect(value).toMatchObject({ status: 404, body: { reasonCode: "PLACEMENT_NOT_FOUND" } });
  });
  await test.step("PARENT_AGENT_DENIAL", async () => {
    const value = await browserFetch(
      full.page,
      "/api/workbench/v1/instances/employee-instance%3Aquality/assignments/employee-assignment%3Aquality/placements/placement%3Aquality?attemptId=attempt%3Aquality&agentInstanceId=agent-instance%3Aother",
    );
    expect(value).toMatchObject({ status: 404, body: { reasonCode: "PLACEMENT_NOT_FOUND" } });
  });

  const control = await request.newContext({ baseURL: controlURL });
  await test.step("PLACEMENT_GRANT_REVOKE", async () => {
    const revoked = await control.post("/revoke-placement", { headers: { "x-control-token": controlToken } });
    expect(revoked.ok()).toBe(true);
  });
  await test.step("PLACEMENT_REVOKED_DENIAL", async () => {
    const value = await browserFetch(
      full.page,
      "/api/workbench/v1/instances/employee-instance%3Aquality/assignments/employee-assignment%3Aquality/placements/placement%3Aquality?attemptId=attempt%3Aquality&agentInstanceId=agent-instance%3Aquality",
    );
    expect(value).toMatchObject({ status: 404, body: { reasonCode: "AUTHORIZATION_NOT_FOUND" } });
    await control.dispose();
  });

  await test.step("FULL_SESSION_LOGOUT", async () => {
    const session = await browserFetch(full.page, "/api/workbench/v1/session");
    expect(session.status).toBe(200);
    const logout = await full.context.request.delete(`${baseURL}/api/workbench/v1/session`, {
      headers: { "x-csrf-token": session.body.csrfToken, origin: baseURL },
    });
    expect(logout.status()).toBe(204);
    expect((await browserFetch(full.page, "/api/workbench/v1/employees?pageSize=1")).status).toBe(401);
    await full.context.close();
  });

  const lister = await login(browser, credentials.list, observations, "LISTER");
  await test.step("LISTER_LIST_ALLOWED", async () => {
    expect((await browserFetch(lister.page, "/api/workbench/v1/employees?pageSize=1")).status).toBe(200);
  });
  await test.step("LISTER_EXACT_DENIED", async () => {
    expect(
      await browserFetch(
        lister.page,
        "/api/workbench/v1/employees/employee-definition%3Aquality/revisions/employee-revision%3A1",
      ),
    ).toMatchObject({ status: 404, body: { reasonCode: "AUTHORIZATION_NOT_FOUND" } });
    await lister.context.close();
  });

  const wrongScope = await login(browser, credentials.wrongScope, observations, "WRONG_SCOPE");
  await test.step("WRONG_SCOPE_EXACT_DENIED", async () => {
    expect(
      await browserFetch(
        wrongScope.page,
        "/api/workbench/v1/employees/employee-definition%3Aquality/revisions/employee-revision%3A1",
      ),
    ).toMatchObject({ status: 404, body: { reasonCode: "EMPLOYEE_NOT_FOUND" } });
    await wrongScope.context.close();
  });

  const wrongGrant = await login(browser, credentials.wrongGrant, observations, "WRONG_GRANT");
  await test.step("WRONG_GRANT_EXACT_DENIED", async () => {
    expect(
      await browserFetch(
        wrongGrant.page,
        "/api/workbench/v1/employees/employee-definition%3Aquality/revisions/employee-revision%3A1",
      ),
    ).toMatchObject({ status: 404, body: { reasonCode: "AUTHORIZATION_NOT_FOUND" } });
    await wrongGrant.context.close();
  });
  await test.step("TRANSPORT_BOUNDARY_ASSERTIONS", async () => {
    expect(observations.identityHeaders).toEqual([]);
    expect(observations.privateRequests).toEqual([]);
  });
});
