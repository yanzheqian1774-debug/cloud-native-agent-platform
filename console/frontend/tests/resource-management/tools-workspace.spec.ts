import {expect,test,type Page} from '@playwright/test';

const principal={principalId:'human:reader',tenantId:'tenant',securityDomain:'test'};
const items=['a','b'].map(id=>({kind:'mcp',identity:'mcp:'+id,revisionId:'revision:'+id,digest:id.repeat(64),name:'来源 '+id,state:'PUBLISHED',enabled:true,isCurrentPublished:true,isCurrentDraft:false,createdAt:null,executionReady:false}));
const result=(id='a',empty=false)=>({identity:'mcp:'+id,name:'来源 '+id,revisionId:'revision:'+id,revisionDigest:id.repeat(64),sourceRevisionState:'PUBLISHED',sourceEnabled:true,sourceArchived:false,subject:principal.principalId,scope:principal,executionAuthority:'NONE',availability:'EXACT_SNAPSHOT_SAVED',snapshotsTruncated:false,snapshots:[{snapshotId:'snapshot:'+id,digest:'c'.repeat(64),capturedAt:'2026-11-10T12:00:00Z',protocolRevision:'saved',toolsTruncated:false,tools:empty?[]:[{name:'find_orders',description:'读取来源 '+id+' 的订单',inputSchema:{type:'object',properties:{orderId:{type:'string',description:'订单编号'}},required:['orderId']},selectedInSavedSnapshot:true,annotations:{readOnlyHint:true}}]}]});
const url=(extra:Record<string,string>={})=>'/tools?'+new URLSearchParams({query:'来源',source:items[0].identity,revision:items[0].revisionId,digest:items[0].digest,...extra});
async function setup(page:Page,mode='normal'){
 const writes:string[]=[],reads:string[]=[];
 await page.route('**/api/workbench/v1/**',route=>{
  const r=route.request(),u=new URL(r.url());if(r.method()!=='GET')writes.push(u.pathname);
  if(u.pathname.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal,session:{},csrfToken:'test'}});
  if(u.pathname==='/api/workbench/v1/resource-directory')return route.fulfill({json:{result:{items,subject:principal.principalId,scope:principal,nextCursor:null,executionAuthority:'NONE'}}});
  if(u.pathname.endsWith('/tools')){
   reads.push(u.pathname);const id=decodeURIComponent(u.pathname).includes('mcp:b')?'b':'a';
   if(mode==='denied'&&id==='b')return route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
   const data=result(id,mode==='empty');if(mode==='unknown'){data.snapshots=[];data.availability='NO_EXACT_SNAPSHOT'}
   if(mode==='disabled'){data.sourceEnabled=false;data.sourceArchived=true}
   if(mode==='many'){const first=data.snapshots[0].tools[0];data.snapshots[0].tools=Array.from({length:30},(_,i)=>({...first,name:'tool_'+i}))}
   return route.fulfill({json:{result:data}});
  }
  if(u.pathname.includes('/resource-directory/mcp/'))return route.fulfill({json:{result:{kind:'mcp',identity:items[0].identity,name:items[0].name,subject:principal.principalId,scope:principal,revision:{revisionId:items[0].revisionId,digest:items[0].digest,state:'PUBLISHED',content:{description:'准确 MCP 来源'}},usage:[]}}});
  return route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}});
 });
 return {writes,reads};
}

test('saved operation detail returns through fixed MCP without invocation or list fanout',async({page},testInfo)=>{
 const {writes,reads}=await setup(page);await page.goto(url());
 await expect(page.getByRole('article',{name:'find_orders',exact:true})).toBeVisible();expect(reads).toHaveLength(1);
 await page.getByLabel('筛选已加载工具',{exact:true}).fill('absent');await expect(page.getByText('当前已加载快照中没有匹配工具。',{exact:true})).toBeVisible();
 await page.getByLabel('筛选已加载工具',{exact:true}).fill('find');expect(reads).toHaveLength(1);
 await page.screenshot({path:testInfo.outputPath('tool-cards.png'),fullPage:true});
 await page.getByRole('button',{name:'查看工具详情',exact:true}).click();
 await expect(page.getByRole('cell',{name:'订单编号',exact:true})).toBeVisible();
 await expect(page.getByText('当前没有可确认准确运行版本的调用回执。',{exact:true})).toBeVisible();
 await page.screenshot({path:testInfo.outputPath('tool-detail.png'),fullPage:true});
 const fixed=page.url();await page.getByRole('link',{name:'查看来源 MCP',exact:true}).click();
 await page.getByRole('link',{name:'返回工具详情',exact:true}).click();
 await expect(page.getByRole('cell',{name:'订单编号',exact:true})).toBeVisible();expect(page.url()).toBe(fixed);
 await page.getByRole('link',{name:'返回工具列表',exact:true}).click();
 expect(new URL(page.url()).searchParams.get('snapshot')).toBe('snapshot:a');expect(new URL(page.url()).searchParams.get('query')).toBe('来源');expect(new URL(page.url()).searchParams.get('toolQuery')).toBe('find');expect(writes).toEqual([]);
});

test('unreadable replacement source and expired session withdraw previous tool contents',async({page})=>{
 const {writes}=await setup(page,'denied');await page.goto(url());await expect(page.getByText('读取来源 a 的订单',{exact:true})).toBeVisible();
 await page.getByLabel('工具来源',{exact:true}).selectOption(JSON.stringify([items[1].identity,items[1].revisionId,items[1].digest]));
 await expect(page.getByRole('alert')).toContainText('此版本的工具记录未读回');await expect(page.getByText('读取来源 a 的订单',{exact:true})).toHaveCount(0);
 await page.evaluate(()=>window.dispatchEvent(new Event('workbench-session-expired')));await expect(page.getByRole('alert')).toContainText('当前登录已失效');expect(writes).toEqual([]);
});

for(const mode of ['empty','unknown'])test(`exact zero tools differs from unavailable provenance ${mode}`,async({page})=>{
 await setup(page,mode);await page.goto(url());await expect(page.getByText(mode==='empty'?'该固定发现快照明确返回 0 项工具。':'尚无可确认属于此版本的发现快照；旧记录来源不明时不会使用最新版替代。',{exact:true})).toBeVisible();
});

test('missing original snapshot never falls back to another same-name operation',async({page})=>{
 await setup(page);await page.goto(url({snapshot:'snapshot:missing',snapshotDigest:'d'.repeat(64),tool:'find_orders'}));await expect(page.getByRole('alert')).toContainText('原发现快照或摘要未能核对');await expect(page.getByText('读取来源 a 的订单',{exact:true})).toHaveCount(0);
});

test('stalled tools read stops visibly and only manual retry requests the same version',async({page})=>{
 await page.addInitScript(()=>{const original=window.setTimeout;window.setTimeout=((handler:TimerHandler,ms?:number,...args:unknown[])=>original(handler,ms===30000?700:ms,...args)) as typeof window.setTimeout});
 const {writes}=await setup(page);let attempts=0;
 await page.route('**/api/workbench/v1/resource-directory/mcp/*/*/tools',route=>{attempts++;if(attempts===1)return;return route.fallback()});
 await page.goto(url());await expect(page.getByRole('alert')).toContainText('读取工具等待超时');expect(attempts).toBe(1);
 await page.getByRole('button',{name:'重新读取',exact:true}).click();await expect(page.getByRole('article',{name:'find_orders',exact:true})).toBeVisible();
 expect(attempts).toBe(2);expect(new URL(page.url()).searchParams.get('revision')).toBe(items[0].revisionId);expect(writes).toEqual([]);
});

test('return from operation detail restores the real workspace scroll container',async({page})=>{
 await setup(page,'many');await page.goto(url());await page.getByRole('article',{name:'tool_24',exact:true}).getByRole('button',{name:'查看工具详情',exact:true}).click();
 await expect(page.getByRole('heading',{name:'tool_24',exact:true})).toBeVisible();
 await page.getByRole('link',{name:'返回工具列表',exact:true}).click();
 await expect(page.getByRole('article',{name:'tool_24',exact:true})).toBeVisible();
 await expect.poll(()=>page.locator('.skill-frame-content').evaluate(n=>n.scrollTop)).toBeGreaterThan(100);
});

test('known archived and disabled source states remain visible on cards and direct tool detail',async({page})=>{
 await setup(page,'disabled');await page.goto(url());const card=page.getByRole('article',{name:'find_orders',exact:true});
 await expect(card.getByText('来源已归档',{exact:true})).toBeVisible();await expect(card.getByText('来源已停用',{exact:true})).toBeVisible();
 await page.goto(url({snapshot:'snapshot:a',snapshotDigest:'c'.repeat(64),tool:'find_orders'}));
 await expect(page.getByLabel('来源当前状态',{exact:true})).toContainText('来源已归档');await expect(page.getByLabel('来源当前状态',{exact:true})).toContainText('来源已停用');
});

test('exact invocation outcomes stay distinct without retry or legacy attribution',async({page},testInfo)=>{
 const {writes}=await setup(page);
 await page.route('**/resource-directory/mcp/*/*/tools',route=>{
  const data=result();
  const enriched={...data,unattributedSourceInvocationCount:2,invocationWindowTruncated:true,snapshots:data.snapshots.map(s=>({...s,tools:s.tools.map(t=>({...t,invocations:[
   {invocationId:'call:ok',invokedAt:'2026-11-12T01:00:00Z',outcome:'TOOL_RESPONSE_RECEIVED'},
   {invocationId:'call:error',invokedAt:'2026-11-12T01:01:00Z',outcome:'TOOL_ERROR'},
   {invocationId:'call:unknown',invokedAt:'2026-11-12T01:02:00Z',outcome:'RESULT_UNKNOWN'},
   {invocationId:'call:cancel',invokedAt:null,outcome:'CANCELLED_BEFORE_DISPATCH'},
   {invocationId:'call:before',invokedAt:null,outcome:'NOT_DISPATCHED'},
  ]}))}))};
  return route.fulfill({json:{result:enriched}});
 });
 await page.goto(url());await page.getByRole('button',{name:'查看工具详情',exact:true}).click();
 const history=page.getByRole('region',{name:'调用记录',exact:true});
 for(const label of ['工具已返回','工具返回错误','调用结果未确认','调用前已取消','未发出工具调用'])await expect(history.getByText(label,{exact:true})).toBeVisible();
 await expect(history).toContainText('可能已产生影响。不会自动重试。');
 await expect(history).toContainText('无法归属于当前工具与版本');
 await expect(history).toContainText('不能据此判断完整调用历史');
 await expect(history.getByRole('button')).toHaveCount(0);
 await page.screenshot({path:testInfo.outputPath('tool-invocation-outcomes.png'),fullPage:true});
 const fixed=page.url();await page.getByRole('link',{name:'查看来源 MCP',exact:true}).click();await page.getByRole('link',{name:'返回工具详情',exact:true}).click();expect(page.url()).toBe(fixed);
 await expect(history.getByText('调用结果未确认',{exact:true})).toBeVisible();expect(writes).toEqual([]);
});
