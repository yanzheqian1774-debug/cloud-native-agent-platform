import { expect, test } from "@playwright/test";

const kinds = ["AGENT", "SKILL", "MCP", "KNOWLEDGE", "WORKFLOW", "RUNTIME_PROFILE"];
const catalog = kinds.map((kind, index) => ({
  kind,
  identity: `${kind.toLowerCase()}:s5-route-${index}`,
  name: `${kind.replace("_", " ")} Route Fixture`,
  revisionId: `revision:${index}`,
  digest: `sha256:${String(index).padStart(64, "0")}`,
  lifecycleStatus: kind === "KNOWLEDGE" ? "AVAILABLE" : "PUBLISHED",
  capabilityStatus: "AVAILABLE",
  compatibility: "COMPATIBLE",
  reviewStatus: "APPROVED",
  limitations: ["PREVIEW", "NOT_CERTIFIED", "NON_PRODUCTION_READY"],
  relationships: [],
  consumers: [],
  deepLink: "/agents",
}));

test.beforeEach(async ({ page }) => {
  await page.route("**/api/internal/v0.2.2/product/dashboard", route => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({resourceCount: 6, attentionCount: 0, capabilityGapCount: 0, countsByKind: Object.fromEntries(kinds.map(kind => [kind, 1])), authority: "Canonical repositories", limitations: []}),
  }));
  await page.route("**/api/internal/v0.2.2/product/catalog**", route => route.fulfill({contentType: "application/json", body: JSON.stringify(catalog)}));
});

test("visible Resource Catalog navigation reaches the canonical immutable-build route", async ({ page }) => {
  await page.goto("/dashboard");
  await page.getByRole("link", {name: "Resource Catalog", exact: true}).click();
  await expect(page).toHaveURL(/\/catalog$/);
  await expect(page.getByRole("heading", {name: "Resource Catalog", exact: true})).toBeVisible();
  await expect(page.getByLabel("Catalog results").locator("a")).toHaveCount(6);
  for (const kind of kinds) await expect(page.getByLabel("Catalog results")).toContainText(kind.replace("_", " "));
});

test("direct entry, refresh, mobile entry and legacy alias preserve catalog URL context", async ({ page }) => {
  const context = "query=s5-route&kind=AGENT&status=PUBLISHED";
  await page.goto(`/catalog?${context}`);
  await expect(page.getByRole("heading", {name: "Resource Catalog", exact: true})).toBeVisible();
  await expect(page.getByLabel("Search")).toHaveValue("s5-route");
  await expect(page.getByLabel("Resource kind")).toHaveValue("AGENT");
  await expect(page.getByLabel("Lifecycle status")).toHaveValue("PUBLISHED");
  await page.reload();
  await expect(page.getByLabel("Search")).toHaveValue("s5-route");
  await page.setViewportSize({width: 390, height: 844});
  await page.goto(`/resources?${context}`);
  await expect(page).toHaveURL(`/catalog?${context}`);
  await expect(page.getByRole("heading", {name: "Resource Catalog", exact: true})).toBeVisible();
});
