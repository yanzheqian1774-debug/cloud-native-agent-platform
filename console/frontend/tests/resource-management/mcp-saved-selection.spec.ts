import {expect,test,type Page} from '@playwright/test';
import type {SkillMcpResource,DiscoverySnapshot} from '../../src/api/skillMcpResources';

const id='mcp-definition:selection-fixture',oldRevision='revision:old',revision='revision:new';
const oldDigest='a'.repeat(64),digest='b'.repeat(64),snapshotId='snapshot:new';
const principal={principalId:'human:selection-fixture',tenantId:'selection-fixture',securityDomain:'isolated'};
const root='/api/workbench/v1/resource-management/mcp';
const content=(description:string)=>({description,capabilities:['read-summary'],endpoint:'http://127.0.0.1:1/not-used',transport:'streamable_http',authentication:'none',sideEffect:'READ'});
const snapshot=(rid:string,hash:string,sid:string):DiscoverySnapshot=>({revisionId:rid,revisionDigest:hash,snapshotId:sid,digest:'c'.repeat(64),protocolRevision:'2024-11-05',catalog:{tools:[{name:'delivery.summary',description:'交付摘要'},{name:'sales.summary',description:'销售摘要'}],resources:[],prompts:[]},capturedAt:'2026-11-28T00:00:00Z'});
type Selection=SkillMcpResource['toolSelections'][number];
const selection=(overrides:Partial<Selection>={}):Selection=>({selectionId:'selection:old',revisionId:oldRevision,revisionDigest:oldDigest,snapshotId:'snapshot:old',toolNames:['delivery.summary','sales.summary'],invocationAuthority:'NOT_GRANTED',...overrides});
function resource():SkillMcpResource{return {resourceId:id,kind:'mcp',name:'MCP选择版本核验',aggregateVersion:5,lifecycleState:'DRAFT',enabled:true,archived:false,currentDraftRevisionId:revision,publishedRevisionId:oldRevision,revisions:[{revisionId:oldRevision,predecessorRevisionId:null,digest:oldDigest,state:'PUBLISHED',content:content('旧版只读说明'),createdAt:'2026-11-27T00:00:00Z'},{revisionId:revision,predecessorRevisionId:oldRevision,digest,state:'DRAFT',content:content('新版只读说明'),createdAt:'2026-11-28T00:00:00Z'}],reviews:[],relationships:[],bindings:[],invocations:[],savedTests:[],testResults:[],discoverySnapshots:[snapshot(oldRevision,oldDigest,'snapshot:old'),snapshot(revision,digest,snapshotId)],toolSelections:[selection()],healthObservations:[],driftRecords:[],limitations:[]};}
async function fixture(page:Page,ownedAccess=false){
 const state={resource:resource(),posts:[] as Record<string,unknown>[],gets:[] as string[],unknown:false,readable:false,managed:!ownedAccess,receipt:null as Record<string,unknown>|null};
 if(ownedAccess){state.resource.currentDraftRevisionId=null;state.resource.publishedRevisionId=revision;state.resource.lifecycleState='PUBLISHED';state.resource.revisions[1].state='PUBLISHED'}
 await page.route('**/api/workbench/v1/**',async route=>{
  const req=route.request(),path=decodeURIComponent(new URL(req.url()).pathname),ok=(value:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:value}});
  if(req.method()==='GET')state.gets.push(path);
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal,session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'selection-csrf'}});
  if(path===root)return ok({subject:principal.principalId,scope:{tenantId:principal.tenantId,securityDomain:principal.securityDomain},items:state.managed?[state.resource]:[],accessCandidates:ownedAccess&&!state.managed?[{kind:'mcp',identity:id,revisionId:revision,digest}]:[]});
  if(path===root+'/commands'){
   const body=req.postDataJSON();state.posts.push(body);expect(ownedAccess?['access','select-tools','health']:['select-tools','health']).toContain(body.action);expect(req.headers()['x-csrf-token']).toBe('selection-csrf');
   if(body.action==='access'){expect(body.identity).toBe(id);expect(body.expectedVersion).toBeUndefined();state.managed=true}
   if(body.action==='select-tools')state.resource.toolSelections.push(selection({selectionId:'selection:current',revisionId:revision,revisionDigest:digest,snapshotId:body.snapshotId,toolNames:body.toolNames}));if(body.action!=='access')state.resource.aggregateVersion++;
   state.receipt={schemaVersion:'resource-management-receipt.v1',kind:'mcp',action:body.action,identity:id,commandKey:body.commandKey,aggregateVersion:state.resource.aggregateVersion,resource:structuredClone(state.resource),executionStarted:false,modelCalls:0,credentialMaterial:'NOT_INCLUDED'};
   if(state.unknown)return route.abort('connectionreset');return ok(state.receipt);
  }
  if(path.startsWith(root+'/commands/'))return state.readable&&state.receipt?ok(state.receipt):route.fulfill({status:503,json:{reasonCode:'FIXTURE_RECEIPT_UNAVAILABLE'}});
  if(path==='/api/workbench/v1/resource-directory'&&ownedAccess)return ok({items:[{kind:'mcp',identity:id,revisionId:revision,digest,name:state.resource.name,state:'PUBLISHED',enabled:true,isCurrentPublished:true,isCurrentDraft:false,executionReady:false,policyReviewed:true,createdAt:null}],subject:principal.principalId,scope:{tenantId:principal.tenantId,securityDomain:principal.securityDomain},nextCursor:null,executionAuthority:'NONE'});
  if(path.includes('/resource-directory/'))return ok({items:[],nextCursor:null,scope:{tenantId:principal.tenantId,securityDomain:principal.securityDomain}});
  return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
 });
 return state;
}
const href=(extra:Record<string,string>={})=>'/mcp?'+new URLSearchParams({managedResource:id,viewRevision:revision,resourceSection:'content',resourceTab:'执行设置',...extra});
const saved=(page:Page)=>page.locator('.rm-connection > p').filter({hasText:/^已保存选择：/});
const history=(page:Page)=>page.locator('.rm-connection > details').filter({has:page.getByText('工具选择历史（不作为当前修订已保存依据）',{exact:true})});

test('new snapshot never presents old revision selection as current or auto checks tools',async({page})=>{
 const state=await fixture(page);await page.goto(href());
 await expect(saved(page)).toHaveText('已保存选择：尚未选择');
 await expect(page.getByRole('checkbox',{name:/delivery.summary/})).not.toBeChecked();await expect(page.getByRole('checkbox',{name:/sales.summary/})).not.toBeChecked();
 await expect(page.getByRole('button',{name:'保存工具选择',exact:true})).toBeDisabled();
 await history(page).locator('summary').first().click();await expect(history(page)).toContainText('delivery.summary、sales.summary');
 await page.reload();await expect(saved(page)).toHaveText('已保存选择：尚未选择');expect(state.posts).toEqual([]);expect(state.resource.toolSelections).toHaveLength(1);
});

for(const [name,entry] of [
 ['older snapshot of same revision',selection({revisionId:revision,revisionDigest:digest,snapshotId:'snapshot:previous'})],
 ['wrong revision despite same snapshot',selection({snapshotId,revisionDigest:digest})],
 ['wrong digest despite same revision and snapshot',selection({revisionId:revision,snapshotId,revisionDigest:'f'.repeat(64)})],
 ['legacy selection without exact revision proof',selection({revisionId:undefined,revisionDigest:undefined,snapshotId})],
] as const)test(name+' is history only',async({page})=>{
 const state=await fixture(page);state.resource.toolSelections=[entry];await page.goto(href());await expect(saved(page)).toHaveText('已保存选择：尚未选择');expect(state.posts).toEqual([]);
});

test('current exact saved selection echoes checks after unrelated history and refresh',async({page})=>{
 const state=await fixture(page);state.resource.toolSelections=[selection({selectionId:'selection:current',revisionId:revision,revisionDigest:digest,snapshotId,toolNames:['sales.summary']}),selection()];state.resource.discoverySnapshots.push(snapshot(oldRevision,oldDigest,'snapshot:late-old'));
 await page.goto(href());await expect(saved(page)).toHaveText('已保存选择：sales.summary');
 await expect(page.getByRole('checkbox',{name:/sales.summary/})).toBeChecked();
 await page.reload();await expect(saved(page)).toHaveText('已保存选择：sales.summary');await expect(page.getByRole('checkbox',{name:/sales.summary/})).toBeChecked();expect(state.posts).toEqual([]);expect(state.resource.toolSelections).toHaveLength(2);
});

test('saving an explicit current selection records only current tuple and keeps old history',async({page})=>{
 const state=await fixture(page);await page.goto(href());await page.getByRole('checkbox',{name:/sales.summary/}).check();await page.getByRole('button',{name:'保存工具选择',exact:true}).click();
 await expect(saved(page)).toHaveText('已保存选择：sales.summary');await expect(page.getByRole('checkbox',{name:/sales.summary/})).toBeChecked();expect(state.posts).toHaveLength(1);expect(state.posts[0]).toMatchObject({snapshotId,toolNames:['sales.summary'],expectedVersion:5});
 expect(state.resource.toolSelections[0]).toEqual(selection());await page.reload();await expect(saved(page)).toHaveText('已保存选择：sales.summary');expect(state.posts).toHaveLength(1);
});

test('historical content and refresh preserve old exact view without pretending a current selection',async({page})=>{
 const state=await fixture(page);state.resource.revisions.splice(1,0,{revisionId:'revision:published',predecessorRevisionId:oldRevision,digest:'d'.repeat(64),state:'PUBLISHED',content:content('当前发布说明'),createdAt:'2026-11-27T12:00:00Z'});state.resource.publishedRevisionId='revision:published';await page.goto(href({viewRevision:oldRevision,resourceTab:'',resourceSection:'content'}));
 await expect(page.getByRole('heading',{name:'历史内容',exact:true})).toBeVisible();await expect(page.getByRole('tabpanel',{name:'内容与定义',exact:true})).toContainText('旧版只读说明');await expect(saved(page)).toHaveCount(0);
 await page.reload();await expect(page.getByRole('heading',{name:'历史内容',exact:true})).toBeVisible();expect(new URL(page.url()).searchParams.get('viewRevision')).toBe(oldRevision);
 await page.goto(href());await expect(saved(page)).toHaveText('已保存选择：尚未选择');expect(state.posts).toEqual([]);expect(state.resource.toolSelections[0]).toEqual(selection());
});

test('unknown selection retains original pending key and reads only that receipt after refresh',async({page})=>{
 const state=await fixture(page);state.unknown=true;await page.goto(href());await page.getByRole('checkbox',{name:/sales.summary/}).check();await page.getByRole('button',{name:'保存工具选择',exact:true}).click();
 await expect(page.getByRole('button',{name:'读取原操作结果',exact:true})).toBeVisible();const key=state.posts[0].commandKey;
 await expect(page.getByRole('button',{name:'发现工具与资料',exact:true})).toBeDisabled();
 await page.reload();await expect(saved(page)).toHaveText('已保存选择：sales.summary');await expect(page.getByRole('button',{name:'读取原操作结果',exact:true})).toBeVisible();
 state.readable=true;await page.getByRole('button',{name:'读取原操作结果',exact:true}).click();await expect(page.getByRole('button',{name:'读取原操作结果',exact:true})).toHaveCount(0);
 expect(state.posts).toHaveLength(1);expect(state.gets.filter(p=>p.includes('/commands/')).every(p=>p.endsWith(String(key)))).toBe(true);await expect(saved(page)).toHaveText('已保存选择：sales.summary');
});


test('unsaved manual checks survive same-snapshot readback and browser reload restores only saved state',async({page})=>{
 const state=await fixture(page);state.resource.toolSelections.push(selection({selectionId:'selection:current',revisionId:revision,revisionDigest:digest,snapshotId,toolNames:['sales.summary']}));
 await page.goto(href());await expect(page.getByRole('checkbox',{name:/sales.summary/})).toBeChecked();
 await page.getByRole('checkbox',{name:/sales.summary/}).uncheck();await page.getByRole('checkbox',{name:/delivery.summary/}).check();
 await expect(page.getByText('本次勾选尚未保存，不会改变已保存选择。',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'测试连接',exact:true}).click();await expect(page.locator('.rm-success')).toContainText('连接检查结果已记录');
 await expect(page.getByRole('checkbox',{name:/delivery.summary/})).toBeChecked();await expect(page.getByRole('checkbox',{name:/sales.summary/})).not.toBeChecked();
 await expect(saved(page)).toHaveText('已保存选择：sales.summary');expect(state.posts.map(x=>x.action)).toEqual(['health']);
 await page.reload();await expect(page.getByRole('checkbox',{name:/sales.summary/})).toBeChecked();await expect(page.getByRole('checkbox',{name:/delivery.summary/})).not.toBeChecked();expect(state.posts.map(x=>x.action)).toEqual(['health']);
});

for(const width of [1280,390])test('compact saved MCP tool rows at '+width,async({page},info)=>{
 const state=await fixture(page);state.resource.toolSelections.push(selection({selectionId:'selection:current',revisionId:revision,revisionDigest:digest,snapshotId,toolNames:['sales.summary']}));
 await page.setViewportSize({width,height:900});await page.goto(href());await expect(saved(page)).toHaveText('已保存选择：sales.summary');
 const rows=page.locator('.rm-tool-option');await expect(rows).toHaveCount(2);
 for(const row of await rows.all()){
  const box=await row.boundingBox(),input=await row.locator('input').boundingBox(),text=await row.locator('strong').boundingBox();expect(box).not.toBeNull();expect(input).not.toBeNull();expect(text).not.toBeNull();
  expect(box!.height).toBeLessThanOrEqual(48);expect(input!.width).toBeLessThanOrEqual(18);expect(Math.abs(input!.y+input!.height/2-text!.y-text!.height/2)).toBeLessThanOrEqual(7);
 }
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.locator('.rm-connection').screenshot({path:info.outputPath('mcp-selection-'+width+'.png')});
 await page.screenshot({path:info.outputPath('mcp-selection-page-'+width+'.png'),fullPage:true});expect(state.posts).toEqual([]);
});


test('new snapshot does not silently transfer an unsaved choice',async({page})=>{
 const state=await fixture(page);await page.goto(href());await page.getByRole('checkbox',{name:/sales.summary/}).check();
 state.resource.discoverySnapshots.push(snapshot(revision,digest,'snapshot:next'));
 await page.getByRole('button',{name:'测试连接',exact:true}).click();await expect(page.locator('.rm-success')).toContainText('连接检查结果已记录');
 await expect(page.getByRole('checkbox',{name:/sales.summary/})).not.toBeChecked();await expect(saved(page)).toHaveText('已保存选择：尚未选择');
 await expect(page.getByText('先前未保存的勾选属于另一版本或发现记录，未应用到当前列表。',{exact:true})).toBeVisible();expect(state.posts.map(x=>x.action)).toEqual(['health']);
});

test('returning manual checks to saved state releases dirty override',async({page})=>{
 const state=await fixture(page);state.resource.toolSelections.push(selection({selectionId:'selection:current',revisionId:revision,revisionDigest:digest,snapshotId,toolNames:['sales.summary']}));
 await page.goto(href());await page.getByRole('checkbox',{name:/sales.summary/}).uncheck();await page.getByRole('checkbox',{name:/sales.summary/}).check();
 await expect(page.getByText('本次勾选尚未保存，不会改变已保存选择。',{exact:true})).toHaveCount(0);
 state.resource.toolSelections.push(selection({selectionId:'selection:latest',revisionId:revision,revisionDigest:digest,snapshotId,toolNames:['delivery.summary']}));
 await page.getByRole('button',{name:'测试连接',exact:true}).click();await expect(page.locator('.rm-success')).toContainText('连接检查结果已记录');
 await expect(page.getByRole('checkbox',{name:/delivery.summary/})).toBeChecked();await expect(page.getByRole('checkbox',{name:/sales.summary/})).not.toBeChecked();expect(state.posts.map(x=>x.action)).toEqual(['health']);
});


for(const unknown of [false,true])test('composed owned MCP qualification to exact selection '+(unknown?'unknown recovery':'save and refresh'),async({page},info)=>{
 const state=await fixture(page,true);
 await page.goto('/mcp?'+new URLSearchParams({returnConversation:'chat:origin'}));
 const qualify=page.getByRole('link',{name:'核对维护资格',exact:true});
 await expect(qualify).toBeVisible();expect(state.posts).toEqual([]);
 await qualify.click();
 expect(new URL(page.url()).searchParams.get('returnConversation')).toBe('chat:origin');
 const recover=page.getByRole('button',{name:'核对原资源访问资格',exact:true});
 await expect(recover).toBeVisible();expect(state.posts).toEqual([]);
 await recover.click();
 await page.getByRole('tab',{name:'内容与定义',exact:true}).click();
 await page.getByRole('button',{name:'连接与工具检查',exact:true}).click();
 await expect(saved(page)).toHaveText('已保存选择：尚未选择');
 await expect(page.getByRole('checkbox',{name:/sales.summary/})).not.toBeChecked();
 expect(state.posts.map(x=>x.action)).toEqual(['access']);
 state.unknown=unknown;
 await page.getByRole('checkbox',{name:/sales.summary/}).check();
 await page.getByRole('button',{name:'保存工具选择',exact:true}).click();
 if(unknown)await expect(page.getByRole('button',{name:'读取原操作结果',exact:true})).toBeVisible();
 else await expect(saved(page)).toHaveText('已保存选择：sales.summary');
 const key=state.posts[1].commandKey;
 expect(state.posts[1]).toMatchObject({action:'select-tools',identity:id,expectedVersion:5,snapshotId,toolNames:['sales.summary']});
 expect(state.resource.toolSelections[0]).toEqual(selection());
 await page.reload();
 await expect(saved(page)).toHaveText('已保存选择：sales.summary');
 await expect(page.getByRole('checkbox',{name:/sales.summary/})).toBeChecked();
 if(unknown){
  await expect(page.getByRole('button',{name:'发现工具与资料',exact:true})).toBeDisabled();
  state.readable=true;await page.getByRole('button',{name:'读取原操作结果',exact:true}).click();
  await expect(page.getByRole('button',{name:'读取原操作结果',exact:true})).toHaveCount(0);
  expect(state.gets.filter(p=>p.includes('/commands/')).every(p=>p.endsWith(String(key)))).toBe(true);
 }
 expect(state.posts.map(x=>x.action)).toEqual(['access','select-tools']);
 expect(state.resource.toolSelections).toHaveLength(2);
 if(unknown)await page.setViewportSize({width:390,height:844});
 await page.locator('.rm-connection').screenshot({path:info.outputPath('composed-mcp-'+(unknown?'390':'desktop')+'.png')});
});
