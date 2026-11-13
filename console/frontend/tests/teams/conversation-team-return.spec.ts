import {test,expect} from '@playwright/test';
import {createHash} from 'node:crypto';
const canonical=(v:unknown):unknown=>Array.isArray(v)?v.map(canonical):v&&typeof v==='object'?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a<b?-1:1).map(([k,x])=>[k,canonical(x)])):v;
for(const mode of ['matched','wrong-origin','wrong-work','denied','wrong-digest','session-change'] as const)test('original conversation team return reauthorizes '+mode,async({page})=>{
 const preparation='b'.repeat(64),problemDigest='c'.repeat(64),principal={principalId:'human:development-admin',tenantId:'tenant',securityDomain:'domain'};
 const link={workflow_run_id:'run:review',preparation_digest:preparation,business_problem_id:'problem:review',problem_revision_id:'revision:review',problem_digest:problemDigest};
 const revision={schemaVersion:'team-definition.v2',scope:{namespace:'tenant',security_domain:'domain'},team_id:'team:return',revision_id:'team-revision:return',title:'原团队',goal:'核对材料',owner_id:principal.principalId,members:[],predecessor_revision_id:null,work_links:[link]};
 const digest=createHash('sha256').update(JSON.stringify(canonical(revision))).digest('hex');let writes=0,projectionReads=0;
 await page.route('**/api/**',async route=>{
  const path=decodeURIComponent(new URL(route.request().url()).pathname);if(route.request().method()!=='GET')writes++;
  const result=(value:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:value,continuationIds:[]}});
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:mode==='session-change'&&projectionReads?{...principal,principalId:'human:changed'}:principal,csrfToken:'csrf',session:{}}});
  if(path.endsWith('/development-administrator')||path.endsWith('/conversations/capabilities'))return result({enabled:true});
  if(path.endsWith('/problems'))return result({problems:[]});
  if(path.endsWith('/draft-assistance/capabilities'))return result({conversationUnderstanding:true,conversationRelationRouting:false});
  if(path.endsWith('/conversations/origin/head'))return result({conversation:{conversation_id:'origin',title:'检查材料',version:1}});
  if(path.endsWith('/conversations/origin'))return result({conversation:{conversation_id:'origin',title:'检查材料',version:1},messages:[],links:[]});
  if(path.endsWith('/origin/journey'))return result({version:2,state:{key:'saved',question:'检查材料',phase:'RUNNING',execution:preparation,problem:{business_problem_id:'problem:review'},messages:[{id:'user:q',text:'检查材料'}],log:['已有执行记录']}});
  if(path.includes('/teams/')){
   if(mode==='denied')return route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
   if(path.endsWith('/work')){projectionReads++;return result({teamId:revision.team_id,revisionId:revision.revision_id,teamDigest:digest,linkedCount:1,unavailableCount:0,items:[{workflowRunId:mode==='wrong-work'?'other-run':link.workflow_run_id,preparationDigest:preparation,problemId:link.business_problem_id,problemRevisionId:link.problem_revision_id,problemDigest,originVerified:true,originConversationId:mode==='wrong-origin'?'private-other':'origin'}]})}
   return result({revision,digest,aggregateVersion:1,headRevisionId:revision.revision_id});
  }
  if(path.endsWith('/prepared-executions/'+preparation))return result({digest:preparation,executionStarted:true,preparation:{plan_id:'plan',plan_version:1,source_snapshot:{resource_id:'doc',revision_id:'1',digest:problemDigest},semantics:{title:'检查材料',target:{problem:{resource_id:link.business_problem_id,revision_id:link.problem_revision_id,digest:problemDigest}},tasks:[]},participants:[]},progress:{state:'SUCCEEDED',version:1,tasks:[]},admission:{state:'ADMITTED',reason:null},resourceUses:[],artifacts:[],events:[],outcome:null});
  return result({items:[],questions:[]});
 });
 await page.goto('/work?'+new URLSearchParams({conversation:'origin',teamRef:revision.team_id,teamRevision:revision.revision_id,teamDigest:mode==='wrong-digest'?'0'.repeat(64):digest}));
 await expect(page.locator('.conversation-journey')).toBeVisible();
 if(mode==='matched')await expect(page.getByRole('link',{name:'返回原团队',exact:true})).toHaveAttribute('href','/teams?'+new URLSearchParams({team:revision.team_id,revision:revision.revision_id}));
 else {await expect(page.locator('.prepared-execution')).toBeVisible();await expect(page.getByRole('link',{name:'返回原团队',exact:true})).toHaveCount(0)}
 expect(writes).toBe(0);
});
