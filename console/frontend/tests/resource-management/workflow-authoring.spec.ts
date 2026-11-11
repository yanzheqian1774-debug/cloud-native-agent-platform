import {test,expect} from '@playwright/test';
for(const lost of [false,true,'retry'] as const)test(`trusted workflow creation and original receipt recovery ${lost}`,async({page})=>{
 let command:Record<string,unknown>|null=null,posts=0;const sent:Record<string,unknown>[]=[];
 const digest='a'.repeat(64);
 const projection=()=>({definition:{workflowDefinitionId:'flow',name:'交接流程',aggregateVersion:1,lifecycleState:'DRAFT',currentDraftRevisionId:'v1',publishedRevisionId:null,revisions:[{revisionId:'v1',digest,state:'DRAFT',content:command?.content}],reviews:[],relationships:[],consumers:[]},productProjection:{},technicalProjection:{}});
 await page.route('**/api/**',route=>{
  const url=new URL(route.request().url()),p=url.pathname;
  const reply=(result:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result}});
  if(p.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:test',tenantId:'tenant',securityDomain:'domain'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'csrf'}});
  if(p.endsWith('/workflows/commands')&&route.request().method()==='POST'){
   posts++;command=route.request().postDataJSON();sent.push(command!);expect(route.request().headers()['x-csrf-token']).toBe('csrf');
   if(lost&&posts===1)return route.abort('failed');
   return reply({workflowId:'flow',commandKey:command?.commandKey,action:'create'});
  }
  if(p.includes('/workflows/commands/')){if(lost==='retry'&&posts===1)return route.fulfill({status:404,json:{reasonCode:'WORKFLOW_COMMAND_NOT_FOUND'}});expect(url.searchParams.get('action')).toBe('create');return reply({workflowId:'flow',commandKey:command?.commandKey,action:'create'})}
  if(p.endsWith('/workflows/flow/authoring'))return reply(projection());
  if(p.endsWith('/workflows'))return reply({items:command?[{workflowDefinitionId:'flow'}]:[]});
  if(p.endsWith('/resource-directory'))return reply({subject:'human:test',scope:{tenantId:'tenant',securityDomain:'domain'},items:[{kind:'runtime',identity:'runtime',revisionId:'runtime-v1',digest,name:'隔离只读环境',enabled:true,isCurrentPublished:true}],nextCursor:null});
  return reply({items:[],entries:[],rejectedResources:0});
 });
 await page.goto('/workflow-definitions');await page.getByRole('button',{name:'新建 Workflow Definition',exact:true}).click();
 await page.getByLabel('方案名称',{exact:true}).fill('交接流程');
 await page.getByRole('button',{name:'方案信息',exact:true}).click();await page.getByLabel('已发布运行环境',{exact:true}).selectOption({label:'隔离只读环境 · ntime-v1'});await page.getByRole('button',{name:'执行步骤',exact:true}).click();
 await page.getByLabel('步骤名称',{exact:true}).fill('检查交接');
 await page.getByRole('button',{name:'保存草稿',exact:true}).click();
 if(lost){await expect(page.getByRole('heading',{name:'上次提交结果待核对'})).toBeVisible();await page.reload();await page.getByRole('button',{name:lost==='retry'?'沿用原记录重试':'读取原提交结果'}).click()}
 await expect(page.getByRole('region',{name:'已保存方案',exact:true})).toBeVisible();expect(posts).toBe(lost==='retry'?2:1);if(lost==='retry')expect(sent[1]).toEqual(sent[0]);
 expect((command?.content as {runtimeProfile:{digest:string}}).runtimeProfile.digest).toBe(digest);
 await expect(page.getByRole('heading',{name:'上次提交结果待核对'})).toHaveCount(0);
});

test('trusted comparison rejects wrong pair and shows readable fixed step changes after retry',async({page})=>{
 let wrong=true;const task={taskId:'check',name:'核对原文',dependsOn:[],inputs:[],outputs:[],capabilityRequirements:[],references:[],retryLimit:0,timeoutSeconds:300,failurePolicy:'FAIL_WORKFLOW'};
 const content={description:'交接核对',inputs:[],outputs:[],runtimeProfile:{kind:'RUNTIME_PROFILE',resourceId:'runtime',revisionId:'runtime-v1'},tasks:[task]};
 const definition={workflowDefinitionId:'flow',name:'交接流程',aggregateVersion:2,lifecycleState:'DRAFT',currentDraftRevisionId:'v2',publishedRevisionId:null,revisions:[{revisionId:'v1',digest:'a'.repeat(64),state:'DRAFT',content},{revisionId:'v2',digest:'sha256:'+'b'.repeat(64),state:'DRAFT',content:{...content,tasks:[task,{...task,taskId:'report',name:'整理缺口清单'}]}}],reviews:[],relationships:[],consumers:[]};
 await page.route('**/api/**',route=>{
  const u=new URL(route.request().url()),p=u.pathname;const reply=(result:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result}});
  if(p.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:test',tenantId:'tenant',securityDomain:'domain'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'csrf'}});
  if(p.endsWith('/workflows'))return reply({items:[{workflowDefinitionId:'flow'}]});
  if(p.endsWith('/workflows/flow/authoring'))return reply({definition,productProjection:{},technicalProjection:{}});
  if(p.endsWith('/business-capabilities')){expect(u.searchParams.get('workflowDigest')).toBe('b'.repeat(64));expect(u.searchParams.get('workflowRevision')).toBe('v2');expect(u.searchParams.get('workflowId')).toBe('flow');return reply({items:[{capabilityId:'derived',revisionId:'derived-v1',digest:'c'.repeat(64),title:'同源交接能力',intent:'核对交接材料',state:'DRAFT',currentDraft:null,currentPublished:null}],nextCursor:null})}
  if(p.endsWith('/workflows/flow/comparison')){expect(u.searchParams.get('leftRevisionId')).toBe('v1');expect(u.searchParams.get('rightRevisionId')).toBe('v2');return reply({workflowDefinitionId:'flow',leftRevisionId:wrong?'wrong':'v1',rightRevisionId:'v2',addedTaskIds:['report'],removedTaskIds:[],changedTaskIds:[],digestChanged:true})}
  return reply({items:[],entries:[],rejectedResources:0});
 });
 await page.goto('/workflow-definitions?resourceId=flow');const comparison=page.getByRole('region',{name:'Workflow revision comparison'});
 await page.getByRole('button',{name:'验证与发布',exact:true}).click();await page.getByText('查看版本与操作记录',{exact:true}).click();await expect(comparison.getByRole('alert')).toContainText('暂时无法核对');await expect(comparison.getByText('整理缺口清单',{exact:true})).toHaveCount(0);
 wrong=false;await comparison.getByRole('button',{name:'重新核对版本变化'}).click();await expect(comparison.getByRole('heading',{name:'新增步骤（1）'})).toBeVisible();await expect(comparison.getByText('整理缺口清单',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'查看由此执行方案形成的能力',exact:true}).click();await expect(page.getByRole('link',{name:'同源交接能力',exact:true})).toHaveAttribute('href','/capabilities?capability=derived&revision=derived-v1&digest='+'c'.repeat(64));
});

test('named multistep editing blocks cycles and referenced deletion and saves stable exact dependencies',async({page})=>{
 let command:{content:{tasks:Array<{taskId:string;name:string;dependsOn:string[];inputs:string[]}>};commandKey:string}|null=null;let posts=0;const digest='a'.repeat(64);
 await page.route('**/api/**',route=>{const u=new URL(route.request().url()),p=u.pathname,reply=(result:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result}});
 if(p.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:test',tenantId:'tenant',securityDomain:'domain'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'csrf'}});
 if(p.endsWith('/resource-directory'))return reply({subject:'human:test',scope:{tenantId:'tenant',securityDomain:'domain'},items:u.searchParams.get('kind')==='runtime'?[{kind:'runtime',identity:'runtime',revisionId:'runtime-v1',digest,name:'隔离只读环境',enabled:true,isCurrentPublished:true}]:[],nextCursor:null});
 if(p.endsWith('/workflows/commands')&&route.request().method()==='POST'){posts++;command=route.request().postDataJSON();return reply({workflowId:'flow',commandKey:command!.commandKey,action:'create'})}
 if(p.includes('/workflows/commands/'))return reply({workflowId:'flow',commandKey:command!.commandKey,action:'create'});
 if(p.endsWith('/workflows'))return reply({items:command?[{workflowDefinitionId:'flow'}]:[]});
 if(p.endsWith('/workflows/flow/authoring'))return reply({definition:{workflowDefinitionId:'flow',name:'多步骤核对',aggregateVersion:1,lifecycleState:'DRAFT',currentDraftRevisionId:'v1',publishedRevisionId:null,revisions:[{revisionId:'v1',digest,state:'DRAFT',content:command?.content}],reviews:[],relationships:[],consumers:[]},productProjection:{},technicalProjection:{}});
 return reply({items:[]});
 });
 await page.goto('/workflow-definitions');await page.getByRole('button',{name:'新建 Workflow Definition',exact:true}).click();await page.getByLabel('方案名称',{exact:true}).fill('多步骤核对');await page.getByLabel('步骤名称',{exact:true}).fill('读取资料');await page.getByLabel('步骤输入',{exact:true}).pressSequentially('first,second');await expect(page.getByLabel('步骤输入',{exact:true})).toHaveValue('first,second');await page.getByRole('button',{name:'添加步骤',exact:true}).click();await page.getByLabel('步骤名称',{exact:true}).fill('整理结果');await page.getByLabel('添加前置步骤',{exact:true}).selectOption({label:'读取资料'});await page.locator('.plan-step-list button').filter({hasText:'步骤 1'}).click();await page.getByLabel('添加前置步骤',{exact:true}).selectOption({label:'整理结果'});await expect(page.getByRole('alert')).toContainText('依赖会形成循环');await expect(page.getByRole('button',{name:'移除前置步骤：整理结果',exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'移除此步骤',exact:true}).click();await expect(page.getByRole('alert')).toContainText('请先调整以下步骤的依赖');await expect(page.locator('.plan-step-list button')).toHaveCount(2);
 await page.locator('.plan-step-list button').filter({hasText:'步骤 2'}).click();await page.getByRole('button',{name:'移除此步骤',exact:true}).click();await page.getByRole('button',{name:'添加步骤',exact:true}).click();await page.getByLabel('步骤名称',{exact:true}).fill('交付核对结果');await page.getByLabel('添加前置步骤',{exact:true}).selectOption({label:'读取资料'});await page.getByLabel('步骤输入',{exact:true}).fill('保留已有输入声明');await page.getByRole('button',{name:'在“读取资料”与“交付核对结果”之间插入步骤',exact:true}).click();await page.getByLabel('步骤名称',{exact:true}).fill('核对中间步骤');await page.getByRole('button',{name:'放大画布',exact:true}).click();await expect(page.getByLabel('画布缩放比例')).toHaveText('110%');await page.getByRole('button',{name:'方案信息',exact:true}).click();await page.getByLabel('已发布运行环境',{exact:true}).selectOption({label:'隔离只读环境 · ntime-v1'});await page.getByRole('button',{name:'执行步骤',exact:true}).click();await page.getByRole('button',{name:'保存草稿',exact:true}).click();await expect(page.getByRole('region',{name:'已保存方案',exact:true})).toBeVisible();
 await expect(page.getByLabel('画布缩放比例')).toHaveText('110%');await expect(page.getByLabel('步骤名称',{exact:true})).toHaveValue('核对中间步骤');await expect(page.getByLabel('步骤名称',{exact:true})).toBeDisabled();expect(posts).toBe(1);expect(command!.content.tasks[0].inputs).toEqual(['first','second']);expect(command!.content.tasks.map(t=>t.name)).toEqual(['读取资料','核对中间步骤','交付核对结果']);expect(new Set(command!.content.tasks.map(t=>t.taskId)).size).toBe(3);expect(command!.content.tasks[1].dependsOn).toEqual([command!.content.tasks[0].taskId]);expect(command!.content.tasks[2].dependsOn).toEqual([command!.content.tasks[1].taskId]);expect(command!.content.tasks[2].inputs).toEqual(['保留已有输入声明']);
});

for(const mode of ['create','edit'] as const)test(`explicit target for same-name ${mode}`,async({page})=>{
 const digest='a'.repeat(64),sent:Record<string,unknown>[]=[];
 const content={description:'原有方案',inputs:[],outputs:[],runtimeProfile:{kind:'RUNTIME_PROFILE',resourceId:'runtime',revisionId:'runtime-v1',digest},tasks:[{taskId:'original-step',name:'原有步骤',dependsOn:[],inputs:[],outputs:[],capabilityRequirements:[],references:[],retryLimit:0,timeoutSeconds:300,failurePolicy:'FAIL_WORKFLOW'}]};
 const original={workflowDefinitionId:'original',name:'同名方案',aggregateVersion:3,lifecycleState:'DRAFT',currentDraftRevisionId:'original-v1',publishedRevisionId:null,revisions:[{revisionId:'original-v1',digest,state:'DRAFT',content}],reviews:[],relationships:[],consumers:[]};
 await page.route('**/api/**',route=>{
  const p=new URL(route.request().url()).pathname,reply=(result:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result}});
  if(p.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:test',tenantId:'tenant',securityDomain:'domain'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'csrf'}});
  if(p.endsWith('/workflows/commands')&&route.request().method()==='POST'){sent.push(route.request().postDataJSON());return reply({workflowId:mode==='create'?'new':'original',commandKey:sent[0].commandKey,action:mode})}
  if(p.includes('/workflows/commands/'))return reply({workflowId:mode==='create'?'new':'original',commandKey:sent[0].commandKey,action:mode});
  if(p.endsWith('/workflows'))return reply({items:[{workflowDefinitionId:'original'}]});
  if(p.endsWith('/authoring'))return reply({definition:p.includes('/new/')?{...original,workflowDefinitionId:'new'}:original,productProjection:{},technicalProjection:{}});
  if(p.endsWith('/resource-directory'))return reply({subject:'human:test',scope:{tenantId:'tenant',securityDomain:'domain'},items:[{kind:'runtime',identity:'runtime',revisionId:'runtime-v1',digest,name:'隔离只读环境',enabled:true,isCurrentPublished:true}],nextCursor:null});
  return reply({items:[],entries:[],rejectedResources:0});
 });
 await page.goto('/workflow-definitions?resourceId=original');await expect(page.getByRole('region',{name:'已保存方案',exact:true})).toBeVisible();
 if(mode==='create')await page.getByRole('button',{name:'返回执行方案目录',exact:true}).click();await page.getByRole('button',{name:mode==='create'?'新建 Workflow Definition':'编辑方案',exact:true}).click();
 const name=page.getByLabel('方案名称',{exact:true});
 if(mode==='create'){await name.fill('同名方案');await page.getByRole('button',{name:'方案信息',exact:true}).click();await page.getByLabel('已发布运行环境',{exact:true}).selectOption({label:'隔离只读环境 · ntime-v1'});await page.getByRole('button',{name:'执行步骤',exact:true}).click()}else{await expect(name).toHaveAttribute('readonly','');await expect(name).toHaveValue('同名方案')}
 await page.getByLabel('步骤名称',{exact:true}).fill('新的步骤内容');await page.getByRole('button',{name:'保存草稿',exact:true}).click();
 await expect(page.getByRole('region',{name:'Workflow authoring',exact:true})).toHaveCount(0);
 expect(sent).toHaveLength(1);expect(sent[0].action).toBe(mode);
 if(mode==='create')expect(sent[0].workflowId).toBeUndefined();else{expect(sent[0].workflowId).toBe('original');expect(sent[0].expectedVersion).toBe(3)}
});

for(const revisionState of ['DRAFT','VALIDATED','HUMAN_REVIEWED'])test(`open editor cannot act on saved ${revisionState} revision`,async({page})=>{
 const digest='a'.repeat(64),sent:Record<string,unknown>[]=[];
 const content={description:'保存的内容',inputs:[],outputs:[],runtimeProfile:{kind:'RUNTIME_PROFILE',resourceId:'runtime',revisionId:'runtime-v1',digest},tasks:[{taskId:'step',name:'原步骤',dependsOn:[],inputs:[],outputs:[],capabilityRequirements:[],references:[],retryLimit:0,timeoutSeconds:300,failurePolicy:'FAIL_WORKFLOW'}]};
 const definition={workflowDefinitionId:'flow',name:'方案',aggregateVersion:3,lifecycleState:revisionState,currentDraftRevisionId:'v1',publishedRevisionId:null,revisions:[{revisionId:'v1',digest,state:revisionState,content}],reviews:revisionState==='HUMAN_REVIEWED'?[{reviewId:'review',digest}]:[],relationships:[],consumers:[]};
 await page.route('**/api/**',route=>{
 const p=new URL(route.request().url()).pathname,reply=(result:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result}});
 if(p.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:test',tenantId:'tenant',securityDomain:'domain'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'csrf'}});
 if(route.request().method()==='POST'){sent.push(route.request().postDataJSON());return reply({workflowId:'flow',commandKey:sent.at(-1)!.commandKey,action:sent.at(-1)!.action})}
 if(p.endsWith('/workflows'))return reply({items:[{workflowDefinitionId:'flow'}]});
 if(p.endsWith('/authoring'))return reply({definition,productProjection:{},technicalProjection:{}});
 return reply({items:[],entries:[],rejectedResources:0});
 });
 await page.goto('/workflow-definitions?resourceId=flow');
 const action=page.getByRole('button',{name:revisionState==='DRAFT'?'验证方案':revisionState==='VALIDATED'?'确认复核':'发布方案',exact:true});
 if(revisionState!=='DRAFT')await page.getByRole('button',{name:'验证与发布',exact:true}).click();
 if(revisionState==='VALIDATED'){await expect(action).toBeDisabled();await page.getByLabel('复核说明',{exact:true}).fill('   ');await expect(action).toBeDisabled();await page.getByLabel('复核说明',{exact:true}).fill('已核对步骤依赖及固定资源。')}
 await expect(action).toBeEnabled();await page.getByRole('button',{name:'编辑方案',exact:true}).click();await page.getByRole('button',{name:'执行步骤',exact:true}).click();await page.getByLabel('步骤名称',{exact:true}).fill('尚未保存的新步骤');if(revisionState!=='DRAFT')await page.getByRole('button',{name:'验证与发布',exact:true}).click();await expect(action).toBeDisabled();expect(sent).toHaveLength(0);
 await page.getByRole('button',{name:'关闭编写器并保留权威版本',exact:true}).click();await expect(action).toBeEnabled();await action.click();await expect.poll(()=>sent.length).toBe(1);expect(sent[0].expectedVersion).toBe(3);
 if(revisionState==='VALIDATED'){expect(sent[0].reason).toBe('已核对步骤依赖及固定资源。');expect(sent[0].digest).toBe(digest)}
});
