import {test,expect,type Page} from '@playwright/test';
const prompt='帮我分析一下最近的销售情况，看看哪里出了问题';
async function fixture(page:Page){
 const state={title:prompt,journal:{version:0,state:null as Record<string,unknown>|null},messages:[] as Record<string,unknown>[],modelCalls:0};
 await page.route('**/api/**',async route=>{const p=new URL(route.request().url()).pathname,method=route.request().method(),body=method==='POST'?route.request().postDataJSON():null;const result=(r:unknown)=>route.fulfill({json:{result:r}});
 if(p.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:development-admin',tenantId:'tenant',securityDomain:'domain'},csrfToken:'csrf',session:{}}});
 if(p.endsWith('/development-administrator'))return result({enabled:true});
 if(p.endsWith('/conversations/capabilities'))return result({enabled:true});
 if(p.endsWith('/conversations'))return method==='POST'?result({conversation_id:'new'}):result({items:[]});
 if(p.endsWith('/new/journey')){if(method==='POST'){if(body.expectedVersion!==state.journal.version)return route.fulfill({status:409,json:{reasonCode:'JOURNEY_VERSION_CONFLICT'}});state.journal={version:state.journal.version+1,state:body.state}}return result(state.journal)}
 if(p.endsWith('/new/messages')){state.messages.push({message_id:'m'+state.messages.length,content:body.content,disposition:'GOAL_RECORDED',created_at:'2026-11-09T08:00:00Z'});return result({identity:'m1'})}
 if(p.endsWith('/conversations/new/head'))return result({conversation:{conversation_id:'new',title:state.title,version:state.messages.length}});
 if(p.endsWith('/conversations/new'))return result({conversation:{conversation_id:'new',title:state.title,version:state.messages.length},messages:state.messages,links:[]});
 if(p.endsWith('/draft-assistance/invocations')){const content=JSON.parse(body.content);if(content.messages.some((m:{id:string})=>!m.id.startsWith('user:')))return route.fulfill({status:404,json:{reasonCode:'DRAFT_CONTEXT_INVALID'}});state.modelCalls++;return result({invocationId:'draft'+state.modelCalls,contextId:'context',turnId:'turn',turnVersion:state.modelCalls,state:'SUCCEEDED',resultKind:'NEEDS_CLARIFICATION',clarificationQuestion:'你想比较哪个时间范围的销售？',draft:null,transport:'REAL_PROVIDER'})}
 if(p.endsWith('/conversation-sources'))return result({items:[{source:{resource_id:'source',revision_id:'1',digest:'a'.repeat(64)},name:'项目销售样本',periods:['2026-08','2026-09'],sourceSchema:'sales-diagnostic-source.v1',synthetic:true}]});
 if(p.endsWith('/problems'))return result({problems:[]});
 return result({items:[]});
 });return state;
}

for(const state of ['QUEUED','STARTING','READY','STOPPING','BLOCKED','UNKNOWN','OFF','WRONG_PREP','WRONG_RUN','QUESTION','DONE','BAD_TIME','BAD_STATE'])test('host observation '+state,async({page})=>{
 const s=await fixture(page),digest='a'.repeat(64);s.journal={version:2,state:{key:'run',phase:'RUNNING',execution:digest,problem:{business_problem_id:'p'},messages:[],log:[]}};let posts=0;
 await page.route('**/api/workbench/v1/prepared-executions/**',async route=>{
 if(route.request().method()!=='GET')posts++;
 if(route.request().url().endsWith('/native-progress'))return route.fulfill({json:{result:{runId:'run-1',steps:[],questions:state==='QUESTION'?[{invocationId:'i',questionKey:'q',questionDigest:'b'.repeat(64),question:'请补充环境',expiresAt:'2099-01-01T00:00:00Z',answer:null,expired:false}]:[],modelInFlight:false,...(state==='OFF'?{}:{hostDispatch:{state:state==='BAD_STATE'?'invented':['WRONG_PREP','WRONG_RUN','QUESTION','DONE'].includes(state)?'READY':state,preparationDigest:state==='WRONG_PREP'?'wrong':digest,runId:state==='WRONG_RUN'?'other':'run-1',observedAt:state==='BAD_TIME'?'invalid':null,reasonCode:null}})}}});
 return route.fulfill({json:{result:{digest,preparation:{semantics:{tasks:[]},participants:[]},progress:{state:state==='DONE'?'SUCCEEDED':'RUNNING',tasks:[]},artifacts:[],resourceUses:[],events:[]}}});});
 await page.goto('/work?conversation=new');const rail=page.getByRole('region',{name:'实时执行过程'});
 const labels:Record<string,string>={QUEUED:'正在排队',STARTING:'正在准备执行环境',READY:'执行环境已就绪',STOPPING:'执行环境正在停止',BLOCKED:'当前执行条件尚未满足',UNKNOWN:'执行准备状态暂时无法核实',OFF:'正在读取已保存的执行进展',WRONG_PREP:'执行准备状态暂时无法核实',WRONG_RUN:'执行准备状态暂时无法核实',QUESTION:'需要你补充一个必要信息',DONE:'执行已结束',BAD_TIME:'执行准备状态暂时无法核实',BAD_STATE:'执行准备状态暂时无法核实'};
 await expect(rail).toContainText(labels[state]);if(['QUESTION','DONE'].includes(state))await expect(rail).not.toContainText('执行环境已就绪');await page.reload();await expect(rail).toContainText(labels[state]);expect(posts).toBe(0);expect(s.modelCalls).toBe(0);
});
