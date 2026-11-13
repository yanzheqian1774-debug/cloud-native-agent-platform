import { test, expect } from '@playwright/test';
const documentContent = {schema_version:'business-document-rules.v1',name:'访谈交接规则',business_owner:'业务负责人',data_owner:'资料负责人',synthetic:true,scope:'访谈交接',mappings:[{code:'source'}],actions:[{operation:'ANALYZE_DATA'}],rules:[{code:'owner',name:'交接负责人',kind:'SINGLE_VALUE_FIELD',section:'交接信息',field:'负责人'}]};
const salesContent = {schema_version:'business-ontology.v1',name:'销售口径',business_owner:'业务负责人',data_owner:'资料负责人',rules:{included_kinds:['SALE','RETURN']},metrics:[{code:'net',name:'净销售额'}],objects:[{code:'sale'}],mappings:[{code:'source'}]};
for (const kind of ['document','sales'] as const) {
 test(`${kind} definition displays its own rules and preserves sales navigation boundary`,async({page},testInfo)=>{
  const writes:string[]=[];
  const content=kind==='document'?documentContent:salesContent;
  await page.route('**/api/**',route=>{
   const path=new URL(route.request().url()).pathname;
   if(route.request().method()==='POST') writes.push(path);
   if(path.endsWith('/session')) return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:test',tenantId:'test',securityDomain:'isolated'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'csrf'}});
   if(path.includes('/ontology-maintenance/capabilities/'))return route.fulfill({json:{result:{schemaVersion:'ontology-maintenance-capabilities.v1',allowedActions:['CREATE','REVISE','VALIDATE','TEST','REVIEW','PUBLISH','DEPRECATE']}}});
   if(path.endsWith('/business-ontologies')) return route.fulfill({json:{result:{items:[{ontology_id:kind,revision_id:'r1',name:content.name,digest:'a'.repeat(64),version:5}]}}});
   if(path.includes('/business-ontologies/')) return route.fulfill({json:{result:{ontology_id:kind,revision_id:'r1',version:5,digest:'a'.repeat(64),content,state:'PUBLISH',facts:kind==='document'?[{action:'TEST',actor:'fixture',result:{checks:[{schemaVersion:'document-rule-result.v1',documentTitle:'客户访谈纪要',rulesDigest:'b'.repeat(64),sourceDigest:'c'.repeat(64),findings:[{ruleCode:'owner',ruleName:'交接负责人',status:'UNKNOWN',evidence:[{documentId:'interview',line:3,text:'负责人：待确认'}]},{ruleCode:'scope',ruleName:'访谈范围',status:'SATISFIED',evidence:[{documentId:'interview',line:4,text:'范围：试用用户'}]},{ruleCode:'rollback',ruleName:'回退说明',status:'MISSING',evidence:[]},{ruleCode:'reviewer',ruleName:'接收人一致',status:'CONFLICT',evidence:[{documentId:'interview',line:5,text:'接收人：李明'},{documentId:'interview',line:6,text:'接收人：陈玲'}]}]}]}}]:[]}}});
   return route.fulfill({json:{result:{items:[],entries:[]}}});
  });
  await page.goto('/ontology');await page.getByRole('button',{name:new RegExp(content.name)}).click();await page.getByRole('button',{name:'规则与来源',exact:true}).click();
  if(kind==='document') {
   await expect(page.getByRole('region',{name:'文档核对规则',exact:true})).toContainText('访谈交接');
   await expect(page.getByRole('region',{name:'文档规则验证结果'})).toContainText('交接负责人 · 待确认');
   await expect(page.getByRole('region',{name:'文档规则验证结果'})).toContainText('第 3 行：负责人：待确认');
   await expect(page.getByRole('checkbox',{name:'销售金额冲减退货'})).toHaveCount(0);
   await expect(page.getByRole('link',{name:'使用此版本进行销售诊断 →'})).toHaveCount(0);
   await expect(page.getByRole('button',{name:'修改定义',exact:true})).toBeVisible();
   await expect(page.getByRole('button',{name:'独立审核',exact:true})).toHaveCount(0);
   await expect(page.getByRole('region',{name:'文档规则验证结果'})).toContainText('1 项满足 · 1 项缺失 · 1 项待确认 · 1 项冲突');
   await page.getByRole('button',{name:'修改定义',exact:true}).click();await page.getByText('已有规则字段',{exact:true}).click();
   await page.getByLabel('核对章节 · 交接负责人').fill('接收信息');
   await expect(page.getByText('正在编辑后继草稿，已保存修订保持不变。')).toBeVisible();
   await expect(page.getByRole('button',{name:'运行样本',exact:true})).toHaveCount(0);
   await expect(page.getByRole('region',{name:'文档规则验证结果'})).toContainText('规则版本：r1');
   await page.getByRole('button',{name:'放弃未保存编辑'}).click();
   await expect(page.getByLabel('核对章节 · 交接负责人')).toHaveValue('交接信息');
  } else {
   await expect(page.getByRole('checkbox',{name:'销售金额冲减退货'})).toBeChecked();
   await expect(page.getByRole('link',{name:'使用此版本进行销售诊断 →'})).toBeVisible();
   await expect(page.getByRole('region',{name:'文档核对规则',exact:true})).toHaveCount(0);
  }
  expect(writes).toEqual([]);
  await page.screenshot({path:testInfo.outputPath(`${kind}-rules.png`),fullPage:true});
  if (kind === "document") {
   await page.getByRole("region",{name:"文档规则验证结果"}).scrollIntoViewIfNeeded();
   await page.screenshot({path:testInfo.outputPath("document-evidence.png"),fullPage:true});
  }
 });
}
