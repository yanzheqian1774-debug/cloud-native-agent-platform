import {expect, test} from "@playwright/test";

// View-only fixtures: never evidence of real resource readiness or execution.
for (const kind of ["skill", "mcp"] as const) {
  test(`${kind} exact revision and schema gaps remain visible without dispatch`, async ({page}, info) => {
    const schema = {type:"object", required:["project"], properties:{project:{type:"string", description:"正式项目标签；缺失时不能推断归属"}}};
    const resource = {
      resourceId:`fixture-${kind}`, kind, name:"隔离合成成本资源", aggregateVersion:2,
      lifecycleState:"DRAFT", enabled:false, archived:false, currentDraftRevisionId:"revision-2", publishedRevisionId:"revision-1",
      revisions:[{revisionId:"revision-2",predecessorRevisionId:"revision-1",state:"DRAFT",digest:"a".repeat(64),createdAt:"2026-09-21T00:00:00Z",
        content:{description:"仅页面测试合成资源",capabilities:["READ_DATA"],instructions:"只读合成资料",inputSchema:schema,outputSchema:{type:"object"},
          operations:[{name:"READ_DATA", inputSchema:schema, outputSchema:{type:"object",properties:{snapshot:{type:"string"}}},sideEffectClass:"READ_ONLY",executorId:"fixture-executor",executorRevision:"1",executorConfigurationDigest:"b".repeat(64)}]}}],
      reviews:[],relationships:[],bindings:[],invocations:[],savedTests:[],testResults:[],toolSelections:[],healthObservations:[],driftRecords:[],limitations:[],
      discoverySnapshots:kind === "mcp" ? [{snapshotId:"fixture-snapshot",digest:"c".repeat(64),protocolRevision:"2025-06-18",capturedAt:"2026-09-21T00:00:00Z",catalog:{tools:[{name:"read_synthetic",description:"合成资料读取",inputSchema:schema}],resources:[],prompts:[]}}] : [],
    };
    const mutations:string[]=[];
    await page.route("**/api/internal/v0.2.2/resources/**", async route => {
      if (route.request().method() !== "GET") mutations.push(route.request().method());
      const path=new URL(route.request().url()).pathname;
      await route.fulfill({json:path.endsWith(`/fixture-${kind}`) ? {resource,productProjection:{},technicalProjection:{}} : path.endsWith(`/${kind}`) ? [resource] : []});
    });
    await page.setViewportSize({width:1536,height:1024});
    await page.goto(`/${kind === "skill" ? "skills" : "mcp"}?resourceId=fixture-${kind}`);
    const details=page.getByRole("region", {name:"精确资源与输入输出"});
    await expect(details).toBeVisible();
    await expect(details.getByText("当前展示草稿。",{exact:false})).toBeVisible();
    if (kind === "skill") {
      await expect(details.getByRole("cell",{name:"project",exact:true})).toBeVisible();
      await expect(details.getByText("副作用：只读")).toBeVisible();
    } else {
      await expect(details.getByText("当前发现契约未提供输出 Schema",{exact:false})).toBeVisible();
    }
    await details.locator("summary").first().focus();
    await page.keyboard.press("Enter");
    await expect(details.locator("details").first()).toHaveAttribute("open","");
    await page.evaluate(()=>window.scrollTo(0,0));
    await page.screenshot({path:info.outputPath(`${kind}-schema-fixture.png`),fullPage:true});
    await page.evaluate(()=>{document.documentElement.style.zoom="1.25"});
    await expect(details).toBeVisible();
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(overflow).toBe(false);
    expect(mutations).toEqual([]);
  });
}
