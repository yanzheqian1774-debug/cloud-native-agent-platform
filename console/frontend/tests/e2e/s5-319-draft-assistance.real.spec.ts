import { expect, test, type BrowserContext, type Locator, type Page } from "@playwright/test";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name}_REQUIRED`);
  return value;
}

const applicantCredential = required("S5_319_APPLICANT_CREDENTIAL");
const administratorCredential = required("S5_319_ADMIN_CREDENTIAL");

async function login(context: BrowserContext, credential: string): Promise<Page> {
  const page = await context.newPage();
  await page.goto("/api/workbench/v1/login");
  await page.locator('input[name="bootstrapCredential"]').fill(credential);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
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

async function authorizeDraft(applicant: Page, administrator: Page): Promise<Locator> {
  const card = applicant.getByLabel("AI 问题理解与草稿辅助");
  await expect(card).toContainText("AUTHORIZATION_PENDING");
  await approve(administrator, await technicalValue(card, "辅助授权申请"));
  await applicant.bringToFront();
  await card.getByRole("button", { name: "重交正文并刷新授权", exact: true }).click();
  await expect.poll(() => technicalValue(card, "模型授权申请")).not.toBe("尚未提交");
  await approve(administrator, await technicalValue(card, "模型授权申请"));
  await applicant.bringToFront();
  await card.getByRole("button", { name: "重交正文并刷新授权", exact: true }).click();
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
  await expect(assistance).toContainText("合成 transport 验收");

  await applicant.getByLabel("待处理补充（仅本页）").fill("目标是在季度末前把来料缺陷率降到百分之一以内，并由质量负责人确认。");
  await applicant.getByLabel("待处理补充（仅本页）").press("Enter");
  assistance = await authorizeDraft(applicant, administrator);
  await expect(assistance).toContainText("结构化草稿已返回");
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
  await expect(applicant.getByRole("heading", { name: "读取成功", exact: true })).toBeVisible();
  await expect(applicant.getByLabel("AI 问题理解与草稿辅助")).toContainText("合成 transport 验收");

  await applicant.screenshot({
    path: testInfo.outputPath("s5-319-formal-problem-readback-1440x1000.png"),
    fullPage: true,
  });
  await administratorContext.close();
  await applicantContext.close();
});
