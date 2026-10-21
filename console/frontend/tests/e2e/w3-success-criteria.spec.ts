import {expect,test} from "@playwright/test";
import type {CriteriaSetRevision,CriterionRevision} from "../../src/api/businessWorkspace";

const problem={scope:{namespace:"tenant-a",security_domain:"quality"},business_problem_id:"problem:w3-1",revision_id:"problem-revision:w3-1:1",revision:1,predecessor_revision_id:null,title:"供应商交付恢复",description:"关键零部件延期影响客户交付。",owner_id:"human:owner",created_by:"human:owner",created_at:"2026-09-14T00:20:00Z",digest:"c".repeat(64)};
const envelope=(result:unknown)=>({schemaVersion:"workbench-operation.v1",result,continuationIds:[]});
type CriterionPayload={problemId?:string;successCriterionId?:string;predecessorRevisionId?:string;expectedVersion?:number;criterionType:string;measurement:Record<string,unknown>;requiredEvidenceKinds:string[];evaluatorType:string;evaluatorVersion:string;applicability:Record<string,unknown>;idempotencyKey:string};
type SetPayload={problemRevisionId:string;predecessorSetRevisionId?:string;orderedCriterionRevisionIds:string[];expectedVersion:number;idempotencyKey:string};
type GrantPayload={purpose:string;requestedGrants:{owner:string;action:string;resource:string}[]};
type State={lifecycle?:string;activationWrites?:unknown[];denyActivation?:boolean;loseActivation?:boolean;aggregateVersion:number;criteria:CriterionRevision[];sets:CriteriaSetRevision[];criterionWrites:CriterionPayload[];setWrites:SetPayload[];grantWrites?:GrantPayload[];grantState?:"PENDING"|"APPROVED"|"REJECTED";principalId?:string;denyCriterion?:boolean;denySet?:boolean;staleSet?:boolean;unknownCriterionOnce?:boolean;unknownSetOnce?:boolean;holdCriterion?:boolean;continueCriterion?:()=>void;holdSet?:boolean;continueSet?:()=>void};

async function installRoutes(page:import("@playwright/test").Page,state:State){
  await page.route("**/api/workbench/v1/session",route=>route.fulfill({contentType:"application/json",body:JSON.stringify({schemaVersion:"workbench-session.v1",principal:{principalId:state.principalId??"human:owner",tenantId:"tenant-a",securityDomain:"quality"},session:{expiresAt:"2026-09-15T00:00:00Z",idleExpiresAt:"2026-09-14T01:00:00Z"},csrfToken:"csrf-test"})}));
  await page.route("**/api/workbench/v1/problems",route=>route.fulfill({contentType:"application/json",body:JSON.stringify(envelope({problems:[problem]}))}));
  await page.route("**/api/workbench/v1/problems/problem%3Aw3-1",route=>route.fulfill({contentType:"application/json",body:JSON.stringify(envelope({problem:{scope:problem.scope,business_problem_id:problem.business_problem_id,owner_id:problem.owner_id,current_state:state.lifecycle??"DRAFT",aggregate_version:state.aggregateVersion,current_revision_id:problem.revision_id,created_by:problem.created_by,created_at:problem.created_at,updated_at:problem.created_at},revisions:[problem],lifecycle:[]}))}));
  await page.route("**/api/workbench/v1/problems/problem%3Aw3-1/criteria",route=>route.fulfill({contentType:"application/json",body:JSON.stringify(envelope({revisions:state.criteria}))}));
  await page.route("**/api/workbench/v1/problems/problem%3Aw3-1/criteria-sets",async route=>{
    if(route.request().method()==="GET"){await route.fulfill({contentType:"application/json",body:JSON.stringify(envelope({revisions:state.sets}))});return}
    const payload=route.request().postDataJSON() as SetPayload;state.setWrites.push(payload);
    if(state.denySet){await route.fulfill({status:403,contentType:"application/json",body:JSON.stringify({reasonCode:"AUTHORIZATION_DENIED"})});return}
    if(state.staleSet){await route.fulfill({status:409,contentType:"application/json",body:JSON.stringify({reasonCode:"BUSINESS_PROBLEM_CONFLICT"})});return}
    if(state.unknownSetOnce){state.unknownSetOnce=false;await route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({reasonCode:"BUSINESS_PROBLEM_STORAGE_UNAVAILABLE"})});return}
    if(state.holdSet){state.holdSet=false;await new Promise<void>(resolve=>{state.continueSet=resolve})}
    const revision={scope:problem.scope,set_revision_id:`set:w3:${state.sets.length+1}`,business_problem_id:problem.business_problem_id,problem_revision_id:payload.problemRevisionId,revision:state.sets.length+1,predecessor_set_revision_id:payload.predecessorSetRevisionId??null,ordered_criterion_revision_ids:payload.orderedCriterionRevisionIds,created_by:"human:owner",created_at:"2026-09-14T00:30:00Z",digest:"d".repeat(64)};state.sets.push(revision);state.aggregateVersion+=1;await route.fulfill({status:201,contentType:"application/json",body:JSON.stringify(envelope({revision}))});
  });
  await page.route("**/api/workbench/v1/problems/problem%3Aw3-1/lifecycle",async route=>{
    const payload=route.request().postDataJSON();(state.activationWrites??=[]).push(payload);
    if(state.denyActivation){await route.fulfill({status:403,json:{reasonCode:"AUTHORIZATION_DENIED"}});return}
    if(payload.expectedVersion!==state.aggregateVersion){await route.fulfill({status:409,json:{reasonCode:"STALE_AGGREGATE_VERSION"}});return}
    state.lifecycle="ACTIVE";state.aggregateVersion++;
    if(state.loseActivation){state.loseActivation=false;await route.abort();return}
    await route.fulfill({json:envelope({businessProblemId:problem.business_problem_id,aggregateVersion:state.aggregateVersion})});
  });
  await page.route("**/api/workbench/v1/success-criteria",async route=>{
    const payload=route.request().postDataJSON() as CriterionPayload;state.criterionWrites.push(payload);
    if(state.denyCriterion){await route.fulfill({status:403,contentType:"application/json",body:JSON.stringify({reasonCode:"AUTHORIZATION_DENIED"})});return}
    if(state.unknownCriterionOnce){state.unknownCriterionOnce=false;await route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({reasonCode:"BUSINESS_PROBLEM_STORAGE_UNAVAILABLE"})});return}
    if(state.holdCriterion){state.holdCriterion=false;await new Promise<void>(resolve=>{state.continueCriterion=resolve})}
    const prior=payload.predecessorRevisionId?state.criteria.find(item=>item.revision_id===payload.predecessorRevisionId):undefined;
    const revision={scope:problem.scope,success_criterion_id:payload.successCriterionId??"criterion:w3-1",revision_id:`criterion-revision:w3:${state.criteria.length+1}`,revision:prior?prior.revision+1:1,predecessor_revision_id:payload.predecessorRevisionId??null,criterion_type:payload.criterionType,measurement:payload.measurement,required_evidence_kinds:payload.requiredEvidenceKinds,evaluator_type:payload.evaluatorType,evaluator_version:payload.evaluatorVersion,applicability:payload.applicability,created_by:"human:owner",created_at:"2026-09-14T00:29:00Z",digest:"e".repeat(64)};state.criteria.push(revision);await route.fulfill({status:201,contentType:"application/json",body:JSON.stringify(envelope({revision}))});
  });
  await page.route("**/api/workbench/v1/authorization/grant-requests**",async route=>{
    if(route.request().method()==="POST"){
      const payload=route.request().postDataJSON() as GrantPayload;(state.grantWrites??=[]).push(payload);state.grantState="PENDING";
      await route.fulfill({status:202,contentType:"application/json",body:JSON.stringify({requestId:`grant-request-${state.grantWrites.length}`,state:"PENDING",aggregateVersion:1,submittedAt:"2026-09-14T00:31:00Z",purpose:payload.purpose,requestedActions:[...new Set(payload.requestedGrants.map(item=>item.action))]})});return;
    }
    const id=route.request().url().split("/").at(-1);await route.fulfill({contentType:"application/json",body:JSON.stringify({requestId:id,state:state.grantState??"PENDING",aggregateVersion:state.grantState==="PENDING"?1:2,submittedAt:"2026-09-14T00:31:00Z",purpose:"WORKBENCH_SUCCESS_CRITERIA",requestedActions:state.grantWrites?.at(-1)?.requestedGrants.map(item=>item.action)??[]})});
  });
}

async function draftCriterion(page:import("@playwright/test").Page,text:string){
  await page.getByRole("button",{name:"定义成功标准",exact:true}).click();
  const composer=page.getByLabel("怎样才算解决？");await expect(composer).toBeFocused();await composer.fill(text);await composer.press("Enter");const card=page.getByLabel("成功标准待确认卡片");await card.getByLabel("人工验收标准").check();return card;
}

test("confirm is the write gate and official readback survives refresh and revision",async({page},testInfo)=>{
  const state:State={aggregateVersion:1,criteria:[],sets:[],criterionWrites:[],setWrites:[]};await installRoutes(page,state);await page.goto("/work?problem=problem%3Aw3-1");
  await expect(page.locator(".px-task-summary-panel")).toContainText("查看权限已核验");await expect(page.locator(".px-task-summary-panel")).not.toContainText("尚未申请");
  const card=await draftCriterion(page,"客户确认未来三批均能按承诺日期交付。");expect(state.criterionWrites).toHaveLength(0);
  await card.getByRole("button",{name:"修改原文"}).click();await page.getByLabel("修改成功标准原文").fill("业务负责人确认未来三批均能按承诺日期交付。");await page.getByRole("button",{name:"采用标准原文"}).click();
  const confirm=card.getByRole("button",{name:"确认并保存"});await confirm.evaluate((button:HTMLButtonElement)=>{button.click();button.click()});await expect(card).toContainText("已保存并完成正式关联");
  expect(state.criterionWrites).toHaveLength(1);expect(state.criterionWrites[0]).toMatchObject({criterionType:"HUMAN_EVALUATED",measurement:{rubric:"业务负责人确认未来三批均能按承诺日期交付。"},requiredEvidenceKinds:[],evaluatorType:"HUMAN",evaluatorVersion:"v1",applicability:{}});expect(state.setWrites).toHaveLength(1);expect(state.setWrites[0]).toMatchObject({problemRevisionId:problem.revision_id,orderedCriterionRevisionIds:["criterion-revision:w3:1"],expectedVersion:1});
  await page.reload();const history=page.getByLabel("已保存成功标准");await expect(history).toContainText("业务负责人确认未来三批均能按承诺日期交付。");await expect(history).toContainText("Criteria Set 修订 1");
  await history.getByRole("button",{name:"修订此标准"}).click();await page.getByLabel("修改成功标准原文").fill("业务负责人确认未来五批均能按承诺日期交付。");await page.getByRole("button",{name:"采用标准原文"}).click();await page.getByRole("button",{name:"确认并保存"}).click();await expect(page.getByLabel("成功标准待确认卡片")).toContainText("已保存并完成正式关联");
  expect(state.criterionWrites[1]).toMatchObject({problemId:problem.business_problem_id,successCriterionId:"criterion:w3-1",predecessorRevisionId:"criterion-revision:w3:1",expectedVersion:1,measurement:{rubric:"业务负责人确认未来五批均能按承诺日期交付。"}});expect(state.setWrites[1]).toMatchObject({predecessorSetRevisionId:"set:w3:1",orderedCriterionRevisionIds:["criterion-revision:w3:2"],expectedVersion:2});
  await page.screenshot({path:testInfo.outputPath("w3-saved-revised-1440.png"),fullPage:true});
});

test("unknown commands preserve payload and new input while access denial and stale CAS fail closed",async({page})=>{
  const state:State={aggregateVersion:1,criteria:[],sets:[],criterionWrites:[],setWrites:[],unknownCriterionOnce:true};await installRoutes(page,state);await page.goto("/work?problem=problem%3Aw3-1");const card=await draftCriterion(page,"人工确认交付恢复。");await card.getByRole("button",{name:"确认并保存"}).click();await expect(card).toContainText("结果未知");const first=state.criterionWrites[0];await card.getByRole("button",{name:"恢复原保存结果"}).click();await expect(card).toContainText("已保存并完成正式关联");expect(state.criterionWrites[1]).toEqual(first);
  await page.reload();await page.getByLabel("已保存成功标准").getByRole("button",{name:"修订此标准"}).click();await page.getByLabel("修改成功标准原文").fill("人工确认连续交付恢复。");await page.getByRole("button",{name:"采用标准原文"}).click();state.unknownSetOnce=true;await page.getByRole("button",{name:"确认并保存"}).click();await expect(page.getByLabel("成功标准待确认卡片")).toContainText("结果未知");const setCommand=state.setWrites.at(-1);const supplement=page.getByLabel("补充或纠正正式目标");await supplement.fill("保存期间的新补充不应被清空。");state.holdSet=true;const recovery=page.getByRole("button",{name:"恢复原保存结果"}).click();await expect.poll(()=>state.setWrites.length).toBe(3);await supplement.focus();state.continueSet?.();await recovery;await expect(supplement).toHaveValue("保存期间的新补充不应被清空。");await expect(supplement).toBeFocused();expect(state.setWrites.at(-1)).toEqual(setCommand);
  await supplement.fill("");state.staleSet=true;await page.reload();await page.getByLabel("已保存成功标准").getByRole("button",{name:"修订此标准"}).first().click();await page.getByRole("button",{name:"采用标准原文"}).click();await page.getByRole("button",{name:"确认并保存"}).click();await expect(page.getByLabel("成功标准待确认卡片")).toContainText("版本冲突");expect(state.aggregateVersion).toBe(3);
});

test("Problem read does not grant success criterion writes",async({page})=>{
  const state:State={aggregateVersion:1,criteria:[],sets:[],criterionWrites:[],setWrites:[],denyCriterion:true};await installRoutes(page,state);await page.goto("/work?problem=problem%3Aw3-1");const card=await draftCriterion(page,"人工确认业务恢复。");await card.getByRole("button",{name:"确认并保存"}).click();await expect(page.getByRole("alert")).toContainText("当前会话不能执行这项操作");await expect(card).toContainText("标准未保存");expect(state.setWrites).toHaveLength(0);
});

test("formal requests and independent decisions resume the frozen criterion and set commands",async({page},testInfo)=>{
  const state:State={aggregateVersion:1,criteria:[],sets:[],criterionWrites:[],setWrites:[],grantWrites:[],denyCriterion:true,denySet:true};await installRoutes(page,state);await page.setViewportSize({width:1440,height:900});await page.goto("/work?problem=problem%3Aw3-1");const card=await draftCriterion(page,"业务负责人确认三批交付恢复。");await card.getByRole("button",{name:"确认并保存"}).click();await expect(card).toContainText("标准未保存");
  await card.getByRole("button",{name:"申请所需精确权限"}).click();await expect(card.getByLabel("成功标准权限申请")).toContainText("等待独立审批");expect(state.grantWrites).toHaveLength(1);expect(state.grantWrites?.[0]).toMatchObject({purpose:"WORKBENCH_SUCCESS_CRITERIA",requestedGrants:[{owner:"SUCCESS_CRITERION",action:"CREATE",resource:"success-criterion:collection"},{owner:"SUCCESS_CRITERION",action:"READ",resource:"success-criterion:collection"}]});
  state.grantState="APPROVED";state.denyCriterion=false;await card.getByRole("button",{name:"刷新权限状态并继续"}).click();await expect(card).toContainText("关联未完成");expect(state.criterionWrites).toHaveLength(2);expect(state.criterionWrites[1]).toEqual(state.criterionWrites[0]);
  await card.getByRole("button",{name:"申请所需精确权限"}).click();expect(state.grantWrites).toHaveLength(2);expect(state.grantWrites?.[1].requestedGrants).toEqual([{owner:"SUCCESS_CRITERION",action:"READ",resource:"success-criterion:revision:criterion-revision:w3:1"},{owner:"SUCCESS_CRITERIA_SET",action:"CREATE",resource:"success-criteria-set:problem:w3-1"},{owner:"SUCCESS_CRITERIA_SET",action:"READ",resource:"success-criteria-set:problem:w3-1"}]);
  state.grantState="APPROVED";state.denySet=false;await card.getByRole("button",{name:"刷新权限状态并继续"}).click();await expect(card).toContainText("已保存并完成正式关联");expect(state.setWrites).toHaveLength(2);expect(state.setWrites[1]).toEqual(state.setWrites[0]);await page.screenshot({path:testInfo.outputPath("w3-formal-authorization-1440x900.png"),fullPage:true});
});

test("a changed trusted session isolates an in-flight criterion command",async({page})=>{
  const state:State={aggregateVersion:1,criteria:[],sets:[],criterionWrites:[],setWrites:[],holdCriterion:true};await installRoutes(page,state);await page.goto("/work?problem=problem%3Aw3-1");const card=await draftCriterion(page,"旧身份的成功标准不得进入新上下文。");const save=card.getByRole("button",{name:"确认并保存"}).click();await expect.poll(()=>state.criterionWrites.length).toBe(1);
  state.principalId="human:replacement";await page.evaluate(()=>window.dispatchEvent(new Event("focus")));await expect(page.getByText("请在当前可信会话重新开始")).toBeVisible();state.continueCriterion?.();await save;await expect(page.getByLabel("你希望解决什么问题？")).toBeEnabled();await expect(page.getByLabel("成功标准待确认卡片")).toHaveCount(0);expect(state.setWrites).toHaveLength(0);
});

test("saved summary and exact revision controls remain reachable at 390 by 844",async({page},testInfo)=>{
  const criterion:CriterionRevision={scope:problem.scope,success_criterion_id:"criterion:w3-1",revision_id:"criterion-revision:w3:1",revision:1,predecessor_revision_id:null,criterion_type:"HUMAN_EVALUATED",measurement:{rubric:"负责人确认三批交付恢复。"},required_evidence_kinds:[],evaluator_type:"HUMAN",evaluator_version:"v1",applicability:{},created_by:"human:owner",created_at:"2026-09-14T00:29:00Z",digest:"e".repeat(64)};
  const set:CriteriaSetRevision={scope:problem.scope,set_revision_id:"set:w3:1",business_problem_id:problem.business_problem_id,problem_revision_id:problem.revision_id,revision:1,predecessor_set_revision_id:null,ordered_criterion_revision_ids:[criterion.revision_id],created_by:"human:owner",created_at:"2026-09-14T00:30:00Z",digest:"d".repeat(64)};
  const state:State={aggregateVersion:2,criteria:[criterion],sets:[set],criterionWrites:[],setWrites:[]};await installRoutes(page,state);await page.setViewportSize({width:390,height:844});await page.goto("/work?problem=problem%3Aw3-1");const history=page.getByLabel("已保存成功标准");await expect(history).toBeVisible();await history.getByRole("button",{name:"修订此标准"}).click();const composer=page.getByLabel("修改成功标准原文");await expect(composer).toBeFocused();await composer.fill("负责人确认五批交付恢复。");await page.getByRole("button",{name:"采用标准原文"}).click();await expect(page.getByLabel("成功标准待确认卡片")).toBeVisible();await page.getByRole("button",{name:"本任务"}).click();await expect(page.getByRole("dialog")).toContainText("负责人确认三批交付恢复。");expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:testInfo.outputPath("w3-success-criteria-390x844.png")});
});

for(const mode of ["normal","denied","lost","stale"] as const){
  test(`problem confirmation preserves saved criteria and recovers ${mode}`,async({page},info)=>{
    const state:State={aggregateVersion:1,criteria:[],sets:[],criterionWrites:[],setWrites:[]};
    await installRoutes(page,state);await page.goto("/work?problem=problem%3Aw3-1");
    const gate=page.getByLabel("问题与完成标准确认");
    await expect(gate.getByRole("button",{name:"确认问题与完成标准",exact:true})).toBeDisabled();
    const card=await draftCriterion(page,"合成采购报告可追溯，缺失资源单列，不启动执行。");
    await card.getByRole("button",{name:"确认并保存",exact:true}).click();
    await expect(card).toContainText("已保存并完成正式关联");
    expect(state.activationWrites??[]).toHaveLength(0);
    await page.screenshot({path:info.outputPath(`323-before-confirm-${mode}.png`),fullPage:true});
    state.denyActivation=mode==="denied";state.loseActivation=mode==="lost";
    if(mode==="stale")state.aggregateVersion++;
    await gate.getByRole("button",{name:"确认问题与完成标准",exact:true}).evaluate((button:HTMLButtonElement)=>{button.click();button.click()});
    if(mode==="normal")await expect(gate.getByRole("link",{name:"制定建议计划"})).toBeVisible();
    else await expect(gate.getByRole("alert")).toBeVisible();
    expect(state.criterionWrites).toHaveLength(1);expect(state.setWrites).toHaveLength(1);
    expect(state.activationWrites??[]).toHaveLength(mode==="stale"?0:1);
    await page.reload();await expect(page.getByLabel("已保存成功标准")).toContainText("合成采购报告可追溯");
    if(mode==="normal"||mode==="lost")await expect(page.getByRole("link",{name:"制定建议计划"})).toBeVisible();
    else await expect(page.getByRole("link",{name:"制定建议计划"})).toHaveCount(0);
    expect(state.activationWrites??[]).toHaveLength(mode==="stale"?0:1);
    await page.screenshot({path:info.outputPath(`323-after-confirm-${mode}.png`),fullPage:true});
  });
}
