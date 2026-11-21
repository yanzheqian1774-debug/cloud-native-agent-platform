import {expect,test} from '@playwright/test';
import {openResourceSection} from '../helpers/resourceDetailNavigation';
for(const outcome of ['SUCCEEDED','UNKNOWN'])test(`published MCP tools call ${outcome} preserves original request across refresh`,async({page})=>{
 const principal={principalId:'human:test',tenantId:'test',securityDomain:'isolated'};
 const ref={resource_id:'mcp:test',revision_id:'published:1',digest:'a'.repeat(64)};
 const option={bindingDigest:'b'.repeat(64),publishedReference:ref,toolName:'verify_project_sales_source',input:{sourceDigest:'c'.repeat(64)}};
 const resource={resourceId:ref.resource_id,kind:'mcp',name:'普通只读来源工具',aggregateVersion:4,lifecycleState:'PUBLISHED',enabled:true,archived:false,currentDraftRevisionId:null,publishedRevisionId:ref.revision_id,revisions:[{revisionId:ref.revision_id,digest:ref.digest,state:'PUBLISHED',content:{description:'只读合成资料',endpoint:'http://127.0.0.1:19761/mcp',capabilities:[option.toolName],sideEffect:'READ'}}],testResults:[],savedTests:[],reviews:[],relationships:[],bindings:[],invocations:[],discoverySnapshots:[],toolSelections:[],healthObservations:[],driftRecords:[],limitations:[]};
 let saved:Record<string,unknown>|null=null,prepare=0,dispatch=0;
 await page.route('**/api/workbench/v1/**',async route=>{const q=route.request(),p=new URL(q.url()).pathname;
  if(p.endsWith('/session'))return route.fulfill({json:{principal,csrfToken:'fixture'}});
  if(p.endsWith('/resource-management/mcp'))return route.fulfill({json:{result:{items:[resource],subject:principal.principalId,scope:{tenantId:principal.tenantId,securityDomain:principal.securityDomain}}}});
  if(p.includes('/tool-tests')){
   if(q.method()==='POST'&&p.endsWith('/tool-tests')){prepare++;const body=q.postDataJSON();expect(body.bindingDigest).toBe(option.bindingDigest);saved={commandKey:body.commandKey,bindingDigest:option.bindingDigest,publishedReference:ref,state:'PREPARED',result:null,retryPermitted:false};return route.fulfill({json:{result:saved}})}
   if(q.method()==='POST'&&p.endsWith('/dispatch')){dispatch++;expect(saved).not.toBeNull();saved={...saved,state:outcome,result:{state:outcome}};return route.fulfill({json:{result:saved}})}
   if(p.endsWith('/tool-tests'))return route.fulfill({json:{result:{options:[option],history:saved?[saved]:[],publishedOnly:true,automaticRetry:false}}});
   return route.fulfill({json:{result:saved}});
  }
  if(p.endsWith('/resource-directory'))return route.fulfill({json:{result:{items:[],nextCursor:null,subject:principal.principalId,scope:{tenantId:principal.tenantId,securityDomain:principal.securityDomain}}}});
  return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
 });
 await page.goto('/mcp?managedResource='+encodeURIComponent(ref.resource_id));await openResourceSection(page,'测试');
 const panel=page.getByRole('region',{name:'已发布 MCP 工具测试'});await expect(panel.getByText('工具测试（已发布版本）')).toBeVisible();
 await panel.getByRole('button',{name:'运行一次工具测试'}).click();await expect(panel.getByText(outcome==='SUCCEEDED'?'工具调用已完成':'调用结果待核对，不会自动重发',{exact:true})).toBeVisible();expect(prepare).toBe(1);expect(dispatch).toBe(1);
 await page.reload();await openResourceSection(page,'测试');await expect(panel.getByText(outcome==='SUCCEEDED'?'工具调用已完成':'调用结果待核对，不会自动重发',{exact:true})).toBeVisible();
 await panel.getByRole('button',{name:'核对测试状态',exact:true}).click();expect(prepare).toBe(1);expect(dispatch).toBe(1);
 if(outcome==='UNKNOWN')await expect(panel.getByRole('button',{name:'运行一次工具测试'})).toBeDisabled();
 await page.screenshot({path:`test-results/mcp-published-${outcome}.png`,fullPage:true});
});
