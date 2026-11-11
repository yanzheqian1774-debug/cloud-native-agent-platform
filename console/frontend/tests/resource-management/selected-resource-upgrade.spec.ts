import {test,expect,type Page} from '@playwright/test';
const principal={principalId:'human:upgrade',tenantId:'upgrade-test',securityDomain:'isolated'};
const digest='d'.repeat(64),oldDigest='a'.repeat(64);
const content={description:'明确标记的交互测试技能',capabilities:['READ_DATA'],instructions:'读取合成材料',operations:[],inputSchema:{},outputSchema:{}};
const sourceResource={resourceId:'skill-definition:upgrade-ui',kind:'skill',name:'交互测试技能',aggregateVersion:7,lifecycleState:'PUBLISHED',enabled:true,currentDraftRevisionId:'revision:new',publishedRevisionId:'revision:old',revisions:[{revisionId:'revision:old',state:'PUBLISHED',digest:oldDigest,content},{revisionId:'revision:new',state:'DRAFT',digest,content}],testResults:[],relationships:[],healthObservations:[],discoverySnapshots:[],toolSelections:[]};
const url='/skills?managedResource=skill-definition%3Aupgrade-ui&resourceTab='+encodeURIComponent('版本');
async function setup(page:Page,mode:'success'|'unknown'|'conflict'|'detail-failure',incoming:Record<string,unknown>[]=[],kind:'skill'|'mcp'='skill'){
 const resource=kind==='skill'?sourceResource:{...sourceResource,kind:'mcp',name:'交互测试MCP连接'};
 const commands:{action:string;body:Record<string,unknown>}[]=[];
 const receipt={schemaVersion:'selected-resource-upgrade-receipt.v1',batchId:'fixture-batch',result:{resource:{...(kind==='mcp'?{resourceKind:'mcp'}:{}),identity:resource.resourceId,revisionId:'revision:new',digest},employees:[],capabilities:[]}};
 await page.route('**/api/workbench/v1/**',async route=>{const request=route.request(),path=new URL(request.url()).pathname;
 if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal,csrfToken:'fixture'}});
 if(path.endsWith('/resource-management/'+kind)&&mode==='detail-failure'&&commands.some(c=>c.action==='submit'))return route.fulfill({status:503,json:{reasonCode:'DETAIL_TEMPORARILY_UNAVAILABLE'}});
 if(path.endsWith('/resource-management/'+kind))return route.fulfill({json:{result:{items:[mode==='success'&&commands.some(c=>c.action==='submit')?{...resource,currentDraftRevisionId:null,publishedRevisionId:'revision:new',aggregateVersion:8,revisions:resource.revisions.map(r=>r.revisionId==='revision:new'?{...r,state:'PUBLISHED'}:r)}:resource],subject:principal.principalId,scope:{tenantId:principal.tenantId,securityDomain:principal.securityDomain}}}});
 if(path.endsWith('/resource-directory'))return route.fulfill({json:{result:{items:[],nextCursor:null,subject:principal.principalId,scope:{tenantId:principal.tenantId,securityDomain:principal.securityDomain}}}});
 if(path.endsWith('/impact'))return route.fulfill({json:{result:{current:{revisionId:'revision:new',digest},previousPublished:{revisionId:'revision:old',digest:oldDigest},changes:[],testCoverage:{ready:true,checks:[]},olderTestsNotCurrent:0,authorizedUses:[],truncated:false,dependencies:{incoming,outgoing:[],limitations:[],unresolvedDeclarations:[]}}}});
 if(path.includes('/resource-upgrades/')){const action=path.split('/').at(-1)!;commands.push({action,body:request.postDataJSON()});if(action==='preview')return route.fulfill({json:{result:{reviewDigest:'f'.repeat(64),preview:{employees:[],capabilities:[]}}}});if(action==='receipt')return route.fulfill({json:{result:{state:'COMMITTED',receipt}}});if(mode==='unknown')return route.abort('failed');if(mode==='conflict')return route.fulfill({status:409,json:{detail:{reasonCode:'UPGRADE_PREVIEW_CHANGED'}}});return route.fulfill({json:{result:{receipt,replayed:false}}})}
 return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
 });return commands;
}
async function prepare(page:Page){await page.goto(url);const area=page.getByRole('region',{name:'集中更新选定引用'});await area.getByRole('button',{name:'预览本次更新'}).click();await expect(area.getByRole('button',{name:'确认并整批发布'})).toBeVisible();return area}
test('one confirmation submits once and success depends on receipt only',async({page})=>{const commands=await setup(page,'success'),area=await prepare(page);await area.getByRole('button',{name:'确认并整批发布'}).dblclick();await expect(area.getByRole('heading',{name:'整批发布完成'})).toBeVisible();expect(commands.filter(c=>c.action==='submit')).toHaveLength(1);expect(commands.filter(c=>c.action==='receipt')).toHaveLength(0);await expect(area).toContainText('发布后的资源详情已更新');await expect(area.getByRole('heading',{name:'整批发布完成'})).toBeVisible();await expect(page.getByText('当前为草稿，以下为拟变更内容。',{exact:true})).toHaveCount(0)});
test('unknown submission survives reload and only reads original command',async({page})=>{const commands=await setup(page,'unknown'),area=await prepare(page);await area.getByRole('button',{name:'确认并整批发布'}).click();await expect(area.getByRole('button',{name:'读取原发布结果'})).toBeVisible();await page.reload();await expect(area.getByRole('button',{name:'读取原发布结果'})).toBeVisible();await expect(area.getByRole('button',{name:'确认并整批发布'})).toHaveCount(0);await area.getByRole('button',{name:'读取原发布结果'}).click();await expect(area.getByRole('heading',{name:'整批发布完成'})).toBeVisible();expect(commands.filter(c=>c.action==='submit')).toHaveLength(1);expect(commands.find(c=>c.action==='receipt')?.body).toEqual(commands.find(c=>c.action==='submit')?.body)});
test('known version conflict keeps draft and requires new preview',async({page})=>{const commands=await setup(page,'conflict'),area=await prepare(page);await area.getByRole('button',{name:'确认并整批发布'}).click();await expect(area).toContainText('本次未发布，原发布内容保持不变');await expect(area.getByRole('button',{name:'确认并整批发布'})).toHaveCount(0);await expect(area.getByRole('button',{name:'预览本次更新'})).toBeEnabled();expect(commands.filter(c=>c.action==='submit')).toHaveLength(1)});

test('selection lists published objects, preserves same-name identities and blocks existing drafts',async({page})=>{
 const candidate=(identity:string,revision:string,state:string,hasDraft=false)=>({kind:'EMPLOYEE',identity,revision,state,hasDraft,name:'同名文档助手',readable:true});
 await setup(page,'success',[candidate('one','old','HISTORICAL_REVISION'),candidate('one','current','PUBLISHED'),candidate('two','current','PUBLISHED',true),candidate('two','draft','DRAFT')]);
 await page.goto(url);const area=page.getByRole('region',{name:'集中更新选定引用'});
 await expect(area.getByRole('checkbox')).toHaveCount(2);
 await expect(area.getByRole('checkbox').nth(0)).toBeEnabled();
 await expect(area.getByRole('checkbox').nth(1)).toBeDisabled();
 await expect(area).toContainText('已有草稿，请先处理草稿');
});

test('detail read failure preserves success and retry only reads details',async({page})=>{
 const commands=await setup(page,'detail-failure'),area=await prepare(page);
 await area.getByRole('button',{name:'确认并整批发布'}).click();
 await expect(area.getByRole('heading',{name:'整批发布完成'})).toBeVisible();
 await expect(area).toContainText('整批已发布，部分详情暂未读取');
 await area.getByRole('button',{name:'重新读取发布后详情'}).click();
 await expect(area).toContainText('整批已发布，部分详情暂未读取');
 await expect(area.getByRole('heading',{name:'整批发布完成'})).toBeVisible();
 expect(commands.filter(c=>c.action==='submit')).toHaveLength(1);
 expect(commands.filter(c=>c.action==='receipt')).toHaveLength(0);
});

test('refresh never silently omits an unavailable selected object',async({page})=>{
 const incoming=[{kind:'EMPLOYEE',identity:'employee:selected',revision:'published',state:'PUBLISHED',name:'原先选择的文档助手',readable:true}];
 const commands=await setup(page,'success',incoming);await page.goto(url);
 const area=page.getByRole('region',{name:'集中更新选定引用'});await area.getByRole('checkbox',{name:/原先选择的文档助手/}).check();
 incoming[0].state='HISTORICAL_REVISION';
 await page.getByRole('button',{name:'核对版本与影响',exact:true}).click();
 await expect(area).toContainText('选择仍保留，不会自动略过');
 await area.getByRole('button',{name:'预览本次更新',exact:true}).click();
 await expect(area).toContainText('暂不能生成发布预览');
 expect(commands).toHaveLength(0);
 await expect(area.getByRole('button',{name:/移除不可用选择/})).toBeVisible();
});

for(const mode of ['success','unknown'] as const)test('MCP selected publication retains its type and recovery '+mode,async({page})=>{
 const commands=await setup(page,mode,[],'mcp');
 await page.goto(url.replace('/skills?','/mcp?'));
 const area=page.getByRole('region',{name:'集中更新选定引用'});
 await expect(area).toContainText('发布当前MCP连接');
 await expect(area).toContainText('发布连接配置不代表工具调用已经验证');
 await area.getByRole('button',{name:'预览本次更新'}).click();
 await expect(area).toContainText('MCP连接、0 个数字人');
 await area.getByRole('button',{name:'确认并整批发布'}).click();
 if(mode==='unknown'){
  await expect(area.getByRole('button',{name:'读取原发布结果'})).toBeVisible();
  await page.reload();await area.getByRole('button',{name:'读取原发布结果'}).click();
 }
 await expect(area.getByRole('heading',{name:'整批发布完成'})).toBeVisible();
 expect(commands.filter(c=>c.action==='submit')).toHaveLength(1);
 expect(commands.every(c=>c.body.resourceKind==='mcp')).toBe(true);
 if(mode==='unknown')expect(commands.find(c=>c.action==='receipt')?.body).toEqual(commands.find(c=>c.action==='submit')?.body);
});
