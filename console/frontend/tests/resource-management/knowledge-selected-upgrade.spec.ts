import {test,expect,type Page} from '@playwright/test';
const principal={principalId:'human:knowledge-upgrade',tenantId:'test',securityDomain:'isolated'},scope={tenantId:'test',securityDomain:'isolated'};
const identity='knowledge:test',oldDigest='a'.repeat(64),digest='b'.repeat(64),url='/knowledge?managedResource=knowledge%3Atest';
async function setup(page:Page,mode:'success'|'unknown'|'references-failed'|'wrong-version'){
 const commands:{action:string;body:Record<string,unknown>}[]=[];let published=false;
 const resource=()=>({knowledgeId:identity,name:'知识整批更新测试',aggregateVersion:published?10:5,lifecycleState:'PUBLISHED',currentDraftRevisionId:published?null:'revision:new',publishedRevisionId:published?'revision:new':'revision:old',activeIndexSnapshotId:null,revisions:[{revisionId:'revision:old',digest:oldDigest,state:'PUBLISHED',content:{documents:[{chunks:[{content:'原始合成资料'}]}]}},{revisionId:'revision:new',digest,state:published?'PUBLISHED':'DRAFT',content:{documents:[{chunks:[{content:'更新合成资料'}]}]}}]});
 const receipt={schemaVersion:'selected-resource-upgrade-receipt.v1',batchId:'test-batch',result:{resource:{resourceKind:'knowledge',identity,revisionId:'revision:new',digest},employees:[],capabilities:[]}};
 await page.route('**/api/workbench/v1/**',async route=>{const r=route.request(),path=new URL(r.url()).pathname;
 if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal,csrfToken:'test'}});
 if(path.endsWith('/definition-management/knowledge'))return route.fulfill({json:{result:{subject:principal.principalId,scope,items:[resource()]}}});
 if(path.endsWith('/resource-directory'))return route.fulfill({json:{result:{subject:principal.principalId,scope,items:[],nextCursor:null}}});
 if(path.endsWith('/references')){if(mode==='references-failed')return route.fulfill({status:503,json:{reasonCode:'UNAVAILABLE'}});const revision=decodeURIComponent(path.split('/').at(-2)!);return route.fulfill({json:{result:{kind:'knowledge',identity,revision:mode==='wrong-version'?'revision:wrong':revision,digest:revision==='revision:old'?oldDigest:digest,subject:principal.principalId,scope,dependencies:{incoming:[]}}}})}
 if(path.includes('/resource-upgrades/')){const action=path.split('/').at(-1)!;commands.push({action,body:r.postDataJSON()});if(action==='preview')return route.fulfill({json:{result:{reviewDigest:'c'.repeat(64),preview:{employees:[],capabilities:[]}}}});if(action==='submit'){published=true;if(mode==='unknown')return route.abort('failed');return route.fulfill({json:{result:{receipt}}})}return route.fulfill({json:{result:{state:'COMMITTED',receipt}}})}
 return route.fulfill({status:404,json:{reasonCode:'TEST_ONLY'}});
 });return commands;
}
for(const mode of ['success','unknown'] as const)test('knowledge batch '+mode,async({page})=>{
 const commands=await setup(page,mode);await page.goto(url);const area=page.getByRole('region',{name:'集中更新选定引用'});
 await expect(area).toContainText('不会自动重建索引');await area.getByRole('button',{name:'预览本次更新'}).click();await area.getByRole('button',{name:'确认并整批发布'}).click();
 if(mode==='unknown'){await expect(area.getByRole('button',{name:'读取原发布结果'})).toBeVisible();await expect(page.getByRole('button',{name:'核验并发布',exact:true})).toBeDisabled();await page.reload();await area.getByRole('button',{name:'读取原发布结果'}).click()}
 await expect(area.getByRole('heading',{name:'整批发布完成'})).toBeVisible();await expect(area).toContainText('发布后的资源详情已更新');expect(commands.filter(c=>c.action==='submit')).toHaveLength(1);expect(commands.every(c=>c.body.resourceKind==='knowledge')).toBe(true);if(mode==='unknown')expect(commands.find(c=>c.action==='receipt')?.body).toEqual(commands.find(c=>c.action==='submit')?.body);
 await page.getByRole('button',{name:'返回维护目录',exact:true}).click();await expect(page).not.toHaveURL(/managedResource/);
});
for(const mode of ['references-failed','wrong-version'] as const)test('knowledge blocks '+mode,async({page})=>{
 const commands=await setup(page,mode);await page.goto(url);await expect(page.getByText('引用信息暂不可读，不能据此判断没有引用。',{exact:false})).toBeVisible();await expect(page.getByRole('button',{name:'预览本次更新'})).toBeDisabled();expect(commands).toEqual([]);
});
