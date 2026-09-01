import { expect, test } from "@playwright/test";
import { backendUrl, restartOwnedBackend } from "../harness/ownedBackend";

const backend = backendUrl();
const qdrant = process.env.KNOWLEDGE_QDRANT_DIRECT_URL;
if (!qdrant) throw new Error("KNOWLEDGE_QDRANT_DIRECT_URL is required");
const authorizedHeaders = {
  "X-Tenant-ID": "tenant-a",
  "X-Security-Domain": "supplier-quality",
  "X-Principal-ID": "human:knowledge-owner",
};

async function publish(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: "Validate draft" }).click();
  await page.getByRole("button", { name: "Human review exact digest" }).click();
  await page.getByRole("button", { name: "Publish immutable revision" }).click();
  await expect(page.getByText("PUBLISHED", { exact: true }).first()).toBeVisible();
}

async function restartBackend(request: import("@playwright/test").APIRequestContext) {
  await restartOwnedBackend();
  await expect.poll(async () => {
    try { return (await request.get(`${backend}/healthz`, { timeout: 500 })).status(); }
    catch { return 0; }
  }, { timeout: 20_000 }).toBe(200);
}

test("completes the real Knowledge lifecycle, retrieval, recovery and purge journey", async ({ page, request }) => {
  await page.goto("/knowledge");
  await expect(page.locator(".demo-primary-nav")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Knowledge Workbench" })).toBeVisible();
  await page.getByRole("button", { name: "Create governed source" }).click();
  await expect(page.getByLabel("Knowledge information hierarchy")).toContainText("Search, Retrieval and Citations");
  await expect(page.getByLabel("Knowledge information hierarchy")).toContainText("Quality Evaluation");
  await expect(page.getByLabel("Knowledge information hierarchy")).toContainText("Import and Duplicate Review");
  await expect(page.getByLabel("Knowledge information hierarchy")).toContainText("Rebuild, Purge and Recovery");
  const identity = (await page.locator(".agent-detail > header .technical-value").textContent())!;
  await expect(page.getByRole("definition").filter({ hasText: "source:supplier-quality" })).toBeVisible();
  await publish(page);
  await page.getByRole("button", { name: "Ingest and index" }).click();
  await expect(page.getByText("COMPLETED", { exact: true })).toBeVisible();

  const first = await (await request.get(`${backend}/api/internal/v0.2.2/knowledge/${encodeURIComponent(identity)}`, { headers: authorizedHeaders })).json();
  const firstRevision = first.knowledge.publishedRevisionId;
  const firstDigest = first.technicalProjection.revisionDigests.at(-1).digest;
  const firstSnapshot = first.knowledge.activeIndexSnapshotId;
  expect(first.productProjection.knowledgeId).toBe(first.technicalProjection.knowledgeId);

  await page.getByRole("button", { name: "Run authorized retrieval" }).click();
  await expect(page.getByText("CITATION", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/Source source:supplier-quality · Provenance human:quality-owner/).first()).toBeVisible();
  await expect(page.getByLabel("Knowledge quality dashboard")).toContainText("POSTGRESQL");
  await page.getByLabel("Retrieval classification").selectOption("HYBRID");
  await page.getByLabel("Filter sourceId").selectOption("source:supplier-quality");
  await page.getByRole("button", { name: "Run Search Playground" }).click();
  await expect(page.getByLabel("Search Playground")).toContainText("CJK_BIGRAM_V1");
  await expect(page.getByLabel("Search Playground").getByRole("table")).toBeVisible();
  await page.getByRole("button", { name: "Evaluate current result" }).click();
  await expect(page.getByLabel("Knowledge quality dashboard")).toContainText("Evaluation runs");
  await expect(page.getByLabel("Evaluation comparison")).toContainText("Run identity");
  await page.getByRole("button", { name: "Compare evaluation run" }).click();
  await expect(page.getByLabel("Evaluation comparison")).toContainText("NO_IMPROVEMENT_CLAIM");
  await page.getByRole("button", { name: "Generate extractive summary" }).click();
  await expect(page.getByLabel("Knowledge operations")).toContainText("DETERMINISTIC_EXTRACTIVE_V1");
  await page.getByRole("button", { name: "Preview bounded import" }).click();
  await expect(page.getByLabel("Import execution")).toContainText("Import PREVIEW");
  await page.getByRole("button", { name: "Execute accepted preview" }).click();
  await expect(page.getByLabel("Import execution")).toContainText("Import PARTIAL");
  await expect(page.getByLabel("Import execution").getByRole("definition").nth(1)).toHaveText("1");
  await expect(page.getByLabel("Import execution").getByRole("definition").nth(2)).toHaveText("1");
  await page.getByRole("button", { name: "Retry controlled import" }).click();
  await expect(page.getByLabel("Import execution").getByRole("definition").nth(1)).toHaveText("1");

  const duplicateDraft = await request.post(`${backend}/api/internal/v0.2.2/knowledge`, {
    headers: authorizedHeaders,
    data: {
      name: "Duplicate supplier procedure",
      source: {
        sourceId: "source:supplier-quality-copy",
        documentId: "document:8d-procedure-copy",
        kind: "TEXT",
        provenance: "human:quality-owner",
        content: "Containment begins immediately after a supplier defect.\n\nRoot cause evidence must cite the verified procedure.",
      },
    },
  });
  expect(duplicateDraft.status()).toBe(201);
  await page.getByRole("button", { name: "Scan duplicates" }).click();
  await expect(page.getByLabel("Duplicate review queue")).toContainText("EXACT candidate");
  await page.getByRole("button", { name: "Classify distinct" }).first().click();
  await expect(page.getByLabel("Duplicate review queue")).toContainText("Human decision recorded");

  const denied = await request.get(`${backend}/api/internal/v0.2.2/knowledge/${encodeURIComponent(identity)}`, { headers: { ...authorizedHeaders, "X-Tenant-ID": "tenant-b" } });
  const absent = await request.get(`${backend}/api/internal/v0.2.2/knowledge/knowledge:absent`, { headers: { ...authorizedHeaders, "X-Tenant-ID": "tenant-b" } });
  expect(denied.status()).toBe(404);
  expect(await denied.text()).toBe(await absent.text());
  const foreignList = await request.get(`${backend}/api/internal/v0.2.2/knowledge`, { headers: { ...authorizedHeaders, "X-Tenant-ID": "tenant-b" } });
  expect(await foreignList.json()).toEqual([]);

  const deniedRetrieval = page.waitForResponse((response) =>
    response.url().includes(`/knowledge/${encodeURIComponent(identity)}/retrievals`)
    && response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Verify denied disclosure" }).click();
  expect((await deniedRetrieval).status()).toBe(404);
  await expect(page.getByRole("alert")).toContainText("unavailable or you are not authorized");
  await page.getByLabel("Successor source content").fill("Updated supplier containment procedure.\n\nCorrective action evidence must cite the approved successor.");
  await page.getByRole("button", { name: "Create successor draft" }).click();
  await publish(page);
  await page.getByRole("button", { name: "Ingest and index" }).click();
  await expect.poll(async () => {
    const response = await request.get(`${backend}/api/internal/v0.2.2/knowledge/${encodeURIComponent(identity)}`, { headers: authorizedHeaders });
    return (await response.json()).knowledge.activeIndexSnapshotId;
  }).not.toBe(firstSnapshot);
  const rebuilt = await (await request.get(`${backend}/api/internal/v0.2.2/knowledge/${encodeURIComponent(identity)}`, { headers: authorizedHeaders })).json();
  expect(rebuilt.knowledge.publishedRevisionId).not.toBe(firstRevision);
  expect(rebuilt.technicalProjection.revisionDigests.at(-1).digest).not.toBe(firstDigest);
  expect(rebuilt.knowledge.activeIndexSnapshotId).not.toBe(firstSnapshot);

  await restartBackend(request);
  await page.reload();
  await page.getByLabel("Filter authorized Packs").fill(identity);
  await page.getByRole("button", { name: /Supplier Quality Procedures/ }).click();
  const recovered = await (await request.get(`${backend}/api/internal/v0.2.2/knowledge/${encodeURIComponent(identity)}`, { headers: authorizedHeaders })).json();
  expect(recovered.knowledge.knowledgeId).toBe(identity);
  expect(recovered.knowledge.publishedRevisionId).toBe(rebuilt.knowledge.publishedRevisionId);
  expect(recovered.knowledge.activeIndexSnapshotId).toBe(rebuilt.knowledge.activeIndexSnapshotId);
  await page.getByRole("tab", { name: "Technical View" }).click();
  await expect(page.getByLabel("Knowledge Technical View").getByText(identity, { exact: true })).toBeVisible();
  await expect(page.getByText("Qdrant contains derived vectors only")).toBeVisible();
  await page.getByRole("tab", { name: "Product View" }).click();
  await page.getByRole("button", { name: "Archive Pack" }).click();
  await expect(page.getByText(/ARCHIVED · Archived/)).toBeVisible();
  await page.getByRole("button", { name: "Review purge impact" }).click();
  await page.getByLabel("Authorization identity").fill("authorization:compliance-one");
  await page.getByLabel("Non-sensitive reason classification").fill("PROHIBITED_CONTENT");
  await page.getByRole("button", { name: "Confirm authorized purge" }).click();
  await expect(page.getByText("Authorized purge completed; only a non-sensitive tombstone remains.")).toBeVisible();

  await page.getByRole("button", { name: "Create governed source" }).click();
  const partialIdentity = (await page.locator(".agent-detail > header .technical-value").textContent())!;
  await publish(page);
  await page.getByRole("button", { name: "Ingest and index" }).click();
  await expect.poll(async () => {
    const response = await request.get(`${backend}/api/internal/v0.2.2/knowledge/${encodeURIComponent(partialIdentity)}`, { headers: authorizedHeaders });
    return (await response.json()).knowledge.lifecycleState;
  }).toBe("AVAILABLE");
  const indexed = await (await request.get(
    `${backend}/api/internal/v0.2.2/knowledge/${encodeURIComponent(partialIdentity)}`,
    { headers: authorizedHeaders },
  )).json();
  expect(indexed).toMatchObject({
    knowledge: { knowledgeId: partialIdentity, lifecycleState: "AVAILABLE" },
    productProjection: { knowledgeId: partialIdentity },
    technicalProjection: { knowledgeId: partialIdentity },
  });
  const indexedKnowledge = indexed.knowledge;
  const indexedRevision = indexedKnowledge.revisions.find(
    (revision: { revisionId: string }) => revision.revisionId === indexedKnowledge.publishedRevisionId,
  );
  expect(indexedRevision).toBeDefined();
  const indexedSnapshot = indexedKnowledge.indexSnapshots.find(
    (snapshot: { snapshotId: string }) => snapshot.snapshotId === indexedKnowledge.activeIndexSnapshotId,
  );
  expect(indexedSnapshot).toMatchObject({
    snapshotId: indexedKnowledge.activeIndexSnapshotId,
    revisionId: indexedKnowledge.publishedRevisionId,
    revisionDigest: indexedRevision.digest,
    status: "ACTIVE",
  });
  const indexedChunkIds = indexedRevision.content.documents.flatMap(
    (document: { chunks: Array<{ chunkId: string }> }) => document.chunks.map((chunk) => chunk.chunkId),
  );
  expect(indexedChunkIds.length).toBeGreaterThan(0);
  const qdrantPoints = await request.post(`${qdrant}/collections/knowledge_v1/points/scroll`, {
    data: {
      filter: {
        must: [
          { key: "namespace", match: { value: "tenant-a" } },
          { key: "securityDomain", match: { value: "supplier-quality" } },
          { key: "knowledgeId", match: { value: partialIdentity } },
          { key: "snapshotId", match: { value: indexedSnapshot.snapshotId } },
        ],
      },
      limit: 100,
      with_payload: true,
      with_vector: false,
    },
  });
  expect(qdrantPoints.status()).toBe(200);
  const pointBody = await qdrantPoints.json();
  expect(pointBody.status).toBe("ok");
  expect(pointBody.result.points.length).toBeGreaterThan(0);
  for (const point of pointBody.result.points) {
    expect(point.id).toBeTruthy();
    expect(point.payload).toMatchObject({
      namespace: "tenant-a",
      securityDomain: "supplier-quality",
      knowledgeId: partialIdentity,
      revisionId: indexedKnowledge.publishedRevisionId,
      revisionDigest: indexedRevision.digest,
      snapshotId: indexedSnapshot.snapshotId,
    });
    expect(indexedChunkIds).toContain(point.payload.chunkId);
  }
  const deletedCollection = await request.delete(`${qdrant}/collections/knowledge_v1`);
  expect(deletedCollection.ok()).toBe(true);
  await expect.poll(async () => (await request.get(`${qdrant}/collections/knowledge_v1`)).status()).toBe(404);
  const recoveryRegion = page.locator(".agent-detail").filter({ hasText: partialIdentity });
  await expect(recoveryRegion).toBeVisible();
  await page.getByRole("button", { name: "Review purge impact" }).click();
  await page.getByLabel("Authorization identity").fill("authorization:compliance-two");
  await page.getByLabel("Non-sensitive reason classification").fill("PROHIBITED_CONTENT");
  const partialPurge = page.waitForResponse((response) =>
    response.url().includes(`/knowledge/${encodeURIComponent(partialIdentity)}/purge`)
    && response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Confirm authorized purge" }).click();
  const partialPurgeResponse = await partialPurge;
  expect(partialPurgeResponse.status()).toBe(202);
  const partialPurgeBody = await partialPurgeResponse.json();
  expect(partialPurgeBody.knowledge).toMatchObject({
    knowledgeId: partialIdentity,
    lifecycleState: "RECOVERY_REQUIRED",
    purge: {
      status: "RECOVERY_REQUIRED",
      remainingSnapshotIds: [indexedSnapshot.snapshotId],
    },
  });
  const persistedRecovery = await (await request.get(
    `${backend}/api/internal/v0.2.2/knowledge/${encodeURIComponent(partialIdentity)}`,
    { headers: authorizedHeaders },
  )).json();
  expect(persistedRecovery.knowledge).toMatchObject(partialPurgeBody.knowledge);
  await expect(recoveryRegion.getByRole("alert").getByText("RECOVERY_REQUIRED", { exact: true })).toBeVisible();

  const design = await page.locator(".agent-workbench").evaluate((element) => {
    const style = getComputedStyle(element);
    return { background: style.backgroundColor, color: style.color };
  });
  expect(design).toEqual({ background: "rgb(246, 247, 249)", color: "rgb(23, 32, 42)" });
});
