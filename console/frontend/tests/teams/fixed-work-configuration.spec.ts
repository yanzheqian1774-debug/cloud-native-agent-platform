import {test,expect,type Page} from '@playwright/test';
import {createHash} from 'node:crypto';
import {fixture as sessionFixture,principal} from '../helpers/resourceMaintenanceFixture';
import type {FixedCommand,FixedItem,FixedResult} from '../../src/api/fixedWorkDrafts';
const canonical=(v:unknown):unknown=>typeof v==='string'?v.normalize('NFC'):Array.isArray(v)?v.map(canonical):v&&typeof v==='object'?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a<b?-1:1).map(([k,x])=>[k,canonical(x)])):v;
const hash=(v:unknown)=>createHash('sha256').update(JSON.stringify(canonical(v))).digest('hex');
const record={schemaVersion:'team-definition.v1',scope:{namespace:principal.tenantId,security_domain:principal.securityDomain},team_id:'team:handover',revision_id:'team-revision:1',title:'服务交接团队',goal:'核对交接资料',owner_id:principal.principalId,members:[],predecessor_revision_id:null};
const team={teamId:record.team_id,revisionId:record.revision_id,digest:hash(record)};
const direct='/teams?'+new URLSearchParams({view:'routines',fixedTeam:team.teamId,fixedRevision:team.revisionId,fixedDigest:team.digest,q:'服务'});
const envelope=(result:unknown)=>({schemaVersion:'workbench-operation.v1',result,continuationIds:[]});
async function fixture(page:Page){
 await sessionFixture(page,true);
 const state={activity:false,activityFail:false,items:[] as FixedItem[],posts:[] as FixedCommand[],canSave:true,lose:false,unavailable:false,holdList:false,listHeld:false,releaseList:null as null|(()=>void)};
 await page.route('**/api/workbench/v1/teams**',async route=>{
  const path=decodeURIComponent(new URL(route.request().url()).pathname),body=route.request().method()==='POST'?route.request().postDataJSON() as FixedCommand:null;
  if(path.includes('/fixed-work-drafts')){
   if(path.endsWith('/activity')){const item=state.items[0];return state.activityFail||!item?route.fulfill({status:503,json:{reasonCode:'FIXED_WORK_ACTIVITY_UNAVAILABLE'}}):route.fulfill({json:envelope({workId:item.draft.workId,revisionId:item.draft.revisionId,workDigest:item.digest,windowLimit:50,automaticTriggerStatus:'NOT_OBSERVED',items:state.activity?[{eventId:'cycle:1',preparationDigest:'a'.repeat(64),runId:'run:1',recordedAt:'2026-11-14T02:00:00Z',state:'RECOVERY_REQUIRED',aggregateVersion:3}]:[]})})}

   if(state.unavailable)return route.fulfill({status:503,json:{reasonCode:'FIXED_WORK_AUTHORING_UNAVAILABLE'}});
   if(body){state.posts.push(body);if(!state.canSave)return route.fulfill({status:403,json:{reasonCode:'FIXED_WORK_AUTHORING_NOT_AUTHORIZED'}});
    let item=state.items.find(i=>i.draft.workId===body.workId&&i.draft.revisionId===body.revisionId);
    if(!item){const draft={schemaVersion:'fixed-work-draft.v1' as const,state:'DRAFT_ONLY' as const,team,workId:body.workId,revisionId:body.revisionId,predecessorRevisionId:body.predecessorRevisionId,aggregateVersion:body.expectedVersion+1,title:body.title,instruction:body.instruction,trigger:body.trigger,createdBy:principal.principalId,createdAt:'2026-11-14T00:00:00+00:00'};item={draft,digest:hash(draft)};state.items=state.items.filter(i=>i.draft.workId!==body.workId);state.items.push(item)}
    if(state.lose){state.lose=false;return route.abort('failed')}
    const result:FixedResult={...item,aggregateVersion:item.draft.aggregateVersion,executionEnabled:false,authorityGranted:false,triggerCreated:false,validation:'CONFIGURATION_STRUCTURE_ONLY'};return route.fulfill({status:201,json:envelope(result)});
   }
   if(path.endsWith('/fixed-work-drafts')&&state.holdList){state.listHeld=true;await new Promise<void>(resolve=>{state.releaseList=resolve})}
   if(path.endsWith('/fixed-work-drafts'))return route.fulfill({json:envelope({items:state.items,team,nextCursor:null,configurationCanSave:state.canSave,executionEnabled:false,authorityGranted:false,triggerCreated:false})});
   const item=state.items.find(i=>path.endsWith('/'+i.draft.workId+'/revisions/'+i.draft.revisionId));
   return item?route.fulfill({json:envelope({...item,aggregateVersion:item.draft.aggregateVersion,executionEnabled:false,authorityGranted:false,triggerCreated:false,validation:'CONFIGURATION_STRUCTURE_ONLY'})}):route.fulfill({status:404,json:{reasonCode:'FIXED_WORK_DRAFT_NOT_FOUND'}});
  }
  if(path.endsWith('/teams'))return route.fulfill({json:envelope({items:[{...team,title:record.title,memberCount:0,ownerId:principal.principalId,aggregateVersion:1}],nextCursor:null})});
  return route.fulfill({json:envelope({revision:record,digest:team.digest,aggregateVersion:1,headRevisionId:record.revision_id})});
 });
 return state;
}
async function draft(page:Page){await page.getByRole('button',{name:'新增固定工作配置',exact:true}).click();const fields=page.getByText('展开核对与修正字段',{exact:true});if(await fields.count())await fields.click();await page.getByLabel('工作名称',{exact:true}).fill('工作日交接核查');await page.getByLabel('工作说明',{exact:true}).fill('每个工作日上午检查服务交接资料，列出缺失项。');}

async function previewSave(page:Page){const preview=page.getByRole('button',{name:'预览本次安排',exact:true});if(await preview.isVisible())await preview.click();await page.getByRole('button',{name:'确认保存配置',exact:true}).click();}

test('real directory selection save and server rediscovery after browser storage cleared',async({page},testInfo)=>{
 const state=await fixture(page);await page.goto('/teams?view=routines');await page.getByRole('button',{name:'查看此团队的固定工作',exact:true}).click();await draft(page);await previewSave(page);await expect(page.getByText('配置已保存。自动触发未启用，没有启动执行。',{exact:true})).toBeVisible();expect(state.posts).toHaveLength(1);
 await page.evaluate(()=>sessionStorage.clear());await page.reload();await expect(page.getByRole('heading',{name:'工作日交接核查',exact:true})).toBeVisible();await page.getByRole('button',{name:'查看配置',exact:true}).click();await expect(page.getByLabel('工作说明',{exact:true})).toHaveValue('每个工作日上午检查服务交接资料，列出缺失项。');expect(state.posts).toHaveLength(1);await page.screenshot({path:testInfo.outputPath('fixed-work-desktop.png'),fullPage:true});await page.getByRole('region',{name:'固定工作配置说明',exact:true}).screenshot({path:testInfo.outputPath('fixed-work-editor.png')});await page.getByLabel('工作说明',{exact:true}).fill('工作日检查服务交接资料，并按负责人分组。');await previewSave(page);await expect(page.getByText('配置已保存。自动触发未启用，没有启动执行。',{exact:true})).toBeVisible();expect(state.posts).toHaveLength(2);expect(state.posts[1].workId).toBe(state.posts[0].workId);expect(state.posts[1].predecessorRevisionId).toBe(state.posts[0].revisionId);expect(state.posts[1].expectedVersion).toBe(1);
 await page.getByRole('link',{name:'返回所选团队',exact:true}).click();await expect(page).toHaveURL(/team=team%3Ahandover&revision=team-revision%3A1/);
});

test('READ-only lists saved configuration with no mutation controls',async({page})=>{
 const state=await fixture(page);await page.goto(direct);await draft(page);await previewSave(page);await expect(page.getByText('配置已保存。自动触发未启用，没有启动执行。',{exact:true})).toBeVisible();state.canSave=false;await page.reload();await expect(page.getByText('当前账号仅可查看配置。',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'新增固定工作配置',exact:true})).toHaveCount(0);await page.getByRole('button',{name:'查看配置',exact:true}).click();await expect(page.getByLabel('工作说明',{exact:true})).toBeDisabled();await expect(page.getByRole('button',{name:'确认保存配置',exact:true})).toHaveCount(0);expect(state.posts).toHaveLength(1);
});

test('lost response survives refresh and reads original saved record without repost',async({page})=>{
 const state=await fixture(page);await page.goto(direct);await draft(page);state.lose=true;await previewSave(page);await expect(page.getByRole('button',{name:'核对原保存记录',exact:true})).toBeVisible();await page.reload();await page.getByRole('button',{name:'核对原保存记录',exact:true}).click();await expect(page.getByText('已核对原保存记录，未重复保存。',{exact:true})).toBeVisible();expect(state.posts).toHaveLength(1);
});

test('permission withdrawn before save preserves text and performs no POST',async({page})=>{
 const state=await fixture(page);await page.goto(direct);await draft(page);state.canSave=false;await previewSave(page);await expect(page.getByRole('alert')).toContainText('当前仅可查看配置');await expect(page.getByLabel('工作说明',{exact:true})).toHaveValue('每个工作日上午检查服务交接资料，列出缺失项。');expect(state.posts).toHaveLength(0);
});

test('narrow configuration and unavailable service retain team context and text',async({page},testInfo)=>{
 const state=await fixture(page);await page.setViewportSize({width:390,height:844});await page.goto(direct);await draft(page);state.unavailable=true;await page.getByRole('button',{name:'刷新配置',exact:true}).click();await expect(page.getByRole('alert')).toContainText('暂不可用');await expect(page.getByLabel('工作说明',{exact:true})).toHaveValue('每个工作日上午检查服务交接资料，列出缺失项。');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.screenshot({path:testInfo.outputPath('fixed-work-narrow.png'),fullPage:true});expect(state.posts).toHaveLength(0);await expect(page.getByRole('link',{name:'返回所选团队',exact:true})).toHaveAttribute('href',/q=%E6%9C%8D%E5%8A%A1/);
});


test('invalid event remains editable and saves after explicit correction without a rejected request',async({page})=>{
 const state=await fixture(page);await page.goto(direct);await draft(page);await page.getByLabel('拟采用的触发方式',{exact:true}).selectOption('EVENT');await previewSave(page);await expect(page.getByRole('alert')).toContainText('请填写事件条件说明');expect(state.posts).toHaveLength(0);await expect(page.getByLabel('事件条件说明',{exact:true})).toBeEnabled();await page.getByLabel('事件条件说明',{exact:true}).fill('有新的服务交接资料时');await previewSave(page);await expect(page.getByText('配置已保存。自动触发未启用，没有启动执行。',{exact:true})).toBeVisible();expect(state.posts).toHaveLength(1);
});


test('session invalidation during save preflight cannot continue with a late response',async({page})=>{
 const state=await fixture(page);await page.goto(direct);await draft(page);state.holdList=true;await previewSave(page);await expect.poll(()=>state.listHeld).toBe(true);await page.evaluate(()=>window.dispatchEvent(new Event('workbench-session-expired')));state.releaseList?.();await expect(page.getByRole('alert')).toContainText('登录已失效');expect(state.posts).toHaveLength(0);
});


test('preview and diff are explicit and activity does not invent successful outcome',async({page},testInfo)=>{
 const state=await fixture(page);state.activity=true;await page.goto(direct);await draft(page);
 await page.getByRole('button',{name:'预览本次安排',exact:true}).click();await expect(page.getByRole('region',{name:'本次安排预览'})).toContainText('工作日上午');expect(state.posts).toHaveLength(0);
 await page.getByRole('button',{name:'确认保存配置',exact:true}).click();await expect(page.getByRole('region',{name:'固定工作执行记录'})).toContainText('结果待核实');expect(state.posts).toHaveLength(1);
 await expect(page.getByRole('link',{name:'查看任务与结果'})).toHaveAttribute('href',/work=aaaaaaaa/);
 await page.getByLabel('工作说明',{exact:true}).fill('每个工作日下午检查资料，列出缺失项。');await page.getByRole('button',{name:'预览本次安排',exact:true}).click();const preview=page.getByRole('region',{name:'本次安排预览'});await expect(preview).toContainText('原安排：每个工作日上午');await expect(preview).toContainText('修改为：每个工作日下午');expect(state.posts).toHaveLength(1);await page.screenshot({path:testInfo.outputPath('fixed-work-diff-and-activity.png'),fullPage:true});await page.getByRole('region',{name:'固定工作执行记录'}).scrollIntoViewIfNeeded();await page.screenshot({path:testInfo.outputPath('fixed-work-activity.png'),fullPage:true});
});

test('activity read failure clears prior facts and preserves current draft',async({page})=>{
 const state=await fixture(page);state.activity=true;await page.goto(direct);await draft(page);await previewSave(page);const panel=page.getByRole('region',{name:'固定工作执行记录'});await expect(panel).toContainText('结果待核实');state.activityFail=true;await panel.getByRole('button',{name:'刷新记录'}).click();await expect(panel).toContainText('执行记录暂未读取成功');await expect(panel.getByRole('link',{name:'查看任务与结果'})).toHaveCount(0);await expect(page.getByLabel('工作说明',{exact:true})).toHaveValue('每个工作日上午检查服务交接资料，列出缺失项。');expect(state.posts).toHaveLength(1);
});

test('return coordinates reopen exact server work after local storage cleared',async({page})=>{
 const state=await fixture(page);await page.goto(direct);await draft(page);await previewSave(page);await expect.poll(()=>state.items.length).toBe(1);const item=state.items[0];await page.evaluate(()=>sessionStorage.clear());await page.goto(direct+'&'+new URLSearchParams({openWork:item.draft.workId,openRevision:item.draft.revisionId,openDigest:item.digest}));await expect(page.getByLabel('工作说明',{exact:true})).toHaveValue(item.draft.instruction);expect(state.posts).toHaveLength(1);await expect(page.getByRole('region',{name:'固定工作执行记录'})).toBeVisible();
});

test('fixed read access is explicit and lost response reuses original command after refresh',async({page},testInfo)=>{
 test.skip(!['playwright.fixed-work-read.config.ts','playwright.fixed-work-workflow-integration.config.ts'].some(name=>testInfo.config.configFile.endsWith(name)),'read adapter explicit opt-in only');
 const state=await fixture(page);const reads:{workDigest:string;commandId:string}[]=[];let lose=true;
 await page.route('**/activity-read',async route=>{reads.push(route.request().postDataJSON());if(lose){lose=false;return route.abort('failed')}state.activity=true;return route.fulfill({status:201,json:envelope({state:'READ_READY',workDigest:state.items[0].digest,runId:'run:1',preparationDigest:'a'.repeat(64)})})});
 await page.goto(direct);await draft(page);await previewSave(page);await expect(page.getByRole('button',{name:'读取最近执行与结果',exact:true})).toBeVisible();expect(reads).toHaveLength(0);
 await page.getByRole('button',{name:'读取最近执行与结果',exact:true}).click();await expect(page.getByText('只读访问尚未核对完成。原工作不会因此重跑，可先刷新记录或按原请求继续核对。',{exact:true})).toBeVisible();expect(reads).toHaveLength(1);
 await page.reload();await expect(page.getByRole('button',{name:'按原请求继续核对读取权限',exact:true})).toBeVisible();expect(reads).toHaveLength(1);await page.getByRole('button',{name:'按原请求继续核对读取权限',exact:true}).click();await expect(page.getByRole('heading',{name:'结果待核实',exact:true})).toBeVisible();expect(reads).toHaveLength(2);expect(reads[1]).toEqual(reads[0]);expect(state.posts).toHaveLength(1);await page.getByRole('region',{name:'固定工作执行记录'}).scrollIntoViewIfNeeded();await page.screenshot({path:testInfo.outputPath('fixed-work-explicit-read.png'),fullPage:true});
});

test('fixed read access denial preserves saved work and does not trigger execution',async({page},testInfo)=>{
 test.skip(!['playwright.fixed-work-read.config.ts','playwright.fixed-work-workflow-integration.config.ts'].some(name=>testInfo.config.configFile.endsWith(name)),'read adapter explicit opt-in only');
 const state=await fixture(page);let reads=0;
 await page.route('**/activity-read',route=>{reads++;return route.fulfill({status:403,json:{reasonCode:'RESOURCE_POLICY_WORK_SCOPE_DENIED'}})});
 await page.goto(direct);await draft(page);await previewSave(page);await page.getByRole('button',{name:'读取最近执行与结果',exact:true}).click();await expect(page.getByText('只读访问尚未核对完成。原工作不会因此重跑，可先刷新记录或按原请求继续核对。',{exact:true})).toBeVisible();expect(reads).toBe(1);expect(state.posts).toHaveLength(1);await expect(page.getByLabel('工作说明',{exact:true})).toHaveValue('每个工作日上午检查服务交接资料，列出缺失项。');await expect(page.locator('details code').filter({hasText:'RESOURCE_POLICY_WORK_SCOPE_DENIED'})).toBeHidden();
});

test('fixed read access requires a separate click for a current-record request after owner conflict',async({page},testInfo)=>{
 test.skip(!['playwright.fixed-work-read.config.ts','playwright.fixed-work-workflow-integration.config.ts'].some(name=>testInfo.config.configFile.endsWith(name)),'read adapter explicit opt-in only');
 const state=await fixture(page);const reads:{commandId:string}[]=[];
 await page.route('**/activity-read',route=>{reads.push(route.request().postDataJSON());return reads.length===1?route.fulfill({status:409,json:{reasonCode:'IDEMPOTENCY_PAYLOAD_MISMATCH'}}):route.fulfill({status:201,json:envelope({state:'NO_RECORD',workDigest:state.items[0].digest})})});
 await page.goto(direct);await draft(page);await previewSave(page);await page.getByRole('button',{name:'读取最近执行与结果',exact:true}).click();await expect(page.getByRole('button',{name:'按当前记录重新核对只读权限',exact:true})).toBeVisible();expect(reads).toHaveLength(1);await page.getByRole('button',{name:'按当前记录重新核对只读权限',exact:true}).click();await expect(page.getByText('当前工作版本尚无执行记录。',{exact:true})).toBeVisible();expect(reads).toHaveLength(2);expect(reads[1].commandId).not.toBe(reads[0].commandId);expect(state.posts).toHaveLength(1);
});

test('global routines distinguishes loading from an observed empty team directory',async({page})=>{
 await fixture(page);let release!:()=>void;
 const gate=new Promise<void>(resolve=>{release=resolve});
 await page.route('**/api/workbench/v1/teams?*',async route=>{await gate;await route.fulfill({json:envelope({items:[],nextCursor:null})})});
 await page.goto('/teams?view=routines');
 await expect(page.getByRole('status')).toContainText('正在读取可访问的团队');
 await expect(page.getByText('当前目录未返回可选团队；也可从已可读的团队详情进入。',{exact:true})).toHaveCount(0);
 await expect(page.getByText('固定工作调度尚未接通',{exact:false})).toHaveCount(0);
 release();
 await expect(page.getByText('当前目录未返回可选团队；也可从已可读的团队详情进入。',{exact:true})).toBeVisible();
 await expect(page.getByRole('link',{name:'返回团队目录',exact:true})).toHaveAttribute('href','/teams');
});
