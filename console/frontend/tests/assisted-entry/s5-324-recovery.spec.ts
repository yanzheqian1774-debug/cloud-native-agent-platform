import {expect,test} from '@playwright/test';
const principal={principalId:'human:fixture',tenantId:'fixture',securityDomain:'isolated'};
const invocation={contextId:'draft-context:original',turnId:'draft-turn:original',turnVersion:1,invocationId:'draft-invocation:original',state:'AUTHORIZATION_PENDING',aggregateVersion:1,resultKind:null,reasonCode:null,contentDisposition:'CONTENT_NOT_RETAINED',clarificationQuestion:null,draft:null,resourceUseId:null,evidenceId:null,resourceUseRecorded:false,evidenceRecorded:false,problemId:null,problemRevisionId:null,problemDigest:null,transport:'REAL_PROVIDER',requestAuthorizationRequestId:'grant-request:draft',modelAuthorizationRequestId:'grant-request:model'};

test('324 authorization GET never resubmits and retained content dispatch needs a separate explicit action',async({page},info)=>{
 let begins=0,resubmits=0;let sent='';let retainedKey='';
 await page.route('**/api/workbench/v1/**',async route=>{
  const request=route.request(),path=new URL(request.url()).pathname;
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal,session:{},csrfToken:'fixture'}});
  if(path.includes('/grant-requests/'))return route.fulfill({json:{state:'APPROVED',requestId:decodeURIComponent(path.split('/').at(-1)!),aggregateVersion:2,requestedActions:['READ']}});
  if(path.includes('/context-admissions/'))return route.fulfill({json:{status:'ACTIVE'}});
  if(path.endsWith('/resubmit')){resubmits++;expect(request.postDataJSON().content).toBe(sent);expect(request.postDataJSON().idempotencyKey).toBe(retainedKey);return route.fulfill({json:{result:invocation}})}
  if(path.endsWith('/invocations')){begins++;sent=request.postDataJSON().content;retainedKey=request.postDataJSON().idempotencyKey;return route.fulfill({status:201,json:{result:invocation}})}
  return route.fulfill({json:{result:{problems:[]}}});
 });
 await page.setViewportSize({width:1536,height:1024});await page.goto('/work');
 await page.locator('#problem-composer').fill('明确合成供应商问题，没有企业数据，不得编造分析结论。'.repeat(5));
 await page.getByRole('button',{name:'发送',exact:true}).click();
 const resume=page.getByRole('button',{name:'使用已保留正文继续 AI 调用'});
 await expect(resume).toBeEnabled();expect(resubmits).toBe(0);await expect(page).toHaveURL(/invocation=draft-invocation/);
 await page.getByRole('button',{name:'查看授权状态（只读）'}).click();await expect(resume).toBeEnabled();expect(begins).toBe(1);expect(resubmits).toBe(0);
 for(const scale of [1,1.25]){await page.setViewportSize({width:Math.floor(1536/scale),height:Math.floor(1024/scale)});await expect(page.getByRole('button',{name:'发送',exact:true})).toBeInViewport();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.screenshot({path:info.outputPath(`pending-content-${scale}.png`)})}
 await resume.click();expect(resubmits).toBe(1);
 await page.reload();expect(resubmits).toBe(1);expect(begins).toBe(1);await expect(page.getByRole('button',{name:'读取原调用事实（只读）'})).toBeVisible();await expect(resume).toHaveCount(0);
});

test('324 lost content cannot resubmit and successor must link the original objects',async({page},info)=>{
 const writes:{path:string;body:Record<string,unknown>}[]=[];
 await page.route('**/api/workbench/v1/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname;if(req.method()==='POST')writes.push({path,body:req.postDataJSON()});
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal,session:{},csrfToken:'fixture'}});
  if(path.includes('/invocations/'))return route.fulfill({json:{result:invocation}});
  if(path.endsWith('/invocations'))return route.fulfill({json:{result:{...invocation,invocationId:'draft-invocation:successor',turnId:'draft-turn:successor',turnVersion:2}}});
  return route.fulfill({json:{result:{problems:[]}}});
 });
 await page.setViewportSize({width:1536,height:1024});await page.goto('/work?invocation=draft-invocation%3Aoriginal');
 expect(writes).toHaveLength(0);await page.getByRole('button',{name:'读取原调用事实（只读）'}).click();
 await expect(page.getByText('原始提交正文在本页不可用',{exact:false})).toBeVisible();
 await expect(page.getByRole('button',{name:'使用已保留正文继续 AI 调用'})).toHaveCount(0);
 await page.locator('#problem-composer').fill('明确新提交的合成后继，不冒充已丢失正文。');await expect(page.getByRole('button',{name:'更新理解',exact:true})).toBeDisabled();
 await page.screenshot({path:info.outputPath('missing-content.png')});
 await page.getByRole('button',{name:'填写关联后继（保留原记录）'}).click();expect(writes).toHaveLength(0);
 await page.getByRole('button',{name:'更新理解',exact:true}).click();expect(writes).toHaveLength(1);
 expect(writes[0].body).toMatchObject({parentContextId:invocation.contextId,parentTurnId:invocation.turnId,expectedParentVersion:1,predecessorInvocationId:invocation.invocationId});
 expect(writes[0].path).toBe('/api/workbench/v1/draft-assistance/invocations');
});

for(const query of ['request=grant-resource','request=grant-employee','request=grant-plan','request=grant-draft','request=grant-model','context=draft-context%3Aoriginal'])test(`324 exact approval entry preserves ${query} without business reads`,async({page})=>{
 const paths:string[]=[];
 await page.route('**/api/workbench/v1/**',async route=>{const req=route.request();paths.push(new URL(req.url()).pathname);expect(req.method()).toBe('GET');return route.fulfill({status:401,json:{reasonCode:'AUTHENTICATION_REQUIRED'}})});
 await page.goto('/authorization-admin?'+query);
 const login=page.getByRole('link',{name:'重新登录并读回'});
 await expect(login).toHaveAttribute('href','/api/workbench/v1/login?returnTo='+encodeURIComponent('/authorization-admin?'+query));
 expect(paths.some(path=>path.includes('/problems'))).toBe(false);
});

test('324 independent reviewer can inspect all exact links without Problem collection access or decisions',async({page},info)=>{
 const reads:string[]=[];let writes=0;
 await page.route('**/api/workbench/v1/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname;reads.push(path);if(req.method()!=='GET')writes++;
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{...principal,principalId:'human:independent-fixture'},session:{},csrfToken:'fixture'}});
  if(path.includes('/grant-requests/'))return route.fulfill({json:{requestId:decodeURIComponent(path.split('/').at(-1)!),state:'PENDING',aggregateVersion:1,purpose:'S5_324_RESOURCE_REVIEW',requestedActions:['READ_RESOURCE']}});
  if(path.includes('/context-admissions/'))return route.fulfill({json:{status:'NOT_ADMITTED',request:{context_id:'draft-context:original',subject_id:'human:fixture',tenant_id:'fixture',security_domain:'isolated',account_revision:1,digest:'a'.repeat(64),record:{configuration:{profile_revision_id:'fixture:1',profile_digest:'b'.repeat(64),configuration_digest:'c'.repeat(64),ledger_id:'fixture-original',calls:12,cost_microusd:10000000,input_tokens:65536,output_tokens:8192}}},decision:null,reasonCode:null}});
  return route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
 });
 await page.setViewportSize({width:1536,height:1024});
 for(const kind of ['resource','employee','plan','draft','model']){
  await page.goto('/authorization-admin?request=grant-'+kind);
  await expect(page.getByLabel('申请编号',{exact:true})).toHaveValue('grant-'+kind);
  await page.getByRole('button',{name:'检查授权申请',exact:true}).click();
  await expect(page.getByRole('region',{name:'授权申请决定'})).toContainText('grant-'+kind);
 }
 await page.goto('/authorization-admin?context=draft-context%3Aoriginal');
 await expect(page.getByLabel('实际 context 编号')).toHaveValue('draft-context:original');
 await page.getByRole('button',{name:'核对调用对象',exact:true}).click();
 await expect(page.getByRole('button',{name:'本人独立签发此 context'})).toBeEnabled();
 expect(writes).toBe(0);expect(reads.some(path=>path.includes('/problems'))).toBe(false);
 await page.screenshot({path:info.outputPath('independent-review-fixture.png')});
});
