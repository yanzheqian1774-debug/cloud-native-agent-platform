import { expect, test, type APIRequestContext, type BrowserContext, type Locator, type Page } from "@playwright/test";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name}_REQUIRED`);
  return value;
}

const applicantCredential = required("S5_320_APPLICANT_CREDENTIAL");
const administratorCredential = required("S5_320_ADMIN_CREDENTIAL");

async function providerDispatches(request: APIRequestContext): Promise<number> {
  const responsesUrl = required("S5_320_MOCK_RESPONSES_URL");
  const response = await request.get(new URL("/stats", responsesUrl).toString());
  expect(response.ok()).toBeTruthy();
  const body = await response.json() as { dispatchCount?: unknown };
  expect(typeof body.dispatchCount).toBe("number");
  return body.dispatchCount as number;
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

test("S5-320 Kimi mock completes clarification, editable draft, confirmation, and formal readback", async ({ browser }, testInfo) => {
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
  await assistance.evaluate((element) => element.scrollIntoView({ block: "center" }));
  await applicant.screenshot({ path: testInfo.outputPath("s5-320-kimi-assistance-1440x1000.png") });
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
  await applicant.locator("#formal-problem-message").scrollIntoViewIfNeeded();
  await applicant.screenshot({ path: testInfo.outputPath("s5-320-kimi-formal-readback-1440x1000.png") });
  await administratorContext.close();
  await applicantContext.close();
});

test("S5-320 authorization denial has zero Kimi mock dispatch", async ({ browser, request }) => {
  const applicantContext = await browser.newContext();
  const administratorContext = await browser.newContext();
  const applicant = await login(applicantContext, applicantCredential);
  const administrator = await login(administratorContext, administratorCredential);
  await applicant.getByLabel("你希望解决什么问题？").fill("授权拒绝的供应商质量问题");
  await applicant.getByLabel("你希望解决什么问题？").press("Enter");
  const card = applicant.getByLabel("AI 问题理解与草稿辅助");
  const before = await providerDispatches(request);
  await deny(administrator, await technicalValue(card, "辅助授权申请"));
  await applicant.bringToFront();
  await card.getByRole("button", { name: "使用已保留正文继续 AI 调用", exact: true }).click();
  const denial = card.locator("xpath=ancestor::article[1]").getByRole("alert");
  await expect(denial).toContainText("DRAFT_ASSISTANCE_NOT_FOUND");
  expect(await providerDispatches(request)).toBe(before);
  await administratorContext.close();
  await applicantContext.close();
});

test("S5-320 Kimi nonterminal remains UNKNOWN and is never redispatched", async ({ browser, request }) => {
  const applicantContext = await browser.newContext();
  const administratorContext = await browser.newContext();
  const applicant = await login(applicantContext, applicantCredential);
  const administrator = await login(administratorContext, administratorCredential);
  await applicant.getByLabel("你希望解决什么问题？").fill("[NONTERMINAL] 供应商质量问题");
  await applicant.getByLabel("你希望解决什么问题？").press("Enter");
  const card = await authorizeDraft(applicant, administrator);
  await expect(card).toContainText("调用结果尚不确定");
  await expect(card).toContainText("PROVIDER_FOREGROUND_NONTERMINAL");
  const afterDispatch = await providerDispatches(request);
  await card.getByRole("button", { name: "观察原调用", exact: true }).click();
  await expect(card).toContainText("PROVIDER_OBSERVATION_UNSUPPORTED_FOREGROUND");
  expect(await providerDispatches(request)).toBe(afterDispatch);
  await card.getByRole("button", { name: "请求取消", exact: true }).click();
  await expect(card).toContainText("PROVIDER_CANCELLATION_UNSUPPORTED_FOREGROUND");
  await expect(card).not.toContainText("已确认取消");
  expect(await providerDispatches(request)).toBe(afterDispatch);
  await administratorContext.close();
  await applicantContext.close();
});

test("S5-320 formal budget refusal blocks product dispatch on the same ledger", async ({ browser, request }, testInfo) => {
  test.setTimeout(240_000);
  const administratorContext = await browser.newContext();
  const administrator = await login(administratorContext, administratorCredential);
  let consumed = await providerDispatches(request);
  // Distinct user operations consume the existing immutable ledger; no ledger,
  // profile, or failed-operation key is replaced to evade its cap.
  while (consumed < 10) {
    const context = await browser.newContext();
    const applicant = await login(context, applicantCredential);
    await applicant.getByLabel("你希望解决什么问题？").fill(`合成预算消耗问题 ${consumed}`);
    await applicant.getByLabel("你希望解决什么问题？").press("Enter");
    const card = await authorizeDraft(applicant, administrator);
    await expect(card).toContainText("需要补充信息");
    expect(await providerDispatches(request)).toBe(consumed + 1);
    consumed += 1;
    await context.close();
  }
  const context = await browser.newContext();
  const applicant = await login(context, applicantCredential);
  const before = await providerDispatches(request);
  await applicant.getByLabel("你希望解决什么问题？").fill("合成预算上限拒绝问题");
  await applicant.getByLabel("你希望解决什么问题？").press("Enter");
  const card = await authorizeDraft(applicant, administrator);
  const refusal = card.locator("xpath=ancestor::article[1]").getByRole("alert");
  await expect(refusal).toContainText("PROVIDER_BUDGET_DENIED");
  await expect(card).not.toContainText("可修改草稿已生成");
  await expect(applicant.getByLabel("问题草稿卡片")).toHaveCount(0);
  await expect(applicant.getByRole("heading", { name: "业务问题已创建", exact: true })).toHaveCount(0);
  const after = await providerDispatches(request);
  expect(before).toBe(10);
  expect(after).toBe(before);
  await refusal.getByRole("button", { name: "使用原正文重试调用", exact: true }).click();
  await expect(applicant.getByText("PROVIDER_BUDGET_DENIED", { exact: true })).toBeVisible();
  await expect(applicant.getByLabel("问题草稿卡片")).toHaveCount(0);
  expect(await providerDispatches(request)).toBe(after);
  await testInfo.attach("budget-refusal-counts", {
    body: Buffer.from(JSON.stringify({ ledgerId: "s5-v023-impl-320-kimi-mock-provider", before, after, afterSameKeyReplay: after, callCap: 10, reason: "PROVIDER_BUDGET_DENIED" })),
    contentType: "application/json",
  });
  await applicant.screenshot({ path: testInfo.outputPath("s5-320-kimi-budget-refusal.png") });
  await context.close();
  await administratorContext.close();
});
