import {test,expect,type Page} from '@playwright/test';
const root='/api/workbench/v1/business-processes';
const architecture={domains:[{domain_id:'d1',name:'采购管理',band:'CORE'}],groups:[{group_id:'g1',domain_id:'d1',name:'供应商管理'}]};
const content={name:'到货核验',business_code:'B-1',domain_id:'d1',group_id:'g1',owner_description:'采购经理',purpose:'核对到货与订单',improvement_notes:null,activities:[{activity_id:'a1',name:'核对到货',responsible_role:'仓储专员',inputs:['到货单'],outputs:['差异清单'],completion_conditions:['每项差异有依据'],human_boundary:'采购经理判断例外处理'},{activity_id:'a2',name:'补充凭证',responsible_role:'采购专员',inputs:[],outputs:[],completion_conditions:[],human_boundary:null}],handoffs:[{from_activity_id:'a1',to_activity_id:'a2',event:'NEEDS_INFORMATION',explanation:'缺少凭证时转去补齐',responsible_role:'采购专员'},{from_activity_id:'a2',to_activity_id:'a1',event:'COMPLETED',explanation:'补齐后返回核对',responsible_role:'采购专员'}]};
async function fixture(page:Page){
 const state={writes:[] as string[],reads:[] as string[],denied:false,mismatch:false,empty:false,editorDenied:false,principalId:'human:test',tenantId:'tenant'};
 await page.route('**/api/**',route=>{
  const url=new URL(route.request().url()),path=url.pathname;state.reads.push(path+url.search);
  if(route.request().method()!=='GET')state.writes.push(path);
  const json=(result:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result}});
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{principalId:state.principalId,tenantId:state.tenantId,securityDomain:'domain'},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'csrf'}});
  if(path===root+'/editor-access')return state.editorDenied?route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}}):json({allowed:true,kind:url.searchParams.get('kind'),action:url.searchParams.get('action'),objectId:url.searchParams.get('objectId')});
  if(path===root+'/architecture')return json({objectId:'architecture',revisionId:url.searchParams.get('revision')||'architecture-current',digest:state.mismatch?'b'.repeat(64):'a'.repeat(64),aggregateVersion:2,record:{content:url.searchParams.has('revision')?architecture:state.empty?{domains:[],groups:[]}:{domains:[{...architecture.domains[0],name:'采购管理（当前）'}],groups:architecture.groups}}});
  if(path===root+'/p1')return state.denied?route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}}):json({objectId:'p1',revisionId:'r1',digest:'c'.repeat(64),aggregateVersion:1,record:{content,architectureReference:{revisionId:'architecture-v1',digest:'a'.repeat(64)}}});
  if(path===root){const second=!!url.searchParams.get('cursor');return json({items:state.empty?[]:[{processId:second?'p2':'p1',revisionId:second?'r2':'r1',name:second?'合同核对':'到货核验',domainId:'d1',groupId:'g1',ownerDescription:'采购经理',state:'DRAFT',aggregateVersion:1}],nextCursor:second||state.empty?null:'page-two'})}
  return json({items:[],entries:[],rejectedResources:0});
 });
 return state;
}
test('independent business directory reads fixed architecture and business handoffs',async({page})=>{
 const state=await fixture(page);await page.goto('/business-processes');
 const nav=page.getByRole('navigation',{name:'P1 核心产品导航',exact:true});
 await expect(nav.getByRole('link',{name:'业务流程',exact:true})).toHaveAttribute('aria-current','page');
 await expect(nav.locator('a[href="/workflow-definitions"]')).not.toHaveAttribute('aria-current','page');
 await page.screenshot({path:test.info().outputPath('directory-controlled.png'),fullPage:true});
 await page.getByRole('link',{name:'查看流程与活动'}).click();
 await expect(page.getByRole('heading',{name:'到货核验',exact:true})).toBeVisible();
 await expect(page.locator('.f3-business-processes')).toContainText('采购管理 / 供应商管理');
 await expect(page.locator('.f3-business-processes')).not.toContainText('采购管理（当前）');
 await expect(page.getByText('仓储专员',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'完成后交接：补充凭证 → 核对到货',exact:true}).click();
 await expect(page.getByText('补齐后返回核对',{exact:true})).toBeVisible();
 await expect(page.getByText('登记草稿 · 尚未发布',{exact:true})).toBeVisible();
 await page.screenshot({path:test.info().outputPath('detail-controlled.png'),fullPage:true});
 await page.reload();await page.getByRole('button',{name:'完成后交接：补充凭证 → 核对到货',exact:true}).click();await expect(page.getByText('补齐后返回核对',{exact:true})).toBeVisible();
 expect(state.reads.some(value=>value.includes('architecture?revision=architecture-v1'))).toBeTruthy();expect(state.writes).toEqual([]);
});
test('pagination and filtering use server data and reset cursor',async({page})=>{
 const state=await fixture(page);await page.goto('/business-processes');await page.getByRole('button',{name:'下一页',exact:true}).click();
 await expect(page.getByRole('heading',{name:'合同核对',exact:true})).toBeVisible();
 await page.getByRole('textbox',{name:'搜索业务流程'}).fill('到货');await page.getByRole('button',{name:'搜索',exact:true}).click();
 await expect(page.getByRole('heading',{name:'到货核验',exact:true})).toBeVisible();expect(new URL(page.url()).searchParams.has('cursor')).toBeFalsy();expect(state.writes).toEqual([]);
});
test('empty architecture does not seed prototype enterprise facts',async({page})=>{
 const state=await fixture(page);state.empty=true;await page.goto('/business-processes?view=architecture');
 await expect(page.getByText('尚未登记业务领域',{exact:true})).toHaveCount(3);await expect(page.locator('.f3-business-processes')).not.toContainText('供应商管理');expect(state.writes).toEqual([]);
});
test('denied process and mismatched reference do not display content',async({page})=>{
 const state=await fixture(page);state.denied=true;await page.goto('/business-processes?process=p1&revision=r1');
 await expect(page.locator('.f3-business-processes [role=alert]')).toContainText('无法读取');await expect(page.getByText('仓储专员',{exact:true})).toHaveCount(0);
 state.denied=false;state.mismatch=true;await page.getByRole('button',{name:'重新读取',exact:true}).click();
 await expect(page.locator('.f3-business-processes [role=alert]')).toContainText('引用版本已变化');await expect(page.getByText('仓储专员',{exact:true})).toHaveCount(0);expect(state.writes).toEqual([]);
});

async function writableFixture(page:Page){
 const state=await fixture(page);
 const writes:Record<string,unknown>[]=[];let saved:Record<string,unknown>|null=null;
 const extra={loseResponse:false,denyReplay:false,hideReceipt:false};
 await page.route('**/api/workbench/v1/business-processes/commands**',route=>{
  const json=(result:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result}});
  if(route.request().method()==='POST'){
   const body=route.request().postDataJSON();writes.push(body);
   if(extra.denyReplay)return route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
   saved=body;
   if(extra.loseResponse)return route.abort('failed');
   return json({objectId:body.objectId,revisionId:'saved-r1',digest:'c'.repeat(64),aggregateVersion:body.expectedVersion+1,state:'DRAFT',executionAuthorized:false});
  }
  if(!saved||extra.hideReceipt)return route.fulfill({status:404,json:{reasonCode:'BUSINESS_PROCESS_COMMAND_NOT_FOUND'}});
  return json({objectId:saved.objectId,revisionId:'saved-r1',digest:'c'.repeat(64),aggregateVersion:Number(saved.expectedVersion)+1,state:'DRAFT',executionAuthorized:false});
 });
 await page.route('**/api/workbench/v1/business-processes/*?revision=*',route=>{
  if(!saved||new URL(route.request().url()).pathname.endsWith('/architecture'))return route.fallback();
  return route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{objectId:saved.objectId,revisionId:'saved-r1',digest:'c'.repeat(64),aggregateVersion:Number(saved.expectedVersion)+1,record:{content:saved.content,architectureReference:{revisionId:'architecture-v1',digest:'a'.repeat(64)}}}}});
 });
 return {state,writes,extra};
}
async function register(page:Page){
 await page.goto('/business-processes');await page.getByRole('button',{name:'登记业务流程',exact:true}).click();
 await page.getByRole('textbox',{name:'流程名称',exact:true}).fill('设备保养交接');
 await page.getByRole('combobox',{name:'业务领域',exact:true}).selectOption('d1');
 await page.getByRole('combobox',{name:'流程组',exact:true}).selectOption('g1');
 await page.getByRole('button',{name:'添加业务活动',exact:true}).click();
 await page.getByRole('textbox',{name:'活动名称',exact:true}).fill('核实保养记录');
 await page.getByRole('textbox',{name:'活动输入（每行一项）',exact:true}).fill('维修记录\n保养计划');
 await page.getByRole('button',{name:'基本信息',exact:true}).click();await page.getByRole('textbox',{name:'业务负责人',exact:true}).fill('设备主管');
}
test('registration saves stable activity identities and latest focused input, then reloads',async({page})=>{
 const {writes}=await writableFixture(page);await register(page);
 await page.getByRole('textbox',{name:'业务负责人',exact:true}).press('Enter');
 await expect(page.getByRole('heading',{name:'设备保养交接',exact:true})).toBeVisible();
 await expect(page.getByText('设备主管',{exact:true})).toBeVisible();
 await page.locator('.bp-activity-node').first().click();
 await expect(page.getByText('维修记录；保养计划',{exact:true})).toBeVisible();
 expect(writes).toHaveLength(1);expect(writes[0].expectedVersion).toBe(0);
 const value=writes[0].content as typeof content;expect(value.activities[0].activity_id).toMatch(/^business-activity:/);expect(value.owner_description).toBe('设备主管');
 await page.reload();await expect(page.getByText('设备主管',{exact:true})).toBeVisible();expect(writes).toHaveLength(1);
});
test('lost save response survives reload and original receipt resolves without another POST',async({page})=>{
 const {writes,extra}=await writableFixture(page);extra.loseResponse=true;await register(page);
 await page.getByRole('button',{name:'保存登记草稿',exact:true}).click();
 await expect(page.getByRole('button',{name:'核实原提交',exact:true})).toBeEnabled();await expect.poll(()=>writes.length).toBe(1);
 await page.reload();await expect(page.getByRole('button',{name:'核实原提交',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'保存登记草稿',exact:true})).toBeDisabled();
 await page.getByRole('button',{name:'核实原提交',exact:true}).click();
 await expect(page.getByRole('heading',{name:'设备保养交接',exact:true})).toBeVisible();expect(writes).toHaveLength(1);
});
test('editing starts from current draft instead of overwriting from historical content',async({page})=>{
 const {state,writes}=await writableFixture(page);await page.goto('/business-processes?process=p1&revision=r1');
 await page.getByRole('button',{name:'修改当前草稿',exact:true}).click();
 await expect(page.getByRole('textbox',{name:'流程名称',exact:true})).toHaveValue('到货核验');
 expect(state.reads.some(value=>value===root+'/p1?revision=')).toBeTruthy();
 await page.getByRole('textbox',{name:'业务目的',exact:true}).fill('核对到货差异并交接补充资料');
 await page.getByRole('button',{name:'保存登记草稿',exact:true}).click();
 await expect(page.getByRole('heading',{name:'到货核验',exact:true})).toBeVisible();await expect(page.locator('dd').filter({hasText:'核对到货差异并交接补充资料'})).toBeVisible();expect(writes).toHaveLength(1);expect(writes[0].expectedVersion).toBe(1);
});

test('a revoked retry keeps the original uncertain command locked across reload',async({page})=>{
 const {writes,extra}=await writableFixture(page);extra.loseResponse=true;extra.hideReceipt=true;await register(page);
 await page.getByRole('button',{name:'保存登记草稿',exact:true}).click();
 await expect(page.getByRole('button',{name:'核实原提交',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'核实原提交',exact:true}).click();
 await expect(page.getByRole('button',{name:'重试同一份提交',exact:true})).toBeVisible();extra.denyReplay=true;
 await page.getByRole('button',{name:'重试同一份提交',exact:true}).click();
 await expect(page.getByRole('button',{name:'保存登记草稿',exact:true})).toBeDisabled();
 await expect.poll(()=>writes.length).toBe(2);expect(writes[1]).toEqual(writes[0]);
 await page.reload();await expect(page.getByRole('button',{name:'核实原提交',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'保存登记草稿',exact:true})).toBeDisabled();expect(writes).toHaveLength(2);
});
test('session expiry hides unsaved business content including uncontrolled fields',async({page})=>{
 await writableFixture(page);await register(page);
 await page.getByRole('textbox',{name:'业务目的',exact:true}).fill('本次未保存的内部交接事项');
 await page.evaluate(()=>window.dispatchEvent(new Event('workbench-session-expired')));
 await expect(page.getByRole('textbox',{name:'业务目的',exact:true})).toHaveCount(0);
 await expect(page.getByRole('textbox',{name:'业务负责人',exact:true})).toHaveCount(0);
 await expect(page.locator('.bp-editor form')).toHaveCount(0);
});

test('business map separates missing-information outbound from completed return, without showing all forms',async({page})=>{
 await fixture(page);await page.goto('/business-processes?process=p1&revision=r1');
 await expect(page.getByRole('navigation',{name:'页面位置',exact:true})).toContainText('业务流程');
 await expect(page.locator('.bp-activity-inspector')).toHaveCount(0);
 await expect(page.locator('.bp-activity-node')).toHaveCount(2);
 await page.getByRole('button',{name:'缺资料，转去补充：核对到货 → 补充凭证',exact:true}).click();
 await expect(page.locator('.bp-activity-inspector')).toContainText('缺少凭证时转去补齐');
 await page.getByRole('button',{name:'完成后交接：补充凭证 → 核对到货',exact:true}).click();
 await expect(page.locator('.bp-activity-inspector')).toContainText('补齐后返回核对');
 await page.locator('.bp-activity-node').first().click();
 await expect(page.locator('.bp-activity-inspector')).toContainText('采购经理判断例外处理');
 await page.getByRole('button',{name:'回到完整图',exact:true}).click();await expect(page.locator('.bp-activity-inspector')).toHaveCount(0);
});

test('same identity restores expired unsent draft only after current edit authorization',async({page})=>{
 const {state,writes}=await writableFixture(page);await register(page);
 await page.getByRole('textbox',{name:'业务目的',exact:true}).fill('待核对的保养交接');
 await page.evaluate(()=>window.dispatchEvent(new Event('workbench-session-expired')));await page.reload();
 await expect(page.getByRole('textbox',{name:'业务目的',exact:true})).toHaveValue('待核对的保养交接');
 state.editorDenied=true;await page.reload();await expect(page.locator('.bp-editor form')).toHaveCount(0);
 await expect(page.locator('.bp-editor [role=alert]')).toContainText('使用范围');expect(writes).toHaveLength(0);
 state.editorDenied=false;await page.reload();await expect(page.getByRole('textbox',{name:'流程名称',exact:true})).toHaveValue('设备保养交接');
});
test('switching accounts does not restore another identity draft',async({page})=>{
 const {state,writes}=await writableFixture(page);await register(page);state.principalId='human:other';await page.reload();
 await expect(page.getByRole('textbox',{name:'流程名称',exact:true})).toHaveValue('');
 state.principalId='human:test';await page.reload();await expect(page.getByRole('textbox',{name:'流程名称',exact:true})).toHaveValue('设备保养交接');expect(writes).toHaveLength(0);
});
test('revoked editing on refocus hides the form without deleting its identity scoped draft',async({page})=>{
 const {state,writes}=await writableFixture(page);await register(page);state.editorDenied=true;
 await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect(page.locator('.bp-editor form')).toHaveCount(0);
 state.editorDenied=false;await page.reload();await expect(page.getByRole('textbox',{name:'流程名称',exact:true})).toHaveValue('设备保养交接');expect(writes).toHaveLength(0);
});

test('explicit logout hides form and the same reauthenticated identity can restore it',async({page})=>{
 const {writes}=await writableFixture(page);await register(page);
 await page.route('**/api/workbench/v1/session',route=>route.request().method()==='DELETE'?route.fulfill({status:204,body:''}):route.fallback());
 await page.locator('.px-identity-menu>summary').click();await page.getByRole('button',{name:'退出登录',exact:true}).click();
 await expect(page.getByRole('heading',{name:'已退出登录',exact:true})).toBeVisible();await expect(page.locator('.bp-editor form')).toHaveCount(0);
 await page.reload();await expect(page.getByRole('textbox',{name:'流程名称',exact:true})).toHaveValue('设备保养交接');expect(writes).toHaveLength(0);
});
test('another workspace cannot recover the previous workspace draft',async({page})=>{
 const {state,writes}=await writableFixture(page);await register(page);state.tenantId='another-tenant';await page.reload();
 await expect(page.getByRole('textbox',{name:'流程名称',exact:true})).toHaveValue('');state.tenantId='tenant';await page.reload();
 await expect(page.getByRole('textbox',{name:'流程名称',exact:true})).toHaveValue('设备保养交接');expect(writes).toHaveLength(0);
});

test('local activity editing preserves one draft and one save, and returns to the filtered directory',async({page})=>{
 const {writes}=await writableFixture(page);await page.goto('/business-processes?query=到货&domain=d1&process=p1&revision=r1');
 await page.getByRole('button',{name:'修改当前草稿',exact:true}).click();
 await page.locator('.bp-activity-node').nth(1).click();
 await expect(page.getByRole('textbox',{name:'活动名称',exact:true})).toHaveCount(1);
 await expect(page.getByRole('textbox',{name:'流程名称',exact:true})).toHaveCount(0);expect(writes).toHaveLength(0);
 await page.getByRole('textbox',{name:'完成标准（每行一项）',exact:true}).fill('核对补充凭证与缺项逐项对应');
 await page.reload();await expect(page.getByRole('textbox',{name:'活动名称',exact:true})).toHaveValue('补充凭证');await expect(page.locator('.bp-activity-node').nth(1)).toHaveAttribute('aria-pressed','true');await expect(page.locator('.bp-activity-node').first()).toHaveAttribute('aria-pressed','false');await expect(page.getByRole('textbox',{name:'完成标准（每行一项）',exact:true})).toHaveValue('核对补充凭证与缺项逐项对应');
 await page.screenshot({path:test.info().outputPath('local-editor-controlled.png')});
 await page.getByRole('button',{name:'保存登记草稿',exact:true}).click();
 await expect(page.getByRole('heading',{name:'到货核验',exact:true})).toBeVisible();expect(writes).toHaveLength(1);
 const saved=writes[0].content as typeof content;expect(saved.activities[1].activity_id).toBe('a2');expect(saved.activities[1].completion_conditions).toEqual(['核对补充凭证与缺项逐项对应']);expect(saved.activities[0]).toEqual(content.activities[0]);
 await page.reload();await page.locator('.bp-activity-node').nth(1).click();await expect(page.locator('.bp-activity-inspector')).toContainText('核对补充凭证与缺项逐项对应');
 await page.getByRole('button',{name:'返回流程目录',exact:true}).click();await expect(page.getByRole('textbox',{name:'搜索业务流程',exact:true})).toHaveValue('到货');await expect(page.getByRole('combobox',{name:'业务领域',exact:true})).toHaveValue('d1');
});

test('missing required information opens its local editor instead of silently failing or submitting',async({page})=>{
 const {writes}=await writableFixture(page);await register(page);await page.locator('.bp-activity-node').first().click();
 await page.getByRole('textbox',{name:'活动名称',exact:true}).fill('');await page.getByRole('button',{name:'基本信息',exact:true}).click();
 await page.getByRole('button',{name:'保存登记草稿',exact:true}).click();await expect(page.getByRole('textbox',{name:'活动名称',exact:true})).toBeFocused();
 await expect(page.locator('.bp-editor [role=alert]')).toContainText('必要信息');expect(writes).toHaveLength(0);
});

test('restored handoff selection and deletion keep the map and local editor aligned',async({page})=>{
 const {writes}=await writableFixture(page);await page.goto('/business-processes?process=p1&revision=r1');await page.getByRole('button',{name:'修改当前草稿',exact:true}).click();
 const handoff=page.getByRole('button',{name:'完成后交接：补充凭证 → 核对到货',exact:true});await handoff.click();await page.evaluate(()=>{const key=Object.keys(sessionStorage).find(item=>item.startsWith('business-process-draft:'));if(!key)throw Error('Draft missing');const draft=JSON.parse(sessionStorage.getItem(key)!);if(typeof draft.selectedHandoff!=='string'||!draft.selectedHandoff.startsWith('business-handoff:'))throw Error('Stable handoff identity missing');draft.content.handoffs.reverse();sessionStorage.setItem(key,JSON.stringify(draft))});await page.reload();
 await expect(handoff).toHaveAttribute('aria-pressed','true');await expect(page.getByRole('textbox',{name:'交接说明',exact:true})).toHaveValue('补齐后返回核对');
 await page.getByRole('button',{name:'移除交接',exact:true}).click();await expect(handoff).toHaveCount(0);await expect(page.getByRole('textbox',{name:'流程名称',exact:true})).toBeVisible();await expect(page.locator('.bp-edge-label[aria-pressed=true]')).toHaveCount(0);
 await page.getByRole('button',{name:'添加业务活动',exact:true}).click();await page.getByRole('textbox',{name:'活动名称',exact:true}).fill('临时草稿活动');await expect(page.locator('.bp-activity-node[aria-pressed=true]')).toContainText('临时草稿活动');
 await page.getByRole('button',{name:'移除活动',exact:true}).click();await expect(page.getByRole('textbox',{name:'流程名称',exact:true})).toBeVisible();await expect(page.locator('.bp-activity-node[aria-pressed=true]')).toHaveCount(0);expect(writes).toHaveLength(0);
});

test('read-only directory and detail hide write entries while preserving readable content',async({page})=>{
 const state=await fixture(page);state.editorDenied=true;
 await page.goto('/business-processes');
 await expect(page.getByText('当前账号可查看，不能修改此项内容。',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'登记业务流程',exact:true})).toHaveCount(0);
 await page.getByRole('link',{name:'查看流程与活动'}).click();
 await expect(page.getByRole('heading',{name:'到货核验',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'修改当前草稿',exact:true})).toHaveCount(0);
 await expect(page.getByText('当前账号可查看，不能修改此项内容。',{exact:true})).toBeVisible();
 await page.goto('/business-processes?process=p1&revision=r1&edit=process');
 await expect(page.getByRole('button',{name:'保存登记草稿',exact:true})).toBeDisabled();
 await expect(page.getByRole('textbox',{name:'流程名称',exact:true})).toHaveCount(0);
 expect(state.writes).toEqual([]);
});

test('view refreshes current edit authority on focus without reloading business data',async({page})=>{
 const state=await fixture(page);await page.goto('/business-processes?process=p1&revision=r1');
 await expect(page.getByRole('button',{name:'修改当前草稿',exact:true})).toBeVisible();
 const detailReads=state.reads.filter(path=>path.startsWith(root+'/p1')).length;
 state.editorDenied=true;await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
 await expect(page.getByText('当前账号可查看，不能修改此项内容。',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'修改当前草稿',exact:true})).toHaveCount(0);
 await expect(page.getByRole('heading',{name:'到货核验',exact:true})).toBeVisible();
 expect(state.reads.filter(path=>path.startsWith(root+'/p1'))).toHaveLength(detailReads);
 state.editorDenied=false;await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
 await expect(page.getByRole('button',{name:'修改当前草稿',exact:true})).toBeVisible();
 expect(state.writes).toEqual([]);
});

test('unavailable edit authority does not mislabel the viewer as read-only',async({page})=>{
 const state=await fixture(page);let unavailable=true;
 await page.route('**/api/workbench/v1/business-processes/editor-access?**',route=>unavailable?route.fulfill({status:503,json:{reasonCode:'AUTHORIZATION_STATE_UNAVAILABLE'}}):route.fallback());
 await page.goto('/business-processes?process=p1&revision=r1');
 await expect(page.getByText('操作权限暂未核实，当前内容仍可查看。',{exact:false})).toBeVisible();
 await expect(page.getByText('当前账号可查看，不能修改此项内容。',{exact:true})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'修改当前草稿',exact:true})).toHaveCount(0);
 unavailable=false;await page.getByRole('button',{name:'重新核对操作权限',exact:true}).click();
 await expect(page.getByRole('button',{name:'修改当前草稿',exact:true})).toBeVisible();
 expect(state.writes).toEqual([]);
});

for(const complete of [false,true])test(`definition validation shows ${complete?'complete definition':'missing facts'} without claiming publication or execution`,async({page})=>{
 const state=await fixture(page);
 await page.route('**/api/workbench/v1/business-processes/p1?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{objectId:'p1',revisionId:'r1',digest:'c'.repeat(64),aggregateVersion:1,record:{content,architectureReference:{revisionId:'architecture-v1',digest:'a'.repeat(64)}},architecture:{objectId:'architecture',revisionId:'architecture-v1',digest:'a'.repeat(64),aggregateVersion:1,record:{content:architecture}},definitionValidation:{status:complete?'COMPLETE':'INCOMPLETE',issues:complete?[]:[{code:'ACTIVITY_FACT_MISSING',path:'activities.1.human_boundary',message:'“补充凭证”尚未填写人工参与边界。'}],executionAuthorized:false}}}}));
 await page.goto('/business-processes?process=p1&revision=r1');
 const validation=page.getByRole('region',{name:'定义校验',exact:true});
 await expect(validation.getByRole('heading',{name:complete?'定义信息已齐全':'待完善 1 项',exact:true})).toBeVisible();
 await expect(validation).toContainText('发布状态以发布记录为准，资源与执行需另行验证');
 if(!complete)await expect(validation).toContainText('“补充凭证”尚未填写人工参与边界。');
 await expect(page.getByText('登记草稿 · 尚未发布',{exact:true})).toBeVisible();
 expect(state.reads.filter(path=>path.startsWith(root+'/architecture'))).toEqual([]);
 expect(state.writes).toEqual([]);
});

async function publicationFixture(page:Page){
 const state=await fixture(page);
 const data={head:'r1',complete:true,loseResponse:false,published:null as null|Record<string,unknown>,writes:[] as Record<string,unknown>[],receipts:new Map<string,Record<string,unknown>>(),publications:new Map<string,Record<string,unknown>>()};
 const digest=(revision:string)=>revision==='r1'?'c'.repeat(64):'d'.repeat(64);
 await page.route('**/api/workbench/v1/business-processes/**',async route=>{
  const url=new URL(route.request().url()),p=url.pathname;
  const json=(result:unknown)=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result}});
  if(p===root+'/p1'){
   const revision=url.searchParams.get('revision')||data.head;
   const hasDraft=!data.published||data.published.revisionId!==data.head;
   return json({objectId:'p1',revisionId:revision,digest:digest(revision),aggregateVersion:data.head==='r1'?1:2,record:{content,architectureReference:{revisionId:'architecture-v1',digest:'a'.repeat(64)}},architecture:{objectId:'architecture',revisionId:'architecture-v1',digest:'a'.repeat(64),aggregateVersion:1,record:{content:architecture}},definitionValidation:{status:data.complete?'COMPLETE':'INCOMPLETE',issues:data.complete?[]:[{code:'MISSING',path:'purpose',message:'请补齐流程目的。'}],executionAuthorized:false},publicationState:{objectId:'p1',published:data.published,draft:hasDraft?{revisionId:data.head,digest:digest(data.head),aggregateVersion:data.head==='r1'?1:2}:null,currentStateAvailable:true,selectedState:data.published?.revisionId===revision?'CURRENT_PUBLISHED':hasDraft&&revision===data.head?'MODIFICATION_DRAFT':data.publications.has(revision)?'HISTORICAL_PUBLISHED':'HISTORICAL_DRAFT',executionAuthorized:false}});
  }
  if(p===root+'/publications'&&route.request().method()==='POST'){
   const command=route.request().postDataJSON();data.writes.push(command);
   const receipt={objectId:'p1',revisionId:command.revisionId,digest:command.digest,contentVersion:command.expectedVersion,publicationVersion:data.receipts.size+1,state:'PUBLISHED',executionAuthorized:false};data.published=receipt;data.receipts.set(command.commandId,receipt);data.publications.set(command.revisionId,receipt);
   if(data.loseResponse)return route.abort('failed');return json(receipt);
  }
  if(p.startsWith(root+'/publications/')){const receipt=data.receipts.get(decodeURIComponent(p.split('/').at(-1)!));return receipt?json(receipt):route.fulfill({status:404,json:{reasonCode:'BUSINESS_PROCESS_COMMAND_NOT_FOUND'}})}
  return route.fallback();
 });
 return {state,data};
}

test('publish and draft navigation preserve current and historical publication labels',async({page})=>{
 const {data}=await publicationFixture(page);await page.goto('/business-processes?process=p1&revision=r1');
 await page.getByRole('button',{name:'发布当前业务定义',exact:true}).click();
 await expect(page.locator('.bp-draft-status')).toHaveText('当前发布版');
 await expect(page.getByRole('button',{name:'修改业务定义',exact:true})).toBeVisible();
 data.head='r2';await page.reload();await page.getByRole('button',{name:'查看修改草稿',exact:true}).click();
 await expect(page.locator('.bp-draft-status')).toHaveText('修改草稿');
 await expect(page.getByRole('button',{name:'查看当前发布版',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'发布当前业务定义',exact:true}).click();await expect(page.locator('.bp-draft-status')).toHaveText('当前发布版');
 await page.goto('/business-processes?process=p1&revision=r1');await expect(page.locator('.bp-draft-status')).toHaveText('历史发布版');await expect(page.getByRole('button',{name:'发布当前业务定义',exact:true})).toHaveCount(0);
 expect(data.writes).toHaveLength(2);expect(data.writes[0].revisionId).toBe('r1');expect(data.writes[1].revisionId).toBe('r2');
});

test('lost publication response restores original command and receipt without another write',async({page})=>{
 const {data}=await publicationFixture(page);data.loseResponse=true;await page.goto('/business-processes?process=p1&revision=r1');await page.getByRole('button',{name:'发布当前业务定义',exact:true}).click();
 await expect.poll(()=>data.writes.length).toBe(1);await expect(page.getByRole('alert')).toContainText('发布结果尚未核实');await page.reload();
 await expect(page.getByRole('button',{name:'核实原发布',exact:true})).toBeVisible();await page.getByRole('button',{name:'核实原发布',exact:true}).click();
 await expect(page.getByRole('button',{name:'核实原发布',exact:true})).toHaveCount(0);await expect(page.locator('.bp-draft-status')).toHaveText('当前发布版');expect(data.writes).toHaveLength(1);
 expect(await page.evaluate(()=>Object.keys(sessionStorage).filter(k=>k.startsWith('business-process-publication:')))).toEqual([]);
});

test('publication requires complete definition and current publisher access',async({page})=>{
 const {state,data}=await publicationFixture(page);data.complete=false;await page.goto('/business-processes?process=p1&revision=r1');
 await expect(page.getByRole('button',{name:'发布当前业务定义',exact:true})).toBeDisabled();
 data.complete=true;state.editorDenied=true;await page.reload();await expect(page.getByText('当前账号可查看，不能修改此项内容。',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'发布当前业务定义',exact:true})).toHaveCount(0);expect(data.writes).toEqual([]);
});

test('another account cannot restore the previous publication command',async({page})=>{
 const {state,data}=await publicationFixture(page);data.loseResponse=true;await page.goto('/business-processes?process=p1&revision=r1');await page.getByRole('button',{name:'发布当前业务定义',exact:true}).click();await expect(page.getByRole('button',{name:'核实原发布',exact:true})).toBeVisible();
 await expect.poll(()=>data.writes.length).toBe(1);await expect(page.getByRole('alert')).toContainText('发布结果尚未核实');
 state.principalId='human:other';state.editorDenied=true;await page.reload();await expect(page.locator('.bp-draft-status')).toHaveText('当前发布版');await expect(page.getByRole('button',{name:'核实原发布',exact:true})).toHaveCount(0);expect(data.writes).toHaveLength(1);
});

for(const [code,status,message] of [
 ['BUSINESS_PROCESS_REFERENCE_NOT_PUBLISHED',422,'关联的资料或数字人版本尚未发布'],
 ['BUSINESS_PROCESS_REFERENCE_UNAVAILABLE',409,'关联的资料或数字人当前不可用'],
 ['BUSINESS_PROCESS_REFERENCE_NOT_FOUND',404,'当前无法读取关联的资料或数字人'],
] as const)test(`publication reference failure explains ${code} without automatic retry`,async({page})=>{
 await publicationFixture(page);let submissions=0;
 await page.route('**/api/workbench/v1/business-processes/publications',route=>{submissions++;return route.fulfill({status,json:{reasonCode:code}})});
 await page.goto('/business-processes?process=p1&revision=r1');
 await page.getByRole('button',{name:'发布当前业务定义',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText(message);
 await expect(page.getByRole('button',{name:'核实原发布',exact:true})).toHaveCount(0);
 expect(submissions).toBe(1);
 expect(await page.evaluate(()=>Object.keys(sessionStorage).filter(k=>k.startsWith('business-process-publication:')))).toEqual([]);
});

async function referenceCandidates(page:Page,state:{principalId:string;tenantId:string}){
 await page.route('**/api/workbench/v1/employees/**/authoring',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{publication:{status:'AVAILABLE',definition:{employeeDefinitionId:'employee:review',employeeDefinitionRevisionId:'employee-r1',employeeDefinitionDigest:'b'.repeat(64),role:'交接核对助手',publicationState:'PUBLISHED'}}}}}));
 await page.route('**/api/workbench/v1/resource-directory?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{subject:state.principalId,scope:{tenantId:state.tenantId,securityDomain:'domain'},items:[{kind:'knowledge',identity:'knowledge:guide',revisionId:'knowledge-r1',digest:'a'.repeat(64),name:'工单交接说明',enabled:true,isCurrentPublished:true,state:'PUBLISHED'}],nextCursor:null}}}));
 await page.route('**/api/workbench/v1/employees?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:[{employeeDefinitionId:'employee:review',employeeDefinitionRevisionId:'employee-r1',employeeDefinitionDigest:'b'.repeat(64),role:'交接核对助手',publicationState:'PUBLISHED'},{employeeDefinitionId:'employee:review',employeeDefinitionRevisionId:'employee-r0',employeeDefinitionDigest:'d'.repeat(64),role:'交接核对助手',publicationState:'PUBLISHED'},{employeeDefinitionId:'employee:draft',employeeDefinitionRevisionId:'employee-r2',employeeDefinitionDigest:'c'.repeat(64),role:'未发布助手',publicationState:'NOT_PUBLISHED'}],nextCursor:null}}}));
}
test('fixed reference picker saves knowledge and employee without replacing business responsibility',async({page})=>{
 const {state,writes}=await writableFixture(page);await referenceCandidates(page,state);
 await page.goto('/business-processes?process=p1&revision=r1&edit=process');
 await page.getByRole('button',{name:'选择流程资料',exact:true}).click();await page.getByRole('button',{name:'工单交接说明',exact:true}).click();
 await expect(page.getByRole('button',{name:'工单交接说明 · 已选择',exact:true})).toBeDisabled();
 await page.locator('.bp-activity-node[title="核对到货"]').click();
 const activity=page.locator('[data-edit-activity="a1"]');await activity.getByRole('button',{name:'选择支撑数字人',exact:true}).click();
 await expect(page.getByRole('button',{name:'未发布助手',exact:true})).toHaveCount(0);
 await activity.getByRole('button',{name:'交接核对助手',exact:true}).click();
 await expect(activity.getByRole('button',{name:'交接核对助手 · 已选择',exact:true})).toBeDisabled();
 await page.getByRole('button',{name:'保存登记草稿',exact:true}).click();
 await expect.poll(()=>writes.length).toBe(1);
 await expect(page.getByRole('button',{name:'保存登记草稿',exact:true})).toHaveCount(0);
 await expect(page.getByRole('heading',{name:'流程与活动',exact:true})).toBeVisible();
 expect(writes).toHaveLength(1);
 const saved=writes[0].content as typeof content&{source_materials:unknown[];activities:(typeof content.activities[number]&{employee?:unknown})[]};
 expect(saved.source_materials).toEqual([{resource_id:'knowledge:guide',revision_id:'knowledge-r1',digest:'a'.repeat(64)}]);
 expect(saved.activities[0].employee).toEqual({resource_id:'employee:review',revision_id:'employee-r1',digest:'b'.repeat(64)});
 expect(saved.activities[0].responsible_role).toBe('仓储专员');
 await page.route('**/api/workbench/v1/resource-directory/knowledge/knowledge%3Aguide/knowledge-r1',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{kind:'knowledge',identity:'knowledge:guide',subject:state.principalId,scope:{tenantId:state.tenantId,securityDomain:'domain'},name:'工单交接说明（固定版本）',revision:{revisionId:'knowledge-r1',digest:'a'.repeat(64),state:'PUBLISHED',content:{}}}}}));
 const source=page.getByRole('region',{name:'流程资料',exact:true});
 await source.getByRole('button',{name:'重新读取关联',exact:true}).click();await expect(source.getByText('工单交接说明（固定版本）',{exact:true})).toBeVisible();
 await page.route('**/api/workbench/v1/resource-directory/knowledge/knowledge%3Aguide/knowledge-r1',route=>route.fulfill({status:404,json:{reasonCode:'NOT_FOUND'}}));
 await page.reload();
 await source.getByRole('button',{name:'重新读取关联',exact:true}).click();await expect(source.getByRole('alert')).toContainText('原关联不会自动替换');
 await expect(source.getByText('资料 1 · 名称待核对',{exact:true})).toBeVisible();expect(writes).toHaveLength(1);
 await page.screenshot({path:test.info().outputPath('fixed-reference-detail-controlled.png'),fullPage:true});
});
test('fixed reference picker refuses selection after account changes',async({page})=>{
 const {state,writes}=await writableFixture(page);await referenceCandidates(page,state);
 await page.goto('/business-processes?process=p1&revision=r1&edit=process');
 await page.getByRole('button',{name:'选择流程资料',exact:true}).click();await expect(page.getByRole('button',{name:'工单交接说明',exact:true})).toBeVisible();
 state.principalId='human:other';await page.getByRole('button',{name:'工单交接说明',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('关联内容暂未核实');await expect(page.getByRole('button',{name:'工单交接说明',exact:true})).toHaveCount(0);expect(writes).toEqual([]);
});

test('fixed reference names are projected automatically and activity support stays in selected activity',async({page})=>{
 const state=await fixture(page);
 const source={resource_id:'knowledge:guide',revision_id:'knowledge-r1',digest:'a'.repeat(64)},employee={resource_id:'employee:review',revision_id:'employee-r1',digest:'b'.repeat(64)};
 await page.route('**/api/workbench/v1/business-processes/p1?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{objectId:'p1',revisionId:'r1',digest:'c'.repeat(64),aggregateVersion:1,record:{content:{...content,source_materials:[source],activities:content.activities.map((item,index)=>index?item:{...item,employee})},architectureReference:{revisionId:'architecture-v1',digest:'a'.repeat(64)}},referenceDetails:{items:[{kind:'knowledge',reference:source,status:'AVAILABLE',name:'上线交接资料'},{kind:'employee',reference:employee,status:'AVAILABLE',name:'交接检查助手'}],executionAuthorized:false}}}}));
 await page.goto('/business-processes?process=p1&revision=r1');
 await expect(page.getByText('上线交接资料',{exact:true})).toBeVisible();
 await expect(page.getByText('交接检查助手',{exact:true})).toHaveCount(0);
 await page.locator('.bp-activity-node[title="核对到货"]').click();
 await expect(page.getByRole('complementary',{name:'选中活动或交接详情'}).getByText('交接检查助手',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'重新读取关联',exact:true})).toHaveCount(0);
 const order=await page.evaluate(()=>{const map=document.querySelector('.bp-activity-workbench')!,source=document.querySelector('.bp-source-card')!;return !!(map.compareDocumentPosition(source)&Node.DOCUMENT_POSITION_FOLLOWING)});expect(order).toBe(true);
 expect(state.reads.filter(url=>url.includes('/resource-directory')||url.includes('/employees/'))).toEqual([]);
 await page.screenshot({path:test.info().outputPath('automatic-reference-names-controlled.png'),fullPage:true});
});

test('fixed reference employee candidates group stable identity and preserve selected historical version',async({page})=>{
 const {state,writes}=await writableFixture(page);await referenceCandidates(page,state);await page.goto('/business-processes?process=p1&revision=r1&edit=process');
 await page.locator('.bp-activity-node[title="核对到货"]').click();const activity=page.locator('[data-edit-activity="a1"]');await activity.getByRole('button',{name:'选择支撑数字人',exact:true}).click();
 const object=activity.locator('.bp-reference-object');await expect(object).toHaveCount(1);await expect(object.getByRole('button',{name:'交接核对助手',exact:true})).toHaveCount(1);
 const history=object.locator(':scope > details');await history.locator(':scope > summary').click();await history.getByRole('button',{name:'交接核对助手',exact:true}).click();
 await expect(activity.getByText('已关联历史版本，保持原版本',{exact:true})).toBeVisible();await page.getByRole('button',{name:'保存登记草稿',exact:true}).click();await expect(page.getByRole('heading',{name:'到货核验',exact:true})).toBeVisible();
 expect(writes).toHaveLength(1);const saved=writes[0].content as {activities:{employee:{revision_id:string}}[]};expect(saved.activities[0].employee.revision_id).toBe('employee-r0');
});

test('fixed capability relations preserve selected activity and distinguish failed reads',async({page})=>{
 const state=await fixture(page);let denied=false;
 await page.route('**/api/workbench/v1/business-processes/capability-relations?**',route=>denied?route.fulfill({status:403,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}}):route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:[{relationId:'rel1',relationRevisionId:'rel-r1',relationVersion:1,record:{relation_type:'SUPPORTS_ACTIVITY',process:{resource_id:'p1',revision_id:'r1',digest:'c'.repeat(64)},capability:{resource_id:'cap1',revision_id:'cap-r1',digest:'d'.repeat(64)},activity_ids:['a1'],coverage_description:'检查到货凭证'},capabilityTitle:'凭证核对能力',activities:[{activityId:'a1',name:'核对到货'}],recordedAt:'2026-11-11'}],nextCursor:null,executionAuthorized:false}}}));
 await page.goto('/business-processes?'+new URLSearchParams({process:'p1',revision:'r1',digest:'c'.repeat(64),activity:'a1'}));
 const panel=page.getByRole('region',{name:'活动能力关联'});
 await expect(panel.getByText('能力支撑活动',{exact:true})).toBeVisible();
 const link=panel.getByRole('link',{name:'凭证核对能力'});await expect(link).toBeVisible();
 const target=new URL(await link.getAttribute('href')??'',page.url());
 expect(target.searchParams.get('revision')).toBe('cap-r1');expect(target.searchParams.get('digest')).toBe('d'.repeat(64));
 const back=new URL(target.searchParams.get('businessProcessReturn')!,page.url());expect(back.searchParams.get('activity')).toBe('a1');expect(back.searchParams.get('digest')).toBe('c'.repeat(64));
 await page.reload();await expect(link).toBeVisible();denied=true;await page.reload();await expect(panel.getByRole('alert')).toBeVisible();await expect(link).toHaveCount(0);expect(state.writes).toEqual([]);
});

test('fixed process digest mismatch rejects details',async({page})=>{
 await fixture(page);await page.goto('/business-processes?'+new URLSearchParams({process:'p1',revision:'r1',digest:'e'.repeat(64),activity:'a1'}));
 await expect(page.locator('.f3-business-processes [role=alert]')).toContainText('引用版本已变化');await expect(page.getByRole('region',{name:'活动能力关联'})).toHaveCount(0);
});


test('activity capability round trip keeps fixed versions and distinct relation meanings',async({page})=>{
 const state=await fixture(page);
 const process={resource_id:'p1',revision_id:'r1',digest:'c'.repeat(64)},capability={resource_id:'cap1',revision_id:'cap-r1',digest:'d'.repeat(64)};
 const reads:string[]=[];let wrongIdentity=false;
 await page.route('**/api/workbench/v1/business-processes/capability-relations?**',route=>{
  const url=new URL(route.request().url());reads.push(url.search);const side=url.searchParams.get('side');
  expect(url.searchParams.get('revision')).toBe(side==='PROCESS'?'r1':'cap-r1');
  return route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:['SUPPORTS_ACTIVITY','DERIVED_FROM_PROCESS'].map((type,i)=>({relationId:'rel'+i,relationRevisionId:'rel-r'+i,relationVersion:1,record:{relation_type:type,process,capability,activity_ids:['a1'],coverage_description:i?'依据到货核验设计检查步骤':'支撑到货凭证核对'},processName:'到货核验',capabilityTitle:'凭证核对能力',activities:[{activityId:'a1',name:'核对到货'}],recordedAt:'2026-11-11'})),nextCursor:null,executionAuthorized:false}}});
 });
 await page.route('**/api/workbench/v1/business-capabilities/**',route=>{
  const path=new URL(route.request().url()).pathname;let result:unknown={domains:[],hasUnassigned:false,readableFavoriteCount:0};
  if(path.endsWith('/preferences'))result={version:0,state:{query:'',domain:'',layout:'cards',favoritesOnly:false,favorites:[],scrollTop:0,loadedCount:50},commandId:null,replayed:false};
  if(path.endsWith('/cap1/revisions/cap-r1'))result={revision:{schemaVersion:'business-capability.v1',scope:{namespace:'tenant',security_domain:'domain'},capability_id:wrongIdentity?'other-capability':'cap1',revision_id:'cap-r1',predecessor_revision_id:null,title:'凭证核对能力',intent:'核对到货凭证',inputs:'到货单',outputs:'差异清单',business_scope:'已授权资料',exclusions:'自动付款',manual_involvement:'负责人复核',acceptance_criteria:['差异可追溯'],known_limitations:'不证明实际到货',origin:{kind:'INDEPENDENT',workflow:null,preparation_digest:null},bindings:[]},digest:capability.digest,aggregateVersion:1,headRevisionId:'cap-r1',publishedRevisionId:'cap-r1',currentDraftRevisionId:null,state:'PUBLISHED',executionAuthorized:false};
  return route.fulfill({json:{schemaVersion:'workbench-operation.v1',result}});
 });
 await page.goto('/business-processes?'+new URLSearchParams({process:'p1',revision:'r1',digest:process.digest,activity:'a1'}));
 await page.getByRole('region',{name:'活动能力关联'}).getByRole('link',{name:'凭证核对能力'}).first().click();
 await expect(page.getByRole('heading',{name:'凭证核对能力',exact:true})).toBeVisible();
 const reverse=page.getByRole('region',{name:'关联流程与活动'});
 await expect(reverse.getByText('能力支撑活动',{exact:true})).toBeVisible();await expect(reverse.getByText('能力来源于流程设计',{exact:true})).toBeVisible();
 await expect(page.locator('.f3-capabilities').getByText('直接创建定义',{exact:true})).toBeVisible();
 await page.getByRole('link',{name:'返回流程活动',exact:true}).click();
 await expect(page.locator('.bp-activity-node[aria-pressed=true]')).toContainText('核对到货');
 expect(new URL(page.url()).searchParams.get('revision')).toBe('r1');expect(new URL(page.url()).searchParams.get('digest')).toBe(process.digest);
 await page.getByRole('button',{name:'回到完整图',exact:true}).click();await page.reload();await expect(page.locator('.bp-activity-node[aria-pressed=true]')).toHaveCount(0);
 expect(reads.some(search=>search.includes('side=CAPABILITY'))).toBeTruthy();expect(state.writes).toEqual([]);
 wrongIdentity=true;await page.goto('/capabilities?'+new URLSearchParams({capability:'cap1',revision:'cap-r1',digest:capability.digest}));
 await expect(page.locator('.f3-capabilities [role=alert]').first()).toContainText('内容或登录身份已变化');await expect(page.getByRole('heading',{name:'凭证核对能力',exact:true})).toHaveCount(0);
});

test('unknown capability relation save restores original receipt without duplicate write',async({page})=>{
 const state=await fixture(page);const commands:import('../../src/api/businessProcesses').BusinessRelationCommand[]=[];
 await page.route('**/api/workbench/v1/business-capabilities?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:[{capabilityId:'cap1',currentPublished:{revisionId:'cap-r1',title:'凭证核对能力',digest:'d'.repeat(64)}}],nextCursor:null}}}));
 await page.route('**/api/workbench/v1/business-processes/capability-relations',route=>{commands.push(route.request().postDataJSON());return route.abort('failed')});
 await page.route('**/api/workbench/v1/business-processes/capability-relations/commands/**',route=>{
  expect(decodeURIComponent(new URL(route.request().url()).pathname.split('/').at(-1)!)).toBe(commands[0].commandId);
  return route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{relationId:commands[0].relation.relation_id,relationRevisionId:commands[0].relation.relation_revision_id,relationVersion:1,digest:'e'.repeat(64),executionAuthorized:false}}});
 });
 await page.goto('/business-processes?process=p1&revision=r1&activity=a1');
 await page.getByRole('button',{name:'关联业务能力',exact:true}).click();await page.getByRole('button',{name:'选择已发布能力'}).click();await page.getByRole('button',{name:'凭证核对能力',exact:true}).click();
 await page.getByLabel('支撑范围说明',{exact:true}).fill('核对到货凭证中的缺项');
 await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect(page.getByRole('button',{name:'保存能力关联'})).toBeEnabled({timeout:15000});await expect(page.getByLabel('支撑范围说明',{exact:true})).toHaveValue('核对到货凭证中的缺项');
 await page.getByRole('button',{name:'保存能力关联'}).click();await expect(page.getByRole('region',{name:'维护活动能力关联'}).getByRole('alert')).toContainText('保存结果尚未核实');
 expect(commands).toHaveLength(1);expect(commands[0].relation.activity_ids).toEqual(['a1']);expect(commands[0].relation.capability.revision_id).toBe('cap-r1');expect(commands[0].relation.relation_type).toBe('SUPPORTS_ACTIVITY');
 state.principalId='human:another';await page.reload();await expect(page.getByRole('button',{name:'核实原关联提交'})).toHaveCount(0);
 state.principalId='human:test';await page.reload();await page.getByRole('button',{name:'核实原关联提交'}).click();await expect(page.getByRole('button',{name:'关联业务能力',exact:true})).toBeVisible();expect(commands).toHaveLength(1);
 state.principalId='human:another';await page.reload();await expect(page.getByRole('button',{name:'核实原关联提交'})).toHaveCount(0);
});

for(const conflict of [false,true])test(`relation revision preserves identity and coverage ${conflict?'on conflict':'on save'}`,async({page})=>{
 await fixture(page);const commands:import('../../src/api/businessProcesses').BusinessRelationCommand[]=[];
 const record={relation_id:'rel1',relation_revision_id:'rr1',relation_type:'SUPPORTS_ACTIVITY',process:{resource_id:'p1',revision_id:'r1',digest:'c'.repeat(64)},capability:{resource_id:'cap1',revision_id:'cr1',digest:'d'.repeat(64)},activity_ids:['a1','a2'],coverage_description:'原支撑说明'};
 await page.route('**/api/workbench/v1/business-processes/capability-relations?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:[{relationId:'rel1',relationRevisionId:'rr1',relationVersion:1,digest:'e'.repeat(64),record,capabilityTitle:'凭证核对能力',activities:[{activityId:'a1',name:'核对到货'},{activityId:'a2',name:'补充凭证'}],recordedAt:'2026-11-11',executionAuthorized:false}],nextCursor:null,executionAuthorized:false}}}));
 await page.route('**/api/workbench/v1/business-processes/capability-relations',route=>{const command=route.request().postDataJSON();commands.push(command);return conflict?route.fulfill({status:409,json:{reasonCode:'BUSINESS_RELATION_VERSION_CONFLICT'}}):route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{relationId:'rel1',relationRevisionId:command.relation.relation_revision_id,relationVersion:2,digest:'f'.repeat(64),executionAuthorized:false}}})});
 await page.goto('/business-processes?process=p1&revision=r1&activity=a1');
 await page.getByRole('button',{name:'修订关联说明',exact:true}).click();const editor=page.getByRole('region',{name:'维护活动能力关联'}).filter({has:page.getByRole('heading',{name:'修订关联说明',exact:true})});
 await expect(editor.getByRole('combobox',{name:'关系类型'})).toBeDisabled();await expect(editor.getByRole('button',{name:'选择已发布能力'})).toHaveCount(0);
 await editor.getByLabel('支撑范围说明',{exact:true}).fill('核对凭证缺项并说明补充责任');await editor.getByRole('button',{name:'保存能力关联'}).click();
 await expect.poll(()=>commands.length).toBe(1);expect(commands[0].expectedVersion).toBe(1);expect(commands[0].relation).toMatchObject({...record,coverage_description:'核对凭证缺项并说明补充责任',relation_revision_id:commands[0].relation.relation_revision_id});expect(commands[0].relation.relation_revision_id).not.toBe('rr1');
 if(conflict){await expect(editor.getByRole('alert')).toContainText('原记录未被覆盖');await expect(editor.getByLabel('支撑范围说明',{exact:true})).toHaveValue('核对凭证缺项并说明补充责任')}else await expect(page.getByRole('button',{name:'修订关联说明',exact:true})).toBeVisible();
 expect(commands).toHaveLength(1);
});

test('many relation rows share one maintenance check and hide writes after revocation',async({page})=>{
 const state=await fixture(page);
 await page.route('**/api/workbench/v1/business-processes/capability-relations?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:Array.from({length:8},(_,i)=>({relationId:'rel'+i,relationRevisionId:'rr'+i,relationVersion:1,digest:'e'.repeat(64),record:{relation_id:'rel'+i,relation_revision_id:'rr'+i,relation_type:'SUPPORTS_ACTIVITY',process:{resource_id:'p1',revision_id:'r1',digest:'c'.repeat(64)},capability:{resource_id:'cap'+i,revision_id:'cr1',digest:'d'.repeat(64)},activity_ids:['a1'],coverage_description:'凭证核对'},capabilityTitle:'凭证能力'+i,activities:[{activityId:'a1',name:'核对到货'}],recordedAt:'2026-11-11',executionAuthorized:false})),nextCursor:null,executionAuthorized:false}}}));
 await page.goto('/business-processes?process=p1&revision=r1&activity=a1');await expect(page.getByRole('button',{name:'修订关联说明',exact:true})).toHaveCount(8);await expect(page.getByRole('button',{name:'关联业务能力',exact:true})).toBeVisible();
 const maintenance=()=>state.reads.filter(path=>path.includes('/editor-access?')&&new URL(path,'http://localhost').searchParams.get('action')==='REVISE').length;
 expect(maintenance()).toBe(2); // The page action and the shared relationship area each check once.
 state.editorDenied=true;await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
 await expect(page.getByRole('button',{name:'修订关联说明',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'关联业务能力',exact:true})).toHaveCount(0);
 await expect.poll(maintenance).toBe(4);await expect(page.getByRole('link',{name:'凭证能力0',exact:true})).toBeVisible();expect(state.writes).toEqual([]);
 state.principalId='human:changed';await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect(page.getByRole('link',{name:'凭证能力0',exact:true})).toHaveCount(0);await expect(page.getByRole('heading',{name:'当前登录已失效',exact:true})).toBeVisible();
});

test('withdrawn relation keeps fixed historical content without revision action',async({page})=>{
 const state=await fixture(page);
 await page.route('**/api/workbench/v1/business-processes/capability-relations?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:[{relationId:'rel1',relationRevisionId:'rr1',relationVersion:1,record:{relation_type:'SUPPORTS_ACTIVITY',process:{resource_id:'p1',revision_id:'r1',digest:'c'.repeat(64)},capability:{resource_id:'cap1',revision_id:'cr1',digest:'d'.repeat(64)},activity_ids:['a1'],coverage_description:'原始凭证核对说明'},capabilityTitle:'原固定能力',activities:[{activityId:'a1',name:'核对到货'}],recordedAt:'2026-11-10',withdrawal:{state:'WITHDRAWN',reason:'业务范围调整',recordedAt:'2026-11-11',executionAuthorized:false}}],nextCursor:null,executionAuthorized:false}}}));
 await page.goto('/business-processes?process=p1&revision=r1&activity=a1');const panel=page.getByRole('region',{name:'活动能力关联'});
 await expect(panel.getByText('当前关系已撤回',{exact:true})).toBeVisible();await panel.getByText('查看撤回关系的历史修订（1）',{exact:true}).click();await expect(panel.getByText('原始凭证核对说明',{exact:true})).toBeVisible();await expect(panel.getByRole('link',{name:'原固定能力',exact:true})).toHaveAttribute('href',/revision=cr1/);await expect(panel.getByRole('button',{name:'修订关联说明'})).toHaveCount(0);expect(state.writes).toEqual([]);
});

for(const lost of [false,true])test(`relation withdrawal confirms reason and preserves original command ${lost?'after lost response':'on success'}`,async({page})=>{
 const state=await fixture(page);const commands:import('../../src/api/businessProcesses').BusinessRelationWithdrawalCommand[]=[];
 const relation={relationId:'rel1',relationRevisionId:'rr1',relationVersion:1,digest:'e'.repeat(64),record:{relation_id:'rel1',relation_revision_id:'rr1',relation_type:'SUPPORTS_ACTIVITY',process:{resource_id:'p1',revision_id:'r1',digest:'c'.repeat(64)},capability:{resource_id:'cap1',revision_id:'cr1',digest:'d'.repeat(64)},activity_ids:['a1'],coverage_description:'原关联内容'},capabilityTitle:'原固定能力',activities:[{activityId:'a1',name:'核对到货'}],recordedAt:'2026-11-10',executionAuthorized:false};
 const receipt=()=>({relationId:'rel1',relationRevisionId:'rr1',relationVersion:1,digest:relation.digest,reason:commands[0].reason,state:'WITHDRAWN',executionAuthorized:false});
 await page.route('**/api/workbench/v1/business-processes/capability-relations?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:[{...relation,withdrawal:commands.length?receipt():null}],nextCursor:null,executionAuthorized:false}}}));
 await page.route('**/api/workbench/v1/business-processes/capability-relations/withdrawals',route=>{commands.push(route.request().postDataJSON());return lost?route.abort('failed'):route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:receipt()}})});
 await page.route('**/api/workbench/v1/business-processes/capability-relations/withdrawals/*',route=>{expect(decodeURIComponent(new URL(route.request().url()).pathname.split('/').at(-1)!)).toBe(commands[0].commandId);return route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:receipt()}})});
 await page.goto('/business-processes?process=p1&revision=r1&activity=a1');await page.getByRole('button',{name:'撤回此关联'}).click();await expect(page.getByRole('button',{name:'确认撤回关联'})).toBeDisabled();await page.getByLabel('撤回原因',{exact:true}).fill('业务范围调整，保留原记录');await page.getByRole('button',{name:'确认撤回关联'}).click();await expect.poll(()=>commands.length).toBe(1);
 if(lost){await expect(page.getByRole('region',{name:'撤回能力关联'}).getByRole('alert')).toContainText('撤回结果尚未核实');state.principalId='human:another';await page.reload();await expect(page.getByText('当前关系已撤回',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'核实原撤回'})).toHaveCount(0);state.principalId='human:test';await page.reload();await page.getByRole('button',{name:'核实原撤回'}).click()}
 await expect(page.getByText('当前关系已撤回',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'核实原撤回'})).toHaveCount(0);await expect(page.getByRole('button',{name:'撤回此关联'})).toHaveCount(0);await expect(page.getByRole('button',{name:'修订关联说明'})).toHaveCount(0);await page.getByText('查看撤回关系的历史修订（1）',{exact:true}).click();await expect(page.getByText('原关联内容',{exact:true})).toBeVisible();expect(commands).toHaveLength(1);expect(commands[0].expectedVersion).toBe(1);expect(commands[0].digest).toBe(relation.digest);
});

test('one stable relation has a current summary and collapsed immutable revisions',async({page})=>{
 await fixture(page);
 await page.route('**/api/workbench/v1/business-processes/capability-relations?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:[1,2].map(version=>({relationId:'rel1',relationRevisionId:'rr'+version,relationVersion:version,isCurrentRelationRevision:version===2,digest:'e'.repeat(64),record:{relation_type:'SUPPORTS_ACTIVITY',process:{resource_id:'p1',revision_id:'r1',digest:'c'.repeat(64)},capability:{resource_id:'cap1',revision_id:'cr1',digest:'d'.repeat(64)},activity_ids:['a1'],coverage_description:version===1?'原历史说明':'当前修订说明'},capabilityTitle:'固定能力',activities:[{activityId:'a1',name:'核对到货'}],recordedAt:'2026-11-11T11:06:21Z',executionAuthorized:false})),nextCursor:null,executionAuthorized:false}}}));
 await page.goto('/business-processes?process=p1&revision=r1&activity=a1');const panel=page.getByRole('region',{name:'活动能力关联'});
 await expect(panel.locator('.bp-relation-group')).toHaveCount(1);await expect(panel.getByText('当前关系修订',{exact:true})).toBeVisible();await expect(panel.getByText('当前修订说明',{exact:true})).toBeVisible();await expect(panel.getByText('原历史说明',{exact:true})).not.toBeVisible();
 await panel.getByText('查看历史修订（1）',{exact:true}).click();await expect(panel.getByText('原历史说明',{exact:true})).toBeVisible();await expect(panel.getByRole('button',{name:'修订关联说明',exact:true})).toHaveCount(1);
 await panel.locator('article').first().getByText('固定版本依据',{exact:true}).click();await expect(panel.getByText('记录时间：2026-11-11 19:06（北京时间）',{exact:true}).first()).toBeVisible();
 expect(await page.locator('.bp-activity-inspector').evaluate(node=>getComputedStyle(node).overflowY)).toBe('auto');
});

test('saved fixed resource opens existing detail and returns to original activity',async({page})=>{
 const state=await fixture(page);await referenceCandidates(page,state);
 const source={resource_id:'knowledge:guide',revision_id:'knowledge-r1',digest:'a'.repeat(64)},employee={resource_id:'employee:review',revision_id:'employee-r0',digest:'d'.repeat(64)};
 await page.route('**/api/workbench/v1/business-processes/p1?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{objectId:'p1',revisionId:'r1',digest:'c'.repeat(64),aggregateVersion:1,record:{content:{...content,source_materials:[source],activities:content.activities.map((item,index)=>index?item:{...item,employee})},architectureReference:{revisionId:'architecture-v1',digest:'a'.repeat(64)}},referenceDetails:{items:[{kind:'knowledge',reference:source,status:'AVAILABLE',name:'工单交接说明'},{kind:'employee',reference:employee,status:'AVAILABLE',name:'交接助手历史版'}],executionAuthorized:false}}}}));
 await page.route('**/api/workbench/v1/resource-directory/knowledge/knowledge%3Aguide/knowledge-r1',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{kind:'knowledge',identity:'knowledge:guide',subject:state.principalId,scope:{tenantId:state.tenantId,securityDomain:'domain'},name:'工单交接说明',revision:{revisionId:'knowledge-r1',digest:source.digest,state:'PUBLISHED',content:{name:'工单交接说明',description:'准确固定的交接说明',documents:[{documentId:'guide',chunks:[{content:'# 固定交接正文\n\n## 负责人\n\n**李明**负责交接。'}]}]}},usage:[]}}}));
 await page.goto('/business-processes?process=p1&revision=r1&activity=a1');
 const employeeLink=page.getByRole('region',{name:'支撑数字人',exact:true}).getByRole('link',{name:'查看固定版本详情'});await expect(employeeLink).toHaveAttribute('href',/employeeDefinitionRevisionId=employee-r0/);
 await page.getByRole('region',{name:'流程资料',exact:true}).getByRole('link',{name:'查看固定版本详情'}).click();await expect(page.getByRole('region',{name:'资源详情滚动区'}).getByRole('heading',{name:'工单交接说明',exact:true})).toBeVisible();expect(new URL(page.url()).searchParams.get('resourceDigest')).toBe(source.digest);
 await page.getByRole('link',{name:'← 返回原流程与活动',exact:true}).click();await expect(page.locator('.bp-activity-node[aria-pressed=true]')).toContainText('核对到货');expect(new URL(page.url()).searchParams.get('digest')).toBe('c'.repeat(64));expect(state.writes).toEqual([]);
 for(const unsafe of ['/business-processes?process=p1&revision=r1&digest='+'c'.repeat(64)+'&activity=a1&handoff=h1','https://example.invalid/business-processes?process=p1&revision=r1&digest='+'c'.repeat(64),'/business-processes?process=p1&revision=r1','/business-processes?edit=process&draft=business-process:00000000-0000-0000-0000-000000000000&process=p1']){
  await page.goto('/knowledge?'+new URLSearchParams({kind:'knowledge',selected:source.resource_id,resourceRevision:source.revision_id,resourceDigest:source.digest,businessProcessReturn:unsafe}));
  await expect(page.getByRole('link',{name:'← 返回原流程与活动',exact:true})).toHaveCount(0);
  await expect(page.getByRole('heading',{name:'当前版本详情未读回',exact:true})).toBeVisible();
  await page.getByText('核查依据',{exact:true}).click();await expect(page.getByText('RESOURCE_RETURN_UNSAFE',{exact:true})).toBeVisible();
 }
 await page.route('**/api/workbench/v1/resource-directory?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{subject:state.principalId,scope:{tenantId:state.tenantId,securityDomain:'domain'},items:[{kind:'knowledge',identity:source.resource_id,revisionId:source.revision_id,digest:source.digest,name:'工单交接说明',enabled:true,isCurrentPublished:false,isCurrentDraft:false,state:'PUBLISHED'}],nextCursor:null}}}));
 await page.goto('/knowledge?'+new URLSearchParams({kind:'knowledge',selected:source.resource_id,resourceRevision:source.revision_id,resourceDigest:source.digest,businessProcessReturn:'/business-processes?'+new URLSearchParams({process:'p1',revision:'r1',digest:'c'.repeat(64),activity:'a1'})}));
 await expect(page.locator('.f3-detail-banner')).toContainText('历史内容 · 只读');
 await page.getByRole('button',{name:'查看完整定义',exact:true}).click();
 await expect(page.getByRole('heading',{name:'固定交接正文',exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'负责人',exact:true})).toBeVisible();
 expect(new URL(page.url()).searchParams.get('resourceRevision')).toBe(source.revision_id);
 expect(state.writes).toEqual([]);
});

for(const storageFailure of [false,true])test('editing resource roundtrip preserves raw inputs and position '+(storageFailure?'when storage fails':'on return'),async({page})=>{
 const state=await fixture(page);await referenceCandidates(page,state);
 const source={resource_id:'knowledge:guide',revision_id:'knowledge-r1',digest:'a'.repeat(64)},employee={resource_id:'employee:review',revision_id:'employee-r0',digest:'d'.repeat(64)};
 await page.route('**/api/workbench/v1/business-processes/p1?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{objectId:'p1',revisionId:'r1',digest:'c'.repeat(64),aggregateVersion:1,record:{content:{...content,source_materials:[source],activities:content.activities.map((item,index)=>index?item:{...item,employee})},architectureReference:{revisionId:'architecture-v1',digest:'a'.repeat(64)}},referenceDetails:{items:[{kind:'knowledge',reference:source,status:'AVAILABLE',name:'工单交接说明'},{kind:'employee',reference:employee,status:'AVAILABLE',name:'交接助手历史版'}],executionAuthorized:false}}}}));
 await page.route('**/api/workbench/v1/resource-directory/knowledge/knowledge%3Aguide/knowledge-r1',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{kind:'knowledge',identity:'knowledge:guide',subject:state.principalId,scope:{tenantId:state.tenantId,securityDomain:'domain'},name:'工单交接说明',revision:{revisionId:'knowledge-r1',digest:source.digest,state:'PUBLISHED',content:{name:'工单交接说明',description:'准确固定的交接说明',documents:[{documentId:'guide',chunks:[{content:'# 固定交接正文\n\n## 负责人\n\n**李明**负责交接。'}]}]}},usage:[]}}}));

 await page.goto('/business-processes?process=p1&revision=r1&edit=process');
 await expect(page.getByRole('textbox',{name:'流程名称',exact:true})).toHaveValue('到货核验');
 const purpose='  未提交的业务目的\n第二行\n\n';
 await page.getByRole('textbox',{name:'业务目的',exact:true}).fill(purpose);
 const link=page.getByRole('region',{name:'流程资料',exact:true}).getByRole('link',{name:'查看固定版本详情'});
 await expect(link).toHaveAttribute('href',/edit%3Dprocess/);
 await link.scrollIntoViewIfNeeded();
 if(storageFailure)await page.evaluate(()=>{Storage.prototype.setItem=()=>{throw Error('Storage disabled')}});
 await link.click();
 if(storageFailure){await expect(page.getByRole('alert')).toContainText('本地草稿暂无法保留');await expect(page.getByRole('textbox',{name:'业务目的',exact:true})).toHaveValue(purpose);expect(new URL(page.url()).pathname).toBe('/business-processes')}
 else{
  await expect(page.getByRole('region',{name:'资源详情滚动区'}).getByRole('heading',{name:'工单交接说明',exact:true})).toBeVisible();
  const snapshot=await page.evaluate(()=>{const key=Object.keys(sessionStorage).find(k=>k.startsWith('business-process-draft:'))!;return JSON.parse(sessionStorage.getItem(key)!)});
  expect(snapshot.position.fields.purpose).toBe(purpose);const scroll=snapshot.position.scroll.find((item:{selector:string})=>item.selector==='.bp-editor-local-fields').top;expect(scroll).toBeGreaterThan(0);
  await page.getByRole('link',{name:'← 返回原流程与活动',exact:true}).click();
  await expect(page.getByRole('textbox',{name:'业务目的',exact:true})).toHaveValue(purpose);
  await expect.poll(()=>page.locator('.bp-editor-local-fields').evaluate(node=>node.scrollTop)).toBe(scroll);
  expect(new URL(page.url()).searchParams.get('edit')).toBe('process');expect(snapshot.version).toBe(1);
 }
 expect(state.writes).toEqual([]);
});

for(const changed of ['none','account','draft'] as const)test('new process resource return keeps local draft identity '+changed,async({page})=>{
 const {state,writes}=await writableFixture(page);await referenceCandidates(page,state);
 await page.route('**/api/workbench/v1/resource-directory/knowledge/knowledge%3Aguide/knowledge-r1',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{kind:'knowledge',identity:'knowledge:guide',subject:state.principalId,scope:{tenantId:state.tenantId,securityDomain:'domain'},name:'工单交接说明',revision:{revisionId:'knowledge-r1',digest:'a'.repeat(64),state:'PUBLISHED',content:{}}}}}));
 await register(page);await page.getByRole('button',{name:'选择流程资料',exact:true}).click();await page.getByRole('button',{name:'工单交接说明',exact:true}).click();
 await page.getByRole('textbox',{name:'业务目的',exact:true}).fill('  尚未登记的原始输入\n\n');
 await page.getByRole('region',{name:'流程资料',exact:true}).getByRole('link',{name:'查看固定版本详情'}).click();
 await expect(page.getByRole('region',{name:'资源详情滚动区'}).getByRole('heading',{name:'工单交接说明',exact:true})).toBeVisible();
 const back=page.getByRole('link',{name:'← 返回原流程与活动',exact:true}),href=await back.getAttribute('href');const draft=new URL(href!,'http://local').searchParams.get('draft');expect(draft).toMatch(/^business-process:/);expect(href).not.toContain('revision=');
 if(changed==='account')state.principalId='human:another';
 if(changed==='draft'){const target=new URL(href!,'http://local');target.searchParams.set('draft','business-process:00000000-0000-0000-0000-000000000000');await page.goto(target.pathname+target.search)}else await back.click();
 if(changed==='none'){
  await expect(page.getByRole('region',{name:'流程资料',exact:true}).getByText('工单交接说明',{exact:true})).toBeVisible();
  await expect(page.getByRole('textbox',{name:'流程名称',exact:true})).toHaveValue('设备保养交接');await expect(page.getByRole('textbox',{name:'业务目的',exact:true})).toHaveValue('  尚未登记的原始输入\n\n');
  await page.getByRole('button',{name:'保存登记草稿',exact:true}).click();await expect(page.getByRole('heading',{name:'设备保养交接',exact:true})).toBeVisible();expect(writes).toHaveLength(1);expect(writes[0].objectId).toBe(draft);expect(writes[0].expectedVersion).toBe(0);expect(new URL(page.url()).searchParams.has('draft')).toBe(false);
 }else{await expect(page.getByText('当前账号下未找到这份未提交草稿，请返回原账号核对；不会创建替代草稿。',{exact:true})).toBeVisible();await expect(page.getByRole('textbox',{name:'流程名称',exact:true})).toHaveCount(0);expect(writes).toEqual([])}
});

test('readonly process return restores fixed evidence and inspector position after delayed relations',async({page})=>{
 const state=await fixture(page);await referenceCandidates(page,state);
 const source={resource_id:'knowledge:guide',revision_id:'knowledge-r1',digest:'a'.repeat(64)},employee={resource_id:'employee:review',revision_id:'employee-r0',digest:'d'.repeat(64)};
 await page.route('**/api/workbench/v1/business-processes/p1?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{objectId:'p1',revisionId:'r1',digest:'c'.repeat(64),aggregateVersion:1,record:{content:{...content,source_materials:[source],activities:content.activities.map((item,index)=>index?item:{...item,employee})},architectureReference:{revisionId:'architecture-v1',digest:'a'.repeat(64)}},referenceDetails:{items:[{kind:'knowledge',reference:source,status:'AVAILABLE',name:'工单交接说明'},{kind:'employee',reference:employee,status:'AVAILABLE',name:'交接助手历史版'}],executionAuthorized:false}}}}));
 await page.route('**/api/workbench/v1/resource-directory/knowledge/knowledge%3Aguide/knowledge-r1',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{kind:'knowledge',identity:'knowledge:guide',subject:state.principalId,scope:{tenantId:state.tenantId,securityDomain:'domain'},name:'工单交接说明',revision:{revisionId:'knowledge-r1',digest:source.digest,state:'PUBLISHED',content:{name:'工单交接说明',description:'准确固定的交接说明',documents:[{documentId:'guide',chunks:[{content:'# 固定交接正文\n\n## 负责人\n\n**李明**负责交接。'}]}]}},usage:[]}}}));

 await page.route('**/api/workbench/v1/business-processes/capability-relations?**',async route=>{await new Promise(resolve=>setTimeout(resolve,200));return route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:[{relationId:'rel1',relationRevisionId:'rr1',relationVersion:1,isCurrentRelationRevision:true,digest:'e'.repeat(64),record:{relation_type:'SUPPORTS_ACTIVITY',process:{resource_id:'p1',revision_id:'r1',digest:'c'.repeat(64)},capability:{resource_id:'cap1',revision_id:'cr1',digest:'d'.repeat(64)},activity_ids:['a1'],coverage_description:Array.from({length:35},(_,i)=>'第'+i+'项检查范围').join('\n')},capabilityTitle:'固定能力',activities:[{activityId:'a1',name:'核对到货'}],recordedAt:'2026-11-11T11:06:21Z',executionAuthorized:false}],nextCursor:null,executionAuthorized:false}}})});
 await page.goto('/business-processes?process=p1&revision=r1&activity=a1');
 const evidence=page.locator('details[data-bp-state-key="relation-evidence:rr1"]');await evidence.locator('summary').click();
 const inspector=page.locator('.bp-activity-inspector');await inspector.evaluate(n=>{n.scrollTop=n.scrollHeight});const top=await inspector.evaluate(n=>n.scrollTop);expect(top).toBeGreaterThan(0);
 await page.getByRole('region',{name:'流程资料',exact:true}).getByRole('link',{name:'查看固定版本详情'}).click();await expect(page.getByRole('region',{name:'资源详情滚动区'}).getByRole('heading',{name:'工单交接说明',exact:true})).toBeVisible();
 await page.getByRole('link',{name:'← 返回原流程与活动',exact:true}).click();await expect(evidence).toHaveAttribute('open','');await expect.poll(()=>inspector.evaluate(n=>n.scrollTop)).toBe(top);expect(state.writes).toEqual([]);
});

for(const uncertain of [false,true])test('relation cross-version adjustment preserves identity and recovers target '+uncertain,async({page})=>{
 const state=await fixture(page);const commands:import('../../src/api/businessProcesses').BusinessRelationCommand[]=[];
 const record={relation_id:'rel1',relation_revision_id:'rr1',relation_type:'SUPPORTS_ACTIVITY',process:{resource_id:'p1',revision_id:'r1',digest:'c'.repeat(64)},capability:{resource_id:'cap1',revision_id:'cr1',digest:'d'.repeat(64)},activity_ids:['a1','a2'],coverage_description:'原支撑说明'};
 await page.route('**/api/workbench/v1/business-processes/capability-relations?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:[{relationId:'rel1',relationRevisionId:'rr1',relationVersion:1,isCurrentRelationRevision:true,digest:'e'.repeat(64),record,processName:'到货核验',capabilityTitle:'凭证核对能力',activities:[{activityId:'a1',name:'核对到货'},{activityId:'a2',name:'补充凭证'}],recordedAt:'2026-11-11',executionAuthorized:false}],nextCursor:null}}}));
 await page.route('**/api/workbench/v1/business-processes/p1?**',route=>{
  const revision=new URL(route.request().url()).searchParams.get('revision');if(revision==='r1')return route.fallback();
  return route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{objectId:'p1',revisionId:'r2',digest:'f'.repeat(64),aggregateVersion:2,record:{content:{...content,activities:[content.activities[1],{...content.activities[0],activity_id:'a3',name:'复核到货'}]},architectureReference:{revisionId:'architecture-v1',digest:'a'.repeat(64)}},publicationState:{currentStateAvailable:true,published:{objectId:'p1',revisionId:'r2',digest:'f'.repeat(64)}}}}});
 });
 await page.route('**/api/workbench/v1/business-capabilities?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:[{capabilityId:'cap1',currentPublished:{revisionId:'cr2',digest:'b'.repeat(64),title:'凭证核对能力新版'}},{capabilityId:'cap-other',currentPublished:{revisionId:'other',digest:'b'.repeat(64),title:'其他能力'}}],nextCursor:null}}}));
 await page.route('**/api/workbench/v1/business-capabilities/cap1/revisions/cr2',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{revision:{capability_id:'cap1',revision_id:'cr2',title:'凭证核对能力新版'},digest:'b'.repeat(64),publishedRevisionId:'cr2'}}}));
 const receipt=()=>({schemaVersion:'workbench-operation.v1',result:{relationId:'rel1',relationRevisionId:commands[0].relation.relation_revision_id,relationVersion:2,digest:'e'.repeat(64),executionAuthorized:false}});
 await page.route('**/api/workbench/v1/business-processes/capability-relations',route=>{commands.push(route.request().postDataJSON());return uncertain?route.abort('failed'):route.fulfill({json:receipt()})});
 await page.route('**/api/workbench/v1/business-processes/capability-relations/commands/**',route=>{expect(decodeURIComponent(new URL(route.request().url()).pathname.split('/').at(-1)!)).toBe(commands[0].commandId);return route.fulfill({json:receipt()})});
 await page.goto('/business-processes?process=p1&revision=r1&activity=a1');await page.getByRole('button',{name:'修订关联说明',exact:true}).click();await page.getByRole('button',{name:'调整关联版本与覆盖',exact:true}).click();
 await page.getByRole('button',{name:'读取当前发布流程版本',exact:true}).click();await expect(page.getByRole('checkbox',{name:'复核到货',exact:true})).toBeVisible();await expect(page.getByRole('checkbox',{name:'补充凭证',exact:true})).toBeChecked();await page.getByRole('checkbox',{name:'复核到货',exact:true}).check();
 await page.getByRole('button',{name:'选择已发布能力',exact:true}).click();await expect(page.getByRole('button',{name:'其他能力',exact:true})).toHaveCount(0);await page.getByRole('button',{name:'凭证核对能力新版',exact:true}).click();await expect(page.getByText('已选择：凭证核对能力新版',{exact:false})).toBeVisible();
 const difference=page.getByRole('region',{name:'关联版本调整差异',exact:true});
 await expect(difference).toContainText('仅核对引用版本与覆盖范围，未验证业务适配');await expect(difference).toContainText('覆盖未变：补充凭证');await expect(difference).toContainText('新增覆盖：复核到货');await expect(difference).toContainText('移除覆盖：核对到货');await expect(difference).toContainText('到货核验');
 await expect(difference.getByRole('link',{name:'查看原流程内容',exact:true})).toHaveAttribute('href',/revision=r1/);await expect(difference.getByRole('link',{name:'查看拟用流程内容',exact:true})).toHaveAttribute('href',/revision=r2/);await expect(difference.getByRole('link',{name:'查看拟用能力内容',exact:true})).toHaveAttribute('href',/revision=cr2/);await expect(difference.getByRole('link',{name:'查看拟用能力内容',exact:true})).toHaveAttribute('target','_blank');
 if(!uncertain)await difference.screenshot({path:test.info().outputPath('controlled-version-difference.png')});
 if(!uncertain){await page.getByRole('button',{name:'核对版本与覆盖调整',exact:true}).click();await expect(page.getByRole('button',{name:'保存能力关联',exact:true})).toBeEnabled();await page.reload();await expect(page.getByRole('checkbox',{name:'复核到货',exact:true})).toBeChecked();await expect(page.getByText('已选择：凭证核对能力新版',{exact:false})).toBeVisible();await expect(page.getByRole('button',{name:'保存能力关联',exact:true})).toBeDisabled()}
 await expect(page.getByRole('button',{name:'保存能力关联',exact:true})).toBeDisabled();await page.getByRole('button',{name:'核对版本与覆盖调整',exact:true}).click();await page.getByRole('button',{name:'保存能力关联',exact:true}).click();
 if(uncertain){await expect(page.getByRole('alert').last()).toContainText('保存结果尚未核实');await page.reload();await page.getByRole('button',{name:'核实原关联提交',exact:true}).click()}
 await expect.poll(()=>new URL(page.url()).searchParams.get('revision')).toBe('r2');expect(new URL(page.url()).searchParams.get('activity')).toBe('a2');expect(commands).toHaveLength(1);expect(commands[0].expectedVersion).toBe(1);expect(commands[0].relation.relation_id).toBe('rel1');expect(commands[0].relation.relation_type).toBe('SUPPORTS_ACTIVITY');expect(commands[0].relation.activity_ids).toEqual(['a2','a3']);expect(commands[0].relation.process).toEqual({resource_id:'p1',revision_id:'r2',digest:'f'.repeat(64)});expect(commands[0].relation.capability).toEqual({resource_id:'cap1',revision_id:'cr2',digest:'b'.repeat(64)});expect(state.writes).toEqual([]);
});

for(const stable of [false,true])test('handoff selection survives refresh and fixed resource return '+stable,async({page})=>{
 const state=await fixture(page);await referenceCandidates(page,state);
 const source={resource_id:'knowledge:guide',revision_id:'knowledge-r1',digest:'a'.repeat(64)};
 const handoffs=content.handoffs.map((item,index)=>({...item,...(stable?{handoff_id:'handoff-'+index}:{})}));
 await page.route('**/api/workbench/v1/business-processes/p1?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{objectId:'p1',revisionId:'r1',digest:'c'.repeat(64),aggregateVersion:1,record:{content:{...content,handoffs,source_materials:[source]},architectureReference:{revisionId:'architecture-v1',digest:'a'.repeat(64)}},referenceDetails:{items:[{kind:'knowledge',reference:source,status:'AVAILABLE',name:'工单交接说明'}],executionAuthorized:false}}}}));
 await page.route('**/api/workbench/v1/resource-directory/knowledge/knowledge%3Aguide/knowledge-r1',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{kind:'knowledge',identity:source.resource_id,subject:state.principalId,scope:{tenantId:state.tenantId,securityDomain:'domain'},name:'工单交接说明',revision:{revisionId:source.revision_id,digest:source.digest,state:'PUBLISHED',content:{name:'工单交接说明',description:'固定说明',documents:[]}},usage:[]}}}));
 await page.goto('/business-processes?process=p1&revision=r1&activity=a1');
 const edge=page.getByRole('button',{name:'完成后交接：补充凭证 → 核对到货',exact:true});await edge.click();await expect(edge).toHaveAttribute('aria-pressed','true');
 const expected=stable?'handoff-1':JSON.stringify(['a2','a1','COMPLETED']);expect(new URL(page.url()).searchParams.get('handoff')).toBe(expected);expect(new URL(page.url()).searchParams.has('activity')).toBe(false);
 await page.reload();await expect(edge).toHaveAttribute('aria-pressed','true');await expect(page.getByText('补齐后返回核对',{exact:true})).toBeVisible();
 await page.getByRole('region',{name:'流程资料',exact:true}).getByRole('link',{name:'查看固定版本详情',exact:true}).click();await expect(page.getByRole('region',{name:'资源详情滚动区'})).toContainText('工单交接说明');
 await page.getByRole('link',{name:'← 返回原流程与活动',exact:true}).click();await expect(edge).toHaveAttribute('aria-pressed','true');expect(new URL(page.url()).searchParams.get('digest')).toBe('c'.repeat(64));
 await page.getByRole('button',{name:'回到完整图',exact:true}).click();expect(new URL(page.url()).searchParams.has('handoff')).toBe(false);await expect(page.getByRole('complementary',{name:'选中活动或交接详情'})).toHaveCount(0);
 await page.goto('/business-processes?'+new URLSearchParams({process:'p1',revision:'r1',handoff:'missing'}));await expect(page.getByRole('status')).toContainText('原交接不在此固定版本');await expect(page.locator('.bp-edge-label[aria-pressed=true]')).toHaveCount(0);
 expect(state.writes).toEqual([]);
});

for(const mismatch of [false,true])test('relation editing draft restores exact references and raw text '+mismatch,async({page})=>{
 const state=await fixture(page);
 const record={relation_id:'rel1',relation_revision_id:'rr1',relation_type:'SUPPORTS_ACTIVITY',process:{resource_id:'p1',revision_id:'r1',digest:'c'.repeat(64)},capability:{resource_id:'cap1',revision_id:'cr1',digest:'d'.repeat(64)},activity_ids:['a1','a2'],coverage_description:'原支撑说明'};
 await page.route('**/api/workbench/v1/business-processes/capability-relations?**',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{items:[{relationId:'rel1',relationRevisionId:'rr1',relationVersion:1,digest:'e'.repeat(64),record,capabilityTitle:'凭证核对能力',activities:[{activityId:'a1',name:'核对到货'},{activityId:'a2',name:'补充凭证'}],recordedAt:'2026-11-11',executionAuthorized:false}],nextCursor:null,executionAuthorized:false}}}));
 await page.route('**/api/workbench/v1/business-capabilities/cap1/revisions/cr1',route=>route.fulfill({json:{schemaVersion:'workbench-operation.v1',result:{revision:{capability_id:'cap1',revision_id:'cr1',title:'凭证核对能力'},digest:(mismatch?'f':'d').repeat(64)}}}));
 const url='/business-processes?process=p1&revision=r1&activity=a1';await page.goto(url);await page.getByRole('button',{name:'修订关联说明',exact:true}).click();
 const raw='  待核对范围\n缺项保留原文\n\n';await page.getByLabel('支撑范围说明',{exact:true}).fill(raw);await page.reload();
 if(mismatch){await expect(page.getByRole('alert')).toContainText('编辑或原提交记录无法核对');await expect(page.getByLabel('支撑范围说明',{exact:true})).toHaveCount(0)}else{
  await expect(page.getByLabel('支撑范围说明',{exact:true})).toHaveValue(raw);
  await page.goto('/business-processes');await page.goto(url);await expect(page.getByLabel('支撑范围说明',{exact:true})).toHaveValue(raw);
  await page.getByRole('button',{name:'取消修改',exact:true}).click();await page.reload();await expect(page.getByLabel('支撑范围说明',{exact:true})).toHaveCount(0);
 }
 expect(state.writes).toEqual([]);
});
