import {expect,test} from '@playwright/test';
import {fixture,conversation,execution} from '../helpers/savedSourceFixture';

for(const readable of [true,false])test('capability preparation and original execution have distinct visible ownership '+readable,async({page})=>{
 const {state}=await fixture(page);
 await page.route('**/conversations/'+conversation,route=>route.fulfill({json:{result:{conversation:{conversation_id:conversation,title:'包含新准备与原结果的会话',version:3,created_at:'2026-11-08'},links:[],messages:[{message_id:'cap-source',sequence:3,kind:'SOURCE',disposition:'SOURCE',content:'业务能力与本次输入已保存',created_at:'2026-11-11T01:00:00Z',facts:readable?{source:{kind:'CAPABILITY',target:{capabilityId:'handover',revisionId:'cap-v1',digest:'a'.repeat(64),objective:'核对新交接资料',inputNotes:'新资料待核对'}},observation:{state:'PREPARED_NOT_EXECUTED',title:'新交接准备',objective:'核对新交接资料',inputNotes:'新资料待核对'}}:{readable:false}}]}}}));
 await page.route('**/conversations/'+conversation+'/journey',route=>route.fulfill({json:{result:{version:5,state:{key:'existing-work',phase:'RUNNING',question:'之前已经执行的销售核对',messages:[],problem:{business_problem_id:'source-problem'},execution,log:[]}}}}));
 await page.goto('/work?conversation='+conversation);
 if(readable){
  const preparation=page.getByRole('region',{name:'当前能力准备',exact:true});await expect(preparation).toContainText('当前准备 · 未启动');await expect(preparation).toContainText('新交接准备');await expect(preparation).not.toContainText('任务已完成');
  await expect(page.getByRole('heading',{name:'原有工作进展',exact:true})).toBeVisible();await expect(page.getByRole('heading',{name:'原有工作的分析结果',exact:true})).toBeVisible();await expect(page.locator('.conversation-original-work')).toContainText('之前已经执行的销售核对');await expect(page.getByRole('region',{name:'全流程进展'})).toContainText('原有工作 · 结果已返回');
  await page.reload();await expect(preparation).toBeVisible();await expect(page.getByRole('heading',{name:'原有工作的分析结果',exact:true})).toBeVisible();
 }else{await expect(page.getByRole('heading',{name:'分析结果',exact:true})).toBeVisible();await expect(page.getByRole('region',{name:'当前能力准备'})).toHaveCount(0);await expect(page.getByText('新交接准备',{exact:true})).toHaveCount(0)}
 expect(state.writes).toEqual([]);
});

for(const mode of ['recorded','pending','other-source','unreadable','conflicting'] as const)test('capability work status uses explicit saved association '+mode,async({page})=>{
 const {state}=await fixture(page);
 const source={kind:'CAPABILITY',target:{capabilityId:'handover',revisionId:'cap-v1',digest:'a'.repeat(64),objective:'核对新交接资料',inputNotes:'新资料'}};
 const intent={message_id:'intent-message',sequence:4,kind:'ACTION_INTENT',disposition:'ACTION_INTENT',content:'已确认',facts:{intentId:'intent-one',messageId:mode==='other-source'?'different-message':'cap-source',action:'CREATE_PROBLEM',source,attemptState:'UNKNOWN'}};
 const receipt={message_id:'receipt',sequence:5,kind:'OWNER_RECEIPT',disposition:'OWNER_RECEIPT',content:'已返回创建回执',facts:mode==='unreadable'?{readable:false}:{intentId:'intent-one',state:'SUCCEEDED',source:{kind:'PROBLEM',target:{problemId:'new-problem',revisionId:'new-revision',problemDigest:'b'.repeat(64)}}}};
 const messages=[{message_id:'cap-source',sequence:3,kind:'SOURCE',disposition:'SOURCE',content:'业务能力与本次输入已保存',facts:{source,observation:{state:'PREPARED_NOT_EXECUTED',title:'交接检查',objective:'核对新交接资料',inputNotes:'新资料'}}},intent,...(mode==='pending'?[]:[receipt]),...(mode==='conflicting'?[{...intent,message_id:'second-intent',facts:{...intent.facts,intentId:'second-intent'}}]:[])];
 await page.route('**/conversations/'+conversation,route=>route.fulfill({json:{result:{conversation:{conversation_id:conversation,title:'能力工作关联',version:messages.length,created_at:'2026-11-11'},links:[],messages}}}));
 await page.route('**/conversations/'+conversation+'/journey',route=>route.fulfill({json:{result:{version:0,state:null}}}));
 await page.goto('/work?conversation='+conversation);
 const region=page.getByRole('region',{name:'当前能力准备',exact:true});
 await expect(region).toContainText(mode==='recorded'?'目标已建立':mode==='other-source'?'未启动':'待核验');
 await expect(region).not.toContainText('任务已完成');
 await page.getByText('查看处理详情',{exact:true}).first().click();
 await expect(page.getByRole('button',{name:'只读核查原动作',exact:true}).first()).toBeVisible();
 await page.reload();
 await expect(region).toContainText(mode==='recorded'?'目标已建立':mode==='other-source'?'未启动':'待核验');
 expect(state.writes).toEqual([]);
});
