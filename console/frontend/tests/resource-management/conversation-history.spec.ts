import {test,expect,type Page} from '@playwright/test';

async function fixture(page:Page){
 const state={writes:[] as string[],deny:false,wrongVersion:false,readDelay:0};
 const digest='d'.repeat(64),problemDigest='b'.repeat(64);
 await page.route('**/api/**',async route=>{
  const request=route.request(),path=new URL(request.url()).pathname;
  const result=(value:unknown)=>route.fulfill({json:{result:value}});
  if(request.method()!=='GET'){state.writes.push(path);return route.fulfill({status:405,json:{reasonCode:'READ_ONLY_TEST'}})}
  if(path.endsWith('/session'))return route.fulfill({json:{principal:{principalId:'human:ordinary',tenantId:'tenant',securityDomain:'domain'},csrfToken:'csrf',session:{}}});
  if(path.endsWith('/development-administrator'))return result({enabled:false});
  if(path.endsWith('/conversations/capabilities'))return result({enabled:true});
  if(path.endsWith('/conversations'))return result({items:[]});
  if(path.endsWith('/historical/journey'))return result({version:0,state:null});
  if(path.endsWith('/conversations/historical'))return result({conversation:{conversation_id:'historical',title:'历史工作体验',version:1},messages:[{message_id:'note',content:'我保存的测试说明',author_id:'human:ordinary',created_at:'2026-11-12T00:00:00Z',disposition:'GOAL_RECORDED'}],links:[{link_id:'work',readable:true,title:'原有交接检查',target:{problemId:'problem',revisionId:'1',problemDigest,executionDigest:digest}}]});
  if(path.includes('/prepared-executions/')){
   if(state.readDelay)await new Promise(resolve=>setTimeout(resolve,state.readDelay));
   if(state.deny)return route.fulfill({status:403,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
   return result({digest,preparation:{semantics:{title:'原有交接检查',target:{problem:{resource_id:'problem',revision_id:state.wrongVersion?'2':'1',digest:problemDigest}},tasks:[]},source_snapshot:{resource_id:'knowledge',revision_id:'1',digest:'a'.repeat(64)}},progress:{state:'SUCCEEDED',tasks:[]},artifacts:[],resourceUses:[],events:[],outcome:null});
  }
  if(path.endsWith('/problems'))return result({problems:[]});
  return result({items:[]});
 });return state;
}

test('historical work is visible by default and refresh never creates a journey',async({page})=>{
 const state=await fixture(page);await page.goto('/work?conversation=historical');
 await expect(page.getByRole('region',{name:'关联历史工作'})).toBeVisible();
 await expect(page.locator('.f3-progress-rail')).toBeVisible();
 await expect(page.getByRole('region',{name:'历史工作进展'})).toContainText('历史执行已完成');
 await expect(page.locator('.private-user')).toContainText('我保存的测试说明');
 await expect(page.getByRole('link',{name:'首页 · 我的工作台',exact:true})).not.toHaveAttribute('aria-current','page');
 await page.locator('#private-input').fill('尚未发送的补充');await page.reload();
 await expect(page.locator('#private-input')).toHaveValue('尚未发送的补充');
 await expect(page.getByRole('region',{name:'历史工作进展'})).toContainText('历史执行已完成');
 expect(state.writes).toEqual([]);
});

for(const failure of ['deny','wrongVersion'] as const)test('history clears after '+failure,async({page})=>{
 const state=await fixture(page);await page.goto('/work?conversation=historical');
 await expect(page.getByRole('region',{name:'历史工作进展'})).toContainText('历史执行已完成');
 state[failure]=true;await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
 await expect(page.getByText('历史工作暂未读回，原记录保留。',{exact:true})).toBeVisible();
 await expect(page.getByRole('region',{name:'历史工作进展'})).not.toContainText('历史执行已完成');
 await expect(page.getByRole('link',{name:'查看原资料与固定版本'})).toHaveCount(0);
 expect(state.writes).toEqual([]);
});

test('unknown legacy receipt restores a truthful rail without inventing execution',async({page})=>{
 const state=await fixture(page);
 await page.route('**/api/workbench/v1/conversations/historical',route=>route.fulfill({json:{result:{conversation:{conversation_id:'historical',title:'旧问题',version:2},messages:[{message_id:'question',content:'请核对供应商',author_id:'human:ordinary',disposition:'GOAL_RECORDED'},{message_id:'receipt',content:'原入口办理回执',kind:'OWNER_RECEIPT',author_id:'human:ordinary',disposition:'OWNER_RECEIPT',facts:{state:'UNKNOWN',reasonCode:'NO_SAFE_OWNER_QUERY_KEEP_UNKNOWN'}}],links:[]}}}));
 await page.goto('/work?conversation=historical');
 await expect(page.getByRole('region',{name:'原请求状态'})).toContainText('结果待核实');
 await expect(page.getByRole('heading',{name:'原请求结果待核实'})).toBeVisible();
 await expect(page.locator('#conversation-message-receipt .conversation-message-identity')).toContainText('办理回执');
 await expect(page.locator('#conversation-message-receipt .conversation-message-identity')).toContainText('操作人：用户');
 await expect(page.locator('.conversation-history .px-delivery-summary')).toHaveCount(0);
 await page.locator('#private-input').fill('未发送的回执补充');
 const originalScroll=await page.locator('.px-message-stream').evaluate(node=>node.scrollTop);
 await page.getByRole('button',{name:'查看原办理回执',exact:true}).click();
 await expect(page.locator('#conversation-message-receipt .private-receipt details')).toHaveAttribute('open','');
 await page.getByRole('button',{name:'返回查看前位置',exact:true}).click();
 await expect(page.locator('#private-input')).toHaveValue('未发送的回执补充');
 await expect.poll(()=>page.locator('.px-message-stream').evaluate(node=>node.scrollTop)).toBe(originalScroll);
 expect(state.writes).toEqual([]);
});


test('delayed historical readback restores the reading position until user interaction',async({page})=>{
 await page.setViewportSize({width:1440,height:600});
 const state=await fixture(page);await page.goto('/work?conversation=historical');
 await expect(page.getByRole('region',{name:'历史工作进展'})).toContainText('历史执行已完成');
 const stream=page.locator('.px-message-stream');
 await stream.evaluate(node=>{node.dispatchEvent(new Event('wheel',{bubbles:true}));node.scrollTop=80});
 await expect.poll(()=>stream.evaluate(node=>node.scrollTop)).toBe(80);
 state.readDelay=1800;await page.reload();
 await expect(page.getByRole('region',{name:'历史工作进展'})).toContainText('历史执行已完成');
 await expect.poll(()=>stream.evaluate(node=>node.scrollTop)).toBe(80);
 await stream.evaluate(node=>{node.dispatchEvent(new Event('wheel',{bubbles:true}));node.scrollTop=0;const marker=document.createElement('div');marker.textContent='阅读位置检查';node.append(marker)});
 await expect.poll(()=>stream.evaluate(node=>node.scrollTop)).toBe(0);
 expect(state.writes).toEqual([]);
});


test('historical reading retains secondary association controls without executing work',async({page})=>{
 const state=await fixture(page);await page.goto('/work?conversation=historical');
 await expect(page.getByRole('region',{name:'历史工作进展'})).toContainText('历史执行已完成');
 await page.getByText('管理关联工作',{exact:true}).click();
 await expect(page.getByRole('combobox',{name:'关联已有问题'})).toBeVisible();
 await expect(page.getByRole('button',{name:'关联到本会话',exact:true})).toBeDisabled();
 await page.getByRole('button',{name:'暂不指定工作',exact:true}).click();
 await expect(page.locator('#private-input')).toBeVisible();
 expect(state.writes).toEqual([]);
});


test('saved assistant reply reads as an assistant and refresh never invokes a model',async({page})=>{
 const state=await fixture(page);
 await page.route('**/api/workbench/v1/conversations/historical',route=>route.fulfill({json:{result:{conversation:{conversation_id:'historical',title:'普通交流',version:2},messages:[{message_id:'answer',content:'先明确目标，再核对所需资料。',kind:'SOURCE',author_id:'human:ordinary',created_at:'2026-11-12T02:00:00Z',facts:{assistantResponse:true,state:'SUCCEEDED',invokedBy:'human:ordinary',source:{kind:'DRAFT',invocationId:'actual-invocation',contextId:'context',turnId:'turn',turnVersion:1}}}],links:[]}}}));
 await page.goto('/work?conversation=historical');
 await expect(page.locator('#conversation-message-answer .conversation-message-author')).toHaveText('工作助手');
 await expect(page.locator('#conversation-message-answer .private-user')).toHaveText('先明确目标，再核对所需资料。');
 await page.reload();
 await expect(page.locator('#conversation-message-answer .private-user')).toHaveText('先明确目标，再核对所需资料。');
 expect(state.writes).toEqual([]);
});
