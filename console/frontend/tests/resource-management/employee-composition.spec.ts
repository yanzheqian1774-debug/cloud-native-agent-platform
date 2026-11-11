import {expect,test} from '@playwright/test';
test('compose all exact resource groups without offering drafts',async({page})=>{
 const principal={principalId:'human:composition',tenantId:'composition',securityDomain:'isolated'},digest='a'.repeat(64);let submitted:Record<string,unknown>|undefined;
 await page.route('**/api/workbench/v1/**',async r=>{const u=new URL(r.request().url()),p=u.pathname;
 if(p.endsWith('/session'))return r.fulfill({json:{schemaVersion:'workbench-session.v1',principal,csrfToken:'fixture'}});
 if(p.endsWith('/agents'))return r.fulfill({status:404,json:{reasonCode:'NOT_AVAILABLE'}});
 if(p.endsWith('/resource-directory')){const kind=u.searchParams.get('kind');return r.fulfill({json:{result:{subject:principal.principalId,scope:{tenantId:principal.tenantId,securityDomain:principal.securityDomain},nextCursor:null,items:[{kind,identity:kind+':one',revisionId:kind+':rev',digest,name:kind+'已发布资源',enabled:true,isCurrentPublished:true},{kind,identity:kind+':draft',revisionId:'draft',digest,name:'不可选草稿',enabled:true,isCurrentPublished:false}]}}})}
 if(p.endsWith('/employees')&&r.request().method()==='POST'){submitted=r.request().postDataJSON();return r.fulfill({status:503,json:{reasonCode:'RESULT_UNKNOWN'}})}if(p.endsWith('/employees'))return r.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:[]}}});return r.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}})});
 await page.goto('/digital-employees?mode=create');await page.getByLabel('职责角色',{exact:true}).fill('诊断员工');await page.getByLabel('职责清单（每行一项，1–32 项）').fill('核对来源');await page.getByText('高级设置 · 自动生成的技术身份',{exact:true}).click();await page.getByLabel('Employee Definition ID',{exact:true}).fill('employee:complete');await page.getByLabel('Revision ID',{exact:true}).fill('employee:rev');await page.getByRole('radio').check();
 for(const [kind,label]of [['skill','技能'],['mcp','MCP连接'],['knowledge','知识与数据'],['workflow','工作流'],['runtime','运行配置']]){await page.getByRole('group',{name:'资源分类'}).getByRole('button',{name:new RegExp('^'+label)}).click();await page.getByRole('checkbox',{name:kind+'已发布资源'}).check()}
 await expect(page.getByText('已组合 5 项业务资源',{exact:true})).toBeVisible();await expect(page.getByText('不可选草稿',{exact:true})).toHaveCount(0);await page.getByRole('button',{name:'检查并进入确认',exact:true}).click();await expect(page.getByText('组合成员：6 项',{exact:true})).toBeVisible();await expect(page.getByRole('group',{name:'资源分类'}).getByRole('button').first()).toBeDisabled();await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();await page.getByRole('button',{name:'确认创建',exact:true}).click();await expect.poll(()=>submitted?.members).toHaveLength(6);expect((submitted!.members as {kind:string}[]).map(x=>x.kind)).toEqual(['AGENT','SKILL','MCP','KNOWLEDGE','WORKFLOW','RUNTIME_PROFILE']);
});

for(const mode of ['same-user','changed-user','changed-category'])test('resource pagination preserves correct context '+mode,async({page})=>{
 let actor='human:composition',release:()=>void=()=>{};const pending=new Promise<void>(resolve=>{release=resolve});
 const item=(kind:string,id:string)=>({kind,identity:kind+':'+id,revisionId:id+':rev',digest:'a'.repeat(64),name:kind+'候选'+id,enabled:true,isCurrentPublished:true});
 await page.route('**/api/workbench/v1/**',async route=>{
  const url=new URL(route.request().url()),path=url.pathname;
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:actor,tenantId:'composition',securityDomain:'isolated'},csrfToken:'fixture'}});
  if(path.endsWith('/resource-directory')){
   const kind=url.searchParams.get('kind')!,more=!!url.searchParams.get('cursor');
   if(more&&mode==='changed-category')await pending;
   if(more&&mode==='changed-user')actor='human:other';
   return route.fulfill({json:{result:{subject:actor,scope:{tenantId:'composition',securityDomain:'isolated'},items:more?[item(kind,'one'),item(kind,'two')]:[item(kind,'one')],nextCursor:more||kind!=='skill'?null:'next'}}});
  }
  if(path.endsWith('/employees'))return route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:[]}}});
  return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
 });
 await page.goto('/digital-employees?mode=create');await page.getByRole('checkbox',{name:'skill候选one'}).check();await page.getByRole('button',{name:'加载更多资源',exact:true}).click();
 if(mode==='changed-category'){
  await page.getByRole('group',{name:'资源分类'}).getByRole('button',{name:/^知识与数据/}).click();await expect(page.getByRole('checkbox',{name:'knowledge候选one'})).toBeVisible();release();await expect(page.getByRole('checkbox',{name:'skill候选two'})).toHaveCount(0);await expect(page.getByText('已组合 1 项业务资源',{exact:true})).toBeVisible();
 }else if(mode==='changed-user'){
  await expect(page.getByText('会话已切换，请重新读取候选',{exact:true})).toBeVisible();await expect(page.getByRole('checkbox',{name:/skill候选/})).toHaveCount(0);await expect(page.getByText('已组合 0 项业务资源',{exact:true})).toBeVisible();await page.getByRole('button',{name:'重新读取资源',exact:true}).click();await expect(page.getByRole('checkbox',{name:'skill候选one'})).toBeVisible();await expect(page.getByRole('checkbox',{name:'skill候选one'})).not.toBeChecked();
 }else{
  await expect(page.getByRole('checkbox',{name:'skill候选two'})).toBeVisible();await expect(page.getByRole('checkbox',{name:'skill候选one'})).toHaveCount(1);await expect(page.getByRole('checkbox',{name:'skill候选one'})).toBeChecked();
 }
});
