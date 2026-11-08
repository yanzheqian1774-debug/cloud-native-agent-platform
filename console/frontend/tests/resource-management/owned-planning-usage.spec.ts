import {test,expect,type Page} from '@playwright/test';
const actor={principalId:'human:usage',tenantId:'usage',securityDomain:'test'};
async function setup(page:Page,mode='normal'){
 const s={writes:[] as string[],reads:[] as string[],denied:false,other:false,hold:false,release:()=>{},held:0};
 await page.route('**/api/**',async route=>{
  const r=route.request(),p=decodeURIComponent(new URL(r.url()).pathname);if(r.method()!=='GET'){s.writes.push(p);return route.abort()}
  if(p.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{...actor,...(s.other?{principalId:'other'}:{})},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture'}});
  if(p.endsWith('/conversations/capabilities'))return route.fulfill({json:{result:{enabled:false}}});
  if(p.endsWith('/conversations'))return route.fulfill({json:{result:{items:[{conversation_id:'original'}]}}});
  if(p.endsWith('/conversations/original'))return route.fulfill({json:{result:{conversation:{conversation_id:'original',title:'原销售分析'},messages:['settled','pending','settled'].map(id=>({facts:{source:{kind:'PLANNING',invocationId:id}}})),links:[]}}});
  if(p.endsWith('/usage')){
   s.reads.push(p);if(s.hold){s.held++;await new Promise<void>(resolve=>{s.release=resolve})}
   if(s.denied)return route.fulfill({status:404,json:{reasonCode:'PROVIDER_USAGE_NOT_FOUND'}});
   if(mode==='identity')s.other=true;
   const settled=p.includes('/settled/');
   return route.fulfill({json:{result:{schemaVersion:'provider-usage-read.v1',reservationId:'reservation:'+p,providerInvoice:'NOT_VERIFIED',settlement:settled?{status:'ESTIMATE_SETTLED',reservation_retained:false,estimate_microusd:mode==='malformed'?-1:1234567,input_tokens:200,output_tokens:30}:{status:'PENDING_RECONCILIATION',reservation_retained:true}}}});
  }
  return route.fulfill({status:404,json:{reasonCode:'NOT_CONFIGURED'}});
 });return s;
}
for(const width of [1280,390])test('owned usage projection and return '+width,async({page})=>{
 await page.setViewportSize({width,height:900});const s=await setup(page);await page.goto('/usage');await expect(page.getByRole('table')).toContainText('USD 1.234567');expect(s.reads).toHaveLength(2);await page.getByRole('row').filter({hasText:'USD 1.234567'}).getByRole('button').click();await expect(page.getByRole('region',{name:'原规划计量详情'})).toContainText('输入 200 Token');await expect(page.getByRole('link',{name:'返回这次调用的原会话'})).toHaveAttribute('href','/work?conversation=original');await page.reload();await expect(page.getByRole('region',{name:'原规划计量详情'})).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.getByLabel('计量状态').selectOption('PENDING_RECONCILIATION');await expect(page.getByRole('table')).not.toContainText('USD');await expect(page.getByRole('table')).toContainText('待核实，不能认定零费用');expect(s.writes).toEqual([]);
});
test('denied refresh withdraws old totals and detail',async({page})=>{const s=await setup(page);await page.goto('/usage?invocation=settled');await expect(page.getByRole('region',{name:'原规划计量详情'})).toBeVisible();s.denied=true;await page.getByRole('button',{name:'重新读取计量记录'}).click();await expect(page.getByRole('region',{name:'原规划计量详情'})).toHaveCount(0);await expect(page.getByRole('region',{name:'已读规划计量统计'})).not.toContainText('USD');await expect(page.getByText('以下不是完整费用总额',{exact:false})).toBeVisible();expect(s.writes).toEqual([])});
test('invalid amount is not displayed or summed',async({page})=>{const s=await setup(page,'malformed');await page.goto('/usage');await expect(page.getByRole('table')).toContainText('原预留保留');await expect(page.getByRole('table')).not.toContainText('USD');await expect(page.getByText('以下不是完整费用总额',{exact:false})).toBeVisible();expect(s.writes).toEqual([])});
test('actor switch during receipt read withdraws all facts',async({page})=>{const s=await setup(page,'identity');await page.goto('/usage');await expect(page.getByRole('alert')).toContainText('身份已变化');await expect(page.getByRole('table')).toHaveCount(0);expect(s.writes).toEqual([])});
test('expiry withdraws totals and selected receipt',async({page})=>{await page.clock.install();const s=await setup(page);await page.goto('/usage?invocation=settled');await expect(page.getByRole('region',{name:'原规划计量详情'})).toBeVisible();await page.clock.fastForward(31000);await expect(page.getByRole('alert')).toContainText('快照已到期');await expect(page.getByRole('region',{name:'原规划计量详情'})).toHaveCount(0);expect(s.writes).toEqual([])});
test('late receipt after logout cannot restore data',async({page})=>{const s=await setup(page);s.hold=true;await page.goto('/usage');await expect.poll(()=>s.held).toBe(1);await page.evaluate(()=>window.dispatchEvent(new Event('workbench-session-expired')));s.hold=false;s.release();await expect(page.getByRole('alert')).toContainText('登录已失效');await expect(page.getByRole('table')).toHaveCount(0);expect(s.writes).toEqual([])});
