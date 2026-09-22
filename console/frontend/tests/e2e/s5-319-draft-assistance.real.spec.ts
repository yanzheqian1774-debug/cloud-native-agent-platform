import { expect, test, type APIRequestContext, type BrowserContext, type Locator, type Page } from "@playwright/test";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name}_REQUIRED`);
  return value;
}

const applicantCredential = required("S5_319_APPLICANT_CREDENTIAL");
const administratorCredential = required("S5_319_ADMIN_CREDENTIAL");

async function providerCalls(request: APIRequestContext): Promise<number> {
  const responsesUrl = process.env.S5_319_MOCK_RESPONSES_URL;
  if (!responsesUrl) throw new Error("S5_319_MOCK_RESPONSES_URL_REQUIRED");
  const response = await request.get(new URL("/stats", responsesUrl).toString());
  expect(response.ok()).toBeTruthy();
  const body = await response.json() as { calls?: unknown };
  expect(typeof body.calls).toBe("number");
  return body.calls as number;
}

async function login(context: BrowserContext, credential: string): Promise<Page> {
  const page = await context.newPage();
  await page.goto("/api/workbench/v1/login");
  await page.locator('input[name="bootstrapCredential"]').fill(credential);
  await page.getByRole("button", { name: "登录并返回工作台", exact: true }).click();
  await page.goto("/work");
  await expect(page.getByRole("heading", { name: "新建对话", exact: true })).toBeVisible();
  return page;
}

async function technicalValue(card: Locator, label: string): Promise<string> {
  const details = card.locator("details");
  if (!(await details.getAttribute("open"))) await details.locator("summary").click();
  const value = await details.locator("dt", { hasText: label })
    .locator("xpath=following-sibling::dd[1]").textContent();
  expect(value).not.toBeNull();
  return value!.trim();
}

async function approve(administrator: Page, requestId: string): Promise<void> {
  await administrator.goto(`/authorization-admin?request=${encodeURIComponent(requestId)}`);
  await administrator.getByRole("button", { name: "检查授权申请", exact: true }).click();
  await expect(administrator.getByText("等待决定", { exact: true })).toBeVisible();
  await administrator.getByRole("button", { name: "批准精确权限", exact: true }).click();
  await expect(administrator.getByText("已批准", { exact: true })).toBeVisible();
}

async function deny(administrator: Page, requestId: string): Promise<void> {
  await administrator.goto(`/authorization-admin?request=${encodeURIComponent(requestId)}`);
  await administrator.getByRole("button", { name: "检查授权申请", exact: true }).click();
  await administrator.getByRole("button", { name: "拒绝申请", exact: true }).click();
  await expect(administrator.getByText("已拒绝", { exact: true })).toBeVisible();
}

async function authorizeDraft(applicant: Page, administrator: Page): Promise<Locator> {
  const card = applicant.getByLabel("AI 问题理解与草稿辅助");
  await expect(card).toContainText("AUTHORIZATION_PENDING");
  await approve(administrator, await technicalValue(card, "辅助授权申请"));
  await applicant.bringToFront();
  await card.getByRole("button", { name: "使用已保留正文继续 AI 调用", exact: true }).click();
  await expect.poll(() => technicalValue(card, "模型授权申请")).not.toBe("尚未提交");
  await approve(administrator, await technicalValue(card, "模型授权申请"));
  await applicant.bringToFront();
  await card.getByRole("button", { name: "使用已保留正文继续 AI 调用", exact: true }).click();
  return card;
}

test("S5-319 completes governed clarification, editable draft, confirmation, and formal readback", async ({ browser }, testInfo) => {
  test.setTimeout(240_000);
  const applicantContext = await browser.newContext();
  const administratorContext = await browser.newContext();
  const applicant = await login(applicantContext, applicantCredential);
  const administrator = await login(administratorContext, administratorCredential);

  await applicant.getByLabel("你希望解决什么问题？").fill("供应商质量有问题");
  await applicant.getByLabel("你希望解决什么问题？").press("Enter");
  let assistance = await authorizeDraft(applicant, administrator);
  await expect(assistance).toContainText("需要补充信息");
  await expect(assistance).toContainText("没有调用真实 AI 服务");

  await applicant.getByLabel("待处理补充（仅本页）").fill("目标是在季度末前把来料缺陷率降到百分之一以内，并由质量负责人确认。");
  await applicant.getByLabel("待处理补充（仅本页）").press("Enter");
  assistance = await authorizeDraft(applicant, administrator);
  await expect(assistance).toContainText("可修改草稿已生成");
  await assistance.evaluate((element) => element.scrollIntoView({block: "center"}));
  await applicant.screenshot({
    path: testInfo.outputPath("s5-319-assistance-viewport-1440x1000.png"),
  });
  const draft = applicant.getByLabel("问题草稿卡片");
  await draft.getByRole("button", { name: "修改", exact: true }).click();
  await draft.getByLabel("建议名称（可选修改）").fill("季度末供应商来料质量改善");
  await draft.getByRole("button", { name: "采用字段修改", exact: true }).click();
  await draft.getByRole("button", { name: "确认创建", exact: true }).click();
  await expect(applicant.getByRole("heading", { name: "业务问题已创建", exact: true })).toBeVisible();

  await applicant.getByRole("button", { name: "申请查看权限", exact: true }).click();
  const problemAuthorization = applicant.locator("#authorization-message");
  const problemRequest = await problemAuthorization.locator("dt", { hasText: "申请编号" })
    .locator("xpath=following-sibling::dd[1]").textContent();
  await approve(administrator, problemRequest!.trim());
  await applicant.bringToFront();
  await problemAuthorization.getByRole("button", { name: "刷新授权状态", exact: true }).click();
  await expect(applicant.getByRole("heading", { name: "问题详情已读取", exact: true })).toBeVisible();
  await expect(applicant.getByLabel("AI 问题理解与草稿辅助")).toContainText("没有调用真实 AI 服务");

  const sidebar = await applicant.locator(".px-sidebar").boundingBox();
  const topbar = await applicant.locator(".px-topbar").boundingBox();
  const content = await applicant.locator(".px-content").boundingBox();
  const formalProblem = await applicant.locator("#formal-problem-message").boundingBox();
  expect(sidebar).not.toBeNull();
  expect(topbar).not.toBeNull();
  expect(content).not.toBeNull();
  expect(formalProblem).not.toBeNull();
  expect(content!.x).toBeGreaterThanOrEqual(sidebar!.x + sidebar!.width);
  expect(formalProblem!.x).toBeGreaterThanOrEqual(sidebar!.x + sidebar!.width);
  expect(formalProblem!.y).toBeGreaterThanOrEqual(topbar!.y + topbar!.height);
  await applicant.locator("#formal-problem-message").scrollIntoViewIfNeeded();
  await applicant.screenshot({path: testInfo.outputPath("s5-319-formal-and-criteria-viewport-1440x1000.png")});
  await administratorContext.close();
  await applicantContext.close();
});

test("S5-319 shows authorization denial without a provider call", async ({ browser, request }) => {
  const applicantContext = await browser.newContext();
  const administratorContext = await browser.newContext();
  const applicant = await login(applicantContext, applicantCredential);
  const administrator = await login(administratorContext, administratorCredential);
  await applicant.getByLabel("你希望解决什么问题？").fill("授权拒绝的供应商质量问题");
  await applicant.getByLabel("你希望解决什么问题？").press("Enter");
  const card = applicant.getByLabel("AI 问题理解与草稿辅助");
  const callsBeforeDenial = await providerCalls(request);
  await deny(administrator, await technicalValue(card, "辅助授权申请"));
  await applicant.bringToFront();
  await card.getByRole("button", { name: "使用已保留正文继续 AI 调用", exact: true }).click();
  const denial = card.locator("xpath=ancestor::article[1]").getByRole("alert");
  await expect(denial).toHaveCount(1);
  await expect(denial).toContainText("无法打开该内容");
  await expect(denial).toContainText("DRAFT_ASSISTANCE_NOT_FOUND");
  await expect(card).toContainText("AUTHORIZATION_PENDING");
  await expect(card).toContainText("尚未建立");
  expect(await providerCalls(request)).toBe(callsBeforeDenial);
  await administratorContext.close();
  await applicantContext.close();
});

test("S5-319 keeps nonterminal foreground calls observable and cancellation unconfirmed", async ({ browser, request }) => {
  const applicantContext = await browser.newContext();
  const administratorContext = await browser.newContext();
  const applicant = await login(applicantContext, applicantCredential);
  const administrator = await login(administratorContext, administratorCredential);
  await applicant.getByLabel("你希望解决什么问题？").fill("[NONTERMINAL] 供应商质量问题");
  await applicant.getByLabel("你希望解决什么问题？").press("Enter");
  const card = applicant.getByLabel("AI 问题理解与草稿辅助");
  await approve(administrator, await technicalValue(card, "辅助授权申请"));
  await applicant.bringToFront();
  await card.getByRole("button", { name: "使用已保留正文继续 AI 调用", exact: true }).click();
  await expect.poll(() => technicalValue(card, "模型授权申请")).not.toBe("尚未提交");
  await approve(administrator, await technicalValue(card, "模型授权申请"));
  await applicant.bringToFront();
  await card.getByRole("button", { name: "使用已保留正文继续 AI 调用", exact: true }).click();
  await expect(card).toContainText("调用结果尚不确定");
  await expect(card).toContainText("PROVIDER_FOREGROUND_NONTERMINAL");
  const callsAfterDispatch = await providerCalls(request);
  await card.getByRole("button", { name: "观察原调用", exact: true }).click();
  await expect(card).toContainText("PROVIDER_OBSERVATION_UNSUPPORTED_FOREGROUND");
  expect(await providerCalls(request)).toBe(callsAfterDispatch);
  await card.getByRole("button", { name: "请求取消", exact: true }).click();
  await expect(card).toContainText("取消已请求，停止未确认");
  await expect(card).toContainText("远端停止和停止计费均未证实");
  await expect(card).toContainText("PROVIDER_CANCELLATION_UNSUPPORTED_FOREGROUND");
  await expect(card).not.toContainText("已确认取消");
  expect(await providerCalls(request)).toBe(callsAfterDispatch);
  await administratorContext.close();
  await applicantContext.close();
});
