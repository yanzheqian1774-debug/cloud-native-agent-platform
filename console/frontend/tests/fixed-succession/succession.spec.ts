import {test,expect} from '@playwright/test';import {createHash} from 'node:crypto';
import {record,session,item} from './fixture';import {canonicalSuccession} from '../../src/api/fixedWorkSuccession';
const hash=(v:unknown)=>createHash('sha256').update(canonicalSuccession(v)).digest('hex');
for(const scenario of ['success','lost','wrong-chat','not-recorded'])test(`exact original-chat update and refresh ${scenario}`,async({page})=>{
 const lost=scenario==='lost'||scenario==='not-recorded';
 const team={teamId:record.team_id,revisionId:record.revision_id,digest:hash(record)},draft=item(team),next={...record,revision_id:'team:2',predecessor_revision_id:record.revision_id,goal:'新合成资料核对'};
 const after={teamId:team.teamId,revisionId:next.revision_id,digest:hash(next)},work={resource_id:draft.draft.workId,revision_id:draft.draft.revisionId,digest:draft.digest};
 let commits=0,saved:unknown=null,heldPreview:unknown=null;const writes:string[]=[];
 await page.route('**/api/workbench/**',async route=>{const req=route.request(),url=decodeURIComponent(new URL(req.url()).pathname);let result:unknown;
 if(url.endsWith('/session'))return route.fulfill({json:session});
 if(req.method()==='POST')writes.push(url);
 if(url.endsWith('/source'))result={state:'AWAITING_CONFIRMED_TARGET',executionEnabled:false,work,handoff:{record:{work,team,subjectId:'human:test',conversationId:'original-chat',executionEnabled:false},digest:'b'.repeat(64)}};
 else if(url.endsWith('/teams/team:test/revisions/team:1'))result={revision:record,digest:hash(record),aggregateVersion:2,headRevisionId:'team:2'};
 else if(url.endsWith('/teams/team:test/revisions/team:2'))result={revision:next,digest:hash(next),aggregateVersion:2,headRevisionId:'team:2'};
 else if(url.endsWith('/succession/preview')){const c=req.postDataJSON();const preview={schemaVersion:'fixed-work-succession-preview.v1',predecessor:work,predecessorHandoffDigest:c.predecessorHandoffDigest,subjectId:'human:test',conversationId:'original-chat',teamBefore:team,teamAfter:after,teamChanges:{goal:{before:record.goal,after:next.goal}},memberChanges:[],preserved:{title:draft.draft.title,instruction:draft.draft.instruction,trigger:draft.draft.trigger},effectivePoint:'BEFORE_FIRST_TARGET_ONLY',configurationOnly:true,executionEnabled:false,currentOwnerChecksRequired:true};heldPreview=preview;result={state:'PREVIEW',preview,previewDigest:hash(preview),executionEnabled:false};}
 else if(url.endsWith('/succession')&&req.method()==='POST'){commits++;const c=req.postDataJSON();const r={schemaVersion:'fixed-work-succession.v1',scope:['tenant','domain'],logicalWorkId:'work:original',subjectId:'human:test',conversationId:'original-chat',predecessor:work,predecessorHandoffDigest:c.predecessorHandoffDigest,command:c,commandId:c.commandId,payloadDigest:hash(c),previewDigest:c.previewDigest,preview:heldPreview,work:{resource_id:'work:successor',revision_id:'work-revision:2',digest:'c'.repeat(64)},effectivePoint:'BEFORE_FIRST_TARGET_ONLY',executionEnabled:false,handoff:{work:{resource_id:'work:successor',revision_id:'work-revision:2',digest:'c'.repeat(64)},team:after,subjectId:'human:test',conversationId:'original-chat',executionEnabled:false}};if(scenario==='wrong-chat')r.conversationId='other-chat';saved=scenario==='not-recorded'?null:{state:'COMMITTED',record:r,digest:hash(r)};if(lost)return route.abort('failed');result=saved;}
 else if(url.includes('/succession/commands/'))result=saved??{state:'NOT_RECORDED'};
 else throw Error('Unexpected request '+req.method()+' '+url);
 return route.fulfill({json:{schemaVersion:'workbench-operation.v1',result}})});
 await page.goto('/tests/fixed-succession/preview.html');await page.getByRole('button',{name:'查看团队更新差异'}).click();await expect(page.getByText('核对合成资料 → 新合成资料核对')).toBeVisible();if(scenario==='success'&&process.env.F3_SUCCESSION_SCREENSHOT_DIR)await page.screenshot({path:process.env.F3_SUCCESSION_SCREENSHOT_DIR+'/preview.png',fullPage:true});await page.getByRole('button',{name:'确认更新团队并保留原会话'}).click();
 if(lost){await expect(page.getByRole('button',{name:'核对原更新记录'})).toBeVisible();await page.reload();await page.getByRole('button',{name:'核对原更新记录'}).click()}
 if(scenario==='wrong-chat'||scenario==='not-recorded'){
  await expect(page.getByRole('button',{name:'核对原更新记录'})).toBeVisible();
  await page.getByRole('button',{name:'核对原更新记录'}).click();
  await expect(page.getByRole('link',{name:'返回原目标确认会话'})).toHaveCount(0);
  expect(commits).toBe(1);expect(writes).toHaveLength(2);return;
 }
 await expect(page.getByRole('link',{name:'返回原目标确认会话'})).toHaveAttribute('href','/work?conversation=original-chat');expect(commits).toBe(1);await page.reload();await page.getByRole('button',{name:'核对原更新记录'}).click();await expect(page.getByRole('link',{name:'查看当前配置'})).toHaveAttribute('href',/openWork=work%3Asuccessor/);expect(commits).toBe(1);expect(writes).toHaveLength(2);if(scenario==='success'&&process.env.F3_SUCCESSION_SCREENSHOT_DIR)await page.screenshot({path:process.env.F3_SUCCESSION_SCREENSHOT_DIR+'/committed.png',fullPage:true});
});
