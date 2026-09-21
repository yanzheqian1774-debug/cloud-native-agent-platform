import {
  expect,
  test,
  type BrowserContext,
  type Locator,
  type Page,
} from "@playwright/test";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name}_REQUIRED`);
  return value;
}

const applicantCredential = required("REL_316_APPLICANT_CREDENTIAL");
const administratorCredential = required("REL_316_ADMIN_CREDENTIAL");

async function login(context: BrowserContext, credential: string): Promise<Page> {
  const page = await context.newPage();
  await page.goto("/api/workbench/v1/login");
  await page.locator('input[name="bootstrapCredential"]').fill(credential);
  const response = page.waitForResponse(value =>
    value.request().method() === "POST"
    && new URL(value.url()).pathname === "/api/workbench/v1/session");
  await page.getByRole("button", { name: "登录并返回工作台", exact: true }).click();
  expect((await response).status()).toBe(303);
  await page.goto("/work");
  await expect(page.getByRole("heading", { name: "新建对话", exact: true })).toBeVisible();
  return page;
}

async function requestIdFrom(container: Locator): Promise<string> {
  const value = await container
    .locator("dt", { hasText: "申请编号" })
    .locator("xpath=following-sibling::dd[1]")
    .textContent();
  expect(value).not.toBeNull();
  return value!.trim();
}

async function approve(
  administrator: Page,
  requestId: string,
  domain: "业务问题与成功标准" | "数字员工配置",
): Promise<void> {
  await administrator.goto(`/authorization-admin?request=${encodeURIComponent(requestId)}`);
  await administrator.getByRole("button", { name: "检查授权申请", exact: true }).click();
  await expect(administrator.getByRole("heading", { name: new RegExp(`^${domain}`) })).toBeVisible();
  await expect(administrator.getByText("等待决定", { exact: true })).toBeVisible();
  await administrator.getByRole("button", { name: "批准精确权限", exact: true }).click();
  await expect(administrator.getByText("已批准", { exact: true })).toBeVisible();
  await expect(administrator.getByText(/不是数字员工生命周期的业务 APPROVE/)).toBeVisible();
}

async function authorizeProblemRequest(
  administrator: Page,
  container: Locator,
): Promise<void> {
  await approve(
    administrator,
    await requestIdFrom(container),
    "业务问题与成功标准",
  );
  await container.getByRole("button", { name: /刷新.*继续|刷新授权状态/ }).click();
}

async function authorizeEmployeeRequest(
  applicant: Page,
  administrator: Page,
): Promise<void> {
  const request = applicant.getByLabel("数字员工权限申请");
  await request.getByRole("button", { name: "提交正式权限申请", exact: true }).click();
  await expect(request.getByText("等待独立管理员决定", { exact: true })).toBeVisible();
  await approve(
    administrator,
    await requestIdFrom(request),
    "数字员工配置",
  );
  await request.getByRole("button", { name: "刷新权限状态并继续", exact: true }).click();
}

test("REL-316 combines trusted Problem, Criteria, and Employee configuration through visible controls", async ({ browser }, testInfo) => {
  test.setTimeout(180_000);
  const applicantContext = await browser.newContext();
  const administratorContext = await browser.newContext();
  const applicant = await login(applicantContext, applicantCredential);
  const administrator = await login(administratorContext, administratorCredential);

  await test.step("Problem create, authorization, and exact readback", async () => {
    await applicant.bringToFront();
    await applicant.getByLabel("你希望解决什么问题？").fill(
      "恢复关键零部件交付，并由业务负责人确认连续三批按承诺日期完成。",
    );
    await applicant.getByLabel("你希望解决什么问题？").press("Enter");
    const draft = applicant.getByLabel("问题草稿卡片");
    await draft.getByRole("button", { name: "确认创建", exact: true }).click();
    await expect(applicant.getByRole("heading", { name: "业务问题已创建", exact: true })).toBeVisible();
    await applicant.getByRole("button", { name: "申请查看权限", exact: true }).click();
    const authorization = applicant.locator("#authorization-message");
    await authorizeProblemRequest(administrator, authorization);
    await expect(applicant.getByRole("heading", { name: "问题详情已读取", exact: true })).toBeVisible();
  });

  await test.step("Criterion and Criteria Set create, authorize, and exact readback", async () => {
    await applicant.bringToFront();
    await applicant.getByRole("button", { name: "申请定义与读取权限", exact: true }).click();
    const workspaceAuthorization = applicant.locator(".px-boundary-card").filter({
      has: applicant.getByText("成功标准权限", { exact: false }),
    });
    await authorizeProblemRequest(administrator, workspaceAuthorization);
    await expect(applicant.getByRole("button", { name: "定义成功标准", exact: true })).toBeVisible();

    await applicant.getByRole("button", { name: "定义成功标准", exact: true }).click();
    await applicant.getByLabel("怎样才算解决？").fill(
      "业务负责人确认未来三批均能按承诺日期交付。",
    );
    await applicant.getByLabel("怎样才算解决？").press("Enter");
    const criterion = applicant.getByLabel("成功标准待确认卡片");
    await criterion.getByLabel("人工验收标准").check();
    await criterion.getByRole("button", { name: "确认并保存", exact: true }).click();
    await expect(criterion).toContainText("关联未完成");
    await criterion.getByRole("button", { name: "申请所需精确权限", exact: true }).click();
    await authorizeProblemRequest(
      administrator,
      criterion.getByLabel("成功标准权限申请"),
    );
    await expect(criterion).toContainText("已保存并完成正式关联");
    await expect(applicant.getByLabel("已保存成功标准")).toContainText(
      "业务负责人确认未来三批均能按承诺日期交付。",
    );
  });

  await test.step("Employee CREATE is frozen, independently authorized, and does not imply READ", async () => {
    await applicant.goto("/digital-employees");
    await applicant.getByRole("button", { name: "＋ 创建数字员工", exact: true }).click();
    await applicant.getByLabel("职责角色").fill("REL-316 可信准备负责人");
    await applicant.getByLabel(/职责清单/).fill("核对业务问题与成功标准\n组织可信数字员工配置");
    await applicant.getByText("高级设置 · 技术身份需配置").click();
    await applicant.getByLabel("Employee Definition ID").fill("employee-definition:rel-316");
    await applicant.getByLabel("Revision ID").fill("employee-revision:rel-316:1");
    await applicant.getByRole("radio", { name: /Quality analysis Agent/ }).check();
    await applicant.getByRole("button", { name: "检查并进入确认", exact: true }).click();
    await expect(applicant.getByLabel("创建命令确认")).toContainText("REL-316 可信准备负责人");
    await applicant.getByRole("button", { name: "确认创建", exact: true }).click();
    await expect(applicant.getByRole("alert")).toContainText("当前身份没有创建权限");
    await authorizeEmployeeRequest(applicant, administrator);
    await expect(applicant.getByRole("status")).toContainText("创建命令已确认 · 草稿");
    await expect(applicant.getByRole("status")).toContainText("当前无权读取详情");
  });

  await test.step("Exact Employee and Agent READ plus lifecycle grants close the lifecycle", async () => {
    await authorizeEmployeeRequest(applicant, administrator);
    await expect(applicant.getByRole("heading", { name: "REL-316 可信准备负责人", exact: true })).toBeVisible();

    for (const action of ["校验修订", "批准修订", "发布修订"] as const) {
      await applicant.getByRole("button", { name: new RegExp(`^${action}`) }).click();
      await applicant.getByRole("button", { name: "确认提交", exact: true }).click();
      await expect(applicant.getByRole("alert")).toContainText("动作权限或成员详情读取权限不足");
      await authorizeEmployeeRequest(applicant, administrator);
      await expect(applicant.getByRole("status")).toContainText(`${action}已确认`);
    }
    await expect(applicant.locator(".employee-detail-context")).toContainText("已发布");
  });

  await test.step("Fresh reload reads formal Problem, Criteria Set, and published Employee state", async () => {
    await applicant.reload();
    await expect(applicant.locator(".employee-detail-context")).toContainText("已发布");
    await applicant.screenshot({
      path: testInfo.outputPath("rel-316-published-employee-1440x900.png"),
      fullPage: true,
    });
    await applicant.goto("/work");
    await applicant.getByText("业务问题与新建入口", { exact: true }).click();
    await applicant.getByRole("button", { name: /恢复关键零部件交付/ }).click();
    await expect(applicant.getByLabel("已保存成功标准")).toContainText(
      "业务负责人确认未来三批均能按承诺日期交付。",
    );
    await applicant.screenshot({
      path: testInfo.outputPath("rel-316-problem-criteria-1440x900.png"),
      fullPage: true,
    });
  });

  await administratorContext.close();
  await applicantContext.close();
});
