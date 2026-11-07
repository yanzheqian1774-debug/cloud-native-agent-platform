import {expect,test,type Page} from '@playwright/test';
const actor={principalId:'human:model-read-fixture',tenantId:'model-fixture',securityDomain:'isolated'};
const item=(n=1)=>({modelId:'model:read',revisionId:'model-revision:'+n,digest:String(n).repeat(64),revision:n,name:'隔离模型目录核对',capabilities:['STRUCTURED_OUTPUT'],compatibility:['JSON_SCHEMA'],invocationLimits:[{name:'max_output_tokens',value:4096,unit:'TOKEN'}],provider:{provider_id:'provider:fixture',revision_id:'1',digest:'a'.repeat(64)},endpoint:{endpoint_id:'endpoint:fixture',revision_id:'1',digest:'b'.repeat(64)},connectionProfile:{profile_id:'profile:fixture',revision_id:'1',digest:'c'.repeat(64)},createdAt:'2026-11-08T00:00:00Z',isCurrentRevision:n===2,state:n===1?'PUBLISHED_ENABLED':'NOT_RECORDED',lifecycleHighWater:n===1?{ordinal:3,fact_id:'fact:3',fact_digest:'d'.repeat(64)}:null,availability:'NOT_MEASURABLE',price:'NOT_MEASURABLE'});
async function fixture(page:Page){
 const state={writes:[] as string[],modelReads:[] as string[],denied:false,actorChange:false,responseActorChange:false,hold:false,held:0,release:()=>{},wrongDigest:false,expires:Date.now()+3600000};
 await page.route('**/api/**',async route=>{
  const r=route.request(),u=new URL(r.url()),path=decodeURIComponent(u.pathname);
  if(r.method()!=='GET'){state.writes.push(r.method()+' '+path);return route.abort()}
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{...actor,...(state.actorChange?{principalId:'human:other'}:{})},session:{expiresAt:new Date(state.expires).toISOString(),idleExpiresAt:new Date(state.expires).toISOString()},csrfToken:'fixture-only'}});
  if(path.endsWith('/conversations/capabilities'))return route.fulfill({json:{result:{enabled:false}}});
  if(path.includes('/model-directory')){
   state.modelReads.push(path+u.search);
   if(state.hold){state.held++;await new Promise<void>(resolve=>{state.release=resolve})}
   if(state.denied)return route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
   const detail=path.includes('/revisions/'),v=item(path.endsWith(':2')?2:1);
   if(state.wrongDigest)v.digest='0'.repeat(64);
   const result={subject:state.responseActorChange?'human:foreign':actor.principalId,scope:{tenantId:actor.tenantId,securityDomain:actor.securityDomain},basis:'CURRENT_EXACT_MODEL_READ',executionAuthority:'NONE',...(detail?{item:v}:{items:u.searchParams.get('query')==='nothing'?[]:[item(u.searchParams.has('cursor')?2:1)],nextCursor:u.searchParams.has('cursor')?null:'opaque-model-cursor'})};
   try{return await route.fulfill({json:{schemaVersion:'workbench-operation.v1',result,continuationIds:[]}})}catch{return}
  }
  return route.fulfill({status:404,json:{reasonCode:'NOT_CONFIGURED'}});
 });
 return state;
}
for(const width of [1280,390])test(`model read complete list exact detail return ${width}`,async({page},info)=>{
 await page.setViewportSize({width,height:900});const state=await fixture(page);await page.goto('/models?query=隔离');
 await expect(page.getByRole('table')).toBeVisible();await page.getByRole('link',{name:'查看准确版本'}).click();await expect(page.getByRole('region',{name:'模型准确版本'})).toContainText('已发布并启用');await expect(page.getByRole('region',{name:'模型准确版本'})).toContainText('历史修订');
 await expect(page).toHaveURL(/digest=1{64}/);await page.reload();await expect(page.getByRole('region',{name:'模型准确版本'})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.screenshot({path:info.outputPath(`model-exact-${width}.png`)});
 await page.getByRole('link',{name:'返回原筛选列表'}).click();await expect(page.getByLabel('搜索模型')).toHaveValue('隔离');await page.getByRole('button',{name:'下一页可读版本'}).click();await expect(page.getByRole('table')).toContainText('尚无生命周期记录');await expect(page.getByRole('table')).toContainText('当前修订');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.screenshot({path:info.outputPath(`model-list-${width}.png`)});expect(state.writes).toEqual([]);
});
test('model permission loss withdraws exact detail and makes no empty claim',async({page})=>{const s=await fixture(page);await page.goto('/models');await page.getByRole('link',{name:'查看准确版本'}).click();await expect(page.getByRole('region',{name:'模型准确版本'})).toBeVisible();s.denied=true;await page.getByRole('button',{name:'重新核对'}).click();await expect(page.getByRole('alert')).toContainText('不能据此判断没有记录');await expect(page.getByRole('region',{name:'模型准确版本'})).toHaveCount(0);expect(s.writes).toEqual([])});
for(const mode of ['actor','digest'])test(`model ${mode} mismatch cannot display exact content`,async({page})=>{const s=await fixture(page);await page.goto('/models');await expect(page.getByRole('table')).toBeVisible();if(mode==='actor')s.responseActorChange=true;else s.wrongDigest=true;await page.getByRole('link',{name:'查看准确版本'}).click();await expect(page.getByRole('alert')).toBeVisible();await expect(page.getByRole('region',{name:'模型准确版本'})).toHaveCount(0);expect(s.writes).toEqual([])});
test('model session expires withdraws visible content and a late list cannot restore it',async({page})=>{const s=await fixture(page);s.expires=Date.now()+2000;await page.goto('/models');await expect(page.getByRole('table')).toBeVisible();await expect(page.getByRole('alert')).toBeVisible({timeout:6000});await expect(page.getByRole('table')).toHaveCount(0);expect(s.writes).toEqual([])});
test('model late list and changed subject do not replace a newer filter',async({page})=>{const s=await fixture(page);await page.goto('/models');await expect(page.getByRole('table')).toBeVisible();s.hold=true;await page.getByRole('button',{name:'下一页可读版本'}).click();await expect.poll(()=>s.held).toBe(1);s.hold=false;await page.getByLabel('搜索模型').fill('nothing');await expect(page.getByRole('heading',{name:'当前筛选下暂无可读模型版本'})).toBeVisible();s.release();await expect(page.getByRole('table')).toHaveCount(0);s.actorChange=true;await page.getByRole('button',{name:'重新核对'}).click();await expect(page.getByRole('alert')).toBeVisible();expect(s.writes).toEqual([])});
test('model malformed exact link does not dispatch a directory read',async({page})=>{const s=await fixture(page);await page.goto('/models?model=foreign&revision=x&digest=bad');await expect(page.getByRole('alert')).toBeVisible();expect(s.modelReads).toEqual([]);expect(s.writes).toEqual([])});
