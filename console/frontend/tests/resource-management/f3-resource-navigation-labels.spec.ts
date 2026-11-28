import {expect,test,type Page} from '@playwright/test';

async function fixture(page:Page){
 const principal={principalId:'human:reader',tenantId:'tenant',securityDomain:'test'},writes:string[]=[];
 await page.route('**/api/**',route=>{
  const request=route.request(),path=new URL(request.url()).pathname;
  if(request.method()!=='GET'){writes.push(path);return route.fulfill({status:405,json:{reasonCode:'READ_ONLY_PREVIEW'}})}
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal,session:{},csrfToken:'fixture'}});
  if(path==='/api/workbench/v1/business-ontologies')return route.fulfill({json:{result:{items:[]}}});
  if(path.includes('/ontology-maintenance/capabilities/'))return route.fulfill({json:{result:{schemaVersion:'ontology-maintenance-capabilities.v1',allowedActions:[],creationAvailable:false}}});
  if(path.startsWith('/api/internal/'))return route.fulfill({json:[]});
  return route.fulfill({json:{result:{items:[],count:0,subject:principal.principalId,scope:principal,nextCursor:null}}});
 });
 return {principal,writes};
}

test('five F3 resource links reach real ontology view; Workflow stays in technical navigation',async({page},testInfo)=>{
 const {writes}=await fixture(page);await page.setViewportSize({width:1440,height:900});await page.goto('/skills');
 const nav=page.getByRole('navigation',{name:'P1 核心产品导航',exact:true}),resources=nav.locator('[data-navigation-group="resources"]');
 await expect(resources.locator('a')).toHaveText(['技能','MCP 服务','本体','知识','工具']);
 await expect(resources.getByRole('link',{name:'工作流',exact:true})).toHaveCount(0);
 await resources.getByRole('link',{name:'本体',exact:true}).click();await expect(page).toHaveURL(/\/ontology$/);
 await expect(page.getByRole('heading',{name:'业务本体',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'保存草稿',exact:true})).toHaveCount(0);
 await page.screenshot({path:testInfo.outputPath('candidate-ontology-navigation.png')});
 const advanced=nav.locator('[data-navigation-group="advanced"]');if(!await advanced.getAttribute('open'))await advanced.locator('summary').click();
 await expect(advanced.getByRole('link',{name:'工作流',exact:true})).toHaveAttribute('href','/workflow-definitions');
 await advanced.getByRole('link',{name:'工作流',exact:true}).click();await expect(page).toHaveURL(/\/workflow-definitions$/);
 await expect(advanced.getByRole('link',{name:'工作流',exact:true})).toHaveAttribute('aria-current','page');
 await page.goto('/workflow-definitions?resourceId=retained-workflow&viewRevision=retained-revision');
 expect(new URL(page.url()).pathname).toBe('/workflow-definitions');expect(new URL(page.url()).searchParams.get('viewRevision')).toBe('retained-revision');expect(writes).toEqual([]);
});

test('basis translates only four known operation labels and retains raw technical codes',async({page},testInfo)=>{
 const {principal,writes}=await fixture(page),codes=['READ_DATA','VALIDATE_DATA','ANALYZE_DATA','RENDER_REPORT','CUSTOM_LOOKUP'];
 const item={kind:'skill',identity:'skill:labels',revisionId:'revision:fixed',digest:'a'.repeat(64),name:'合成技能 · 业务标签核对',state:'PUBLISHED',enabled:false,isCurrentPublished:true,isCurrentDraft:false,executionReady:false,policyReviewed:true,createdAt:null};
 const basis={schemaVersion:'resource-version-basis.v1',revisionId:item.revisionId,revisionDigest:item.digest,executionAuthority:'NONE',businessAcceptance:'NOT_ESTABLISHED',tests:{scope:'ISOLATED_SYNTHETIC_ONLY_NOT_BUSINESS_ACCEPTANCE',ready:true,operations:codes.map(operation=>({operation,passed:true,caseCount:1}))},publication:{recorded:true,publishedAt:'2026-11-27T12:01:00Z',basisType:'POLICY'}};
 await page.route('**/api/workbench/v1/resource-directory**',route=>{
  const path=new URL(route.request().url()).pathname;
  if(path==='/api/workbench/v1/resource-directory')return route.fulfill({json:{result:{items:[item],subject:principal.principalId,scope:principal,nextCursor:null,executionAuthority:'NONE'}}});
  return route.fulfill({json:{result:{kind:item.kind,identity:item.identity,name:item.name,subject:principal.principalId,scope:principal,revision:{revisionId:item.revisionId,digest:item.digest,state:'PUBLISHED',content:{description:'仅合成预览，不代表已安装验收',capabilities:[],operations:codes.map(name=>({name,inputSchema:{type:'object'},outputSchema:{type:'object'}}))}},versionBasis:basis,usage:[]}}});
 });
 await page.setViewportSize({width:1440,height:900});await page.goto('/skills?'+new URLSearchParams({selected:item.identity,resourceRevision:item.revisionId,resourceDigest:item.digest,resourceSection:'content'}));
 for(const label of ['读取资料','核对资料','分析变化','形成报告','CUSTOM_LOOKUP'])await expect(page.getByText(label+'：1 项通过',{exact:true})).toBeVisible();
 for(const code of codes.slice(0,4))await expect(page.getByText(code+'：1 项通过',{exact:true})).toHaveCount(0);
 const disclosure=page.locator('details').filter({has:page.locator('summary').getByText('查看操作代码',{exact:true})});await disclosure.locator('summary').click();
 await expect(disclosure.locator('code')).toHaveText(codes);
 await page.getByText('本版本合成契约测试通过。',{exact:true}).scrollIntoViewIfNeeded();
 await page.screenshot({path:testInfo.outputPath('candidate-operation-labels.png')});expect(writes).toEqual([]);
});
