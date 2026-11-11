import {expect,test} from '@playwright/test';

for(const denied of [false,true])test(`stalled fixed detail ends loading; explicit retry respects current authorization ${denied}`,async({page})=>{
 await page.addInitScript(()=>{const original=window.setTimeout;window.setTimeout=((handler:TimerHandler,ms?:number,...args:unknown[])=>original(handler,ms===30000?1000:ms,...args)) as typeof window.setTimeout});
 const principal={principalId:'human:reader',tenantId:'tenant',securityDomain:'test'},item={kind:'skill',identity:'skill:exact',revisionId:'revision:fixed',digest:'a'.repeat(64),name:'固定资料核对',state:'PUBLISHED',enabled:true,isCurrentPublished:true,isCurrentDraft:false,executionReady:false,policyReviewed:true,createdAt:null};
 let hold=true,reads=0;const writes:string[]=[];
 await page.route('**/api/workbench/v1/**',async route=>{
  const request=route.request(),u=new URL(request.url());if(request.method()!=='GET')writes.push(u.pathname);
  if(u.pathname.endsWith('/session'))return route.fulfill({json:{principal,session:{},csrfToken:'fixture'}});
  if(u.pathname==='/api/workbench/v1/resource-directory')return route.fulfill({json:{result:{items:[item],subject:principal.principalId,scope:principal,nextCursor:null,executionAuthority:'NONE'}}});
  if(u.pathname.includes('/resource-directory/skill/')){reads++;if(hold)return;if(denied)return route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});return route.fulfill({json:{result:{kind:item.kind,identity:item.identity,name:item.name,subject:principal.principalId,scope:principal,revision:{revisionId:item.revisionId,digest:item.digest,state:'PUBLISHED',content:{description:'准确固定修订的正文'}},usage:[]}}})}
  return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
 });
 await page.goto('/skills?'+new URLSearchParams({selected:item.identity,resourceRevision:item.revisionId,resourceDigest:item.digest}));
 await expect(page.getByRole('alert')).toContainText('读取等待超时',{timeout:6000});
 await expect(page.getByText('正在核对准确版本与读取资格…',{exact:true})).toHaveCount(0);
 expect(reads).toBe(1);await expect(page.getByText('准确固定修订的正文',{exact:true})).toHaveCount(0);
 hold=false;await page.getByRole('button',{name:'重新读取当前版本',exact:true}).click();
 if(denied){await expect(page.getByRole('alert')).toContainText('当前版本详情未读回');await expect(page.getByText('准确固定修订的正文',{exact:true})).toHaveCount(0)}else await expect(page.getByRole('tabpanel',{name:'概览',exact:true}).getByText('准确固定修订的正文',{exact:true})).toBeVisible();
 expect(reads).toBe(2);expect(writes).toEqual([]);expect(new URL(page.url()).searchParams.get('resourceRevision')).toBe(item.revisionId);
});
