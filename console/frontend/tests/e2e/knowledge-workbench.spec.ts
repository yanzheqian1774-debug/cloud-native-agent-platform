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

async function createSource(page: import("@playwright/test").Page) {
  await page.getByRole("button", {name:"创建知识源",exact:true}).click();
  const dialog=page.getByRole("dialog",{name:"创建知识源"});
  await dialog.getByLabel("名称",{exact:true}).fill("Supplier Quality Procedures");
  await dialog.getByLabel("来源ID",{exact:true}).fill("source:supplier-quality");
  await dialog.getByLabel("文档ID",{exact:true}).fill("document:8d-procedure");
  await dialog.getByLabel("出处标识",{exact:true}).fill("human:quality-owner");
  await dialog.getByLabel("知识正文",{exact:true}).fill("Containment begins immediately after a supplier defect.\n\nRoot cause evidence must cite the verified procedure.");
  await dialog.getByRole("button",{name:"创建草稿",exact:true}).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator(".agent-detail > header .technical-value")).toBeVisible();
}

async function publish(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: "校验草稿" }).click();
  await page.getByRole("button", { name: "人工审阅精确摘要" }).click();
  await page.getByRole("button", { name: "发布不可变修订" }).click();
  await expect(page.getByText("已发布 · PUBLISHED", { exact: true }).first()).toBeVisible();
}

async function restartBackend(request: import("@playwright/test").APIRequestContext) {
  await restartOwnedBackend();
  await expect.poll(async () => {
    try { return (await request.get(`${backend}/healthz`, { timeout: 500 })).status(); }
    catch { return 0; }
  }, { timeout: 20_000 }).toBe(200);
}

test("completes the real Knowledge lifecycle, retrieval, recovery and purge journey", async ({ page, request }, testInfo) => {
  await page.setViewportSize({width:1440,height:900});
  await page.goto("/knowledge");
  await expect(page.getByRole("navigation", { name: "P1 核心产品导航" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "知识中心", exact: true })).toBeVisible();
  await createSource(page);
  const hierarchy=page.getByRole("navigation",{name:"Knowledge information hierarchy"});
  const hierarchyItems=hierarchy.locator("li");
  await expect(hierarchyItems).toHaveCount(4);
  await expect(hierarchyItems.first()).toContainText("日常检索与引用");
  await expect(hierarchyItems.first()).toContainText("Routine: Search, Retrieval and Citations");
  await expect(hierarchyItems.nth(1)).toContainText("质量评估");
  await expect(hierarchyItems.nth(2)).toContainText("导入与重复项审查");
  await expect(hierarchyItems.last()).toContainText("索引重建、清除与恢复");
  await expect(hierarchyItems.last()).toContainText("Advanced high-impact: Rebuild, Purge and Recovery");
  const identity = (await page.locator(".agent-detail > header .technical-value").textContent())!;
  await expect(page.getByRole("definition").filter({ hasText: "source:supplier-quality" })).toBeVisible();
  await publish(page);
  await page.getByRole("button", { name: "导入并建立索引" }).click();
  await expect(page.getByText(/ingestion-job.*COMPLETED/)).toBeVisible();

  const first = await (await request.get(`${backend}/api/internal/v0.2.2/knowledge/${encodeURIComponent(identity)}`, { headers: authorizedHeaders })).json();
  const firstRevision = first.knowledge.publishedRevisionId;
  const firstDigest = first.technicalProjection.revisionDigests.at(-1).digest;
  const firstSnapshot = first.knowledge.activeIndexSnapshotId;
  expect(first.productProjection.knowledgeId).toBe(first.technicalProjection.knowledgeId);

  await page.getByLabel("检索词", {exact:true}).fill("supplier defect containment procedure");
  await page.getByRole("button", { name: "执行授权检索" }).click();
  await expect(page.getByText(/^CITATION ·/).first()).toBeVisible();
  await expect(page.getByLabel("Workbench retrieval history")).toContainText("source:supplier-quality");
  await expect(page.getByLabel("Workbench retrieval history")).toContainText("human:quality-owner");
  await expect(page.getByLabel("Knowledge quality dashboard")).toContainText("POSTGRESQL");
  await page.screenshot({path:testInfo.outputPath("knowledge-1440.png")});
  await page.getByLabel("检索方式").selectOption("HYBRID");
  await page.getByLabel("Filter sourceId").selectOption("source:supplier-quality");
  await page.getByRole("button", { name: "执行检索实验" }).click();
  await expect(page.getByLabel("Search Playground")).toContainText("CJK_BIGRAM_V1");
  await expect(page.getByLabel("Search Playground").getByRole("table")).toBeVisible();
  await page.getByRole("button", { name: "评估当前结果" }).click();
  await expect(page.getByLabel("Evaluation comparison")).toContainText("EVALUATION_RUN");
  await expect(page.getByLabel("Evaluation comparison")).toContainText("entityId");
  await page.getByRole("button", { name: "比较评估记录" }).click();
  await expect(page.getByLabel("Evaluation comparison")).toContainText("NO_IMPROVEMENT_CLAIM");
  await page.getByRole("button", { name: "生成抽取式摘要" }).click();
  await expect(page.getByLabel("Knowledge operations")).toContainText("DETERMINISTIC_EXTRACTIVE_V1");
  await page.getByLabel("导入格式").selectOption("jsonl");
  await page.getByLabel("导入内容", {exact:true}).fill('{"name":"Imported procedure","content":"Authorized draft content."}\n{"name":"","content":"Rejected without disclosure"}');
  await page.getByRole("button", { name: "预览导入" }).click();
  await expect(page.getByLabel("Import execution")).toContainText("导入状态 PREVIEW");
  await page.getByRole("button", { name: "执行已确认预览" }).click();
  await expect(page.getByLabel("Import execution")).toContainText("导入状态 PARTIAL");
  await expect(page.getByLabel("Import execution").getByRole("definition").nth(3)).toHaveText("1");
  await expect(page.getByLabel("Import execution").getByRole("definition").nth(4)).toHaveText("1");
  await page.getByRole("button", { name: "重试部分导入" }).click();
  await expect(page.getByLabel("Import execution").getByRole("definition").nth(3)).toHaveText("1");

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
  await page.getByRole("button", { name: "扫描重复项" }).click();
  await expect(page.getByLabel("Duplicate review queue")).toContainText("EXACT candidate");
  await page.getByRole("button", { name: "判定不同" }).first().click();
  await expect(page.getByLabel("Duplicate review queue")).toContainText("人工决定已记录");

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
  await page.getByRole("button", { name: "验证拒绝披露" }).click();
  expect((await deniedRetrieval).status()).toBe(404);
  await expect(page.getByRole("alert")).toContainText("资源不可用或当前访问未获授权");
  // A separately authorized retrieval advances the aggregate while the form holds an old version.
  const beforeConflict = await (await request.get(`${backend}/api/internal/v0.2.2/knowledge/${encodeURIComponent(identity)}`, {headers:authorizedHeaders})).json();
  const concurrentRetrieval = await request.post(`${backend}/api/internal/v0.2.2/knowledge/${encodeURIComponent(identity)}/retrievals`, {
    headers:authorizedHeaders,data:{expectedVersion:beforeConflict.knowledge.aggregateVersion,query:"supplier containment",authorization:"ALLOW",authorizationDecisionId:"authorization:278-concurrent"},
  });
  expect(concurrentRetrieval.ok()).toBe(true);
  await page.getByLabel("后继正文").fill("Updated supplier containment procedure.\n\nCorrective action evidence must cite the approved successor.");
  await page.getByRole("button", { name: "创建后继草稿" }).click();
  await expect(page.getByLabel("Guided conflict recovery")).toContainText("权威版本");
  await expect(page.getByLabel("后继正文",{exact:true})).toHaveValue("Updated supplier containment procedure.\n\nCorrective action evidence must cite the approved successor.");
  await page.getByRole("button",{name:"核对后保留输入"}).click();
  await page.getByRole("button", { name: "创建后继草稿" }).click();
  await publish(page);
  await page.getByRole("button", { name: "导入并建立索引" }).click();
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
  await page.getByLabel("筛选知识包").fill(identity);
  await page.getByRole("button", { name: /Supplier Quality Procedures/ }).click();
  const recovered = await (await request.get(`${backend}/api/internal/v0.2.2/knowledge/${encodeURIComponent(identity)}`, { headers: authorizedHeaders })).json();
  expect(recovered.knowledge.knowledgeId).toBe(identity);
  expect(recovered.knowledge.publishedRevisionId).toBe(rebuilt.knowledge.publishedRevisionId);
  expect(recovered.knowledge.activeIndexSnapshotId).toBe(rebuilt.knowledge.activeIndexSnapshotId);
  await page.getByRole("button", { name: "技术视图" }).click();
  await expect(page.getByLabel("Knowledge Technical View").getByText(identity, { exact: true })).toBeVisible();
  await expect(page.getByText(/Qdrant仅包含派生向量/)).toBeVisible();
  await page.getByRole("button", { name: "产品视图" }).click();
  await page.getByRole("button", { name: "归档知识包" }).click();
  await expect(page.getByText(/ARCHIVED · 已归档/)).toBeVisible();
  await page.getByRole("button", { name: "审查清除影响" }).click();
  await page.getByLabel("授权标识").fill("authorization:compliance-one");
  await page.getByLabel("非敏感原因分类").fill("PROHIBITED_CONTENT");
  await page.getByRole("button", { name: "确认授权清除" }).click();
  await expect(page.getByText(/清除响应已收到/)).toBeVisible();
  expect((await request.get(`${backend}/api/internal/v0.2.2/knowledge/${encodeURIComponent(identity)}`, {headers:authorizedHeaders})).status()).toBe(404);

  await createSource(page);
  const partialIdentity = (await page.locator(".agent-detail > header .technical-value").textContent())!;
  await publish(page);
  await page.getByRole("button", { name: "导入并建立索引" }).click();
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
  await page.getByRole("button", { name: "审查清除影响" }).click();
  await page.getByLabel("授权标识").fill("authorization:compliance-two");
  await page.getByLabel("非敏感原因分类").fill("PROHIBITED_CONTENT");
  const partialPurge = page.waitForResponse((response) =>
    response.url().includes(`/knowledge/${encodeURIComponent(partialIdentity)}/purge`)
    && response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "确认授权清除" }).click();
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
  await expect(recoveryRegion.getByRole("alert").filter({hasText:"RECOVERY_REQUIRED"})).toBeVisible();

  const design = await page.locator(".agent-workbench").evaluate((element) => {
    const style = getComputedStyle(element);
    return { background: style.backgroundColor, color: style.color };
  });
  expect(design).toEqual({ background: "rgb(246, 247, 249)", color: "rgb(23, 32, 42)" });
});

// Transport fixtures isolate frontend race/error behavior; the journey above proves real services.
async function installUiFixtures(page: import("@playwright/test").Page) {
  const resource=(id:string)=>({knowledgeId:id,name:`知识包 ${id}`,aggregateVersion:1,lifecycleState:"AVAILABLE",archived:false,currentDraftRevisionId:null,publishedRevisionId:`revision:${id}`,activeIndexSnapshotId:`snapshot:${id}`,revisions:[{revisionId:`revision:${id}`,state:"PUBLISHED",digest:`digest:${id}`,content:{name:id,source:{sourceId:`source:${id}`,kind:"TEXT",provenance:"human:278"},documents:[]}}],ingestionJobs:[],indexSnapshots:[],retrievals:[],purge:null,limitations:[]});
  await page.route("**/api/internal/v0.2.2/knowledge**",async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith("/operations/dashboard"))return route.fulfill({json:{authorizedKnowledgeCount:2,activeSnapshotCount:2,authority:"UI_TEST_FIXTURE"}});
    if(path.endsWith("/operations/metadata"))return route.fulfill({json:{sourceId:[],documentId:[],contentType:[],revisionId:[],snapshotId:[]}});
    if(path.endsWith("/knowledge"))return route.fulfill({json:[resource("a"),resource("b")]});
    const id=path.split("/").at(-1)!;
    return route.fulfill({json:{knowledge:resource(id),technicalProjection:{knowledgeId:id},productProjection:{knowledgeId:id}}});
  });
}

test("isolates late retrieval responses and preserves filter and exact revision context",async({page})=>{
  await installUiFixtures(page);
  let finish!:()=>void;
  const delayed=new Promise<void>(resolve=>{finish=resolve;});
  let requested=false;
  await page.route("**/knowledge/operations/search",async route=>{requested=true;await delayed;await route.fulfill({json:{classification:"HYBRID",tokenizerVersion:"late-a-result",results:[]}});});
  await page.goto("/knowledge?q=知识包&resourceId=b");
  await expect(page.locator(".agent-detail h2")).toHaveText("知识包 b");
  await page.getByRole("button",{name:/知识包 a/}).click();
  await expect(page.locator(".agent-detail h2")).toHaveText("知识包 a");
  await page.getByLabel("检索词",{exact:true}).fill("query a");
  await page.getByRole("button",{name:"执行检索实验",exact:true}).click();
  await expect.poll(()=>requested).toBe(true);
  await page.goBack();
  await expect(page.locator(".agent-detail h2")).toHaveText("知识包 b");
  await expect(page.locator(".agent-detail h2")).toBeFocused();
  const lateResponse=page.waitForResponse(response=>response.url().endsWith("/operations/search"));
  finish();
  await (await lateResponse).finished();
  await expect(page.getByText("late-a-result")).toHaveCount(0);
  await expect(page.getByLabel("检索词",{exact:true})).toHaveValue("");
  await page.getByLabel("查看修订").selectOption("revision:b");
  await expect(page).toHaveURL(/revisionId=revision%3Ab/);
  await page.getByRole("button",{name:"返回筛选列表"}).click();
  await expect(page.getByLabel("筛选知识包")).toHaveValue("知识包");
  await expect(page.getByRole("heading",{name:"知识包列表"})).toBeFocused();
  await page.goto("/knowledge?resourceId=b&revisionId=missing");
  await expect(page.getByRole("alert")).toContainText("不能用其他修订替代");
});

test("validates real form inputs and keeps denied and service failures distinct at mobile width",async({page},testInfo)=>{
  await installUiFixtures(page);
  await page.setViewportSize({width:390,height:844});
  await page.goto("/knowledge");
  await page.getByRole("button",{name:"创建知识源",exact:true}).click();
  const dialog=page.getByRole("dialog",{name:"创建知识源"});
  await dialog.getByLabel("名称",{exact:true}).fill("278 用户输入");
  await dialog.getByLabel("来源ID",{exact:true}).fill("非法来源");
  await dialog.getByLabel("文档ID",{exact:true}).fill("document:278");
  await dialog.getByLabel("出处标识",{exact:true}).fill("human:278");
  await dialog.getByLabel("知识正文",{exact:true}).fill("用户提供的正文");
  await dialog.getByRole("button",{name:"创建草稿"}).click();
  await expect(dialog.getByRole("alert")).toContainText("来源ID");
  await dialog.getByLabel("来源ID",{exact:true}).fill("source:278");
  let submissions=0;
  await page.route("**/knowledge",async route=>{
    if(route.request().method()==="POST"){
      submissions++;
      expect(route.request().postDataJSON()).toMatchObject({name:"278 用户输入",source:{sourceId:"source:278",content:"用户提供的正文"}});
      return route.fulfill({status:503,json:{detail:{reasonCode:"KNOWLEDGE_STORAGE_UNAVAILABLE"}}});
    }
    return route.fallback();
  });
  await dialog.getByRole("button",{name:"创建草稿"}).evaluate(button=>{button.click();button.click();});
  await expect(dialog.getByRole("alert")).toContainText("知识服务暂不可用");
  expect(submissions).toBe(1);
  await expect(dialog.getByLabel("知识正文",{exact:true})).toHaveValue("用户提供的正文");
  await page.screenshot({path:testInfo.outputPath("knowledge-390-form.png")});
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button",{name:"创建知识源",exact:true})).toBeFocused();
  await page.route("**/knowledge/b",route=>route.fulfill({status:404,json:{detail:{reasonCode:"KNOWLEDGE_NOT_FOUND"}}}));
  await page.getByRole("button",{name:/知识包 b/}).click();
  await expect(page.getByRole("alert")).toContainText("资源不可用或当前访问未获授权");
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
