import { expect, test } from "@playwright/test";
import { backendUrl, restartOwnedBackend } from "../harness/ownedBackend";
import { runKnowledgeOperation } from "../harness/structuredKnowledgeReporter";

const backend = backendUrl();
const qdrant = process.env.KNOWLEDGE_QDRANT_DIRECT_URL;
if (!qdrant) throw new Error("KNOWLEDGE_QDRANT_DIRECT_URL is required");
const authorizedHeaders = {
  "X-Tenant-ID": "tenant-a",
  "X-Security-Domain": "supplier-quality",
  "X-Principal-ID": "human:knowledge-owner",
};
const chineseDocx = Buffer.from("UEsDBBQAAAAIAGyzKV3GEnoHrAAAAPEAAAATAAAAW0NvbnRlbnRfVHlwZXNdLnhtbF2Puw7CMAxFf6XKihoXBgaUlIEdGPgBK3HbiOahJBT4exKQOjBax/dcWxxfdm4Wisl4J9mWd+zYi9s7UGoKcUmyKedwAEhqIouJ+0CukMFHi7mMcYSA6o4jwa7r9qC8y+Rym6uD9eJS5NFoaq4Y8xktSQZPHzVorx62bPJiY83pF6vNkmEIs1GYy02wOP3X2fphMIrWfLWF6BWlZNxoZ74Si8Ztqh56Ad+n+g9QSwMEFAAAAAgAbLMpXdU4Q/EaAQAAdwEAABEAAAB3b3JkL2RvY3VtZW50LnhtbI2QzUrDQBRGXyXM3k50IRKSdOcT6APEJLaBzkyYRKM7f0iR2lCFSLQibcXqQiyiYGta6sM4MyFvYaKIIC7cnMvl+zhwr1rdQQ1p26aeQ7AGFisykGxsEsvBNQ2sr60urICqrgaKRcwtZGNfKvrYUwIN1H3fVSD0zLqNDK9CXBsX2SahyPCLldZgQKjlUmLanlfoUAMuyfIyRIaDQancINZuOd0StISvs/klT2N+1sxmaX4x5m9hPphm98c8es67cXY7fd87UGHZLEk/6f6W8PFT1htmD7EYHCkSmxzyaJ+lbf7YEckLb4aic8LSG9Ea8tPWf3wi6X/J8mSUX5+zScRmXZbeZXGPt1/zMGLzKxGN/lbB70PhzxP1D1BLAQIUAxQAAAAIAGyzKV3GEnoHrAAAAPEAAAATAAAAAAAAAAAAAACAAQAAAABbQ29udGVudF9UeXBlc10ueG1sUEsBAhQDFAAAAAgAbLMpXdU4Q/EaAQAAdwEAABEAAAAAAAAAAAAAAIAB3QAAAHdvcmQvZG9jdW1lbnQueG1sUEsFBgAAAAACAAIAgAAAACYCAAAAAA==","base64");

async function createSource(page: import("@playwright/test").Page) {
  await page.getByRole("button", {name:"上传或创建文档",exact:true}).click();
  const dialog=page.getByRole("dialog",{name:"上传或创建知识文档"});
  await dialog.getByLabel("文档标题",{exact:true}).fill("供应商质量管理制度");
  await dialog.getByLabel("来源说明",{exact:true}).fill("质量部门正式制度");
  await dialog.getByLabel("可选外部编号或 URL",{exact:true}).fill("SQ-2026-09");
  await dialog.getByLabel("选择 PDF 或 DOCX").setInputFiles({name:"供应商质量管理制度.docx",mimeType:"application/vnd.openxmlformats-officedocument.wordprocessingml.document",buffer:chineseDocx});
  await expect(dialog.getByLabel("解析预览")).toContainText("七十二小时");
  await expect(dialog.getByLabel("解析预览")).toContainText("原文件未保存");
  await dialog.getByRole("button",{name:"从解析结果创建草稿",exact:true}).click();
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
  let identity = "";
  let firstRevision = "";
  let firstDigest = "";
  let firstSnapshot = "";
  let rebuilt: {
    knowledge: { publishedRevisionId: string; activeIndexSnapshotId: string };
    technicalProjection: { revisionDigests: Array<{ digest: string }> };
  } | undefined;

  await runKnowledgeOperation(testInfo, "KNOWLEDGE_GOVERNED_CREATE_PUBLISH", async () => {
  await page.setViewportSize({width:1440,height:900});
  await page.goto("/knowledge");
  await expect(page.getByRole("navigation", { name: "P1 核心产品导航" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "知识中心", exact: true })).toBeVisible();
  await createSource(page);
  const hierarchy=page.getByRole("navigation",{name:"知识中心操作分区"});
  await expect(hierarchy.getByRole("link")).toHaveCount(4);
  await expect(hierarchy).toContainText("文档列表");
  await expect(hierarchy).toContainText("检索测试与出处");
  identity = (await page.locator(".agent-detail > header .technical-value").textContent())!;
  await expect(page.getByRole("definition").filter({ hasText: "质量部门正式制度" })).toBeVisible();
  await publish(page);
  });

  await runKnowledgeOperation(testInfo, "KNOWLEDGE_INDEX_RETRIEVE", async () => {
  await test.step("KNOWLEDGE_INDEX_SUBMIT", async () => {
    await page.getByRole("button", { name: "导入并建立索引" }).click();
  });
  await test.step("KNOWLEDGE_INDEX_READY", async () => {
    await expect(page.getByText(/ingestion-job.*COMPLETED/)).toBeVisible();
  });

  await test.step("KNOWLEDGE_INDEX_AUTHORITY_READBACK", async () => {
    const first = await (await request.get(`${backend}/api/internal/v0.2.2/knowledge/${encodeURIComponent(identity)}`, { headers: authorizedHeaders })).json();
    firstRevision = first.knowledge.publishedRevisionId;
    firstDigest = first.technicalProjection.revisionDigests.at(-1).digest;
    firstSnapshot = first.knowledge.activeIndexSnapshotId;
    expect(first.productProjection.knowledgeId).toBe(first.technicalProjection.knowledgeId);
  });

  await test.step("KNOWLEDGE_RETRIEVAL_SUBMIT", async () => {
    await page.getByLabel("中文问题", {exact:true}).fill("缺陷报告需要多久提交");
    await page.getByRole("button", { name: "检索当前文档" }).click();
  });
  await test.step("KNOWLEDGE_RETRIEVAL_RESULT_RENDERED", async () => {
    await expect(page.getByText(/原文出处 · 供应商质量管理制度.docx/).first()).toBeVisible();
  });
  await test.step("KNOWLEDGE_RETRIEVAL_CITATION_VERIFIED", async () => {
    await expect(page.getByLabel("Workbench retrieval history")).toContainText("第 2 段");
    await expect(page.getByLabel("Knowledge quality dashboard")).toContainText("POSTGRESQL");
    await page.screenshot({path:testInfo.outputPath("knowledge-1440.png")});
  });
  await test.step("KNOWLEDGE_SEARCH_RESULT_RENDERED", async () => {
    await page.getByLabel("检索方式").selectOption("HYBRID");
    const generatedSourceId = await page.getByRole("definition").filter({hasText:"knowledge-source:"}).textContent();
    await page.getByLabel("Filter sourceId").selectOption((generatedSourceId??"").trim());
    await page.getByRole("button", { name: "执行检索实验" }).click();
    await expect(page.getByLabel("Search Playground")).toContainText("CJK_BIGRAM_V1");
    await expect(page.getByLabel("Search Playground")).toContainText("排序信号，不是正确率");
  });
  await test.step("KNOWLEDGE_EVALUATION_RECORDED", async () => {
    await page.getByRole("button", { name: "评估当前结果" }).click();
    await expect(page.getByLabel("Evaluation comparison")).toContainText("EVALUATION_RUN");
    await expect(page.getByLabel("Evaluation comparison")).toContainText("entityId");
    await page.getByRole("button", { name: "比较评估记录" }).click();
    await expect(page.getByLabel("Evaluation comparison")).toContainText("NO_IMPROVEMENT_CLAIM");
  });
  await test.step("KNOWLEDGE_SUMMARY_RECORDED", async () => {
    await page.getByRole("button", { name: "生成抽取式摘要" }).click();
    await expect(page.getByLabel("Knowledge operations")).toContainText("DETERMINISTIC_EXTRACTIVE_V1");
  });
  await test.step("KNOWLEDGE_IMPORT_PREVIEW", async () => {
    await page.getByLabel("导入格式").selectOption("jsonl");
    await page.getByLabel("导入内容", {exact:true}).fill('{"name":"Imported procedure","content":"Authorized draft content."}\n{"name":"","content":"Rejected without disclosure"}');
    await page.getByRole("button", { name: "预览导入" }).click();
    await expect(page.getByLabel("Import execution")).toContainText("导入状态 PREVIEW");
  });
  await test.step("KNOWLEDGE_IMPORT_EXECUTE", async () => {
    await page.getByRole("button", { name: "执行已确认预览" }).click();
    await expect(page.getByLabel("Import execution")).toContainText("导入状态 PARTIAL");
    await expect(page.getByLabel("Import execution").getByRole("definition").nth(3)).toHaveText("1");
    await expect(page.getByLabel("Import execution").getByRole("definition").nth(4)).toHaveText("1");
  });
  await test.step("KNOWLEDGE_IMPORT_RETRY", async () => {
    await page.getByRole("button", { name: "重试部分导入" }).click();
    await expect(page.getByLabel("Import execution").getByRole("definition").nth(3)).toHaveText("1");
  });

  await test.step("KNOWLEDGE_DUPLICATE_REVIEW", async () => {
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
  });

  await test.step("KNOWLEDGE_SCOPE_DENIAL_READBACK", async () => {
    const denied = await request.get(`${backend}/api/internal/v0.2.2/knowledge/${encodeURIComponent(identity)}`, { headers: { ...authorizedHeaders, "X-Tenant-ID": "tenant-b" } });
    const absent = await request.get(`${backend}/api/internal/v0.2.2/knowledge/knowledge:absent`, { headers: { ...authorizedHeaders, "X-Tenant-ID": "tenant-b" } });
    expect(denied.status()).toBe(404);
    expect(await denied.text()).toBe(await absent.text());
    const foreignList = await request.get(`${backend}/api/internal/v0.2.2/knowledge`, { headers: { ...authorizedHeaders, "X-Tenant-ID": "tenant-b" } });
    expect(await foreignList.json()).toEqual([]);
  });
  });

  await runKnowledgeOperation(testInfo, "KNOWLEDGE_UPDATE", async () => {
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
  rebuilt = await (await request.get(`${backend}/api/internal/v0.2.2/knowledge/${encodeURIComponent(identity)}`, { headers: authorizedHeaders })).json();
  expect(rebuilt.knowledge.publishedRevisionId).not.toBe(firstRevision);
  expect(rebuilt.technicalProjection.revisionDigests.at(-1).digest).not.toBe(firstDigest);
  expect(rebuilt.knowledge.activeIndexSnapshotId).not.toBe(firstSnapshot);
  });

  await runKnowledgeOperation(testInfo, "KNOWLEDGE_RESTART_READBACK", async () => {
  await restartBackend(request);
  await page.reload();
  await page.getByLabel("筛选文档").fill(identity);
  await page.getByRole("button", { name: /供应商质量管理制度/ }).click();
  const recovered = await (await request.get(`${backend}/api/internal/v0.2.2/knowledge/${encodeURIComponent(identity)}`, { headers: authorizedHeaders })).json();
  expect(recovered.knowledge.knowledgeId).toBe(identity);
  expect(recovered.knowledge.publishedRevisionId).toBe(rebuilt!.knowledge.publishedRevisionId);
  expect(recovered.knowledge.activeIndexSnapshotId).toBe(rebuilt!.knowledge.activeIndexSnapshotId);
  await page.getByRole("button", { name: "技术视图" }).click();
  await expect(page.getByLabel("Knowledge Technical View").getByText(identity, { exact: true })).toBeVisible();
  await expect(page.getByText(/Qdrant仅包含派生向量/)).toBeVisible();
  await page.getByRole("button", { name: "产品视图" }).click();
  await page.getByRole("button", { name: "归档知识包" }).click();
  await expect(page.getByText(/ARCHIVED · 已归档/)).toBeVisible();
  });

  await runKnowledgeOperation(testInfo, "KNOWLEDGE_PURGE_RECOVERY", async () => {
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
  await page.getByLabel("中文问题",{exact:true}).fill("query a");
  await page.getByRole("button",{name:"执行检索实验",exact:true}).click();
  await expect.poll(()=>requested).toBe(true);
  await page.goBack();
  await expect(page.locator(".agent-detail h2")).toHaveText("知识包 b");
  await expect(page.locator(".agent-detail h2")).toBeFocused();
  const lateResponse=page.waitForResponse(response=>response.url().endsWith("/operations/search"));
  finish();
  await (await lateResponse).finished();
  await expect(page.getByText("late-a-result")).toHaveCount(0);
  await expect(page.getByLabel("中文问题",{exact:true})).toHaveValue("");
  await page.getByLabel("查看修订").selectOption("revision:b");
  await expect(page).toHaveURL(/revisionId=revision%3Ab/);
  await page.getByRole("button",{name:"返回筛选列表"}).click();
  await expect(page.getByLabel("筛选文档")).toHaveValue("知识包");
  await expect(page.getByRole("heading",{name:"文档列表"})).toBeFocused();
  await page.goto("/knowledge?resourceId=b&revisionId=missing");
  await expect(page.getByRole("alert")).toContainText("不能用其他修订替代");
});

test("validates real form inputs and keeps denied and service failures distinct at mobile width",async({page},testInfo)=>{
  await installUiFixtures(page);
  await page.setViewportSize({width:390,height:844});
  await page.goto("/knowledge");
  await page.getByRole("button",{name:"上传或创建文档",exact:true}).click();
  const dialog=page.getByRole("dialog",{name:"上传或创建知识文档"});
  await dialog.getByRole("tab",{name:"粘贴文字"}).click();
  await dialog.getByLabel("文档标题",{exact:true}).fill("278 用户输入");
  await dialog.getByLabel("来源说明",{exact:true}).fill("来".repeat(2001));
  await dialog.getByLabel("知识正文",{exact:true}).fill("用户提供的正文");
  await dialog.getByRole("button",{name:"创建文字草稿"}).click();
  await expect(dialog.getByRole("alert")).toContainText("2000");
  await dialog.getByLabel("来源说明",{exact:true}).fill("中文人工来源");
  let submissions=0;
  await page.route("**/knowledge",async route=>{
    if(route.request().method()==="POST"){
      submissions++;
      expect(route.request().postDataJSON()).toMatchObject({name:"278 用户输入",source:{sourceDescription:"中文人工来源",content:"用户提供的正文"}});
      return route.fulfill({status:503,json:{detail:{reasonCode:"KNOWLEDGE_STORAGE_UNAVAILABLE"}}});
    }
    return route.fallback();
  });
  await dialog.getByRole("button",{name:"创建文字草稿"}).evaluate(button=>{button.click();button.click();});
  await expect(dialog.getByRole("alert")).toContainText("知识服务暂不可用");
  expect(submissions).toBe(1);
  await expect(dialog.getByLabel("知识正文",{exact:true})).toHaveValue("用户提供的正文");
  await page.screenshot({path:testInfo.outputPath("knowledge-390-form.png")});
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button",{name:"上传或创建文档",exact:true})).toBeFocused();
  await page.route("**/knowledge/b",route=>route.fulfill({status:404,json:{detail:{reasonCode:"KNOWLEDGE_NOT_FOUND"}}}));
  await page.getByRole("button",{name:/知识包 b/}).click();
  await expect(page.getByRole("alert")).toContainText("资源不可用或当前访问未获授权");
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
