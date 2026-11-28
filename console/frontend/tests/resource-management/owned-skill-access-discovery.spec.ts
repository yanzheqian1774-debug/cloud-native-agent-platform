import {expect,test} from '@playwright/test';

for(const scenario of ['card','historical-detail','non-owner','no-read','session-change','detail-session-change','unknown-command'])test(`owned Skill access discovery ${scenario}`,async({page})=>{
 const principal={principalId:'human:owner',tenantId:'tenant',securityDomain:'test'},identity='skill:owned';let changed=false,recovered=false;
 const candidate={kind:'skill',identity,revisionId:'revision:current',digest:'b'.repeat(64)};
 const current={kind:'skill',identity,revisionId:candidate.revisionId,digest:candidate.digest,name:'本人合成技能',state:'PUBLISHED',enabled:true,isCurrentPublished:true,isCurrentDraft:false,executionReady:false,policyReviewed:true,createdAt:null};
 const old={...current,revisionId:'revision:old',digest:'a'.repeat(64),isCurrentPublished:false};
 const content={description:'合成维护资格测试',capabilities:['READ_DATA'],instructions:'仅合成资料',operations:[]};
 const resource={kind:'skill',resourceId:identity,name:current.name,aggregateVersion:3,lifecycleState:'PUBLISHED',enabled:true,archived:false,currentDraftRevisionId:null,publishedRevisionId:current.revisionId,revisions:[{revisionId:old.revisionId,digest:old.digest,state:'PUBLISHED',content,createdAt:'2026-11-20T12:00:00Z',predecessorRevisionId:null},{revisionId:current.revisionId,digest:current.digest,state:'PUBLISHED',content,createdAt:'2026-11-27T12:00:00Z',predecessorRevisionId:old.revisionId}],reviews:[],relationships:[],bindings:[],invocations:[],savedTests:[],testResults:[],discoverySnapshots:[],toolSelections:[],healthObservations:[],driftRecords:[],limitations:[]};
 const posts:Record<string,unknown>[]=[],reads:string[]=[];
 if(scenario==='unknown-command')await page.addInitScript(({principal,identity})=>{
  const marker='resource-management:'+principal.principalId+':'+principal.tenantId+':'+principal.securityDomain+':skill',key='unknown-original-key';
  sessionStorage.setItem(marker,key);sessionStorage.setItem(marker+':intent',JSON.stringify({version:1,commandKey:key,action:'edit',kind:'skill',principal:JSON.stringify(principal),identity,expectedVersion:2,viewResource:identity}));
 },{principal,identity});
 await page.route('**/api/**',async route=>{
  const request=route.request(),u=new URL(request.url()),actor=changed?{...principal,principalId:'human:other'}:principal;
  if(request.method()==='POST'){
   const body=request.postDataJSON();posts.push(body);
   if(!['card','historical-detail'].includes(scenario)||u.pathname!=='/api/workbench/v1/resource-management/skill/commands'||body.action!=='access')return route.fulfill({status:403,json:{reasonCode:'UNEXPECTED_WRITE'}});
   expect(body.identity).toBe(identity);expect(body.expectedVersion).toBeUndefined();recovered=true;
   return route.fulfill({json:{result:{schemaVersion:'resource-management-receipt.v1',identity,kind:'skill',action:'access',commandKey:body.commandKey,aggregateVersion:resource.aggregateVersion,resource,executionStarted:false,modelCalls:0,credentialMaterial:'NOT_INCLUDED'}}});
  }
  reads.push(u.pathname);
  if(u.pathname.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:actor,session:{},csrfToken:'fixture'}});
  if(u.pathname==='/api/workbench/v1/resource-directory')return route.fulfill({json:{result:{items:scenario==='no-read'?[]:[current,old],subject:actor.principalId,scope:actor,nextCursor:null,executionAuthority:'NONE'}}});
  if(u.pathname==='/api/workbench/v1/resource-management/skill')return route.fulfill({json:{result:{kind:'skill',items:recovered?[resource]:[],accessCandidates:!changed&&!['non-owner','no-read'].includes(scenario)?[candidate]:[],subject:actor.principalId,scope:actor,enabled:true}}});
  if(u.pathname.includes('/resource-directory/skill/'))return route.fulfill({json:{result:{kind:'skill',identity,name:current.name,subject:actor.principalId,scope:actor,revision:{revisionId:old.revisionId,digest:old.digest,state:'PUBLISHED',content},usage:[]}}});
  return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
 });
 const query=['historical-detail','detail-session-change'].includes(scenario)?new URLSearchParams({kind:'skill',selected:identity,resourceRevision:old.revisionId,resourceDigest:old.digest,resourceSection:'content'}):new URLSearchParams();
 await page.goto('/skills?'+query);
 if(['non-owner','no-read'].includes(scenario)){
  await expect(page.getByRole('heading',{name:scenario==='no-read'?'暂无符合条件的可读资源版本':current.name,exact:true})).toBeVisible();
  await expect(page.getByRole('link',{name:'核对维护资格',exact:true})).toHaveCount(0);expect(posts).toEqual([]);return;
 }
 const link=page.getByRole('link',{name:'核对维护资格',exact:true});await expect(link).toBeVisible();expect(posts).toEqual([]);
 if(['session-change','detail-session-change'].includes(scenario)){
  changed=true;await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect(link).toHaveCount(0);expect(posts).toEqual([]);return;
 }
 const href=await link.getAttribute('href');expect(href).toContain('managedResource=skill%3Aowned');expect(href).not.toContain('selected=');expect(href).not.toContain('viewRevision=');
 if(scenario==='historical-detail')await expect(page.getByText('进入当前定义核对；本页历史版本与已有引用保持不变。',{exact:true})).toBeVisible();
 await link.click();const recover=page.getByRole('button',{name:'核对原资源访问资格',exact:true});await expect(recover).toBeVisible();expect(posts).toEqual([]);
 if(scenario==='unknown-command'){
  await expect(recover).toBeDisabled();await page.getByRole('button',{name:'读取原操作结果',exact:true}).click();expect(posts).toEqual([]);await expect.poll(()=>reads.some(x=>x.endsWith('/commands/unknown-original-key'))).toBe(true);return;
 }
 await recover.click();await expect(page.getByRole('region',{name:'当前资源配置',exact:true})).toBeVisible();
 expect(posts).toHaveLength(1);expect(posts[0].action).toBe('access');expect(posts[0]).not.toHaveProperty('expectedVersion');
 await expect(recover).toHaveCount(0);expect(resource.publishedRevisionId).toBe(current.revisionId);
});
