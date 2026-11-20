import {test,expect,type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
const plan=JSON.parse(readFileSync(new URL('../e2e/fixtures/delivery-plan.json',import.meta.url),'utf8'));
const ref={resource_id:'document-source',revision_id:'source-1',digest:'a'.repeat(64)};
const line=(line:number,text:string)=>({line,text});
const report=()=>({schemaVersion:'document-review-output.v1',operation:'RENDER_REPORT',sourceSnapshot:ref,documentReview:{scope:'生产环境',missingSections:['验证记录'],incompleteSections:['回退步骤'],findings:[{section:'负责人',status:'PRESENT_NOT_VALIDATED',requirement:{documentId:'policy',line:3,text:'## 负责人',body:[line(4,'写明交接负责人和接收人。')]},evidence:{documentId:'handover',line:3,heading:'## 负责人',body:[line(4,'交接负责人：测试甲；接收人：测试乙。')]}},{section:'回退步骤',status:'INCOMPLETE',requirement:{documentId:'policy',line:7,text:'## 回退步骤',body:[line(8,'列明回退步骤、触发条件和责任人。')]},evidence:{documentId:'handover',line:7,heading:'## 回退步骤',body:[line(8,'待补充：回退命令。')]}},{section:'验证记录',status:'MISSING',requirement:{documentId:'policy',line:9,text:'## 验证记录',body:[line(10,'提供变更后的验证记录及证据位置。')]},evidence:null}]}});
async function fixture(page:Page){
 const state={value:report(),writes:[] as string[]};await page.route('**/api/**',r=>{const p=new URL(r.request().url()).pathname;if(r.request().method()!=='GET'){state.writes.push(p);return r.abort()}const ok=(result:unknown)=>r.fulfill({json:{result}});
 if(p.endsWith('/session'))return r.fulfill({json:{principal:{principalId:'human:f3',tenantId:'fixture',securityDomain:'isolated'},csrfToken:'fixture',session:{}}});
 if(p.endsWith('/conversations/capabilities'))return ok({enabled:true});if(p.endsWith('/conversations'))return ok({items:[]});
 if(p.endsWith('/problems/p'))return ok({problem:{business_problem_id:'p'},revisions:[{business_problem_id:'p',revision_id:'p:1',digest:'b'.repeat(64),title:'检查交接资料'}]});
 if(p.endsWith('/prepared-executions/e'))return ok({digest:'e',executionStarted:true,preparation:{plan_id:'plan',plan_version:1,source_snapshot:ref,semantics:{...plan.semantics,target:{problem:{resource_id:'p',revision_id:'p:1',digest:'b'.repeat(64)}}},participants:plan.semantics.tasks.map((t:{task_id:string;operation:string})=>({task_id:t.task_id,instance_id:'worker',definition:ref,skill:{reference:ref,operation:t.operation},profile:ref}))},progress:{state:'SUCCEEDED',tasks:plan.semantics.tasks.map((t:{task_id:string})=>({task_id:t.task_id,state:'SUCCEEDED',attempt_ordinal:1}))},admission:{state:'ADMITTED'},resourceUses:[],events:[],artifacts:[{artifact_id:'report',task_id:plan.semantics.tasks.at(-1).task_id,digest:'c'.repeat(64),bytes:1000,created_at:'2026-11-10T00:00:00Z',contentAccess:'AUTHORIZED',content:JSON.stringify(state.value)}],outcome:null});return ok({items:[],enabled:false})});return state;
}
for(const width of [1440,390])test('document reply leads with actual gaps and citations, disclosures survive refresh '+width,async({page})=>{
 const s=await fixture(page);await page.setViewportSize({width,height:1000});await page.goto('/tasks?work=e');const result=page.getByRole('region',{name:'文档检查结果'});await expect(result.locator('.document-lead')).toHaveText('缺少验证记录。回退步骤尚未补全。');await expect(page.getByLabel('交付结果摘要')).toHaveCount(0);await expect(result.getByText('交接负责人：测试甲；接收人：测试乙。',{exact:false})).not.toBeVisible();
 await result.getByText('查看规范与核查范围',{exact:true}).click();await expect(result.getByText('policy · 第 9 行：## 验证记录',{exact:true})).toBeVisible();await expect(result.getByText('没有可引用的缺失原文。',{exact:false})).toBeVisible();
 await result.getByText('对照原文与规范',{exact:true}).first().click();await expect(result.getByText('第 8 行：待补充：回退命令。',{exact:true})).toBeVisible();await page.reload();await expect(result.getByText('第 8 行：待补充：回退命令。',{exact:true})).toBeVisible();await expect(result.getByText('policy · 第 9 行：## 验证记录',{exact:true})).toBeVisible();await result.getByText('另有 1 项已提供：负责人',{exact:true}).click();await expect(result.getByText('文本已提供，不代表技术正确或审核通过。')).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);expect(s.writes).toEqual([]);
});
test('unknown finding status is never reinterpreted as provided or approved',async({page})=>{const s=await fixture(page);s.value.documentReview.findings[0].status='UNKNOWN';await page.goto('/tasks?work=e');await expect(page.getByText('检查状态待核实',{exact:true})).toBeVisible();await expect(page.getByText('另有 1 项已提供：负责人',{exact:true})).toHaveCount(0);expect(s.writes).toEqual([])});
test('contradictory document summary does not become a business conclusion',async({page})=>{const s=await fixture(page);s.value.documentReview.missingSections=[];await page.goto('/tasks?work=e');await expect(page.getByText('文档检查汇总与逐项记录不一致，请核对原报告。')).toBeVisible();await expect(page.locator('.document-lead')).toHaveCount(0)});
test('malformed and empty document findings do not imply successful checks',async({page})=>{const s=await fixture(page);s.value.documentReview.findings=[];s.value.documentReview.missingSections=[];s.value.documentReview.incompleteSections=[];await page.goto('/tasks?work=e');await expect(page.getByText('未取得可核对的章节记录，尚不能给出完整性结论。')).toBeVisible();s.value=report();s.value.documentReview.findings[0].requirement.line=0;await page.reload();await expect(page.getByText('文档检查结果格式尚未核实，未生成替代结论。')).toBeVisible()});
test('fixed document rules show distinct outcomes and exact provenance in the result',async({page},testInfo)=>{
 const s=await fixture(page);s.value.documentReview.incompleteSections=['负责人','发布范围'];
 const ruleResult={schemaVersion:'document-rule-result.v1',scope:'生产环境',documentTitle:'订单服务上线交接',rulesDigest:'d'.repeat(64),sourceDigest:'e'.repeat(64),findings:[{ruleCode:'owner',ruleName:'单一上线负责人',status:'CONFLICT',evidence:[{documentId:'handover',line:4,text:'负责人：李明'},{documentId:'handover',line:5,text:'负责人：陈玲'}]},{ruleCode:'rollback',ruleName:'上线回退步骤',status:'MISSING',evidence:[]},{ruleCode:'scope',ruleName:'明确发布范围',status:'UNKNOWN',evidence:[{documentId:'handover',line:6,text:'范围：待确认'}]},{ruleCode:'validation',ruleName:'验证记录',status:'SATISFIED',evidence:[{documentId:'handover',line:8,text:'验证记录：已附测试结果'}]}]};
 Object.assign(s.value.documentReview,{ruleResult,ruleBinding:{schema_version:'document-semantics-binding.v1',scope:'生产环境',ontology:{resource_id:'handover-rules',revision_id:'rules-r2',digest:'f'.repeat(64)}}});
 await page.goto('/tasks?work=e');const result=page.getByRole('region',{name:'文档规则核对结果'});
 await expect(result).toContainText('1 项满足 · 1 项缺失 · 1 项待确认 · 1 项冲突');
 await expect(result).toContainText('核对原文：订单服务上线交接');await expect(result.getByText('规则版本：rules-r2',{exact:true})).not.toBeVisible();
 await expect(page.getByText('文档规则核对：1 项满足 · 1 项缺失 · 1 项待确认 · 1 项冲突。已识别需要处理的问题，现有结果不足以判定整体满足要求。',{exact:true})).toBeVisible();
 await expect(page.getByText(/文档检查发现.*待补充/)).toHaveCount(0);
 await expect(result).toContainText('第 5 行：负责人：陈玲');
 await page.screenshot({path:testInfo.outputPath('four-category-result.png'),fullPage:true});
 await result.getByText('查看规则版本与原文依据',{exact:true}).click();await expect(result).toContainText('规则标识：handover-rules');await expect(result.getByText('规则版本：rules-r2',{exact:true})).toBeVisible();
 ruleResult.findings[0].status='UNVERIFIED';await page.reload();await expect(page.getByRole('alert').filter({hasText:'规则核对结果或版本依据尚未核实'})).toBeVisible();await expect(page.getByText(/文档检查发现.*待补充/)).toHaveCount(0);
 expect(s.writes).toEqual([]);
});

test('typed rule summary preserves four categories and inaccessible evidence remains unknown',async()=>{
 const {documentRuleResult,ruleCounts,reportRuleResult,ruleBusinessConclusion}=await import('../../src/problems/documentRuleSummary');
 const rule={schemaVersion:'document-rule-result.v1',scope:'生产环境',documentTitle:'交接说明',rulesDigest:'a'.repeat(64),sourceDigest:'b'.repeat(64),findings:['SATISFIED','MISSING','UNKNOWN','CONFLICT'].map((status,i)=>({ruleCode:String(i),ruleName:String(i),status,evidence:[]}))};
 const parsed=documentRuleResult(rule)!;expect(ruleCounts(parsed)).toBe('1 项满足 · 1 项缺失 · 1 项待确认 · 1 项冲突');expect(ruleBusinessConclusion(parsed)).toContain('不足以判定整体满足要求');
 expect(documentRuleResult({...rule,findings:[]})).toBeNull();expect(documentRuleResult({...rule,findings:[{...rule.findings[0],status:'UNVERIFIED'}]})).toBeNull();
 const content=JSON.stringify({schemaVersion:'document-review-output.v1',operation:'RENDER_REPORT',sourceSnapshot:ref,documentReview:{ruleResult:rule,ruleBinding:{schema_version:'document-semantics-binding.v1',scope:'生产环境',ontology:{revision_id:'r',digest:'c'.repeat(64)}}}});
 const v={preparation:{source_snapshot:ref},artifacts:[{contentAccess:'AUTHORIZED',content}]} as unknown as import('../../src/api/preparedExecution').ExecutionView;
 expect(reportRuleResult(v)).not.toBeNull();v.artifacts[0].contentAccess='RESTRICTED';expect(reportRuleResult(v)).toBeNull();v.artifacts[0].contentAccess='AUTHORIZED';v.preparation.source_snapshot={...ref,digest:'e'.repeat(64)};expect(reportRuleResult(v)).toBeNull();
});
