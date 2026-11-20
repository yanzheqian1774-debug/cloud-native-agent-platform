import {test,expect} from '@playwright/test';
for(const mode of ['off','publish','lost'] as const)test(`truthful development policy publication ${mode}`,async({page})=>{
 const digest='a'.repeat(64);let published=false,posts=0,command:Record<string,unknown>|undefined;
 const basis={schemaVersion:'workflow-policy-review.v1',reviewId:'policy-review',revisionId:'v1',digest,actor:'human:test',reviewedAt:'2026-11-20T00:00:00Z',policyBasis:{type:'DEVELOPMENT_ADMINISTRATOR',issuer:'human:test',authorityGeneration:1,commandDigest:'b'.repeat(64)}};
 const content={description:'核对交接',inputs:[],outputs:[],runtimeProfile:{kind:'RUNTIME_PROFILE',resourceId:'runtime',revisionId:'runtime-v1',digest},tasks:[{taskId:'check',name:'检查交接',dependsOn:[],inputs:[],outputs:[],capabilityRequirements:[],references:[],retryLimit:0,timeoutSeconds:300,failurePolicy:'FAIL_WORKFLOW'}]};
 await page.route('**/api/**',route=>{
  const u=new URL(route.request().url()),p=u.pathname,reply=(result:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result}});
  if(p.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:test',tenantId:'tenant',securityDomain:'domain'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'csrf'}});
  if(p.endsWith('/workflows/policy-publications')&&route.request().method()==='POST'){
   posts++;command=route.request().postDataJSON();expect(Object.keys(command!).sort()).toEqual(['action','commandKey','digest','expectedVersion','workflowId']);published=true;
   if(mode==='lost')return route.abort('failed');return reply({...command,revisionId:'v1',policyReview:basis,executionAuthorized:false});
  }
  if(p.includes('/workflows/policy-publications/')){expect(u.searchParams.get('workflowId')).toBe('flow');return reply({...command,revisionId:'v1',policyReview:basis,executionAuthorized:false,replayed:true})}
  if(p.endsWith('/workflows'))return reply({items:[{workflowDefinitionId:'flow'}]});
  if(p.endsWith('/authoring'))return reply({definition:{workflowDefinitionId:'flow',name:'交接流程',aggregateVersion:published?4:2,lifecycleState:published?'PUBLISHED':'VALIDATED',currentDraftRevisionId:published?null:'v1',publishedRevisionId:published?'v1':null,revisions:[{revisionId:'v1',digest,state:published?'PUBLISHED':'VALIDATED',content,...(published?{publicationBasis:basis}:{})}],reviews:[],relationships:[],consumers:[]},productProjection:{},technicalProjection:{},...(mode==='off'?{}:{policyPublicationAvailable:true})});
  return reply({items:[],entries:[],rejectedResources:0});
 });
 await page.goto('/workflow-definitions?resourceId=flow');await page.getByRole('button',{name:'验证与发布',exact:true}).click();
 const button=page.getByRole('button',{name:'按开发授权核验并发布',exact:true});
 if(mode==='off'){await expect(button).toHaveCount(0);await expect(page.getByRole('button',{name:'确认复核',exact:true})).toBeDisabled();expect(posts).toBe(0);return}
 await button.click();
 if(mode==='lost'){await expect(page.getByRole('heading',{name:'上次提交结果待核对'})).toBeVisible();await page.reload();await page.getByRole('button',{name:'读取原提交结果'}).click();await page.getByRole('button',{name:'验证与发布',exact:true}).click()}
 await expect(page.getByText('已依据开发管理员授权核验并发布。此记录不是逐项人工复核，发布不启动任务。',{exact:true})).toBeVisible();expect(posts).toBe(1);
});
