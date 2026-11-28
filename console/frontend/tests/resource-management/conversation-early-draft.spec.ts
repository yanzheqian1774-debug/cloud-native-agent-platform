import {writeFileSync} from 'node:fs';
import {test,expect} from '@playwright/test';
for(const mode of ['EARLY','LEGACY','CLEARED']as const)test('saved DIRECT_DONE draft transition '+mode+' preserves exact local input without sending',async({page})=>{
 let releaseJourney=()=>{},releaseCapability=()=>{};const journey=new Promise<void>(done=>releaseJourney=done),capability=new Promise<void>(done=>releaseCapability=done);const requests:string[]=[],writes:string[]=[];let sessions=0;
 const chat={conversation_id:'qa-early',title:'原已完成普通问答',version:2,created_at:'2026-11-28T00:00:00Z'};
 const response={state:'SUCCEEDED',resultKind:'DIRECT_ANSWER',invocationId:'saved-original',contextId:'saved-context',turnId:'saved-turn',turnVersion:1,aggregateVersion:2,answer:'原会话真实结构的已保存助手答复。',draft:null,dataNeeds:[],conversationDelivery:{state:'SAVED',messageId:'answer-original'}};
 const messages=[{message_id:'question-original',sequence:1,author_id:'human:ordinary',content:'原普通问题',disposition:'GOAL_RECORDED',request_key:'original-user',created_at:'2026-11-28T00:00:00Z'},{message_id:'answer-original',sequence:2,author_id:'human:ordinary',kind:'SOURCE',content:response.answer,facts:{assistantResponse:true,invokedBy:'human:ordinary',requestKey:'original-request',userMessageId:'question-original',state:'SUCCEEDED',response,source:{kind:'DRAFT',invocationId:response.invocationId}},created_at:'2026-11-28T00:00:01Z'}];
 await page.addInitScript(()=>{(window as unknown as {draftFocusCount:number}).draftFocusCount=0;window.addEventListener('focus',()=>{(window as unknown as {draftFocusCount:number}).draftFocusCount++})});
 page.on('pageerror',e=>console.log('BROWSER_ERROR',e.message));
 await page.route('**/api/**',async route=>{const req=route.request(),url=new URL(req.url()),p=url.pathname;if(!p.startsWith('/api/'))return route.continue();requests.push(req.method()+' '+p);if(req.method()!=='GET')writes.push(p);const result=(v:unknown)=>route.fulfill({json:{result:v}});
  if(p.endsWith('/session')){sessions++;return route.fulfill({json:{principal:{principalId:'human:ordinary',tenantId:'tenant',securityDomain:'domain'},csrfToken:'current-synthetic-csrf',session:{}}})}
  if(p.endsWith('/development-administrator'))return result({enabled:false});
  if(p.endsWith('/conversations/capabilities'))return result({enabled:true,historyMessagePaging:true,historyReadPreparation:true});
  if(p.endsWith('/draft-assistance/capabilities')){await capability;return result({conversationUnderstanding:true,conversationRelationRouting:true,initialUnderstandingAdoption:true})}
  if(p.endsWith('/history-access'))return result({available:true,items:[{state:'EFFECTIVE'}]});
  if(p.endsWith('/messages'))return result({conversation:chat,messages,page:{hasMore:false,nextCursor:null,resumeCursor:'opaque-current'}});
  if(p.endsWith('/work-links'))return result({conversation:chat,links:[]});
  if(p.endsWith('/capability-context'))return result({conversation:chat,message:null});
  if(p.endsWith('/understanding-successes'))return result({conversation:chat,items:[],page:{hasMore:false,nextCursor:null,resumeCursor:null},unavailable:false});
  if(p.endsWith('/journey')){await journey;return result({version:4,state:{key:'original-qa',phase:'DIRECT_DONE',understandingProtocol:3,userMessageId:'question-original',question:'原普通问题',messages:[{id:'user:question-original',text:'原普通问题'}],draft:response,log:[]}})}
  if(p.endsWith('/head'))return result({conversation:chat});
  if(req.method()!=='GET')return route.fulfill({status:405,json:{reasonCode:'UNEXPECTED_BUSINESS_WRITE'}});
  return result({items:[]});
 });
 try{
  const scope=JSON.stringify(['human:ordinary','tenant','domain',null]),legacyKey='work-view.v1:'+scope+':qa-early:original-qa:1:answer',currentKey='work-view.v1:'+scope+':private:qa-early:routed-input:answer';
  await page.addInitScript(({legacyKey,currentKey,mode})=>{sessionStorage.setItem(legacyKey,'历史未发送原稿');if(mode==='CLEARED')sessionStorage.setItem(currentKey,'')},{legacyKey,currentKey,mode});
  await page.goto('/work?conversation=qa-early');await expect(page.locator('#conversation-message-answer-original .private-user')).toHaveText(response.answer);
  const text=mode==='EARLY'?'只读测速草稿，不发送':mode==='LEGACY'?'历史未发送原稿':'',input=page.getByLabel('描述你的问题',{exact:true});
  const snapshot=async(label:string)=>({value:await page.getByLabel(label,{exact:true}).inputValue(),id:await page.getByLabel(label,{exact:true}).getAttribute('id'),focused:await page.evaluate(()=>document.activeElement?.id),windowFocusCount:await page.evaluate(()=>(window as unknown as {draftFocusCount:number}).draftFocusCount),sessions,allTextareas:await page.locator('textarea').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect(),style=getComputedStyle(n);return {id:n.id,value:n.value,disabled:n.disabled,label:document.querySelector('label[for="'+n.id+'"]')?.textContent,rect:{x:r.x,y:r.y,width:r.width,height:r.height},viewport:{width:innerWidth,height:innerHeight},display:style.display,visibility:style.visibility,inViewport:r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth}})),requests:[...requests],writes:[...writes]});
  writeFileSync('../../../BEFORE_INPUT-'+mode+'.json',JSON.stringify(await snapshot('描述你的问题'),null,2));
  await expect(input).toBeInViewport();await expect(input).toBeEditable();if(mode==='EARLY'){await input.fill(text);await expect(input).toHaveValue(text)}await expect(page.getByRole('button',{name:'发送',exact:true})).toBeDisabled();
  writeFileSync('../../../EARLY_INPUT-'+mode+'.json',JSON.stringify(await snapshot('描述你的问题'),null,2));releaseCapability();releaseJourney();
  const current=page.getByLabel('继续提问',{exact:true});await expect(current).toBeVisible();writeFileSync('../../../AFTER_CONTEXT-'+mode+'.json',JSON.stringify(await snapshot('继续提问'),null,2));
  await expect(current).toBeInViewport();await expect(current).toHaveValue(text);if(mode==='CLEARED')await expect(page.getByRole('button',{name:'发送',exact:true})).toBeDisabled();else await expect(page.getByRole('button',{name:'发送',exact:true})).toBeEnabled();expect(await page.evaluate(key=>sessionStorage.getItem(key),legacyKey)).toBe('历史未发送原稿');
  expect(writes).toEqual(['/api/workbench/v1/conversations/qa-early/history-access']);
 }finally{releaseCapability();releaseJourney()}
});
