import {expect,test} from '@playwright/test';

for(const scenario of ['published','historical','untested','legacy','wrong-tuple','denied','expired'])test(`exact resource basis ${scenario}`,async({page})=>{
 const principal={principalId:'human:reader',tenantId:'tenant',securityDomain:'test'};
 const item={kind:'skill',identity:'skill:exact',revisionId:'revision:fixed',digest:'a'.repeat(64),name:'准确技能',state:scenario==='untested'?'DRAFT':'PUBLISHED',enabled:false,isCurrentPublished:scenario==='published',isCurrentDraft:scenario==='untested',executionReady:false,policyReviewed:true,createdAt:null};
 const basis={schemaVersion:'resource-version-basis.v1',revisionId:scenario==='wrong-tuple'?'revision:other':item.revisionId,revisionDigest:item.digest,executionAuthority:'NONE',businessAcceptance:'NOT_ESTABLISHED',tests:{scope:'ISOLATED_SYNTHETIC_ONLY_NOT_BUSINESS_ACCEPTANCE',ready:scenario!=='untested',operations:[{operation:'READ_DATA',passed:scenario!=='untested',caseCount:scenario==='untested'?0:1,passedCount:scenario==='untested'?0:1}]},publication:{recorded:scenario!=='untested',publishedAt:scenario==='untested'?null:'2026-11-27T12:01:00Z',basisType:'POLICY'}};
 const writes:string[]=[];
 await page.route('**/api/workbench/v1/**',route=>{
  const request=route.request(),u=new URL(request.url());if(request.method()!=='GET')writes.push(u.pathname);
  if(u.pathname.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal,session:{},csrfToken:'fixture'}});
  if(u.pathname==='/api/workbench/v1/resource-directory')return route.fulfill({json:{result:{items:[item],subject:principal.principalId,scope:principal,nextCursor:null,executionAuthority:'NONE'}}});
  if(u.pathname.includes('/resource-directory/skill/')){
   if(scenario==='denied')return route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
   return route.fulfill({json:{result:{kind:item.kind,identity:item.identity,name:item.name,subject:principal.principalId,scope:principal,revision:{revisionId:item.revisionId,digest:item.digest,state:item.state,content:{description:'准确版本说明'}},...(scenario==='legacy'?{}:{versionBasis:basis}),usage:[]}}});
  }
  return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
 });
 await page.goto('/skills?'+new URLSearchParams({selected:item.identity,resourceRevision:item.revisionId,resourceDigest:item.digest,resourceSection:'content'}));
 if(scenario==='denied')await expect(page.getByRole('alert')).toContainText('当前版本详情未读回');
 else if(['legacy','wrong-tuple'].includes(scenario))await expect(page.getByText('当前读取接口未返回本版本测试与发布校验回执，无法据此判断测试是否通过或当前是否可执行。历史成功不代表当前执行授权。',{exact:true})).toBeVisible();
 else {
  await expect(page.getByText(scenario==='untested'?'本版本未记录合成契约测试结果。':'本版本合成契约测试通过。',{exact:true})).toBeVisible();
  await expect(page.getByText('合成契约测试与发布记录不代表业务成果已接受，也不授予当前执行权限。',{exact:true})).toBeVisible();
  if(scenario==='untested')await expect(page.getByText('本版本未读回发布记录。',{exact:true})).toBeVisible();
  else await expect(page.getByText(/依据资源策略发布/)).toBeVisible();
  if(scenario==='historical')await expect(page.getByText('历史内容 · 只读',{exact:true})).toBeVisible();
  if(scenario==='expired'){
   await page.evaluate(()=>window.dispatchEvent(new Event('workbench-session-expired')));
   await expect(page.getByText('本版本合成契约测试通过。',{exact:true})).toHaveCount(0);
  }
 }
 expect(writes).toEqual([]);
});
