import {expect,test,type Page} from '@playwright/test';
const root='/api/workbench/v1/tool-definitions',principal={principalId:'human:maintainer',tenantId:'tenant',securityDomain:'test'};
async function setup(page:Page,mode:'normal'|'unknown'|'readback'='normal'){
 const employeeWrites:Record<string,unknown>[]=[],writes:Record<string,unknown>[]=[],receipts=new Map<string,Record<string,unknown>>();let published=false,version=1,readable=mode!=='readback',readAttempts=0;
 const tool=()=>({toolId:'tool:one',revisionId:'rev:1',digest:'a'.repeat(64),aggregateVersion:version,draftRevisionId:published?null:'rev:1',publishedRevisionId:published?'rev:1':null,record:{name:'合成工具',purpose:'只核契约，不请求外部服务',state:'DRAFT',validation:null,operation:{name:'inspect',description:'contract',inputSchema:{type:'object'},outputSchema:{type:'object'},sideEffect:'read-only',source:{kind:'PLUGIN'},blockingIssues:[]}},executionAuthorized:false});
 await page.route('**/api/workbench/v1/**',route=>{
  const req=route.request(),url=new URL(req.url()),path=decodeURIComponent(url.pathname),result=(body:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:body}});
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal,session:{},csrfToken:'synthetic'}});
  if(path===root+'/candidates')return result({items:published?[tool()]:[],complete:true,executionAuthorized:false});
  if(path==='/api/workbench/v1/employees'&&req.method()==='POST'){employeeWrites.push(req.postDataJSON());return route.fulfill({status:500,json:{reasonCode:'UNEXPECTED_EMPLOYEE_WRITE'}})}
  if(path==='/api/workbench/v1/employees'||path==='/api/workbench/v1/agents')return result({items:[],nextCursor:null});
  if(path==='/api/workbench/v1/employees/capabilities')return result({status:'AVAILABLE',subjectId:principal.principalId,tenantId:principal.tenantId,securityDomain:principal.securityDomain,generation:1,recoveryEpoch:1,readAt:new Date().toISOString(),target:null,actions:{CREATE:{authorized:true,lifecycleEligible:true}},authorityGranted:false,executionStarted:false});
  if(path===root+'/tool:one/history')return result({revisions:[tool()],commands:[...receipts.values()],validations:[...receipts.values()].filter(r=>r.commandKind==='VALIDATE').flatMap(r=>r.items as {revisionId:string;digest:string}[]),references:[],impactComplete:false,automaticMigration:false,executionAuthorized:false});
  if(path===root+'/tool:one/commands'){
   const body=req.postDataJSON();writes.push(body);if(body.action==='publish'){published=true;version++}
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
test('exact validation/publication keeps fixed tuple and offers Tool candidate',async({page})=>{
 const state=await setup(page);await open(page);await expect(page.getByRole('button',{name:'发布已校验版本',exact:true})).toBeDisabled();await page.getByRole('button',{name:'验证当前草稿',exact:true}).click();await expect.poll(()=>state.writes.length).toBe(1);await expect(page.getByRole('button',{name:'发布已校验版本',exact:true})).toBeEnabled();await page.getByRole('button',{name:'发布已校验版本',exact:true}).click();await expect(page.getByRole('link',{name:'加入数字人候选',exact:true})).toHaveAttribute('href',/^\/employees\?mode=create&toolCandidate=tool%3Aone.*toolRevision=rev%3A1.*toolDigest=a{64}$/);await expect(page.getByRole('button',{name:'编辑 / 创建新版本',exact:true})).toBeVisible();expect(state.writes.map(x=>x.action)).toEqual(['validate','publish']);
});
test('unknown lifecycle command survives refresh and only reads original receipt',async({page})=>{
 const state=await setup(page,'unknown');await open(page);await page.getByRole('button',{name:'验证当前草稿',exact:true}).click();await expect.poll(()=>state.writes.length).toBe(1);await expect(page.getByText('操作尚未确认，请保留并读取原记录。',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'读取原操作结果',exact:true})).toBeVisible();await page.reload();await expect(page.getByRole('button',{name:'读取原操作结果',exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'验证当前草稿',exact:true})).toBeDisabled();await expect(page.getByRole('button',{name:'保存草稿修改',exact:true})).toBeDisabled();await page.getByRole('button',{name:'读取原操作结果',exact:true}).click();await expect(page.getByRole('button',{name:'读取原操作结果',exact:true})).toHaveCount(0);expect(state.writes).toHaveLength(1);
});
test('successful POST followed by failed readback retains original command',async({page})=>{
 const state=await setup(page,'readback');await open(page);await page.getByRole('button',{name:'验证当前草稿',exact:true}).click();await expect(page.getByRole('button',{name:'读取原操作结果',exact:true})).toBeVisible();await expect.poll(()=>state.readAttempts()).toBe(1);state.setReadable();await page.getByRole('button',{name:'读取原操作结果',exact:true}).click();await expect(page.getByRole('button',{name:'读取原操作结果',exact:true})).toHaveCount(0);expect(state.writes).toHaveLength(1);
});
test('test UI displays actual null rather than invented expected output',async({page},testInfo)=>{
 const state=await setup(page);await open(page);await page.getByRole('button',{name:'契约测试与调用记录',exact:true}).click();await page.getByRole('textbox',{name:'预期输出',exact:true}).fill('{"invented":true}');await page.getByRole('button',{name:'测试当前准确版本',exact:true}).click();await expect(page.getByRole('heading',{name:'合成契约检查 · 未执行'})).toBeVisible();await expect(page.getByText('执行器未运行，未生成实际输出。',{exact:true})).toBeVisible();await expect(page.locator('article pre').first()).toContainText('"actual": null');expect(state.writes).toHaveLength(1);await page.setViewportSize({width:390,height:844});await page.screenshot({path:testInfo.outputPath('tool-lifecycle-390.png'),fullPage:true});
});

test('unsaved form changes cannot validate or test stored revision',async({page},testInfo)=>{
 const state=await setup(page);await open(page);await page.getByLabel('名称',{exact:true}).fill('未保存的修改');await expect(page.getByRole('button',{name:'验证当前草稿',exact:true})).toBeDisabled();await page.getByRole('button',{name:'契约测试与调用记录',exact:true}).click();await expect(page.getByRole('button',{name:'测试当前准确版本',exact:true})).toBeDisabled();expect(state.writes).toEqual([]);await page.screenshot({path:testInfo.outputPath('tool-lifecycle-desktop.png'),fullPage:true});
});


test('candidate link enters real employees creation and rereads exact Tool tuple',async({page})=>{
 const state=await setup(page);await open(page);
 await page.getByRole('button',{name:'验证当前草稿',exact:true}).click();
 await page.getByRole('button',{name:'发布已校验版本',exact:true}).click();
 await page.getByRole('link',{name:'加入数字人候选',exact:true}).click();
 await expect(page).toHaveURL(/\/employees\?mode=create&toolCandidate=tool%3Aone&toolRevision=rev%3A1&toolDigest=a{64}$/);
 await expect(page.getByRole('heading',{name:'创建数字员工定义',exact:true})).toBeVisible();
 const candidate=page.getByRole('checkbox',{name:/^合成工具 · 本次工具候选\s*已发布 · rev:1$/});
 await expect(candidate).toBeEnabled();await expect(candidate).not.toBeChecked();
 await candidate.check();await expect(candidate).toBeChecked();
 const preview=page.getByRole('complementary',{name:'装配预览'});
 await preview.getByText('查看所选资源版本依据',{exact:true}).click();
 await expect(preview).toContainText('tool:one / rev:1');
 await expect(preview).toContainText('摘要：'+'a'.repeat(64));
 expect(state.employeeWrites).toEqual([]);
 expect(state.writes.map(x=>x.action)).toEqual(['validate','publish']);
});
