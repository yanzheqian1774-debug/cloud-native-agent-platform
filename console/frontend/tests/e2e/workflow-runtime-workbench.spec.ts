import { expect, test } from "@playwright/test";

test("publishes a Runtime Profile then a governed Workflow through real Workbenches", async ({ page }) => {
  await page.goto("/runtime-profiles");
  await expect(page.getByRole("heading", { name: "Runtime Profile Workbench" })).toBeVisible();
  await page.getByRole("button", { name: "Create Native Kubernetes Profile" }).click();
  await expect(page.getByRole("heading", { name: "NATIVE_KUBERNETES declaration" })).toBeVisible();
  await page.getByRole("button", { name: "Validate Runtime Profile" }).click();
  await page.getByRole("button", { name: "Review exact Runtime digest" }).click();
  await page.getByRole("button", { name: "Publish immutable Runtime Profile" }).click();
  await expect(page.getByText("PUBLISHED", { exact: true }).first()).toBeVisible();
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

  await page.goto("/workflow-definitions");
  await expect(page.getByRole("heading", { name: "Workflow Workbench" })).toBeVisible();
  await page.getByLabel("Published Runtime Profile ID").fill(runtimeId);
  await page.getByLabel("Published Runtime revision ID").fill(runtimeRevisionId);
  await page.getByRole("button", { name: "Open Workflow Builder" }).click();
  await expect(page.getByLabel("Workflow Builder")).toContainText("Canonical Tasks");
  await page.getByRole("button", { name: "Save governed Workflow draft" }).click();
  await expect(page.getByRole("heading", { name: "Canonical DAG" })).toBeVisible();
  await page.getByRole("button", { name: "Validate DAG and references" }).click();
  await page.getByRole("button", { name: "Review exact Workflow digest" }).click();
  await page.getByRole("button", { name: "Publish immutable Workflow" }).click();
  await expect(page.getByText("PUBLISHED", { exact: true }).first()).toBeVisible();
  await expect(page.getByLabel("Workflow Technical projection")).toContainText("publishedRevisionId");
  await expect(page.getByText("0 relationships · 0 consumers")).toBeVisible();
});

test("shows controlled empty and validation failure states", async ({ page }) => {
  await page.goto("/workflow-definitions");
  await expect(page.getByText(/No Workflow Definitions yet|Select a Workflow Definition/)).toBeVisible();
  await page.goto("/runtime-profiles");
  await page.getByRole("button", { name: "Create bounded OpenClaw Profile" }).click();
  await expect(page.getByRole("heading", { name: "OPENCLAW declaration" })).toBeVisible();
  await expect(page.getByText(/Profile definition only/)).toBeVisible();
  await page.goto("/workflow-definitions");
  await page.getByLabel("Published Runtime Profile ID").fill("runtime-profile:missing");
  await page.getByLabel("Published Runtime revision ID").fill("runtime-profile-revision:missing");
  await page.getByRole("button", { name: "Open Workflow Builder" }).click();
  await page.getByRole("button", { name: "Save governed Workflow draft" }).click();
  await page.getByRole("button", { name: "Validate DAG and references" }).click();
  await expect(page.getByLabel("Guided conflict recovery")).toContainText("Attempted aggregate version");
  await expect(page.getByLabel("Guided conflict recovery")).toContainText("Authoritative aggregate version");
  await expect(page.getByLabel("Guided conflict recovery")).toContainText("lifecycle actions are never replayed automatically");
  await expect(page.getByRole("button", { name: "Explicitly reapply safe draft input" })).toHaveCount(0);
  await page.getByRole("button", { name: "Acknowledge authoritative version" }).click();
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
  await expect(page.getByRole("alert")).toContainText("unavailable or access is not authorized");
  await expect(page.getByRole("alert")).not.toContainText("WORKFLOW_ACCESS_DENIED");
});
