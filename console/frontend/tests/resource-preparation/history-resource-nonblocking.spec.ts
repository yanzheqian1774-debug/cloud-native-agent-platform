import {test,expect,type Page} from '@playwright/test';

async function fixture(page:Page,protectedMessage=false){
 const digest='a'.repeat(64),ref={resource_id:'problem',revision_id:'1',digest:'b'.repeat(64)};
 let release!:()=>void;const pending=new Promise<void>(resolve=>release=resolve);
 const state={ready:false,preparations:[] as string[],businessPosts:[] as string[],conversationReads:0};
 await page.route('**/api/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname;
  const result=(value:unknown)=>route.fulfill({json:{result:value}});
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:'human:ordinary',tenantId:'test',securityDomain:'isolated'},csrfToken:'synthetic-csrf',session:{expiresAt:'2099-01-01T00:00:00Z'}}});
  if(path.endsWith('/test-resource-access/status'))return result({available:true,policyDigest:'c'.repeat(64)});
  if(path.endsWith('/test-resource-access/prepare')){
   state.preparations.push(req.postDataJSON().idempotencyKey);await pending;
   return result({policyDigest:'c'.repeat(64),items:[{state:'APPROVED'}]});
  }
  if(req.method()!=='GET'){state.businessPosts.push(path);return route.fulfill({status:405,json:{reasonCode:'UNEXPECTED_BUSINESS_WRITE'}})}
  if(path.endsWith('/conversations/capabilities'))return result({enabled:true});
  if(path.endsWith('/conversations/saved/head'))return result({conversation:{conversation_id:'saved',title:'已保存核对',version:2}});
  if(path.endsWith('/conversations/saved/journey'))return result({version:3,state:{key:'original',question:'核对原说明',phase:'RUNNING',execution:digest,problem:{business_problem_id:'problem'},messages:[{id:'user:q',text:'核对原说明'}],log:['原执行已结束']}});
  if(path.endsWith('/conversations/saved')){
   state.conversationReads++;
   return result({conversation:{conversation_id:'saved',title:'已保存核对',version:2},messages:[{message_id:'q',content:'原问题：核对原说明',author_id:'human:ordinary'},...(protectedMessage?[{message_id:'protected',kind:'SOURCE',content:state.ready?'已核对的受保护旧记录':'这条原记录暂不可读取',facts:state.ready?{source:{kind:'DRAFT',invocationId:'original'}}:{readable:false}}]:[])],links:[]});
  }
  if(path.includes('/prepared-executions/'))return result(path.endsWith('/native-progress')?{steps:[],questions:[],modelInFlight:false}:{digest,executionStarted:true,preparation:{plan_id:'original-plan',plan_version:1,source_snapshot:ref,semantics:{title:'已保存核对结果',target:{problem:ref},tasks:[]},participants:[]},progress:{state:'SUCCEEDED',version:4,tasks:[]},admission:{state:'ADMITTED'},resourceUses:[],artifacts:[],events:[],outcome:null});
  if(path.endsWith('/problems'))return result({problems:[]});
  return result({items:[],enabled:false});
 });
 return {state,finish:()=>{state.ready=true;release()}};
}

test('slow advisory preparation does not block saved messages or successful result and never resubmits work',async({page})=>{
 const f=await fixture(page);
 try{
  await page.goto('/work?conversation=saved');
  await expect.poll(()=>f.state.preparations.length).toBe(1);
  await expect(page.locator('#conversation-message-q')).toContainText('原问题：核对原说明',{timeout:3000});
  await expect(page.getByRole('heading',{name:'分析结果',exact:true})).toBeVisible({timeout:3000});
  await expect(page.getByText('正在准备可用的测试资源…已有会话和成果可继续读取，操作资格仍按实际权限核对。',{exact:true})).toBeVisible();
  expect(f.state.ready).toBe(false);expect(f.state.businessPosts).toEqual([]);expect(f.state.preparations).toHaveLength(1);
  await page.screenshot({path:test.info().outputPath('slow-preparation-saved-result.png'),fullPage:true});
  f.finish();
  await expect(page.getByText('正在准备可用的测试资源…已有会话和成果可继续读取，操作资格仍按实际权限核对。',{exact:true})).toHaveCount(0);
  await expect(page.getByRole('heading',{name:'分析结果',exact:true})).toBeVisible();
  expect(f.state.businessPosts).toEqual([]);expect(f.state.preparations).toHaveLength(1);
 }finally{f.finish()}
});

test('an exact unreadable saved record stays blocked until authority is ready and explicit readback restores it',async({page})=>{
 const f=await fixture(page,true);
 try{
  await page.goto('/work?conversation=saved');
  const record=page.locator('#conversation-message-protected');
  await expect(record).toContainText('这条原记录暂不可读取',{timeout:3000});
  await record.getByText('查看处理详情',{exact:true}).click();
  await expect(record.getByRole('button',{name:'重新读取记录',exact:true})).toBeVisible({timeout:3000});
  await record.getByRole('button',{name:'重新读取记录',exact:true}).click();
  await expect.poll(()=>f.state.conversationReads).toBeGreaterThanOrEqual(2);
  await expect(page.getByText('已核对的受保护旧记录',{exact:true})).toHaveCount(0);
  await expect(record.getByRole('button',{name:'重新读取记录',exact:true})).toBeVisible();
  expect(f.state.businessPosts).toEqual([]);expect(f.state.preparations).toHaveLength(1);
  f.finish();
  await expect(page.getByText('正在准备可用的测试资源…已有会话和成果可继续读取，操作资格仍按实际权限核对。',{exact:true})).toHaveCount(0);
  await record.getByRole('button',{name:'重新读取记录',exact:true}).click();
  await expect(record).toContainText('已核对的受保护旧记录');
  await expect(record.getByRole('button',{name:'重新读取记录',exact:true})).toHaveCount(0);
  expect(f.state.businessPosts).toEqual([]);expect(f.state.preparations).toHaveLength(1);
 }finally{f.finish()}
});
