import { expect, test } from "@playwright/test";

test("publishes an exact reviewed revision through the real Workbench", async ({ page }) => {
  await page.goto("/agents");
  await expect(page.getByRole("heading", { name: "Agent Workbench" })).toBeVisible();
  await page.getByRole("button", { name: "Create supplier-quality Agent" }).click();
  await expect(page.getByText("Current draft")).toBeVisible();
  await page.getByRole("button", { name: "Validate draft" }).click();
  await page.getByRole("button", { name: "Human review exact digest" }).click();
  await page.getByRole("button", { name: "Publish immutable revision" }).click();
  await expect(page.getByText("PUBLISHED · Enabled")).toBeVisible();
  await expect(page.getByText("Publication grants governed discovery")).toBeVisible();
});
