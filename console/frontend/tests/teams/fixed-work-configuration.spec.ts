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
 const state={items:[] as FixedItem[],posts:[] as FixedCommand[],canSave:true,lose:false,unavailable:false,holdList:false,listHeld:false,releaseList:null as null|(()=>void)};
 await page.route('**/api/workbench/v1/teams**',async route=>{
  const path=decodeURIComponent(new URL(route.request().url()).pathname),body=route.request().method()==='POST'?route.request().postDataJSON() as FixedCommand:null;
  if(path.includes('/fixed-work-drafts')){
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
async function draft(page:Page){await page.getByRole('button',{name:'新增固定工作配置',exact:true}).click();await page.getByLabel('工作名称',{exact:true}).fill('工作日交接核查');await page.getByLabel('工作说明',{exact:true}).fill('每个工作日上午检查服务交接资料，列出缺失项。');}

test('real directory selection save and server rediscovery after browser storage cleared',async({page},testInfo)=>{
 const state=await fixture(page);await page.goto('/teams?view=routines');await page.getByRole('button',{name:'查看此团队的固定工作',exact:true}).click();await draft(page);await page.getByRole('button',{name:'确认保存配置',exact:true}).click();await expect(page.getByText('配置已保存。自动触发未启用，没有启动执行。',{exact:true})).toBeVisible();expect(state.posts).toHaveLength(1);
 await page.evaluate(()=>sessionStorage.clear());await page.reload();await expect(page.getByRole('heading',{name:'工作日交接核查',exact:true})).toBeVisible();await page.getByRole('button',{name:'查看配置',exact:true}).click();await expect(page.getByLabel('工作说明',{exact:true})).toHaveValue('每个工作日上午检查服务交接资料，列出缺失项。');expect(state.posts).toHaveLength(1);await page.screenshot({path:testInfo.outputPath('fixed-work-desktop.png'),fullPage:true});await page.getByRole('region',{name:'固定工作配置说明',exact:true}).screenshot({path:testInfo.outputPath('fixed-work-editor.png')});await page.getByLabel('工作说明',{exact:true}).fill('工作日检查服务交接资料，并按负责人分组。');await page.getByRole('button',{name:'确认保存配置',exact:true}).click();await expect(page.getByText('配置已保存。自动触发未启用，没有启动执行。',{exact:true})).toBeVisible();expect(state.posts).toHaveLength(2);expect(state.posts[1].workId).toBe(state.posts[0].workId);expect(state.posts[1].predecessorRevisionId).toBe(state.posts[0].revisionId);expect(state.posts[1].expectedVersion).toBe(1);
 await page.getByRole('link',{name:'返回所选团队',exact:true}).click();await expect(page).toHaveURL(/team=team%3Ahandover&revision=team-revision%3A1/);
});

test('READ-only lists saved configuration with no mutation controls',async({page})=>{
 const state=await fixture(page);await page.goto(direct);await draft(page);await page.getByRole('button',{name:'确认保存配置',exact:true}).click();await expect(page.getByText('配置已保存。自动触发未启用，没有启动执行。',{exact:true})).toBeVisible();state.canSave=false;await page.reload();await expect(page.getByText('当前账号仅可查看配置。',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'新增固定工作配置',exact:true})).toHaveCount(0);await page.getByRole('button',{name:'查看配置',exact:true}).click();await expect(page.getByLabel('工作说明',{exact:true})).toBeDisabled();await expect(page.getByRole('button',{name:'确认保存配置',exact:true})).toHaveCount(0);expect(state.posts).toHaveLength(1);
});

test('lost response survives refresh and reads original saved record without repost',async({page})=>{
 const state=await fixture(page);await page.goto(direct);await draft(page);state.lose=true;await page.getByRole('button',{name:'确认保存配置',exact:true}).click();await expect(page.getByRole('button',{name:'核对原保存记录',exact:true})).toBeVisible();await page.reload();await page.getByRole('button',{name:'核对原保存记录',exact:true}).click();await expect(page.getByText('已核对原保存记录，未重复保存。',{exact:true})).toBeVisible();expect(state.posts).toHaveLength(1);
});

test('permission withdrawn before save preserves text and performs no POST',async({page})=>{
 const state=await fixture(page);await page.goto(direct);await draft(page);state.canSave=false;await page.getByRole('button',{name:'确认保存配置',exact:true}).click();await expect(page.getByRole('alert')).toContainText('当前仅可查看配置');await expect(page.getByLabel('工作说明',{exact:true})).toHaveValue('每个工作日上午检查服务交接资料，列出缺失项。');expect(state.posts).toHaveLength(0);
});

test('narrow configuration and unavailable service retain team context and text',async({page},testInfo)=>{
 const state=await fixture(page);await page.setViewportSize({width:390,height:844});await page.goto(direct);await draft(page);state.unavailable=true;await page.getByRole('button',{name:'刷新配置',exact:true}).click();await expect(page.getByRole('alert')).toContainText('暂不可用');await expect(page.getByLabel('工作说明',{exact:true})).toHaveValue('每个工作日上午检查服务交接资料，列出缺失项。');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.screenshot({path:testInfo.outputPath('fixed-work-narrow.png'),fullPage:true});expect(state.posts).toHaveLength(0);await expect(page.getByRole('link',{name:'返回所选团队',exact:true})).toHaveAttribute('href',/q=%E6%9C%8D%E5%8A%A1/);
});


test('invalid event remains editable and saves after explicit correction without a rejected request',async({page})=>{
 const state=await fixture(page);await page.goto(direct);await draft(page);await page.getByLabel('拟采用的触发方式',{exact:true}).selectOption('EVENT');await page.getByRole('button',{name:'确认保存配置',exact:true}).click();await expect(page.getByRole('alert')).toContainText('请填写事件条件说明');expect(state.posts).toHaveLength(0);await expect(page.getByLabel('事件条件说明',{exact:true})).toBeEnabled();await page.getByLabel('事件条件说明',{exact:true}).fill('有新的服务交接资料时');await page.getByRole('button',{name:'确认保存配置',exact:true}).click();await expect(page.getByText('配置已保存。自动触发未启用，没有启动执行。',{exact:true})).toBeVisible();expect(state.posts).toHaveLength(1);
});


test('session invalidation during save preflight cannot continue with a late response',async({page})=>{
 const state=await fixture(page);await page.goto(direct);await draft(page);state.holdList=true;await page.getByRole('button',{name:'确认保存配置',exact:true}).click();await expect.poll(()=>state.listHeld).toBe(true);await page.evaluate(()=>window.dispatchEvent(new Event('workbench-session-expired')));state.releaseList?.();await expect(page.getByRole('alert')).toContainText('登录已失效');expect(state.posts).toHaveLength(0);
});
