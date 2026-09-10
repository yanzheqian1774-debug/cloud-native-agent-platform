import {expect,test,type Page} from "@playwright/test";

const digest=(value:string)=>`sha256:${value.repeat(64)}`;
const markTestAdapter=(page:Page)=>page.evaluate(()=>{let badge=document.getElementById("s5-311-test-adapter");if(!badge){badge=document.createElement("div");badge.id="s5-311-test-adapter";badge.textContent="TEST_ADAPTER · INTERACTION EVIDENCE";document.body.appendChild(badge)}badge.style.cssText=`position:fixed;z-index:99999;right:8px;${innerWidth<=720?"top:108px":"top:58px"};padding:4px 7px;border:2px solid #9b2c2c;border-radius:6px;color:#7f1d1d;background:#fff7f7e8;font:700 10px system-ui;box-shadow:0 3px 12px #0002`});

test("edits a dependency-derived node without changing sibling content or exact bindings",async({page})=>{
  const binding={skillId:"skill-definition:quality",skillRevisionId:"skill-revision:7",skillDigest:digest("a"),operation:"quality.read"};
  const secondBinding={...binding,operation:"quality.inspect"};
  const operation=(name:string)=>({name,inputSchema:{type:"object",required:["supplier"]},outputSchema:{type:"object",properties:{status:{type:"string"}}},sideEffectClass:"READ_ONLY",executorId:"readonly",executorRevision:"1",executorConfigurationDigest:"1".repeat(64),sideEffectPolicy:{policyId:"readonly",policyRevision:"1",policyDigest:"2".repeat(64)},ioLimits:{policyId:"bounded",policyRevision:"1",maxInputBytes:1024,maxOutputBytes:2048,maxObjectDepth:8,maxProperties:64,timeoutMs:1000}});
  const skill={resourceId:binding.skillId,kind:"skill",name:"Quality Skill",lifecycleState:"PUBLISHED",enabled:true,archived:false,publishedRevisionId:binding.skillRevisionId,revisions:[{revisionId:binding.skillRevisionId,state:"PUBLISHED",digest:binding.skillDigest,content:{operations:[operation(binding.operation),operation(secondBinding.operation)]}}]};
  const collect={taskId:"collect",name:"Collect",dependsOn:[],inputs:["request"],outputs:["records"],capabilityRequirements:["quality.read"],references:[{kind:"SKILL",resourceId:binding.skillId,revisionId:binding.skillRevisionId,digest:binding.skillDigest},{kind:"KNOWLEDGE",resourceId:"knowledge:quality",revisionId:"knowledge-revision:3",digest:digest("b")}],skillOperationBindings:[binding,secondBinding],retryLimit:1,timeoutSeconds:120,failurePolicy:"FAIL_WORKFLOW"};
  const analyze={taskId:"analyze",name:"Analyze",dependsOn:["collect"],inputs:["records"],outputs:["report"],capabilityRequirements:["quality.analysis"],references:[{kind:"AGENT",resourceId:"agent:analyst",revisionId:"agent-revision:5",digest:digest("c")}],retryLimit:2,timeoutSeconds:300,failurePolicy:"SKIP_DEPENDENTS"};
  const content={description:"Two-step quality workflow",inputs:["request"],outputs:["report"],runtimeProfile:{kind:"RUNTIME_PROFILE",resourceId:"runtime-profile:native",revisionId:"runtime-revision:9",digest:digest("d")},tasks:[collect,analyze]};
  let projection={definition:{workflowDefinitionId:"workflow-definition:visual",name:"Visual Workflow",aggregateVersion:4,lifecycleState:"DRAFT",currentDraftRevisionId:"workflow-revision:4",publishedRevisionId:null,revisions:[{revisionId:"workflow-revision:4",predecessorRevisionId:"workflow-revision:3",state:"DRAFT",digest:digest("e"),content,createdAt:"2026-09-09T00:00:00Z"}],reviews:[],relationships:[],consumers:[]},productProjection:{},technicalProjection:{}};
  const submitted:Array<{expectedVersion:number;content:typeof content}>=[];
  await page.route("**/api/internal/v0.2.2/resources/skill",route=>route.fulfill({contentType:"application/json",body:JSON.stringify([skill])}));
  await page.route("**/api/internal/v0.2.2/workflow-definitions**",async route=>{
    const request=route.request(),url=new URL(request.url());
    if(request.method()==="PUT"){
      const body=request.postDataJSON() as {expectedVersion:number;content:typeof content};submitted.push(body);
      projection={...projection,definition:{...projection.definition,aggregateVersion:5,revisions:[...projection.definition.revisions,{...projection.definition.revisions[0],revisionId:"workflow-revision:5",predecessorRevisionId:"workflow-revision:4",content:body.content}],currentDraftRevisionId:"workflow-revision:5"}};
      await route.fulfill({contentType:"application/json",body:JSON.stringify(projection)});return;
    }
    await route.fulfill({contentType:"application/json",body:JSON.stringify(url.pathname.endsWith("/workflow-definitions")?[projection]:projection)});
  });

  await page.goto("/workflow-definitions");
  await page.getByRole("button",{name:/Visual Workflow/}).click();
  await expect(page.getByLabel("Workflow 流程画布")).toBeVisible();
  await expect(page.getByLabel("Workflow 节点详情")).toContainText("这里不是运行进度");
  const collectNode=page.getByRole("button",{name:"查看步骤 Collect"});
  await collectNode.focus();await page.keyboard.press("Enter");
  await expect(page.getByLabel("步骤 collect 的资源详情")).toContainText("Quality Skill");
  await expect(page.getByLabel("步骤 collect 的资源详情")).toContainText(binding.skillDigest);
  await expect(page.getByLabel("步骤 collect 的资源详情")).toContainText("1024 / 2048 bytes");
  if(process.env.S5_311_SCREENSHOT_DIR){await page.setViewportSize({width:1440,height:1000});await markTestAdapter(page);await page.locator(".workflow-catalog-layout").evaluate(element=>window.scrollTo({top:element.getBoundingClientRect().top+window.scrollY-70}));await page.screenshot({path:`${process.env.S5_311_SCREENSHOT_DIR}/workflow-designer-desktop.png`})}
  await page.getByRole("button",{name:"编辑当前 Draft"}).click();
  await page.getByRole("button",{name:"编辑步骤 Analyze"}).click();
  await page.getByLabel("名称",{exact:true}).fill("Analyze precisely");
  await expect(page.getByLabel("步骤 analyze 配置").getByText("collect",{exact:true})).toBeVisible();
  await page.getByRole("button",{name:"保存工作流草稿"}).click();

  expect(submitted).toHaveLength(1);
  expect(submitted[0].content.tasks[0]).toEqual(collect);
  expect(submitted[0].content.tasks[1]).toEqual({...analyze,name:"Analyze precisely"});
  expect(submitted[0].content.runtimeProfile).toEqual(content.runtimeProfile);
  await expect(page.getByRole("button",{name:"查看步骤 Analyze precisely"})).toBeVisible();

  await page.getByRole("button",{name:"编辑当前 Draft"}).click();
  await page.getByRole("button",{name:"编辑步骤 Collect"}).click();
  await page.setViewportSize({width:390,height:844});
  await page.getByLabel("Workflow authoring").getByRole("tab",{name:"节点详情"}).click();
  const narrowSkillSelect=page.getByLabel("步骤 collect 选择 Skill",{exact:true});
  await narrowSkillSelect.focus();await expect(narrowSkillSelect).toBeFocused();
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole("button",{name:"检查并移除此步骤"}).click();
  const impact=page.getByRole("alert").filter({hasText:"此操作会删除步骤 collect"});
  await expect(impact).toContainText("analyze");
  await expect(impact).toContainText("references 与 bindings 不会改变");
  await impact.getByRole("button",{name:"取消"}).click();
  await page.getByRole("button",{name:"编辑步骤 Analyze precisely"}).click();
  await page.getByLabel("名称",{exact:true}).fill("Expanded edit retained");
  await page.getByRole("button",{name:"展开画布"}).first().click();
  await page.getByLabel("当前 Workflow 节点搜索").first().fill("analyze");
  await page.getByRole("button",{name:"定位节点"}).first().click();
  await page.getByRole("button",{name:"退出展开"}).click();
  await expect(page.getByLabel("名称",{exact:true})).toHaveValue("Expanded edit retained");
  await page.getByRole("button",{name:"编辑步骤 Collect"}).click();
  await page.getByRole("button",{name:"检查并移除此步骤"}).click();
  await page.getByRole("button",{name:"确认删除步骤及上述依赖"}).click();
  await page.getByRole("button",{name:"保存工作流草稿"}).click();
  expect(submitted).toHaveLength(2);
  expect(submitted[1].content.tasks).toEqual([{...analyze,name:"Expanded edit retained",dependsOn:[]}]);

  await page.setViewportSize({width:390,height:844});
  await page.getByRole("button",{name:"编辑当前 Draft"}).click();
  const authoring=page.getByLabel("Workflow authoring");
  await authoring.getByRole("tab",{name:"步骤列表"}).click();
  await expect(authoring.getByLabel("等价 Workflow 步骤列表")).toBeVisible();
  await authoring.getByLabel("等价 Workflow 步骤列表").getByRole("button",{name:/Analyze precisely/}).click();
  await expect(page.getByLabel("步骤 analyze 配置")).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBe(true);
  if(process.env.S5_311_SCREENSHOT_DIR){await markTestAdapter(page);await page.locator(".workflow-mobile-pane-tabs").evaluate(element=>{let top=0,current:HTMLElement|null=element as HTMLElement;while(current){top+=current.offsetTop;current=current.offsetParent as HTMLElement|null}window.scrollTo({top:Math.max(0,top-56)})});await page.screenshot({path:`${process.env.S5_311_SCREENSHOT_DIR}/workflow-designer-390px.png`})}
  const mobileBarsDoNotOverlap=await page.evaluate(()=>{const save=document.querySelector(".workflow-savebar")?.getBoundingClientRect(),nav=document.querySelector(".px-mobile-nav")?.getBoundingClientRect();return !save||!nav||save.bottom<=nav.top||save.top>=nav.bottom});
  expect(mobileBarsDoNotOverlap).toBe(true);
});

test("requires an explicit decision before switching away from unsaved authoring",async({page})=>{
  const makeProjection=(id:string,name:string)=>({definition:{workflowDefinitionId:id,name,aggregateVersion:1,lifecycleState:"DRAFT",currentDraftRevisionId:`${id}:revision`,publishedRevisionId:null,revisions:[{revisionId:`${id}:revision`,predecessorRevisionId:null,state:"DRAFT",digest:digest("9"),content:{description:name,inputs:[],outputs:[],runtimeProfile:{kind:"RUNTIME_PROFILE",resourceId:"runtime:1",revisionId:"runtime-revision:1"},tasks:[{taskId:"one",name:"One",dependsOn:[],inputs:[],outputs:[],capabilityRequirements:[],references:[],retryLimit:0,timeoutSeconds:300,failurePolicy:"FAIL_WORKFLOW"}]},createdAt:"2026-09-09T00:00:00Z"}],reviews:[],relationships:[],consumers:[]},productProjection:{},technicalProjection:{}});
  const first=makeProjection("workflow:first","First Workflow"),second=makeProjection("workflow:second","Second Workflow");
  await page.route("**/api/internal/v0.2.2/resources/skill",route=>route.fulfill({contentType:"application/json",body:"[]"}));
  await page.route("**/api/internal/v0.2.2/workflow-definitions**",route=>{const path=decodeURIComponent(new URL(route.request().url()).pathname);route.fulfill({contentType:"application/json",body:JSON.stringify(path.endsWith("/workflow-definitions")?[first,second]:path.endsWith(first.definition.workflowDefinitionId)?first:second)})});
  await page.goto("/workflow-definitions");await page.setViewportSize({width:390,height:844});await expect(page.getByRole("tab",{name:"工作流目录"})).toHaveAttribute("aria-selected","true");await page.setViewportSize({width:1440,height:1000});await expect(page.getByRole("button",{name:/First Workflow/})).toContainText("摘要：First Workflow");await page.getByRole("button",{name:/First Workflow/}).click();await page.getByRole("button",{name:"编辑当前 Draft"}).click();
  await page.getByLabel("用途说明").fill("unsaved authoring");
  await page.getByRole("button",{name:/Second Workflow/}).click();
  const warning=page.getByLabel("未保存 Workflow 编辑");await expect(warning).toContainText("不会被静默丢弃");await expect(page.getByLabel("用途说明")).toHaveValue("unsaved authoring");
  await warning.getByRole("button",{name:"继续编辑当前 Workflow"}).click();await expect(page.getByLabel("用途说明")).toHaveValue("unsaved authoring");
  await page.getByRole("button",{name:/Second Workflow/}).click();await page.getByRole("button",{name:"放弃未保存输入并切换"}).click();
  await expect(page.getByRole("heading",{name:"Second Workflow",exact:true})).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole("tab",{name:"流程设计"})).toHaveAttribute("aria-selected","true");
});

test("shows local graph issues and keeps invalid legacy dependency editable",async({page})=>{
  const content={description:"Invalid legacy graph",inputs:[],outputs:[],runtimeProfile:{kind:"RUNTIME_PROFILE",resourceId:"runtime:1",revisionId:"runtime-revision:1"},tasks:[{taskId:"one",name:"One",dependsOn:["one","missing","missing"],inputs:[],outputs:[],capabilityRequirements:[],references:[],retryLimit:0,timeoutSeconds:300,failurePolicy:"FAIL_WORKFLOW"}]};
  const projection={definition:{workflowDefinitionId:"workflow-definition:invalid",name:"Invalid Workflow",aggregateVersion:1,lifecycleState:"DRAFT",currentDraftRevisionId:"workflow-revision:1",publishedRevisionId:null,revisions:[{revisionId:"workflow-revision:1",predecessorRevisionId:null,state:"DRAFT",digest:digest("f"),content,createdAt:"2026-09-09T00:00:00Z"}],reviews:[],relationships:[],consumers:[]},productProjection:{},technicalProjection:{}};
  await page.route("**/api/internal/v0.2.2/resources/skill",route=>route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({detail:{reasonCode:"SKILL_OPERATION_DIRECTORY_UNAVAILABLE"}})}));
  await page.route("**/api/internal/v0.2.2/workflow-definitions**",route=>route.fulfill({contentType:"application/json",body:JSON.stringify(new URL(route.request().url()).pathname.endsWith("/workflow-definitions")?[projection]:projection)}));
  await page.goto("/workflow-definitions");await page.getByRole("button",{name:/Invalid Workflow/}).click();await page.getByRole("button",{name:"编辑当前 Draft"}).click();
  const errors=page.getByLabel("Workflow 校验错误列表");
  await expect(errors).toContainText("不能依赖自身");await expect(errors).toContainText("重复依赖");await expect(errors).toContainText("不存在的依赖");
  await page.getByRole("button",{name:"编辑步骤 One"}).click();
  await expect(page.getByText("无效目标：").first()).toBeVisible();
  await page.getByRole("button",{name:"移除无效依赖"}).first().click();
  await expect(page.getByRole("alert").filter({hasText:"移除直接依赖 missing"})).toContainText("不会自动连接其上游");
  await page.getByRole("button",{name:"确认依赖变更"}).click();
  await expect(page.getByText("无效目标：")).toHaveCount(0);
  await expect(errors).toContainText("不会替代后端权威校验");
});

test("navigates a complex published Workflow without offering draft edits or creating writes",async({page})=>{
  const tasks=Array.from({length:14},(_,index)=>({taskId:`step-${index+1}`,name:`复杂步骤 ${index+1}`,dependsOn:index?[`step-${index}`]:[],inputs:index?[`input-${index}`]:[],outputs:[`output-${index+1}`],capabilityRequirements:[],references:index===6?[{kind:"SKILL",resourceId:"skill:complex",revisionId:"skill-revision:1",digest:digest("a")}]:[],retryLimit:0,timeoutSeconds:300,failurePolicy:"FAIL_WORKFLOW"}));
  const makeProjection=(index:number,published=false)=>({definition:{workflowDefinitionId:`workflow:${index}`,name:published?"复杂已发布 Workflow":`目录 Workflow ${index}`,aggregateVersion:1,lifecycleState:published?"PUBLISHED":"DRAFT",currentDraftRevisionId:published?null:`revision:${index}`,publishedRevisionId:published?`revision:${index}`:null,revisions:[{revisionId:`revision:${index}`,predecessorRevisionId:null,state:published?"PUBLISHED":"DRAFT",digest:digest(String(index%10)),content:{description:`目录摘要 ${index}`,inputs:[],outputs:[],runtimeProfile:{kind:"RUNTIME_PROFILE",resourceId:"runtime:1",revisionId:"runtime-revision:1"},tasks:published?tasks:[tasks[0]]},createdAt:"2026-09-09T00:00:00Z"}],reviews:[],relationships:[],consumers:[]},productProjection:{},technicalProjection:{}});
  const target=makeProjection(0,true),catalog=[target,...Array.from({length:9},(_,index)=>makeProjection(index+1))];let writes=0;
  await page.route("**/api/internal/v0.2.2/resources/skill",route=>route.fulfill({contentType:"application/json",body:"[]"}));
  await page.route("**/api/internal/v0.2.2/workflow-definitions**",route=>{if(route.request().method()!=="GET")writes+=1;const path=decodeURIComponent(new URL(route.request().url()).pathname);route.fulfill({contentType:"application/json",body:JSON.stringify(path.endsWith("/workflow-definitions")?catalog:target)})});
  await page.goto("/workflow-definitions");
  await expect(page.getByLabel("Workflow 列表分页")).toContainText("1 / 2");await page.getByRole("button",{name:"下一页"}).click();await expect(page.getByText("目录 Workflow 9",{exact:true})).toBeVisible();await page.getByRole("button",{name:"上一页"}).click();
  await page.getByRole("button",{name:/复杂已发布 Workflow/}).click();
  await expect(page.getByRole("button",{name:"编辑当前 Draft"})).toHaveCount(0);await expect(page.getByRole("button",{name:"Create Workflow successor"})).toBeVisible();
  await page.getByRole("button",{name:"恢复 100%"}).click();await expect(page.getByRole("button",{name:"恢复 100%"})).toHaveText("100%");
  await page.getByLabel("当前 Workflow 节点搜索").fill("step-14");await page.getByRole("button",{name:"定位节点"}).click();await expect(page.getByLabel("Workflow 节点详情")).toContainText("复杂步骤 14");await expect(page.getByRole("button",{name:"恢复 100%"})).toHaveText("100%");
  await page.getByRole("button",{name:"适配画布"}).click();await page.getByRole("button",{name:"折叠 Workflow 列表"}).click();await expect(page.getByRole("button",{name:"展开 Workflow 列表"})).toBeVisible();
  expect(writes).toBe(0);
  await page.setViewportSize({width:390,height:844});await page.getByRole("tab",{name:"步骤列表"}).click();await expect(page.getByLabel("等价 Workflow 步骤列表")).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBe(true);
});
