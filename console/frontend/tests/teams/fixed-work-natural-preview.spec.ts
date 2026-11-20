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

async function natural(page:Page,issues:string[]=[]){
 await page.route('**/fixed-work-preview',async route=>{const b=route.request().postDataJSON();await route.fulfill({json:envelope({team,instruction:b.instruction,instructionDigest:hash(b.instruction),previous:b.previous,proposedTitle:b.title||b.instruction.slice(0,120),candidateTrigger:{kind:'SCHEDULE',timezone:'Asia/Shanghai',localTime:'09:30',cadence:'WEEKDAY',eventDescription:null},issues,modelInvoked:false,executionEnabled:false,authorityGranted:false,validation:'CONFIGURATION_STRUCTURE_ONLY'})})});
}
test('natural instruction becomes explicit difference then original save and server refresh',async({page},info)=>{
 const state=await fixture(page);await natural(page);await page.goto(direct);await page.getByRole('button',{name:'新增固定工作配置',exact:true}).click();
 await page.getByLabel('工作说明',{exact:true}).fill('每个工作日北京时间上午9点半检查交接资料');
 await page.getByRole('button',{name:'从说明生成安排预览',exact:true}).click();await expect(page.getByText('已提取明确的安排字段。请核对下方预览与差异，再确认保存；没有开始运行。')).toBeVisible();expect(state.posts).toHaveLength(0);
 await page.getByRole('button',{name:'预览本次安排',exact:true}).click();await expect(page.getByRole('region',{name:'本次安排预览'})).toContainText('09:30');await page.screenshot({path:info.outputPath('natural-preview.png'),fullPage:true});
 await page.getByRole('button',{name:'确认保存配置',exact:true}).click();await expect(page.getByText('配置已保存。自动触发未启用，没有启动执行。',{exact:true})).toBeVisible();expect(state.posts).toHaveLength(1);expect(state.posts[0].trigger.localTime).toBe('09:30');
 await page.evaluate(()=>sessionStorage.clear());await page.reload();await expect(page.getByRole('heading',{name:'每个工作日北京时间上午9点半检查交接资料',exact:true})).toBeVisible();expect(state.posts).toHaveLength(1);
});
test('ambiguous preview retains explanation and never saves implicitly',async({page})=>{
 const state=await fixture(page);await natural(page,['说明中有多个时间，未替你选择。']);await page.goto(direct);await page.getByRole('button',{name:'新增固定工作配置',exact:true}).click();await page.getByLabel('工作说明',{exact:true}).fill('每天9点或10点检查');await page.getByRole('button',{name:'从说明生成安排预览',exact:true}).click();await expect(page.getByText('说明中有多个时间，未替你选择。')).toBeVisible();await expect(page.getByLabel('工作说明',{exact:true})).toHaveValue('每天9点或10点检查');expect(state.posts).toHaveLength(0);
});
