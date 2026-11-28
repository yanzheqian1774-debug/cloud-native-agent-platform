import {expect,test,type Page} from '@playwright/test';
const root='/api/workbench/v1/tool-definitions',principal={principalId:'human:maintainer',tenantId:'tenant',securityDomain:'test'};
async function setup(page:Page,mode:'normal'|'unknown'|'readback'='normal'){
 const employeeWrites:Record<string,unknown>[]=[],writes:Record<string,unknown>[]=[],receipts=new Map<string,Record<string,unknown>>();let published=false,validated=false,version=1,readable=mode!=='readback',readAttempts=0;
 const tool=()=>({sourceValidation:validated?{blockingIssues:[],resolvedIssues:['PLUGIN_RUNTIME_VALIDATION_REQUIRED'],sourceExecutionVerified:true,runtimeEvidence:{sourceDigest:'b'.repeat(64),entrypointDigest:'c'.repeat(64),runtime:'reviewed-python-function.v1',runtimeRevision:'registered-1',commandKey:'source-test:1'},executionAuthorized:false,currentAuthorizationChecked:false}:null,effectiveBlockingIssues:validated?[]:['PLUGIN_RUNTIME_VALIDATION_REQUIRED'],toolId:'tool:one',revisionId:'rev:1',digest:'a'.repeat(64),aggregateVersion:version,draftRevisionId:published?null:'rev:1',publishedRevisionId:published?'rev:1':null,record:{name:'合成工具',purpose:'只核契约，不请求外部服务',state:'DRAFT',validation:null,operation:{name:'inspect',description:'contract',inputSchema:{type:'object'},outputSchema:{type:'object'},sideEffect:'read-only',source:{kind:'PLUGIN'},blockingIssues:['PLUGIN_RUNTIME_VALIDATION_REQUIRED']}},executionAuthorized:false});
 await page.route('**/api/workbench/v1/**',route=>{
  const req=route.request(),url=new URL(req.url()),path=decodeURIComponent(url.pathname),result=(body:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:body}});
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal,session:{},csrfToken:'synthetic'}});
  if(path===root+'/candidates')return result({items:published?[tool()]:[],complete:true,executionAuthorized:false});
  if(path==='/api/workbench/v1/employees'&&req.method()==='POST'){employeeWrites.push(req.postDataJSON());return route.fulfill({status:500,json:{reasonCode:'UNEXPECTED_EMPLOYEE_WRITE'}})}
  if(path==='/api/workbench/v1/employees'||path==='/api/workbench/v1/agents')return result({items:[],nextCursor:null});
  if(path==='/api/workbench/v1/employees/capabilities')return result({status:'AVAILABLE',subjectId:principal.principalId,tenantId:principal.tenantId,securityDomain:principal.securityDomain,generation:1,recoveryEpoch:1,readAt:new Date().toISOString(),target:null,actions:{CREATE:{authorized:true,lifecycleEligible:true}},authorityGranted:false,executionStarted:false});
  if(path===root+'/tool:one/history')return result({revisions:[tool()],commands:[...receipts.values()],validations:[...receipts.values()].filter(r=>r.commandKind==='VALIDATE').flatMap(r=>r.items as {revisionId:string;digest:string}[]),references:[],impactComplete:false,automaticMigration:false,executionAuthorized:false});
  if(path===root+'/tool:one/commands'){
   const body=req.postDataJSON();writes.push(body);if(body.action==='validate')validated=true;if(body.action==='publish'){published=true;version++}
   const receipt={commandKind:body.action.toUpperCase(),items:[{toolId:'tool:one',revisionId:'rev:1',digest:'a'.repeat(64),aggregateVersion:version,changed:body.action==='publish'}],...(body.action==='test'?{testCase:{name:body.testName,input:body.input,expected:body.expectedOutput},testResult:{status:'NOT_EXECUTED',actual:null,actualExecution:false,reasonCode:'TOOL_EXECUTOR_NOT_CONFIGURED',revisionId:'rev:1',revisionDigest:'a'.repeat(64)}}:{}),executionAuthorized:false};
   receipts.set(body.commandId,receipt);if(mode==='unknown')return route.abort('connectionreset');return result(receipt);
  }
  if(path.startsWith(root+'/imports/')){readAttempts++;if(!readable)return route.fulfill({status:503,json:{reasonCode:'READBACK_UNAVAILABLE'}});const saved=receipts.get(path.slice((root+'/imports/').length));return saved?result(saved):route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}})}
  if(path===root+'/tool:one')return result(tool());
  return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
 });
 return {writes,employeeWrites,readAttempts:()=>readAttempts,setReadable:()=>{readable=true}};
}
const open=(page:Page)=>page.goto('/tools/draft?'+new URLSearchParams({id:'tool:one',revision:'rev:1'}));
test('exact source runtime evidence resolves derived readiness and retains original import fact',async({page},testInfo)=>{
 const state=await setup(page);await open(page);
 await expect(page.getByRole('button',{name:'发布已校验版本',exact:true})).toBeDisabled();
 await page.getByRole('button',{name:'验证当前草稿',exact:true}).click();
 await expect(page.getByText('仅证明曾有准确源码执行与输入输出契约依据；不代表当前可用、最新验证通过或全部测试通过。',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'发布已校验版本',exact:true})).toBeEnabled();
 await page.getByRole('button',{name:'发布已校验版本',exact:true}).click();
 await expect(page.getByRole('link',{name:'加入数字人候选',exact:true})).toHaveAttribute('href',/^\/employees\?mode=create&toolCandidate=tool%3Aone.*toolRevision=rev%3A1.*toolDigest=a{64}$/);
 await page.getByText('来源与待适配内容',{exact:true}).click();
 const details=page.locator('details').filter({hasText:'来源与待适配内容'});
 await expect(details).toContainText('"effectiveIssues": []');
 await expect(details).toContainText('"originalImportIssues": [');
 await expect(details).toContainText('PLUGIN_RUNTIME_VALIDATION_REQUIRED');
 await expect(page.getByText('正在查看历史版本，不能直接覆盖当前草稿。',{exact:true})).toHaveCount(0);
 expect(state.writes.map(x=>x.action)).toEqual(['validate','publish']);
 await page.evaluate(()=>{window.scrollTo(0,0);document.querySelectorAll('*').forEach(el=>{if(el instanceof HTMLElement&&el.scrollHeight>el.clientHeight)el.scrollTop=0})});
 await page.screenshot({path:testInfo.outputPath('source-validation-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.evaluate(()=>{window.scrollTo(0,0);document.querySelectorAll('*').forEach(el=>{if(el instanceof HTMLElement&&el.scrollHeight>el.clientHeight)el.scrollTop=0})});
 await page.screenshot({path:testInfo.outputPath('source-validation-390.png'),fullPage:true});
});

for(const status of ['UNKNOWN','FAILED'] as const)test('historical runtime basis does not label latest source failure current '+status,async({page})=>{
 await setup(page);
 const attempt={commandKey:'old-source',revisionId:'rev:1',digest:'a'.repeat(64),sourceDigest:'b'.repeat(64),startedAt:'2026-11-28T01:00:00Z',recordedAt:'2026-11-28T01:01:00Z',status:'FAILED',reasonCode:'TOOL_SOURCE_EXPECTATION_MISMATCH',runtime:'reviewed-python-function.v1',runtimeRevision:'registered-1',expectationMismatch:true};
 await page.route('**/api/workbench/v1/tool-definitions/tool%3Aone?*',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{toolId:'tool:one',revisionId:'rev:1',digest:'a'.repeat(64),aggregateVersion:1,draftRevisionId:'rev:1',publishedRevisionId:null,executionAuthorized:false,sourceValidation:{sourceExecutionVerified:true,runtimeEvidence:{commandKey:'old-source'},executionAuthorized:false,currentAuthorizationChecked:false},sourceRuntimeReadback:{basis:attempt,latest:{...attempt,commandKey:'latest-source',status,reasonCode:status==='UNKNOWN'?null:'TOOL_SOURCE_OUTPUT_INVALID',recordedAt:status==='UNKNOWN'?null:'2026-11-28T02:01:00Z',expectationMismatch:false},currentAvailability:'NOT_ESTABLISHED',allTestsPassed:'NOT_ESTABLISHED',executionAuthorized:false},record:{name:'合成工具',purpose:'只核展示',state:'DRAFT',validation:null,operation:{name:'inspect',inputSchema:{type:'object'},outputSchema:{type:'object'},sideEffect:'read-only',source:{kind:'PLUGIN'},blockingIssues:['PLUGIN_RUNTIME_VALIDATION_REQUIRED']}}}}}));
 await open(page);
 const basis=page.getByRole('region',{name:'历史可执行依据'}),latest=page.getByRole('region',{name:'最近一次源码尝试'});
 await expect(basis).toContainText('不代表当前可用、最新验证通过或全部测试通过');
 await expect(basis).toContainText('已运行；输入输出契约有效；预期不符');
 await expect(latest).toContainText(status==='UNKNOWN'?'结果未确认':'已记录输出无效');
 await expect(latest).toContainText('不能据此判断当前可用');
 await latest.getByText('查看本条版本与运行记录').click();await expect(latest).toContainText(status);
 await expect(page.getByRole('button',{name:'发布已校验版本'})).toBeDisabled();
});
