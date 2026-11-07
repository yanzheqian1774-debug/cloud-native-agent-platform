import {expect,test,type Page} from '@playwright/test';
const principal={principalId:'human:employee-relations-fixture',tenantId:'fixture-relations',securityDomain:'isolated'};
const def=(revision='1')=>({resourceKind:'DIGITAL_EMPLOYEE_DEFINITION',employeeDefinitionId:'employee:relations',employeeDefinitionRevisionId:revision,employeeDefinitionDigest:(revision==='1'?'a':'b').repeat(64),role:'数字员工关联核对',publicationState:'PUBLISHED',lifecycleState:'PUBLISHED',aggregateVersion:4,responsibilities:['核对已有工作与证据'],members:[{kind:'AGENT',resourceId:'agent:relations',revisionId:'1',digest:'c'.repeat(64)}]});
const instance=(revision='1')=>({instanceId:'instance:'+revision,employeeDefinition:{authorityKind:'DIGITAL_EMPLOYEE_DEFINITION_V1',employeeDefinitionId:def().employeeDefinitionId,employeeDefinitionRevisionId:revision,digest:def(revision).employeeDefinitionDigest},ownerId:'当前业务工作',organizationId:'fixture-relations',lifecycle:'ENABLED',execution:{state:'UNAVAILABLE',reasonCode:'EXECUTION_NOT_ASSEMBLED'},health:{state:'UNAVAILABLE',reasonCode:'HEALTH_NOT_ASSEMBLED'}});
const assignment={assignmentId:'assignment:1',instanceId:'instance:1',assigneeId:'human:fixture',businessRole:'已保存的分析分工',lifecycle:'ACTIVE',effectiveFrom:'2026-11-08T00:00:00Z',effectiveUntil:null,binding:{state:'UNAVAILABLE',reasonCode:'WORKFLOW_BINDING_NOT_ASSEMBLED'}};
const root=(revision='1')=>'/employees?'+new URLSearchParams({employeeDefinitionId:def().employeeDefinitionId,employeeDefinitionRevisionId:revision,detail:'open'});
const region=(page:Page,name:string)=>page.getByRole('region',{name,exact:true});
async function setup(page:Page,mode='normal'){
 const state={writes:[] as string[],reads:[] as string[],denied:false,other:false,hold:false,release:()=>{},held:0};
 const envelope=(result:unknown)=>({schemaVersion:'workbench-operation.v1',result,continuationIds:[]});
 await page.route('**/api/**',async route=>{
  const req=route.request(),u=new URL(req.url()),path=decodeURIComponent(u.pathname);state.reads.push(path);
  if(req.method()!=='GET'){state.writes.push(req.method()+' '+path);return route.abort()}
  if(path.endsWith('/session'))return route.fulfill({json:{schemaVersion:'workbench-session.v1',principal:{...principal,...(state.other?{principalId:'human:changed'}:{})},session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture-not-for-storage'}});
  if(path.endsWith('/conversations/capabilities'))return route.fulfill({json:{result:{enabled:false}}});
  if(path.endsWith('/employees'))return route.fulfill({json:envelope({items:[def()],nextCursor:null})});
  if(path.includes('/employees/employee:relations/revisions/')){
   const parts=path.split('/'),revision=parts[parts.indexOf('revisions')+1],last=parts.at(-1);
   if(last==='history'||last==='instances'){
    if(last==='instances'&&state.hold){state.held++;await new Promise<void>(resolve=>{state.release=resolve})}
    if(state.denied)return route.fulfill({status:404,json:{reasonCode:'AUTHORIZATION_NOT_FOUND'}});
    const value=def(revision),parent={employeeDefinitionId:value.employeeDefinitionId,employeeDefinitionRevisionId:revision,employeeDefinitionDigest:value.employeeDefinitionDigest};
    let items=last==='history'?[def(),def('2')]:[instance(revision)],nextCursor:string|null=null;
    if(mode==='pagination'&&last==='history'){items=u.searchParams.has('cursor')?[def('2')]:[def()];nextCursor=u.searchParams.has('cursor')?null:'fixture-opaque-cursor'}
    if(mode==='limited'&&last==='instances')items=[];
    if(mode==='wrong-parent')parent.employeeDefinitionDigest='0'.repeat(64);
    if(mode==='wrong-child'&&last==='instances')items=[{...instance(revision),employeeDefinition:{...instance(revision).employeeDefinition,employeeDefinitionId:'foreign'}}];
    if(mode==='identity')state.other=true;
    return route.fulfill({json:envelope({relation:last==='history'?'READ_EMPLOYEE_HISTORY':'READ_EMPLOYEE_INSTANCES',parent,items,nextCursor,visibility:'AUTHORIZED_ONLY',scanLimited:mode==='limited',executionStarted:false})});
   }
   return route.fulfill({json:envelope(def(revision))});
  }
  if(path.endsWith('/instances/instance:1/assignments'))return route.fulfill({json:envelope({relation:'READ_INSTANCE_ASSIGNMENTS',parent:{instanceId:'instance:1'},items:[assignment],nextCursor:null,visibility:'AUTHORIZED_ONLY',scanLimited:false,executionStarted:false})});
  if(path.endsWith('/instances/instance:1/assignments/assignment:1'))return route.fulfill({json:envelope(assignment)});
  if(path.includes('/instances/instance:'))return route.fulfill({json:envelope(instance(path.endsWith(':2')?'2':'1'))});
  if(path.includes('/agents/'))return route.fulfill({json:envelope({definitionId:'agent:relations',revisionId:'1',digest:'c'.repeat(64),name:'既有分析Agent',role:{title:'分析与核对',duties:['只读核对'],businessPurpose:'隔离界面验证',capabilities:[]}})});
  if(path.endsWith('/resource-directory'))return route.fulfill({json:{result:{items:[],nextCursor:null,subject:principal.principalId,scope:{tenantId:principal.tenantId,securityDomain:principal.securityDomain}}}});
  return route.fulfill({status:404,json:{reasonCode:'CONTROLLED_UI_FIXTURE_NOT_AVAILABLE'}});
 });return state;
}
async function open(page:Page){await page.goto(root());await expect(page.getByRole('region',{name:'选中员工详情',exact:true}).getByRole('heading',{name:'数字员工关联核对',exact:true})).toBeVisible()}
async function instances(page:Page){await page.getByRole('button',{name:'实例',exact:true}).click();await expect(region(page,'关联实例').getByRole('button',{name:'查看此实例'})).toBeVisible()}

test('browse versions, exact instances and their assignments without entering internal identifiers',async({page},info)=>{
 const state=await setup(page);await open(page);const history=region(page,'已保存的员工版本');await expect(history.getByRole('button',{name:'查看此版本'})).toHaveCount(2);await history.getByRole('button',{name:'查看此版本'}).last().click();await expect(page).toHaveURL(/employeeDefinitionRevisionId=2/);
 await region(page,'已保存的员工版本').getByRole('button',{name:'查看此版本'}).first().click();await expect(page).toHaveURL(/employeeDefinitionRevisionId=1/);await instances(page);
 await region(page,'关联实例').getByRole('button',{name:'查看此实例'}).click();await expect(page.getByRole('heading',{name:'已读取实例摘要'})).toBeVisible();await expect(page.locator('.employee-read-result')).toContainText('执行信息未接通');await expect(page.locator('.employee-read-result')).not.toContainText('运行中');
 await page.getByRole('button',{name:'工作分配',exact:true}).click();await region(page,'关联工作分配').getByRole('button',{name:'查看工作分配'}).click();await expect(page.getByRole('heading',{name:'当前查询的实例与工作分配'})).toBeVisible();await expect(page.locator('.employee-read-result')).toContainText('已保存的分析分工');
 for(const width of [1280,390]){await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.screenshot({path:info.outputPath(`employee-relations-${width}.png`)})}
 await page.reload();await expect(page.getByRole('heading',{name:'当前查询的实例与工作分配'})).toBeVisible();expect(state.writes).toEqual([]);expect(state.reads.filter(p=>p.endsWith('/instances/instance:1')).length).toBeGreaterThan(1);
});
test('history pagination stays at the same exact selected employee revision',async({page})=>{const state=await setup(page,'pagination');await open(page);const list=region(page,'已保存的员工版本');await expect(list.getByRole('button',{name:'查看此版本'})).toHaveCount(1);await list.getByRole('button',{name:'加载更多'}).click();await expect(list.getByRole('button',{name:'查看此版本'})).toHaveCount(2);await expect(list.getByRole('button',{name:'加载更多'})).toHaveCount(0);expect(state.writes).toEqual([])});
test('loss of relation read access withdraws stale instance choices without a false empty state',async({page})=>{const state=await setup(page);await open(page);await instances(page);state.denied=true;await region(page,'关联实例').getByRole('button',{name:'刷新列表'}).click();await expect(region(page,'关联实例').getByRole('alert')).toContainText('不能据此判断没有记录');await expect(region(page,'关联实例').getByRole('button',{name:'查看此实例'})).toHaveCount(0);expect(state.writes).toEqual([])});
for(const mode of ['wrong-parent','identity'])test('relation '+mode+' never exposes a version choice',async({page})=>{const state=await setup(page,mode);await open(page);await expect(region(page,'已保存的员工版本').getByRole('alert')).toBeVisible();await expect(region(page,'已保存的员工版本').getByRole('button',{name:'查看此版本'})).toHaveCount(0);expect(state.writes).toEqual([])});
test('wrong child definition cannot become a selectable related instance',async({page})=>{const state=await setup(page,'wrong-child');await open(page);await page.getByRole('button',{name:'实例',exact:true}).click();await expect(region(page,'关联实例').getByRole('alert')).toBeVisible();await expect(region(page,'关联实例').getByRole('button',{name:'查看此实例'})).toHaveCount(0);expect(state.writes).toEqual([])});
test('scan limited reads clearly remain incomplete',async({page})=>{const state=await setup(page,'limited');await open(page);await page.getByRole('button',{name:'实例',exact:true}).click();await expect(region(page,'关联实例')).toContainText('列表仍可能不完整');await expect(region(page,'关联实例').getByRole('button',{name:'查看此实例'})).toHaveCount(0);expect(state.writes).toEqual([])});
test('leaving a held instance read for another saved revision cannot restore old choices',async({page})=>{const state=await setup(page);await open(page);await instances(page);state.hold=true;await region(page,'关联实例').getByRole('button',{name:'刷新列表'}).click();await expect.poll(()=>state.held).toBeGreaterThan(0);await page.getByRole('button',{name:'概览',exact:true}).click();await region(page,'已保存的员工版本').getByRole('button',{name:'查看此版本'}).last().click();await expect(page).toHaveURL(/employeeDefinitionRevisionId=2/);state.release();await expect(region(page,'关联实例')).toHaveCount(0);await expect(region(page,'已保存的员工版本')).toBeVisible();expect(state.writes).toEqual([])});
test('assignments are not browsed before an exact instance is selected',async({page})=>{const state=await setup(page);await open(page);await page.getByRole('button',{name:'工作分配',exact:true}).click();await expect(region(page,'关联工作分配')).toContainText('先在实例页选择');expect(state.reads.some(p=>p.endsWith('/assignments'))).toBe(false);expect(state.writes).toEqual([])});
