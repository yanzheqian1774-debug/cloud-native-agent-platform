import {test,expect,type Page} from '@playwright/test';
import {createHash} from 'node:crypto';
import {fixture as sessionFixture,principal} from '../helpers/resourceMaintenanceFixture';
const normalized=(v:unknown):unknown=>typeof v==='string'?v.normalize('NFC'):Array.isArray(v)?v.map(normalized):v&&typeof v==='object'?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a<b?-1:1).map(([k,x])=>[k,normalized(x)])):v;
const hash=(v:unknown)=>createHash('sha256').update(JSON.stringify(normalized(v))).digest('hex');
const record={schemaVersion:'team-definition.v1',scope:{namespace:principal.tenantId,security_domain:principal.securityDomain},team_id:'team:handover',revision_id:'team-revision:1',title:'服务交接团队',goal:'核对交接资料',owner_id:principal.principalId,members:[],predecessor_revision_id:null};
const team={teamId:record.team_id,revisionId:record.revision_id,digest:hash(record)};
const draft={schemaVersion:'fixed-work-draft.v1',state:'DRAFT_ONLY',team,workId:'work:source',revisionId:'work-revision:1',predecessorRevisionId:null,aggregateVersion:1,title:'每天交接检查',instruction:'每天上午检查服务交接资料，列出缺失项。',trigger:{kind:'SCHEDULE',timezone:'Asia/Shanghai',localTime:'09:00',cadence:'DAILY',eventDescription:null},createdBy:principal.principalId,createdAt:'2026-11-14T00:00:00+00:00'};
const item={draft,digest:hash(draft)},work={resource_id:draft.workId,revision_id:draft.revisionId,digest:item.digest};
const preview={work,team,subjectId:principal.principalId,conversationId:'conversation:source',title:'核对交接材料完整性',description:'依据选定的合成资料，列出缺失项和原文依据。',criteria:[{revision_id:'criterion:1',measurement:{rubric:'每项缺失附原文出处。'}}],target:{problem:{resource_id:'problem:1',revision_id:'p:1',digest:'a'.repeat(64)},criteria:{resource_id:'problem:1',revision_id:'criteria:1',digest:'b'.repeat(64)},criterion_revision_ids:['criterion:1']}};
const url='/teams?'+new URLSearchParams({view:'routines',fixedTeam:team.teamId,fixedRevision:team.revisionId,fixedDigest:team.digest,openWork:draft.workId,openRevision:draft.revisionId,openDigest:item.digest});
const envelope=(result:unknown)=>({schemaVersion:'workbench-operation.v1',result,continuationIds:[]});
async function fixture(page:Page){
 await sessionFixture(page,true);
 const state={canSave:true,source:'READY_TO_CONFIRM',posts:[] as unknown[],reads:0,fail:false};
 await page.route('**/api/workbench/v1/teams**',async route=>{const path=decodeURIComponent(new URL(route.request().url()).pathname);
  if(path.endsWith('/source')){if(route.request().method()==='POST'){state.posts.push(route.request().postDataJSON());state.source='BOUND'}else state.reads++;
   if(state.fail)return route.fulfill({status:403,json:{reasonCode:'FIXED_WORK_AUTHORING_NOT_AUTHORIZED'}});
   return route.fulfill({json:envelope({state:state.source,preview,previewDigest:hash(preview),executionEnabled:false})});}
  if(path.endsWith('/activity'))return route.fulfill({status:503,json:{reasonCode:'FIXED_WORK_ACTIVITY_UNAVAILABLE'}});
  if(path.endsWith('/fixed-work-drafts'))return route.fulfill({json:envelope({items:[item],team,nextCursor:null,configurationCanSave:state.canSave,executionEnabled:false,authorityGranted:false,triggerCreated:false})});
  if(path.includes('/fixed-work-drafts/'))return route.fulfill({json:envelope({...item,aggregateVersion:1,executionEnabled:false,authorityGranted:false,triggerCreated:false,validation:'CONFIGURATION_STRUCTURE_ONLY'})});
  return route.fulfill({json:envelope({revision:record,digest:team.digest,aggregateVersion:1,headRevisionId:record.revision_id})});
 });
 return state;
}
test('exact saved target is explicitly read and confirmed, then rediscovered without a new command',async({page})=>{
 const state=await fixture(page);await page.goto(url);await page.getByRole('button',{name:'读取已有目标',exact:true}).click();await expect(page.getByText(preview.description,{exact:true})).toBeVisible();expect(state.posts).toHaveLength(0);
 await page.getByRole('button',{name:'确认采用这个目标',exact:true}).click();await expect(page.getByText('已保存这项工作的目标来源。服务授权、触发窗口和运行状态尚待核验；未启用自动运行。')).toBeVisible();expect(state.posts).toHaveLength(1);
 expect(state.posts[0]).toEqual({conversationId:preview.conversationId,workDigest:item.digest,commandId:'fixed-source:'+item.digest+':confirm',previewDigest:hash(preview)});
 await page.evaluate(()=>sessionStorage.clear());await page.reload();await page.getByRole('button',{name:'读取已有目标',exact:true}).click();await expect(page.getByRole('button',{name:'确认采用这个目标',exact:true})).toHaveCount(0);expect(state.posts).toHaveLength(1);
});
test('read only retains original conversation link without source mutation controls',async({page})=>{
 const state=await fixture(page);state.canSave=false;await page.goto(url);await page.getByRole('button',{name:'读取已有目标',exact:true}).click();await expect(page.getByRole('link',{name:'返回目标确认会话',exact:true})).toHaveAttribute('href','/work?conversation=conversation%3Asource');await expect(page.getByRole('button',{name:'确认采用这个目标',exact:true})).toHaveCount(0);expect(state.posts).toHaveLength(0);
});
test('lost current read clears prior confirmation rather than claiming source is ready',async({page})=>{
 const state=await fixture(page);await page.goto(url);await page.getByRole('button',{name:'读取已有目标',exact:true}).click();await expect(page.getByRole('button',{name:'确认采用这个目标',exact:true})).toBeVisible();state.fail=true;await page.getByRole('button',{name:'读取已有目标',exact:true}).click();await expect(page.getByRole('button',{name:'确认采用这个目标',exact:true})).toHaveCount(0);await expect(page.getByText('当前记录尚未核对完成，原说明和会话保留。请读取原记录后继续。')).toBeVisible();expect(state.posts).toHaveLength(0);
});
test('retained owner handoff pauses original PLAN on refresh with zero model or execution writes',async({page},info)=>{
 let posts=0;page.on('pageerror',error=>console.log('SOURCE_PAGE_ERROR',error.message));
 const state={key:'fixed-goal',question:draft.instruction,phase:'PLAN',messages:[{id:'user:m1',text:draft.instruction}],log:['目标和完成标准已准备，等待固定工作确认。'],problem:{business_problem_id:'p',revision_id:'r',digest:'d'.repeat(64)},criterion:'criterion:1'};
 await page.route('**/api/**',async route=>{const path=new URL(route.request().url()).pathname;if(route.request().method()==='POST'){posts++;return route.fulfill({status:409,json:{reasonCode:'UNEXPECTED_WRITE'}})}const result=(value:unknown)=>route.fulfill({json:{result:value}});
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal,csrfToken:'csrf',session:{expiresAt:'2099-01-01T00:00:00Z',idleExpiresAt:'2099-01-01T00:00:00Z'}}});
  if(path.endsWith('/development-administrator'))return result({enabled:false});
  if(path.endsWith('/conversations/capabilities'))return result({enabled:true});
  if(path.endsWith('/conversations/new/journey'))return result({version:8,state,fixedWorkSource:{mode:'TARGET_REVIEW_ONLY',handoffDigest:'e'.repeat(64),work,team}});
  if(path.endsWith('/conversations/new/head'))return result({conversation:{conversation_id:'new',title:draft.title,version:1}});
  if(path.endsWith('/conversations/new'))return result({conversation:{conversation_id:'new',title:draft.title,version:1},messages:[{message_id:'user:m1',content:draft.instruction,author_id:principal.principalId,disposition:'GOAL_RECORDED'}],links:[]});
  if(path.endsWith('/problems'))return result({problems:[]});
  return result({items:[]});
 });
 await page.goto('/work?conversation=new');await expect(page.getByRole('heading',{name:'固定工作目标已准备',exact:true})).toBeVisible();await expect(page.getByRole('link',{name:'返回编辑工作说明',exact:true})).toHaveAttribute('href',url);expect(posts).toBe(0);await page.reload();await expect(page.getByRole('heading',{name:'固定工作目标已准备',exact:true})).toBeVisible();expect(posts).toBe(0);await expect(page.locator('#private-input')).toBeVisible();await expect(page.locator('#private-input')).toBeEditable();await page.locator('#private-input').fill('保留未发送的补充说明');await page.reload();await expect(page.locator('#private-input')).toHaveValue('保留未发送的补充说明');await expect(page.getByRole('link',{name:'发起另一个问题',exact:true})).toHaveCount(0);await page.screenshot({path:info.outputPath('fixed-work-target-review.png'),fullPage:true});
});
