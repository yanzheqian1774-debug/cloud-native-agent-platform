import {test,expect} from '@playwright/test';
const digest='a'.repeat(64),principal={principalId:'human:test',tenantId:'tenant',securityDomain:'domain'};
const operation={name:'READ_DOCUMENT',inputSchema:{type:'object'},outputSchema:{type:'object'},sideEffectClass:'READ_ONLY',executorId:'reader',executorRevision:'1',executorConfigurationDigest:digest,sideEffectPolicy:{policyId:'read-only',policyRevision:'1',policyDigest:digest},ioLimits:{policyId:'bounded',policyRevision:'1',maxInputBytes:1024,maxOutputBytes:1024,maxObjectDepth:8,maxProperties:20,timeoutMs:1000}};
for(const mode of ['ready','wrong-version','denied','deprecated','disabled','duplicate-operation','identity-change'] as const)test(`trusted workflow skill directory ${mode}`,async({page})=>{
 let posts=0,legacy=0,details=0;const cursors:string[]=[];let changed=false;
 await page.route('**/api/**',route=>{
  const r=route.request(),u=new URL(r.url()),p=u.pathname;
  if(r.method()==='POST')posts++;
  const reply=(result:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result}});
  if(p.includes('/internal/')){legacy++;return route.fulfill({status:404,json:{}})}
  if(p.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:changed?{...principal,principalId:'human:other'}:principal,csrfToken:'csrf',session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'}}});
  if(p.endsWith('/workflows'))return reply({items:[]});
  if(p.endsWith('/resource-directory')){
   if(u.searchParams.get('kind')!=='skill')return reply({subject:principal.principalId,scope:{tenantId:'tenant',securityDomain:'domain'},items:[],nextCursor:null});
   const cursor=u.searchParams.get('cursor')??'';cursors.push(cursor);
   expect(u.searchParams.get('projection')).toBe('workflow-skill-operations');
   if(cursor&&mode==='denied')return route.fulfill({status:403,json:{reasonCode:'DENIED'}});
   if(cursor&&mode==='identity-change')changed=true;
   return reply({subject:principal.principalId,scope:{tenantId:'tenant',securityDomain:'domain'},items:cursor?[{kind:'skill',identity:'skill-doc',revisionId:'revision-1',digest:'sha256:'+digest,name:'文档读取',state:'PUBLISHED',enabled:true,isCurrentPublished:true,workflowOperations:{identity:'skill-doc',revisionId:mode==='wrong-version'?'wrong':'revision-1',digest:'sha256:'+digest,enabled:mode!=='disabled',archived:false,lifecycleState:mode==='deprecated'?'DEPRECATED':'PUBLISHED',publishedRevisionId:'revision-1',operations:mode==='duplicate-operation'?[operation,operation]:[operation]}}]:[],nextCursor:cursor?null:'next-page'});
  }
  if(p.includes('/resource-directory/skill/')){details++;return route.fulfill({status:500,json:{reasonCode:'UNEXPECTED_DETAIL_FANOUT'}})}
  return reply({items:[]});
 });
 await page.goto('/workflow-definitions?resourceView=professional');const status=page.getByRole('region',{name:'Skill operation directory status'});
 if(['wrong-version','denied','identity-change'].includes(mode))await expect(status).toContainText('目录不可用');
 else await expect(status).toContainText(mode==='ready'?'1 个合格 operation':'0 个合格 operation');
 expect(cursors).toEqual(['','next-page']);expect(details).toBe(0);expect(legacy).toBe(0);
 if(mode==='ready'){
  await page.getByRole('button',{name:'新建 Workflow Definition',exact:true}).click();
  const picker=page.getByRole('region',{name:'步骤使用的技能'});
  await picker.getByLabel('使用技能',{exact:true}).selectOption('skill-doc');
  await picker.getByLabel('执行操作',{exact:true}).selectOption('READ_DOCUMENT');
  await picker.getByRole('button',{name:'加入当前步骤'}).click();
  await expect(picker).toContainText('目录版本已核对');await picker.getByText('查看技能版本与约束',{exact:true}).click();await expect(picker).toContainText('sha256:'+digest);
  await expect(picker).toContainText('skill-doc · revision-1');
 }
 expect(posts).toBe(0);
});
