import { expect, test } from "@playwright/test";
import { restartOwnedBackend } from "../harness/ownedBackend";

test("publishes a Runtime Profile then a governed Workflow through real Workbenches", async ({ page }) => {
  await page.setViewportSize({width:1440,height:900});
  await page.goto("/runtime-profiles");
  await expect(page.getByRole("heading", { name: "运行配置中心", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Create Native Kubernetes Profile" }).click();
  await page.getByLabel("名称").fill("Native Kubernetes acceptance");
  await page.getByLabel("CPU request").fill("300m");
  await page.getByLabel("Secret References（逗号分隔）").fill("secret-ref:supplier-quality/model-provider");
  await page.getByRole("button", { name: "保存 Runtime Profile Draft" }).click();
  await expect(page.getByRole("heading", { name: "NATIVE_KUBERNETES declaration" })).toBeVisible();
  await page.getByRole("button", { name: "Validate Runtime Profile" }).click();
  await page.getByRole("button", { name: "Review exact Runtime digest" }).click();
  await page.getByRole("button", { name: "Publish immutable Runtime Profile" }).click();
  await expect(page.locator(".module-layout > section").getByText("PUBLISHED", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Execution / placement authority")).toBeVisible();
  await expect(page.getByText("NOT_GRANTED", { exact: true })).toBeVisible();
  await expect(page.getByText("UNVERIFIED", { exact: true })).toBeVisible();

  const profiles = await page.evaluate(async () => {
    const response = await fetch("/api/internal/v0.2.2/runtime-profiles");
    return response.json();
  });
  const published = profiles.find((item: { profile: { lifecycleState: string } }) => item.profile.lifecycleState === "PUBLISHED");
  const runtimeId = published.profile.runtimeProfileId;
  const runtimeRevisionId = published.profile.publishedRevisionId;
  await page.getByRole("button", { name: "Create Runtime successor" }).click();
  await page.getByRole("button", { name: "编辑当前 Profile Draft" }).click();
  await page.getByLabel("CPU request").fill("350m");
  await page.getByRole("button", { name: "保存 Runtime Profile Draft" }).click();
  await expect(page.getByText("350m → 500m")).toBeVisible();

  await page.goto("/workflow-definitions");
  await expect(page.getByRole("heading", { name: "工作流中心", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "新建 Workflow Definition" }).click();
  await page.getByLabel("Workflow 名称").fill("Supplier Quality Response");
  await page.getByLabel("资源 ID").fill(runtimeId);
  await page.getByLabel("修订 ID").fill(runtimeRevisionId);
  await page.getByLabel("用途说明").fill("Supplier quality response");
  await page.getByLabel("步骤 ID", { exact: true }).fill("analyze");
  await page.getByLabel("名称", { exact: true }).fill("Analyze supplier quality");
  await expect(page.getByLabel("Workflow Builder")).toContainText("Workflow Definition 编写器");
  await page.getByRole("button", { name: "Save governed Workflow draft" }).click();
  await expect(page.getByRole("heading", { name: "Canonical DAG" })).toBeVisible();
  await page.getByRole("button", { name: "Validate DAG and references" }).click();
  await page.getByRole("button", { name: "Review exact Workflow digest" }).click();
  await page.getByRole("button", { name: "Publish immutable Workflow" }).click();
  await expect(page.locator(".module-layout > section").getByText("PUBLISHED", { exact: true }).first()).toBeVisible();
  await expect(page.getByLabel("Workflow Technical projection")).toContainText("publishedRevisionId");
  await expect(page.getByText("0 relationships · 0 consumers")).toBeVisible();
  const workflow = await page.evaluate(async () => {
    const values = await (await fetch("/api/internal/v0.2.2/workflow-definitions")).json();
    return values.find((item: {definition:{name:string}}) => item.definition.name === "Supplier Quality Response");
  });
  await page.evaluate(async ({id,version}:{id:string;version:number}) => {
    await fetch(`/api/internal/v0.2.2/workflow-definitions/${encodeURIComponent(id)}/successors`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({expectedVersion:version})});
  }, {id:workflow.definition.workflowDefinitionId,version:workflow.definition.aggregateVersion});
  await page.getByRole("button", { name: "Create Workflow successor" }).click();
  await expect(page.getByLabel("Guided conflict recovery")).toContainText("stale");
  await expect(page.getByLabel("Guided conflict recovery")).toContainText("生命周期命令不会自动重放");
  await page.getByRole("button", { name: "确认权威版本" }).click();
  await page.getByRole("button", { name: "编辑当前 Draft" }).click();
  await page.getByLabel("用途说明").fill("Edited Workflow Definition after explicit CAS recovery");
  await page.getByRole("button", { name: "Save governed Workflow draft" }).click();
  await expect(page.getByText("Edited Workflow Definition after explicit CAS recovery")).toBeVisible();
  await restartOwnedBackend();
  await page.reload();
  await expect(page.getByRole("heading", {name:"Supplier Quality Response", exact:true})).toBeVisible();
  const recovered = await page.evaluate(async (id:string) => (await fetch(`/api/internal/v0.2.2/workflow-definitions/${encodeURIComponent(id)}`)).json(), workflow.definition.workflowDefinitionId);
  expect(recovered.definition.revisions.at(-1).content.description).toBe("Edited Workflow Definition after explicit CAS recovery");
  const recoveredProfile = await page.evaluate(async (id:string) => (await fetch(`/api/internal/v0.2.2/runtime-profiles/${encodeURIComponent(id)}`)).json(), runtimeId);
  expect(recoveredProfile.profile.revisions.at(-1).content.resources.cpuRequest).toBe("350m");
  await page.setViewportSize({width:390,height:844});
  await page.getByLabel("搜索 Workflow Definition").focus();
  await expect(page.getByLabel("搜索 Workflow Definition")).toBeFocused();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBe(true);
});

test("shows controlled empty and validation failure states", async ({ page }) => {
  await page.goto("/workflow-definitions");
  await expect(page.getByRole("heading", { name: "选择 Workflow Definition", exact: true })).toBeVisible();
  await expect(page.getByText("DAG、精确资源绑定、digest、消费者与历史会显示在这里。", { exact: true })).toBeVisible();
  await page.goto("/runtime-profiles");
  await page.getByRole("button", { name: "Create bounded OpenClaw Profile" }).click();
  await page.getByLabel("名称").fill("OpenClaw declaration");
  await page.getByLabel("OpenClaw immutable package reference").fill("oci://registry.example/openclaw@sha256:bounded");
  await page.getByRole("button", { name: "保存 Runtime Profile Draft" }).click();
  await expect(page.getByRole("heading", { name: "OPENCLAW declaration", exact: true })).toBeVisible();
  await expect(page.getByText(/Profile definition only/)).toBeVisible();
  await page.goto("/workflow-definitions");
  await page.getByRole("button", { name: "新建 Workflow Definition" }).click();
  await page.getByLabel("Workflow 名称").fill("Missing reference workflow");
  await page.getByLabel("资源 ID").fill("runtime-profile:missing");
  await page.getByLabel("修订 ID").fill("runtime-profile-revision:missing");
  await page.getByLabel("步骤 ID", { exact: true }).fill("analyze");
  await page.getByLabel("名称", { exact: true }).fill("Analyze missing profile");
  await page.getByRole("button", { name: "Save governed Workflow draft" }).click();
  await page.getByRole("button", { name: "Validate DAG and references" }).click();
  await expect(page.getByLabel("Guided conflict recovery")).toContainText("尝试的聚合版本");
  await expect(page.getByLabel("Guided conflict recovery")).toContainText("权威聚合版本");
  await expect(page.getByLabel("Guided conflict recovery")).toContainText("生命周期命令不会自动重放");
  await expect(page.getByRole("button", { name: "明确恢复保留的定义输入" })).toHaveCount(0);
  await page.getByRole("button", { name: "确认权威版本" }).click();
  await expect(page.getByLabel("Guided conflict recovery")).toHaveCount(0);
});

test("renders a disclosure-safe denied state", async ({ page }) => {
  await page.route("**/api/internal/v0.2.2/workflow-definitions", route => route.fulfill({
    status: 403,
    contentType: "application/json",
    body: JSON.stringify({ detail: { reasonCode: "WORKFLOW_ACCESS_DENIED" } }),
  }));
  await page.goto("/workflow-definitions");
  await expect(page.getByRole("alert")).toContainText("denied");
  await expect(page.getByRole("alert")).toContainText("不可用或当前访问未获授权");
  await expect(page.getByRole("alert")).not.toContainText("WORKFLOW_ACCESS_DENIED");
});
