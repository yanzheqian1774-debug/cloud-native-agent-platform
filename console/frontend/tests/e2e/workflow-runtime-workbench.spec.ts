import { expect, test } from "@playwright/test";
import { restartOwnedBackend } from "../harness/ownedBackend";

test("publishes a Runtime Profile then a governed Workflow through real Workbenches", async ({ page }) => {
  let runtimeId="",runtimeRevisionId="";
  let workflow:{definition:{workflowDefinitionId:string;aggregateVersion:number}};
  await test.step("WORKFLOW_RUNTIME_01_RESOURCE_PREPARATION",async()=>{
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
  runtimeId = published.profile.runtimeProfileId;
  runtimeRevisionId = published.profile.publishedRevisionId;
  await page.getByRole("button", { name: "Create Runtime successor" }).click();
  await page.getByRole("button", { name: "编辑当前 Profile Draft" }).click();
  await page.getByLabel("CPU request").fill("350m");
  await page.getByRole("button", { name: "保存 Runtime Profile Draft" }).click();
  await expect(page.getByText("350m → 500m")).toBeVisible();
  });

  await test.step("WORKFLOW_RUNTIME_02_WORKFLOW_CREATE",async()=>{
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
  });
  await test.step("WORKFLOW_RUNTIME_03_WORKFLOW_SAVE",async()=>{
  await page.getByRole("button", { name: "Save governed Workflow draft" }).click();
  await expect(page.getByRole("heading", { name: "Canonical DAG" })).toBeVisible();
  });
  await test.step("WORKFLOW_RUNTIME_04_WORKFLOW_VALIDATE",async()=>{
  await page.getByRole("button", { name: "Validate DAG and references" }).click();
  });
  await test.step("WORKFLOW_RUNTIME_05_WORKFLOW_PUBLISH",async()=>{
  await page.getByRole("button", { name: "Review exact Workflow digest" }).click();
  await page.getByRole("button", { name: "Publish immutable Workflow" }).click();
  await expect(page.locator(".module-layout > section").getByText("PUBLISHED", { exact: true }).first()).toBeVisible();
  await expect(page.getByLabel("Workflow Technical projection")).toContainText("publishedRevisionId");
  await expect(page.getByText("0 relationships · 0 consumers")).toBeVisible();
  workflow = await page.evaluate(async () => {
    const values = await (await fetch("/api/internal/v0.2.2/workflow-definitions")).json();
    return values.find((item: {definition:{name:string}}) => item.definition.name === "Supplier Quality Response");
  });
  });
  await test.step("WORKFLOW_RUNTIME_06_SUCCESSOR_EDIT_SAVE",async()=>{
  await page.evaluate(async ({id,version}:{id:string;version:number}) => {
    await fetch(`/api/internal/v0.2.2/workflow-definitions/${encodeURIComponent(id)}/successors`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({expectedVersion:version})});
  }, {id:workflow.definition.workflowDefinitionId,version:workflow.definition.aggregateVersion});
  await page.getByRole("button", { name: "Create Workflow successor" }).click();
  await expect(page.getByLabel("Guided conflict recovery")).toContainText("stale");
  await expect(page.getByLabel("Guided conflict recovery")).toContainText("写请求不会自动重放");
  await page.getByRole("button", { name: "确认权威版本" }).click();
  await page.getByRole("button", { name: "编辑当前 Draft" }).click();
  await page.getByLabel("用途说明").fill("Edited Workflow Definition after explicit CAS recovery");
  await page.getByRole("button", { name: "Save governed Workflow draft" }).click();
  await expect(page.getByText("Edited Workflow Definition after explicit CAS recovery")).toBeVisible();
  });
  await test.step("WORKFLOW_RUNTIME_07A_BACKEND_RESTART",async()=>{
  await restartOwnedBackend();
  });
  await test.step("WORKFLOW_RUNTIME_07B_PAGE_RELOAD",async()=>{
  await page.reload();
  });
  await test.step("WORKFLOW_RUNTIME_07C_TITLE_RESTORE",async()=>{
  await expect(page.getByRole("heading", {name:"Supplier Quality Response", exact:true})).toBeVisible();
  });
  await test.step("WORKFLOW_RUNTIME_07D_WORKFLOW_READBACK",async()=>{
  const recovered = await page.evaluate(async (id:string) => (await fetch(`/api/internal/v0.2.2/workflow-definitions/${encodeURIComponent(id)}`)).json(), workflow.definition.workflowDefinitionId);
  expect(recovered.definition.revisions.at(-1).content.description).toBe("Edited Workflow Definition after explicit CAS recovery");
  });
  await test.step("WORKFLOW_RUNTIME_07E_RUNTIME_PROFILE_READBACK",async()=>{
  const recoveredProfile = await page.evaluate(async (id:string) => (await fetch(`/api/internal/v0.2.2/runtime-profiles/${encodeURIComponent(id)}`)).json(), runtimeId);
  expect(recoveredProfile.profile.revisions.at(-1).content.resources.cpuRequest).toBe("350m");
  });
  await test.step("WORKFLOW_RUNTIME_07F_MOBILE_VIEWPORT",async()=>{
  await page.setViewportSize({width:390,height:844});
  });
  await test.step("WORKFLOW_RUNTIME_07G_SEARCH_FOCUS",async()=>{
  const catalogTab = page.getByRole("tab", {name:"工作流目录"});
  await expect(catalogTab).toBeVisible();
  await catalogTab.focus();
  await expect(catalogTab).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(catalogTab).toHaveAttribute("aria-selected", "true");
  const catalog = page.getByLabel("Workflow 列表");
  await expect(catalog).toBeVisible();
  await expect(catalog.locator(".workflow-catalog__item.selected")).toContainText("Supplier Quality Response");
  const search = page.getByLabel("搜索 Workflow Definition");
  await expect(search).toBeVisible();
  await search.focus();
  await expect(search).toBeFocused();
  });
  await test.step("WORKFLOW_RUNTIME_07H_HORIZONTAL_OVERFLOW",async()=>{
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBe(true);
  });
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
  await expect(page.getByLabel("Guided conflict recovery")).toContainText("写请求不会自动重放");
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

test("binds a formally published Skill operation through the real Workflow UI", async ({ page }) => {
  const suffix=Date.now(),json=async(method:string,path:string,body?:unknown)=>page.evaluate(async({method,path,body})=>{
    const response=await fetch(path,{method,headers:{"Content-Type":"application/json"},body:body===undefined?undefined:JSON.stringify(body)});
    return {status:response.status,body:response.status===204?null:await response.json()};
  },{method,path,body});
  async function holdDraftResponse(){
    let release!:()=>void,received!:(value:{status:number;content:Record<string,unknown>})=>void;
    const held=new Promise<void>(resolve=>release=resolve);
    const responseReady=new Promise<{status:number;content:Record<string,unknown>}>(resolve=>received=resolve);
    let writes=0;
    const countWrite=(request:import("@playwright/test").Request)=>{if(request.method()==="PUT"&&new URL(request.url()).pathname.endsWith("/draft"))writes+=1};
    page.on("request",countWrite);
    await page.route("**/api/internal/v0.2.2/workflow-definitions/*/draft",async route=>{
      if(route.request().method()!=="PUT"){await route.continue();return}
      const content=route.request().postDataJSON().content;
      const actual=await route.fetch();
      received({status:actual.status(),content});
      await held;
      await route.fulfill({response:actual});
    },{times:1});
    return {responseReady,release:()=>{page.off("request",countWrite);release()},writes:()=>writes};
  }
  async function expectFrozenEditor(description:string){
    const fields=page.getByRole("group",{name:"Workflow editor fields",exact:true});
    await expect(page.getByLabel("Workflow authoring")).toHaveAttribute("aria-busy","true");
    await expect(page.getByRole("status").filter({hasText:"提交内容已锁定"})).toBeVisible();
    for(const control of await fields.locator("input,textarea,select,button").all())await expect(control).toBeDisabled();
    await page.keyboard.type("must-not-change-submitted-input");
    await fields.getByRole("button",{name:"添加步骤",exact:true}).click({force:true});
    await fields.getByRole("button",{name:"保存精确 Skill operation binding"}).click({force:true});
    await expect(page.getByLabel("用途说明")).toHaveValue(description);
    await expect(fields.getByLabel("步骤 ID",{exact:true})).toHaveCount(1);
  }
  const runtimeContent={provider:"NATIVE_KUBERNETES",resources:{cpuRequest:"250m",cpuLimit:"500m",memoryRequest:"256Mi",memoryLimit:"1Gi"},isolation:"NAMESPACE",stateMode:"STATELESS",sessionAffinity:"NONE",secretReferences:[],openClawPackageRef:null};
  const operation={name:`quality.read-${suffix}`,inputSchema:{type:"object",properties:{supplier:{type:"string"}}},outputSchema:{type:"object",properties:{status:{type:"string"}}},sideEffectClass:"READ_ONLY",executorId:"workflow-ui-readonly",executorRevision:"1.0.0",executorConfigurationDigest:"1".repeat(64),sideEffectPolicy:{policyId:"workflow-ui-readonly",policyRevision:"1",policyDigest:"2".repeat(64)},ioLimits:{policyId:"workflow-ui-bounds",policyRevision:"1",maxInputBytes:4096,maxOutputBytes:4096,maxObjectDepth:8,maxProperties:64,timeoutMs:1000}};
  const skillContent={description:"Formal Skill operation for the Workflow UI",capabilities:[operation.name],instructions:"Read only.",operations:[operation]};

  await page.goto("/dashboard");
  let response=await json("POST","/api/internal/v0.2.2/runtime-profiles",{name:`Workflow binding Runtime ${suffix}`,content:runtimeContent});expect(response.status).toBe(201);
  let runtime=response.body.profile;const runtimeRevision=runtime.revisions.at(-1);
  response=await json("POST",`/api/internal/v0.2.2/runtime-profiles/${encodeURIComponent(runtime.runtimeProfileId)}/validation`,{expectedVersion:runtime.aggregateVersion});expect(response.status).toBe(200);runtime=response.body.profile;
  response=await json("POST",`/api/internal/v0.2.2/runtime-profiles/${encodeURIComponent(runtime.runtimeProfileId)}/reviews`,{expectedVersion:runtime.aggregateVersion,digest:runtimeRevision.digest,decision:"APPROVE",reason:"Exact real UI integration review"});expect(response.status).toBe(200);runtime=response.body.profile;
  response=await json("POST",`/api/internal/v0.2.2/runtime-profiles/${encodeURIComponent(runtime.runtimeProfileId)}/publications`,{expectedVersion:runtime.aggregateVersion,digest:runtimeRevision.digest,reviewId:runtime.reviews.at(-1).reviewId});expect(response.status).toBe(200);runtime=response.body.profile;

  response=await json("POST","/api/internal/v0.2.2/resources/skill",{name:`Workflow binding Skill ${suffix}`,content:skillContent});expect(response.status).toBe(201);
  let skill=response.body.resource;const skillRevision=skill.revisions.at(-1);
  response=await json("POST",`/api/internal/v0.2.2/resources/skill/${encodeURIComponent(skill.resourceId)}/validation`,{expectedVersion:skill.aggregateVersion});expect(response.status).toBe(200);skill=response.body.resource;
  response=await json("POST",`/api/internal/v0.2.2/resources/skill/${encodeURIComponent(skill.resourceId)}/reviews`,{expectedVersion:skill.aggregateVersion,digest:skillRevision.digest,decision:"APPROVE",reason:"Exact real UI integration review"});expect(response.status).toBe(200);skill=response.body.resource;
  response=await json("POST",`/api/internal/v0.2.2/resources/skill/${encodeURIComponent(skill.resourceId)}/publications`,{expectedVersion:skill.aggregateVersion,digest:skillRevision.digest,reviewId:skill.reviews.at(-1).reviewId});expect(response.status).toBe(200);skill=response.body.resource;
  response=await json("POST",`/api/internal/v0.2.2/resources/skill/${encodeURIComponent(skill.resourceId)}/successors`,{expectedVersion:skill.aggregateVersion});expect(response.status).toBe(200);skill=response.body.resource;
  expect(skill.publishedRevisionId).toBe(skillRevision.revisionId);
  expect(skill.revisions.at(-1).revisionId).not.toBe(skill.publishedRevisionId);

  response=await json("POST","/api/internal/v0.2.2/resources/skill",{name:`Unpublished Workflow Skill ${suffix}`,content:skillContent});expect(response.status).toBe(201);
  const unpublished=response.body.resource,unpublishedRevision=unpublished.revisions.at(-1);
  response=await json("POST","/api/internal/v0.2.2/resources/skill",{name:`Invalid Workflow Skill ${suffix}`,content:{...skillContent,operations:[{name:"incomplete"}]}});expect(response.status).toBe(422);

  await page.goto("/workflow-definitions");
  await expect(page.getByLabel("Skill operation directory status")).toContainText("个合格 operation");
  await expect(page.getByLabel("步骤 step-1 选择 Skill",{exact:true})).toHaveCount(0);
  await page.getByRole("button",{name:"新建 Workflow Definition"}).click();
  await page.getByLabel("Workflow 名称").fill(`Real Skill-bound Workflow ${suffix}`);
  await page.getByLabel("资源 ID").fill(runtime.runtimeProfileId);
  await page.getByLabel("修订 ID").fill(runtime.publishedRevisionId);
  await page.getByLabel("用途说明").fill("Historical unbound Workflow revision");
  await page.getByLabel("名称",{exact:true}).fill("Read supplier quality");
  await page.getByRole("button",{name:"Save governed Workflow draft"}).click();
  await expect(page.getByRole("heading",{name:"Canonical DAG"})).toBeVisible();
  await page.getByRole("button",{name:"编辑当前 Draft"}).click();
  const skillSelect=page.getByLabel("步骤 step-1 选择 Skill",{exact:true}),revisionSelect=page.getByLabel("步骤 step-1 选择 Skill revision",{exact:true}),operationSelect=page.getByLabel("步骤 step-1 选择 operation",{exact:true});
  await expect(skillSelect.locator(`option[value="${unpublished.resourceId}"]`)).toHaveCount(0);
  await skillSelect.selectOption(skill.resourceId);
  await revisionSelect.selectOption(skill.publishedRevisionId);
  await operationSelect.selectOption(operation.name);
  const preview=page.getByLabel("Selected Skill operation details");
  await expect(preview).toContainText(skill.resourceId);await expect(preview).toContainText(skill.publishedRevisionId);await expect(preview).toContainText(skillRevision.digest);await expect(preview).toContainText(operation.name);
  await page.getByRole("button",{name:"保存精确 Skill operation binding"}).click();
  await page.getByLabel("用途说明").fill("Exact Skill operation binding saved through real UI");
  const heldSave=await holdDraftResponse();
  await page.getByRole("button",{name:"Save governed Workflow draft"}).dblclick();
  const submitted=await heldSave.responseReady;
  try{
    expect(submitted.status).toBe(200);
    await expectFrozenEditor("Exact Skill operation binding saved through real UI");
    expect(heldSave.writes()).toBe(1);
  }finally{heldSave.release()}
  await expect(page.getByLabel("Workflow authoring")).toHaveCount(0);
  const workflowId=(await page.locator(".module-layout > section > header .technical-value").textContent())!.trim();
  response=await json("GET",`/api/internal/v0.2.2/workflow-definitions/${encodeURIComponent(workflowId)}`);expect(response.status).toBe(200);
  let workflow=response.body.definition,task=workflow.revisions.at(-1).content.tasks[0];
  expect(workflow.revisions.at(-1).content).toEqual(submitted.content);
  const binding={skillId:skill.resourceId,skillRevisionId:skill.publishedRevisionId,skillDigest:skillRevision.digest,operation:operation.name};
  expect(task.skillOperationBindings).toEqual([binding]);
  expect(task.references).toEqual([{kind:"SKILL",resourceId:binding.skillId,revisionId:binding.skillRevisionId,digest:binding.skillDigest}]);
  expect(workflow.revisions[0].content.tasks[0].skillOperationBindings).toBeUndefined();
  expect(workflow.revisions.at(-1).content.runtimeProfile).toEqual({kind:"RUNTIME_PROFILE",resourceId:runtime.runtimeProfileId,revisionId:runtime.publishedRevisionId});

  await page.getByRole("button",{name:"编辑当前 Draft"}).click();
  await page.getByLabel("用途说明").fill("Unrelated real UI edit retains binding");
  let realPutCount=0;page.on("request",request=>{if(request.method()==="PUT"&&decodeURIComponent(new URL(request.url()).pathname)===`/api/internal/v0.2.2/workflow-definitions/${workflowId}/draft`)realPutCount+=1});
  const detachedSave=await holdDraftResponse();
  await page.getByRole("button",{name:"Save governed Workflow draft"}).dblclick();
  const detached=await detachedSave.responseReady;
  try{
    expect(detached.status).toBe(200);
    await page.getByRole("button",{name:"关闭编写器并保留权威版本"}).click();
    await page.getByRole("button",{name:"新建 Workflow Definition",exact:true}).click();
  }finally{detachedSave.release()}
  await expect(page.getByLabel("Workflow authoring")).toBeVisible();
  await expect(page.getByLabel("用途说明")).toBeEnabled();
  await expect(page.getByLabel("用途说明")).toHaveValue("");
  await page.getByLabel("用途说明").fill("Later editor survives the old save response");
  await expect(page.getByLabel("用途说明")).toHaveValue("Later editor survives the old save response");
  await page.getByRole("button",{name:"关闭编写器并保留权威版本"}).click();
  await page.getByRole("button",{name:new RegExp(`Real Skill-bound Workflow ${suffix}`)}).click();
  await expect(page.getByText("Unrelated real UI edit retains binding",{exact:true})).toBeVisible();
  expect(realPutCount).toBe(1);
  response=await json("GET",`/api/internal/v0.2.2/workflow-definitions/${encodeURIComponent(workflowId)}`);workflow=response.body.definition;task=workflow.revisions.at(-1).content.tasks[0];expect(task.skillOperationBindings).toEqual([binding]);
  const review=page.getByLabel("Workflow Skill operation binding review");await expect(review).toContainText(binding.skillId);await expect(review).toContainText(binding.skillRevisionId);await expect(review).toContainText(binding.skillDigest);await expect(review).toContainText(binding.operation);
  await page.getByRole("button",{name:"Validate DAG and references"}).click();
  await page.getByRole("button",{name:"Review exact Workflow digest"}).click();
  await page.getByRole("button",{name:"Publish immutable Workflow"}).click();
  await expect(page.locator(".module-layout > section").getByText("PUBLISHED",{exact:true}).first()).toBeVisible();
  await page.getByRole("button",{name:"Create Workflow successor"}).click();
  await page.getByRole("button",{name:"编辑当前 Draft"}).click();
  await page.getByLabel("用途说明").fill("Retained input after real CAS conflict");
  response=await json("GET",`/api/internal/v0.2.2/workflow-definitions/${encodeURIComponent(workflowId)}`);workflow=response.body.definition;
  const authoritativeContent=structuredClone(workflow.revisions.at(-1).content);authoritativeContent.description="Concurrent authoritative edit";
  response=await json("PUT",`/api/internal/v0.2.2/workflow-definitions/${encodeURIComponent(workflowId)}/draft`,{expectedVersion:workflow.aggregateVersion,content:authoritativeContent});expect(response.status).toBe(200);
  const heldConflict=await holdDraftResponse();
  await page.getByRole("button",{name:"Save governed Workflow draft"}).dblclick();
  const conflicted=await heldConflict.responseReady;
  try{
    expect(conflicted.status).toBe(409);
    await expectFrozenEditor("Retained input after real CAS conflict");
    expect(heldConflict.writes()).toBe(1);
  }finally{heldConflict.release()}
  await expect(page.getByLabel("Guided conflict recovery")).toContainText("stale");
  await expect(page.getByLabel("用途说明")).toBeEnabled();
  await expect(page.getByLabel("用途说明")).toHaveValue("Retained input after real CAS conflict");
  await expect(page.getByLabel("步骤 step-1 选择 Skill",{exact:true})).toBeEnabled();
  await page.getByRole("button",{name:"Explicitly reapply safe draft input"}).click();
  await expect(page.getByLabel("用途说明")).toHaveValue("Retained input after real CAS conflict");
  await expect(page.getByLabel("Workflow authoring").getByLabel("步骤 step-1 的 Skill operation 绑定")).toContainText(binding.operation);
  await page.setViewportSize({width:390,height:844});await skillSelect.focus();await expect(skillSelect).toBeFocused();await skillSelect.press("Tab");await expect(revisionSelect).toBeFocused();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBe(true);
  await page.getByRole("button",{name:"Save governed Workflow draft"}).click();
  await expect(page.getByLabel("Workflow authoring")).toHaveCount(0);

  response=await json("GET",`/api/internal/v0.2.2/workflow-definitions/${encodeURIComponent(workflowId)}`);workflow=response.body.definition;
  const invalidCases=[
    {name:`Wrong operation ${suffix}`,identity:{...binding,operation:`${binding.operation}.missing`}},
    {name:`Unavailable Skill ${suffix}`,identity:{skillId:unpublished.resourceId,skillRevisionId:unpublishedRevision.revisionId,skillDigest:unpublishedRevision.digest,operation:operation.name}},
  ];
  for(const invalid of invalidCases){const content=structuredClone(workflow.revisions.at(-1).content),target=content.tasks[0];target.skillOperationBindings=[invalid.identity];target.references=[{kind:"SKILL",resourceId:invalid.identity.skillId,revisionId:invalid.identity.skillRevisionId,digest:invalid.identity.skillDigest}];response=await json("POST","/api/internal/v0.2.2/workflow-definitions",{name:invalid.name,content});expect(response.status).toBe(201);const invalidWorkflow=response.body.definition;response=await json("POST",`/api/internal/v0.2.2/workflow-definitions/${encodeURIComponent(invalidWorkflow.workflowDefinitionId)}/validation`,{expectedVersion:invalidWorkflow.aggregateVersion});expect(response.status).toBe(409);expect(response.body.detail.reasonCode).toBe("EXACT_REFERENCE_NOT_FOUND")}

  const secondContent=structuredClone(workflow.revisions.at(-1).content);response=await json("POST","/api/internal/v0.2.2/workflow-definitions",{name:`Late response target ${suffix}`,content:secondContent});expect(response.status).toBe(201);const secondId=response.body.definition.workflowDefinitionId;
  await page.goto("/workflow-definitions");let release!:()=>void,started!:()=>void;const held=new Promise<void>(resolve=>release=resolve),waiting=new Promise<void>(resolve=>started=resolve);const delayedPath=`/api/internal/v0.2.2/workflow-definitions/${workflowId}`;
  await page.route("**/api/internal/v0.2.2/workflow-definitions/*",async route=>{if(route.request().method()==="GET"&&decodeURIComponent(new URL(route.request().url()).pathname)===delayedPath){const actual=await route.fetch();started();await held;await route.fulfill({response:actual})}else await route.continue()});
  await page.getByRole("button",{name:new RegExp(`Real Skill-bound Workflow ${suffix}`)}).click();await waiting;await page.getByRole("button",{name:new RegExp(`Late response target ${suffix}`)}).click();await expect(page.getByRole("heading",{name:`Late response target ${suffix}`,exact:true})).toBeVisible();release();await page.waitForTimeout(100);await expect(page.getByRole("heading",{name:`Late response target ${suffix}`,exact:true})).toBeVisible();expect(new URL(page.url()).searchParams.get("resourceId")).toBe(secondId);
});

test("explicitly selects and round-trips an exact Skill operation binding", async ({ page }) => {
  const binding={skillId:"skill-definition:quality",skillRevisionId:"skill-revision:published-7",skillDigest:`sha256:${"a".repeat(64)}`,operation:"quality.read"};
  const operation={name:binding.operation,inputSchema:{type:"object",required:["supplier"]},outputSchema:{type:"object"},sideEffectClass:"READ_ONLY",executorId:"readonly",executorRevision:"1",executorConfigurationDigest:"1".repeat(64),sideEffectPolicy:{policyId:"readonly",policyRevision:"1",policyDigest:"2".repeat(64)},ioLimits:{policyId:"bounded",policyRevision:"1",maxInputBytes:1024,maxOutputBytes:2048,maxObjectDepth:8,maxProperties:64,timeoutMs:1000}};
  const alternate={...operation,name:"quality.inspect"};
  const content={description:"Bound workflow",inputs:[],outputs:[],runtimeProfile:{kind:"RUNTIME_PROFILE",resourceId:"runtime-profile:native",revisionId:"runtime-profile-revision:published",digest:`sha256:${"b".repeat(64)}`},tasks:[{taskId:"analyze",name:"Analyze quality",dependsOn:[],inputs:[],outputs:[],capabilityRequirements:[],references:[],retryLimit:0,timeoutSeconds:300,failurePolicy:"FAIL_WORKFLOW"}]};
  const skill={resourceId:binding.skillId,kind:"skill",name:"Quality Skill",aggregateVersion:4,lifecycleState:"DRAFT",enabled:true,archived:false,currentDraftRevisionId:"skill-revision:successor",publishedRevisionId:binding.skillRevisionId,revisions:[{revisionId:"skill-revision:old",predecessorRevisionId:null,state:"PUBLISHED",digest:`sha256:${"9".repeat(64)}`,content:{operations:[]},createdAt:"2026-09-07T00:00:00Z"},{revisionId:binding.skillRevisionId,predecessorRevisionId:"skill-revision:old",state:"PUBLISHED",digest:binding.skillDigest,content:{operations:[operation,alternate]},createdAt:"2026-09-08T00:00:00Z"},{revisionId:"skill-revision:successor",predecessorRevisionId:binding.skillRevisionId,state:"DRAFT",digest:`sha256:${"8".repeat(64)}`,content:{operations:[]},createdAt:"2026-09-08T01:00:00Z"}]};
  const submitted:Array<{content:typeof content&{tasks:Array<(typeof content.tasks)[number]&{skillOperationBindings?:typeof binding[]}>}}>=[];
  let projection={definition:{workflowDefinitionId:"workflow-definition:bound",name:"Bound Workflow",aggregateVersion:1,lifecycleState:"DRAFT",currentDraftRevisionId:"workflow-revision:draft-1",publishedRevisionId:null,revisions:[{revisionId:"workflow-revision:draft-1",predecessorRevisionId:null,state:"DRAFT",digest:`sha256:${"c".repeat(64)}`,content,createdAt:"2026-09-08T00:00:00Z"}],reviews:[],relationships:[],consumers:[]},productProjection:{},technicalProjection:{}};
  await page.route("**/api/internal/v0.2.2/resources/skill",route=>route.fulfill({contentType:"application/json",body:JSON.stringify([skill])}));
  await page.route("**/api/internal/v0.2.2/workflow-definitions**",async route=>{
    const request=route.request(),url=new URL(request.url());
    if(request.method()==="PUT"){
      const body=request.postDataJSON() as (typeof submitted)[number];submitted.push(body);
      const prior=projection.definition.revisions.at(-1)!;const revisionId=`workflow-revision:draft-${submitted.length+1}`;
      projection={...projection,definition:{...projection.definition,aggregateVersion:projection.definition.aggregateVersion+1,currentDraftRevisionId:revisionId,revisions:[...projection.definition.revisions,{...prior,revisionId,predecessorRevisionId:prior.revisionId,content:body.content}]}};
      await route.fulfill({contentType:"application/json",body:JSON.stringify(projection)});
      return;
    }
    await route.fulfill({contentType:"application/json",body:JSON.stringify(url.pathname.endsWith("/workflow-definitions")?[projection]:projection)});
  });
  await page.goto("/workflow-definitions");
  await expect(page.getByLabel("Skill operation directory status")).toContainText("2 个合格 operation");
  await page.getByRole("button",{name:/Bound Workflow/}).click();
  await page.getByRole("button",{name:"编辑当前 Draft"}).click();
  const skillSelect=page.getByLabel("步骤 analyze 选择 Skill",{exact:true}),revisionSelect=page.getByLabel("步骤 analyze 选择 Skill revision",{exact:true}),operationSelect=page.getByLabel("步骤 analyze 选择 operation",{exact:true});
  await expect(skillSelect).toHaveValue("");await expect(revisionSelect).toHaveValue("");await expect(operationSelect).toHaveValue("");
  await skillSelect.selectOption(binding.skillId);await expect(revisionSelect).toHaveValue("");
  await revisionSelect.selectOption(binding.skillRevisionId);await expect(operationSelect).toHaveValue("");
  await operationSelect.selectOption(binding.operation);
  await expect(page.getByLabel("Selected Skill operation details")).toContainText("READ_ONLY");
  await expect(page.getByLabel("Selected Skill operation details")).toContainText("1024 / 2048");
  await page.getByRole("button",{name:"保存精确 Skill operation binding"}).click();
  await page.getByRole("button",{name:"Save governed Workflow draft"}).click();
  expect(submitted[0].content.tasks[0].skillOperationBindings).toEqual([binding]);
  expect(submitted[0].content.tasks[0].references[0].digest).toBe(binding.skillDigest);
  expect(submitted[0].content.runtimeProfile).toEqual(content.runtimeProfile);
  const review=page.getByLabel("Workflow Skill operation binding review");
  await expect(review).toContainText(binding.skillId);
  await expect(review).toContainText(binding.skillRevisionId);
  await expect(review).toContainText(binding.skillDigest);
  await expect(review).toContainText(binding.operation);
  await expect(review).toContainText("READ_ONLY");
  await expect(review).toContainText("1000 ms");
  await expect(review).toContainText("绑定和发布只保存精确身份，不授予执行");
  await expect(page.getByRole("button",{name:"Validate DAG and references"})).toBeEnabled();
  await page.getByRole("button",{name:"编辑当前 Draft"}).click();
  await expect(page.getByRole("button",{name:"移除此引用"})).toBeDisabled();
  await page.getByRole("button",{name:"显式更换此绑定"}).click();
  await page.getByLabel("步骤 analyze 选择 operation",{exact:true}).selectOption(alternate.name);
  await page.getByRole("button",{name:"保存精确 Skill operation binding"}).click();
  await page.getByRole("button",{name:"Save governed Workflow draft"}).click();
  expect(submitted[1].content.tasks[0].skillOperationBindings).toEqual([{...binding,operation:alternate.name}]);
  expect(submitted[1].content.tasks[0].references).toHaveLength(1);
  await page.getByRole("button",{name:"编辑当前 Draft"}).click();
  await page.getByLabel("用途说明").fill("Unrelated edit keeps exact binding");
  await page.getByRole("button",{name:"Save governed Workflow draft"}).click();
  expect(submitted[2].content.tasks[0].skillOperationBindings).toEqual([{...binding,operation:alternate.name}]);
  await expect(page.getByText("Unrelated edit keeps exact binding",{exact:true})).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  await page.getByLabel("搜索 Workflow Definition").focus();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBe(true);
});

test("keeps complete binding input after edit CAS conflict and reads authority without replay", async ({ page }) => {
  const binding={skillId:"skill-definition:cas",skillRevisionId:"skill-revision:cas",skillDigest:`sha256:${"d".repeat(64)}`,operation:"quality.inspect"};
  const content={description:"Authority",inputs:[],outputs:[],runtimeProfile:{kind:"RUNTIME_PROFILE",resourceId:"runtime-profile:native",revisionId:"runtime-profile-revision:published"},tasks:[{taskId:"inspect",name:"Inspect",dependsOn:[],inputs:[],outputs:[],capabilityRequirements:[],references:[{kind:"SKILL",resourceId:binding.skillId,revisionId:binding.skillRevisionId}],skillOperationBindings:[binding],retryLimit:0,timeoutSeconds:300,failurePolicy:"FAIL_WORKFLOW"}]};
  const projection={definition:{workflowDefinitionId:"workflow-definition:cas",name:"CAS Workflow",aggregateVersion:2,lifecycleState:"DRAFT",currentDraftRevisionId:"workflow-revision:authority",publishedRevisionId:null,revisions:[{revisionId:"workflow-revision:authority",predecessorRevisionId:"workflow-revision:old",state:"DRAFT",digest:`sha256:${"e".repeat(64)}`,content,createdAt:"2026-09-08T00:00:00Z"}],reviews:[],relationships:[],consumers:[]},productProjection:{},technicalProjection:{}};
  let putCount=0;
  await page.route("**/api/internal/v0.2.2/resources/skill",route=>route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({detail:{reasonCode:"SKILL_OPERATION_DIRECTORY_UNAVAILABLE"}})}));
  await page.route("**/api/internal/v0.2.2/workflow-definitions**",async route=>{
    const request=route.request(),url=new URL(request.url());
    if(request.method()==="PUT"){putCount+=1;await route.fulfill({status:409,contentType:"application/json",body:JSON.stringify({detail:{reasonCode:"STALE_WORKFLOW_DEFINITION"}})});return}
    await route.fulfill({contentType:"application/json",body:JSON.stringify(url.pathname.endsWith("/workflow-definitions")?[projection]:projection)});
  });
  await page.goto("/workflow-definitions");
  await page.getByRole("button",{name:/CAS Workflow/}).click();
  await page.getByRole("button",{name:"编辑当前 Draft"}).click();
  await page.getByLabel("用途说明").fill("My retained CAS edit");
  await page.getByRole("button",{name:"Save governed Workflow draft"}).dblclick();
  await expect(page.getByLabel("Guided conflict recovery")).toContainText("尝试的聚合版本");
  await expect(page.getByLabel("Guided conflict recovery")).toContainText("已只读获取权威版本");
  expect(putCount).toBe(1);
  await page.getByRole("button",{name:"Explicitly reapply safe draft input"}).click();
  await expect(page.getByLabel("用途说明")).toHaveValue("My retained CAS edit");
  await expect(page.getByLabel("Workflow authoring").getByLabel("步骤 inspect 的 Skill operation 绑定")).toContainText(binding.operation);
});

test("ignores a late Workflow detail response after the user switches resources", async ({ page }) => {
  const makeProjection=(id:string,name:string)=>({definition:{workflowDefinitionId:id,name,aggregateVersion:1,lifecycleState:"DRAFT",currentDraftRevisionId:`${id}:revision`,publishedRevisionId:null,revisions:[{revisionId:`${id}:revision`,predecessorRevisionId:null,state:"DRAFT",digest:`sha256:${"f".repeat(64)}`,content:{description:name,inputs:[],outputs:[],runtimeProfile:{kind:"RUNTIME_PROFILE",resourceId:"runtime-profile:native",revisionId:"runtime-profile-revision:published"},tasks:[{taskId:"inspect",name:"Inspect",dependsOn:[],inputs:[],outputs:[],capabilityRequirements:[],references:[],retryLimit:0,timeoutSeconds:300,failurePolicy:"FAIL_WORKFLOW"}]},createdAt:"2026-09-08T00:00:00Z"}],reviews:[],relationships:[],consumers:[]},productProjection:{},technicalProjection:{}});
  const first=makeProjection("workflow-definition:first","First Workflow"),second=makeProjection("workflow-definition:second","Second Workflow");
  await page.route("**/api/internal/v0.2.2/resources/skill",route=>route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({detail:{reasonCode:"SKILL_OPERATION_DIRECTORY_UNAVAILABLE"}})}));
  await page.route("**/api/internal/v0.2.2/workflow-definitions**",async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith("/workflow-definitions")){await route.fulfill({contentType:"application/json",body:JSON.stringify([first,second])});return}
    if(path.endsWith(encodeURIComponent(first.definition.workflowDefinitionId)))await new Promise(resolve=>setTimeout(resolve,250));
    await route.fulfill({contentType:"application/json",body:JSON.stringify(path.endsWith(encodeURIComponent(first.definition.workflowDefinitionId))?first:second)});
  });
  await page.goto("/workflow-definitions");
  await page.getByRole("button",{name:/Second Workflow/}).click();
  await expect(page.getByRole("heading",{name:"Second Workflow",exact:true})).toBeVisible();
  await page.getByRole("button",{name:/First Workflow/}).click();
  await expect(page.getByRole("button",{name:"编辑当前 Draft"})).toBeDisabled();
  await page.getByRole("button",{name:/Second Workflow/}).click();
  await expect(page.getByRole("heading",{name:"Second Workflow",exact:true})).toBeVisible();
  await page.waitForTimeout(300);
  await expect(page.getByRole("heading",{name:"Second Workflow",exact:true})).toBeVisible();
  await expect(page.getByRole("heading",{name:"First Workflow",exact:true})).toHaveCount(0);
});

test("does not offer an ineligible or operation-less Skill as a valid binding", async ({ page }) => {
  const invalidSkill={resourceId:"skill-definition:disabled",kind:"skill",name:"Disabled Skill",aggregateVersion:1,lifecycleState:"PUBLISHED",enabled:false,archived:false,currentDraftRevisionId:null,publishedRevisionId:"skill-revision:disabled",revisions:[{revisionId:"skill-revision:disabled",state:"PUBLISHED",digest:`sha256:${"a".repeat(64)}`,content:{capabilities:["quality.read"]}}]};
  await page.route("**/api/internal/v0.2.2/resources/skill",route=>route.fulfill({contentType:"application/json",body:JSON.stringify([invalidSkill])}));
  await page.route("**/api/internal/v0.2.2/workflow-definitions",route=>route.fulfill({contentType:"application/json",body:"[]"}));
  await page.goto("/workflow-definitions");
  await expect(page.getByLabel("Skill operation directory status")).toContainText("0 个合格 operation；1 个不合格");
  await page.getByRole("button",{name:"新建 Workflow Definition"}).click();
  await expect(page.getByText("没有合格的 Skill operation",{exact:true})).toBeVisible();
  await expect(page.getByLabel("步骤 step-1 选择 Skill",{exact:true})).toBeDisabled();
  await expect(page.getByRole("button",{name:"保存精确 Skill operation binding"})).toBeDisabled();
});

test("blocks validation when the Skill reference digest differs from the binding", async ({ page }) => {
  const binding={skillId:"skill-definition:digest",skillRevisionId:"skill-revision:published",skillDigest:`sha256:${"a".repeat(64)}`,operation:"quality.read"};
  const operation={name:binding.operation,inputSchema:{type:"object"},outputSchema:{type:"object"},sideEffectClass:"READ_ONLY",executorId:"readonly",executorRevision:"1",executorConfigurationDigest:"1".repeat(64),sideEffectPolicy:{policyId:"readonly",policyRevision:"1",policyDigest:"2".repeat(64)},ioLimits:{policyId:"bounded",policyRevision:"1",maxInputBytes:1024,maxOutputBytes:2048,maxObjectDepth:8,maxProperties:64,timeoutMs:1000}};
  const skill={resourceId:binding.skillId,kind:"skill",name:"Digest Skill",lifecycleState:"PUBLISHED",enabled:true,archived:false,publishedRevisionId:binding.skillRevisionId,revisions:[{revisionId:binding.skillRevisionId,state:"PUBLISHED",digest:binding.skillDigest,content:{operations:[operation]}}]};
  const content={description:"Digest mismatch",inputs:[],outputs:[],runtimeProfile:{kind:"RUNTIME_PROFILE",resourceId:"runtime-profile:native",revisionId:"runtime-profile-revision:published"},tasks:[{taskId:"inspect",name:"Inspect",dependsOn:[],inputs:[],outputs:[],capabilityRequirements:[],references:[{kind:"SKILL",resourceId:binding.skillId,revisionId:binding.skillRevisionId,digest:`sha256:${"b".repeat(64)}`}],skillOperationBindings:[binding],retryLimit:0,timeoutSeconds:300,failurePolicy:"FAIL_WORKFLOW"}]};
  const projection={definition:{workflowDefinitionId:"workflow-definition:digest",name:"Digest Workflow",aggregateVersion:1,lifecycleState:"DRAFT",currentDraftRevisionId:"workflow-revision:draft",publishedRevisionId:null,revisions:[{revisionId:"workflow-revision:draft",predecessorRevisionId:null,state:"DRAFT",digest:`sha256:${"c".repeat(64)}`,content,createdAt:"2026-09-08T00:00:00Z"}],reviews:[],relationships:[],consumers:[]},productProjection:{},technicalProjection:{}};
  await page.route("**/api/internal/v0.2.2/resources/skill",route=>route.fulfill({contentType:"application/json",body:JSON.stringify([skill])}));
  await page.route("**/api/internal/v0.2.2/workflow-definitions**",route=>route.fulfill({contentType:"application/json",body:JSON.stringify(new URL(route.request().url()).pathname.endsWith("/workflow-definitions")?[projection]:projection)}));
  await page.goto("/workflow-definitions");
  await page.getByRole("button",{name:/Digest Workflow/}).click();
  await expect(page.getByLabel("Workflow Skill operation binding review")).toContainText("SKILL reference digest 不一致");
  await expect(page.getByRole("button",{name:"Validate DAG and references"})).toBeDisabled();
});

test("handles FastAPI detail arrays without losing controlled error states", async ({ page }) => {
  const detail=[{type:"missing",loc:["body","content"],msg:"Field required",input:null}];
  await page.route("**/api/internal/v0.2.2/resources/skill",route=>route.fulfill({status:422,contentType:"application/json",body:JSON.stringify({detail})}));
  await page.route("**/api/internal/v0.2.2/workflow-definitions",route=>route.fulfill({status:422,contentType:"application/json",body:JSON.stringify({detail})}));
  await page.goto("/workflow-definitions");
  await expect(page.getByRole("alert")).toContainText("validation error");
  await expect(page.getByRole("alert")).toContainText("WORKFLOW_DEFINITION_UNAVAILABLE");
  await expect(page.getByLabel("Skill operation directory status")).toContainText("目录不可用：SKILL_OPERATION_DIRECTORY_UNAVAILABLE");
});
