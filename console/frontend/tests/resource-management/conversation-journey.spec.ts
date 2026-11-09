import {test,expect,type Page} from '@playwright/test';
const prompt='帮我分析一下最近的销售情况，看看哪里出了问题';
async function fixture(page:Page){
 const state={journal:{version:0,state:null as Record<string,unknown>|null},messages:[] as Record<string,unknown>[],modelCalls:0};
 await page.route('**/api/**',async route=>{const p=new URL(route.request().url()).pathname,method=route.request().method(),body=method==='POST'?route.request().postDataJSON():null;const result=(r:unknown)=>route.fulfill({json:{result:r}});
 if(p.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:development-admin',tenantId:'tenant',securityDomain:'domain'},csrfToken:'csrf',session:{}}});
 if(p.endsWith('/development-administrator'))return result({enabled:true});
 if(p.endsWith('/conversations/capabilities'))return result({enabled:true});
 if(p.endsWith('/conversations'))return method==='POST'?result({conversation_id:'new'}):result({items:[]});
 if(p.endsWith('/new/journey')){if(method==='POST'){if(body.expectedVersion!==state.journal.version)return route.fulfill({status:409,json:{reasonCode:'JOURNEY_VERSION_CONFLICT'}});state.journal={version:state.journal.version+1,state:body.state}}return result(state.journal)}
 if(p.endsWith('/new/messages')){state.messages.push({message_id:'m'+state.messages.length,content:body.content,disposition:'GOAL_RECORDED',created_at:'2026-11-09T08:00:00Z'});return result({identity:'m1'})}
 if(p.endsWith('/conversations/new'))return result({conversation:{conversation_id:'new',title:prompt,version:state.messages.length},messages:state.messages,links:[]});
 if(p.endsWith('/draft-assistance/invocations')){const content=JSON.parse(body.content);if(content.messages.some((m:{id:string})=>!m.id.startsWith('user:')))return route.fulfill({status:404,json:{reasonCode:'DRAFT_CONTEXT_INVALID'}});state.modelCalls++;return result({invocationId:'draft'+state.modelCalls,contextId:'context',turnId:'turn',turnVersion:state.modelCalls,state:'SUCCEEDED',resultKind:'NEEDS_CLARIFICATION',clarificationQuestion:'你想比较哪个时间范围的销售？',draft:null,transport:'REAL_PROVIDER'})}
 if(p.endsWith('/conversation-sources'))return result({items:[{source:{resource_id:'source',revision_id:'1',digest:'a'.repeat(64)},name:'项目销售样本',periods:['2026-08','2026-09'],sourceSchema:'sales-diagnostic-source.v1',synthetic:true}]});
 if(p.endsWith('/problems'))return result({problems:[]});
 return result({items:[]});
 });return state;
}
test('one short message starts understanding and clarification stays in the same conversation after reload',async({page})=>{
 const s=await fixture(page);await page.goto('/work');await page.locator('#private-input').fill(prompt);await page.getByRole('button',{name:'发送',exact:true}).click();await expect(page).toHaveURL(/conversation=new/);await expect(page.getByText('你想比较哪个时间范围的销售？',{exact:true})).toBeVisible();expect(s.modelCalls).toBe(1);await expect(page.getByRole('link',{name:'在本会话核对目标与草稿'})).toHaveCount(0);
 await page.reload();await expect(page.getByRole('button',{name:'使用2026-08、2026-09销售测试资料'})).toBeVisible();expect(s.modelCalls).toBe(1);
 await page.getByRole('button',{name:'使用2026-08、2026-09销售测试资料'}).click();await expect.poll(()=>s.modelCalls).toBe(2);await expect(page).toHaveURL(/conversation=new/);await expect(page.locator('.conversation-journey blockquote')).toContainText('项目销售样本');
});
test('an interrupted claimed operation is preserved and never dispatched again on refresh',async({page})=>{
 const s=await fixture(page);s.journal={version:2,state:{key:'k',question:prompt,phase:'UNDERSTAND',pending:'understanding',messages:[{id:'q',text:prompt}],log:['已收到问题']}};
 await page.goto('/work?conversation=new');await expect(page.getByText('上次请求尚未核实，已保留原记录，暂不重复执行。')).toBeVisible();await page.reload();await expect(page.getByText('上次请求尚未核实，已保留原记录，暂不重复执行。')).toBeVisible();expect(s.modelCalls).toBe(0);
});
