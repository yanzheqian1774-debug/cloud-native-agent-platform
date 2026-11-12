import {expect,test,type Page} from '@playwright/test';
const principal={principalId:'human:maintainer',tenantId:'tenant',securityDomain:'test'};
const root='/api/workbench/v1/tool-definitions';
const operation={name:'inspect_document',description:'核对交接材料',inputSchema:{type:'object'},outputSchema:null,sideEffect:'UNCONFIRMED',source:{kind:'API'},blockingIssues:['OUTPUT_SCHEMA_REQUIRED']};
async function setup(page:Page,unknown=false){
 const writes:{path:string;body:Record<string,unknown>}[]=[];let version=1,name=operation.name,command='';
 await page.route('**/api/workbench/v1/**',route=>{
  const request=route.request(),path=new URL(request.url()).pathname;
  const result=(value:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:value}});
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal,session:{},csrfToken:'test'}});
  if(path===root+'/import-access')return result({allowed:true,executionAuthorized:false});
  if(path===root+'/import-preview')return result({sourceDigest:'a'.repeat(64),operations:[operation],persisted:false,executionAuthorized:false});
  if(request.method()==='POST'&&path.startsWith(root)){
   const body=request.postDataJSON();writes.push({path,body});command=body.commandId;
   if(path.endsWith('/draft')){version++;name=body.content.name}
   if(unknown)return route.abort('connectionreset');
   return result({items:[{toolId:'tool:one',revisionId:'rev:'+version,aggregateVersion:version,changed:true}],executionAuthorized:false});
  }
  if(path===root+'/imports/'+command)return result({items:[{toolId:'tool:one',revisionId:'rev:'+version,aggregateVersion:version,changed:true}],executionAuthorized:false});
  if(path===root+'/tool%3Aone'||path===root+'/tool:one')return result({toolId:'tool:one',revisionId:'rev:'+version,draftRevisionId:'rev:'+version,publishedRevisionId:null,aggregateVersion:version,digest:'a'.repeat(64),record:{name,purpose:'核对材料',operation,validation:null,state:'DRAFT'},executionAuthorized:false});
  if(path===root)return result({items:[{toolId:'tool:one',revisionId:'rev:'+version,name,purpose:'核对材料',sourceKind:'API'}],nextCursor:null,executionAuthorized:false});
  if(path==='/api/workbench/v1/resource-directory')return result({items:[],subject:principal.principalId,scope:principal,nextCursor:null,executionAuthority:'NONE'});
  return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
 });
 return writes;
}
async function preview(page:Page){await page.goto('/tools/import');await page.getByRole('button',{name:'选择 API 描述',exact:true}).click();await page.getByLabel('或粘贴描述内容').fill('{"openapi":"3.0.0"}');await page.getByRole('button',{name:'解析并预览',exact:true}).click();await expect(page.getByRole('heading',{name:'核对导入操作'})).toBeVisible()}
test('preview survives return, save reaches exact draft and catalog finds it',async({page})=>{
 const writes=await setup(page);await preview(page);await page.getByRole('link',{name:'返回工具',exact:true}).click();await page.getByRole('link',{name:'接入 / 导入工具',exact:true}).click();await expect(page.getByRole('heading',{name:'核对导入操作'})).toBeVisible();
 await page.getByLabel('inspect_document执行影响',{exact:true}).selectOption('read-only');await page.getByRole('button',{name:'保存所选草稿',exact:true}).click();await expect.poll(()=>writes.length).toBe(1);expect(writes[0].body.effects).toEqual({inspect_document:'read-only'});await page.getByRole('link',{name:'查看保存的草稿'}).click();await expect(page.getByLabel('名称',{exact:true})).toHaveValue('inspect_document');await page.getByLabel('执行影响',{exact:true}).selectOption('creates-file');await page.getByLabel('名称',{exact:true}).fill('材料检查');await page.getByLabel('用途',{exact:true}).fill('检查缺失的回退说明');await page.reload();await expect(page.getByLabel('用途',{exact:true})).toHaveValue('检查缺失的回退说明');await expect(page.getByLabel('执行影响',{exact:true})).toHaveValue('creates-file');await expect(page.getByLabel('名称',{exact:true})).toHaveValue('材料检查');
 await page.getByRole('button',{name:'保存草稿修改'}).click();await expect(page.getByText('修改已保存，并已重新读回。',{exact:true})).toBeVisible();await page.getByRole('link',{name:'返回工具',exact:true}).click();await expect(page.getByRole('article',{name:'材料检查',exact:true})).toBeVisible();expect(writes).toHaveLength(2);await page.getByRole('link',{name:'接入 / 导入工具',exact:true}).click();await page.getByRole('button',{name:'继续导入其他工具',exact:true}).click();await expect(page.getByRole('button',{name:'选择 API 描述',exact:true})).toBeVisible();expect(writes).toHaveLength(2);
});
test('unknown import survives reload and reads receipt without another write',async({page})=>{
 const writes=await setup(page,true);await preview(page);await page.getByRole('button',{name:'保存所选草稿',exact:true}).click();await expect(page.getByRole('alert')).toContainText('保存结果尚未确认');await page.reload();await expect(page.getByRole('button',{name:'读取保存记录',exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'保存所选草稿',exact:true})).toBeDisabled();await page.getByRole('button',{name:'读取保存记录',exact:true}).click();await expect(page.getByRole('heading',{name:'草稿已保存或已复用'})).toBeVisible();expect(writes).toHaveLength(1);
});
test('expired login removes retained import material',async({page})=>{
 await setup(page);await preview(page);await page.evaluate(()=>window.dispatchEvent(new Event('workbench-session-expired')));await expect.poll(()=>page.evaluate(()=>Object.keys(sessionStorage).filter(k=>k.startsWith('f3-tool-buffer:')).length)).toBe(0);await page.goto('/tools/import');await page.getByRole('button',{name:'选择 API 描述',exact:true}).click();await expect(page.getByLabel('或粘贴描述内容')).toHaveValue('');
});
test('unknown edit recovers its exact command after reload without another save',async({page})=>{
 const writes=await setup(page,true);await page.goto('/tools/draft?'+new URLSearchParams({id:'tool:one',revision:'rev:1'}));await page.getByLabel('名称',{exact:true}).fill('已提交的新名称');await page.getByRole('button',{name:'保存草稿修改'}).click();await expect(page.getByRole('alert')).toContainText('保存结果待确认');await page.reload();await expect(page.getByRole('button',{name:'读取保存记录',exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'保存草稿修改'})).toBeDisabled();await page.getByRole('button',{name:'读取保存记录',exact:true}).click();await expect(page.getByText('修改已保存，并已重新读回。',{exact:true})).toBeVisible();await expect(page.getByLabel('名称',{exact:true})).toHaveValue('已提交的新名称');expect(writes).toHaveLength(1);
});

test('existing tools keep navigation context and continue without an import command',async({page})=>{
 const writes=await setup(page);
 await page.route('**/tool-definitions/import-preview',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{sourceDigest:'a'.repeat(64),operations:[{...operation,existing:{toolId:'tool:one',revisionId:'rev:1',aggregateVersion:1}}],persisted:false,executionAuthorized:false}}}));
 await preview(page);await expect(page.getByRole('navigation',{name:'页面位置'})).toContainText('资源管理');await expect(page.getByRole('navigation',{name:'页面位置'})).toContainText('导入');await expect(page.locator('.px-business-nav a[href="/tools"]')).toHaveAttribute('aria-current','page');await expect(page.locator('.px-business-nav a[href="/tools"]')).toBeVisible();
 await expect(page.getByRole('button',{name:'保存所选草稿',exact:true})).toHaveCount(0);await expect(page.getByLabel('inspect_document执行影响',{exact:true})).toHaveCount(0);await page.getByRole('link',{name:'查看已有工具',exact:true}).click();await expect(page.getByLabel('名称',{exact:true})).toHaveValue('inspect_document');await expect(page.getByRole('navigation',{name:'页面位置'})).toContainText('草稿');expect(writes).toEqual([]);
});
test('plugin package preview lists inspected files without implying runtime validation',async({page})=>{
 const writes=await setup(page);
 await page.route('**/tool-definitions/import-preview',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{sourceDigest:'a'.repeat(64),files:[{path:'manifest.json',bytes:80,digest:'a'.repeat(64)},{path:'main.py',bytes:20,digest:'b'.repeat(64)}],operations:[{...operation,source:{kind:'PLUGIN'},blockingIssues:['PLUGIN_RUNTIME_VALIDATION_REQUIRED']}],persisted:false,executionAuthorized:false}}}));
 await page.goto('/tools/import');await page.getByRole('button',{name:'选择插件包',exact:true}).click();await page.getByLabel('接入方式',{exact:true}).selectOption('PLUGIN_ZIP');await page.getByLabel('选择文件',{exact:true}).setInputFiles({name:'fixture.zip',mimeType:'application/zip',buffer:Buffer.from('controlled preview fixture')});await page.getByRole('button',{name:'解析并预览',exact:true}).click();await expect(page.getByRole('region',{name:'插件包文件预览'})).toContainText('manifest.json');await expect(page.getByRole('region',{name:'插件包文件预览'})).toContainText('运行环境验证仍待完成');expect(writes).toEqual([]);
});
