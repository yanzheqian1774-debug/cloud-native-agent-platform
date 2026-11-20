import {test,expect,type Page} from '@playwright/test';
import {fixture,skillId} from '../helpers/resourceMaintenanceFixture';
const href='/skills?managedResource='+encodeURIComponent(skillId)+'&resourceSection=content&resourceTab='+encodeURIComponent('测试');
async function seed(page:Page){
 const s=await fixture(page,true);s.resource.revisions[0].state='PUBLISHED';s.resource.publishedRevisionId='revision:1';s.resource.currentDraftRevisionId=null;
 const records=[{id:'one',status:'PASSED',actual:{operation:'READ_DATA',count:4}},{id:'two',status:'FAILED',actual:{operation:'VALIDATE_DATA',count:2}}];
 s.resource.testResults=records.map((r,i)=>({resultId:r.id,testId:'case:'+r.id,caseName:'样例'+r.id,operation:i?'VALIDATE_DATA':'READ_DATA',revisionId:'revision:1',revisionDigest:'a'.repeat(64),status:r.status,actual:r.actual,actualExecution:true,verificationLevel:'ISOLATED_SYNTHETIC_EXECUTOR',reasonCode:i?'TEST_EXPECTATION_MISMATCH':'ACTUAL_OUTPUT_MATCHED'}));
 Object.assign(s.resource,{savedTests:records.map(r=>({testId:'case:'+r.id,name:'样例'+r.id,input:{source:'合成资料'+r.id},expected:{count:4}}))});return s;
}
test('default latest is selected on both sides and case clicks show exact saved summaries',async({page},info)=>{
 const s=await seed(page);await page.setViewportSize({width:1440,height:1000});await page.goto(href);
 const list=page.locator('.rd-test-list'),result=page.getByRole('region',{name:'所选契约样例结果'});
 await expect(list.getByRole('button',{name:/样例two/})).toHaveAttribute('aria-pressed','true');await expect(result).toContainText('样例two');
 await expect(page.getByRole('region',{name:'已存输入',exact:true})).toContainText('合成资料two');await expect(page.getByRole('region',{name:'预期结果',exact:true})).toContainText('count：4');
 await list.getByRole('button',{name:/样例one/}).click();await expect(result).toContainText('样例one');await expect(list.getByRole('button',{name:/样例one/})).toHaveAttribute('aria-pressed','true');await expect(page.getByRole('region',{name:'实际结果',exact:true})).toContainText('count：4');
 await expect(page.getByRole('heading',{name:s.resource.name,exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'返回来源'})).toBeVisible();
 await expect(page.getByRole('combobox',{name:'查看配置内容'})).toHaveCount(0);await expect(page.getByRole('navigation',{name:'当前配置内容'})).toHaveCount(1);
 await page.screenshot({path:info.outputPath('test-1440.png'),fullPage:true});await page.reload();await expect(list.getByRole('button',{name:/样例two/})).toHaveAttribute('aria-pressed','true');expect(s.posts).toEqual([]);
});
test('missing stored input remains missing and unexecuted case cannot inherit passing details',async({page},info)=>{
 const s=await seed(page);Object.assign(s.resource,{savedTests:[]});s.resource.testResults[1].actualExecution=false;s.resource.testResults[1].actual=null;s.resource.testResults[1].status='NOT_EXECUTED';
 await page.setViewportSize({width:390,height:844});await page.goto(href);await expect(page.getByRole('region',{name:'已存输入',exact:true})).toContainText('未记录');await expect(page.getByRole('region',{name:'实际结果',exact:true})).toContainText('未记录');await expect(page.getByRole('region',{name:'所选契约样例结果'})).toContainText('尚未执行');await expect(page.getByText('当前契约样例入口不会启动业务任务、调用模型或外部服务',{exact:false})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.screenshot({path:info.outputPath('test-390.png'),fullPage:true});expect(s.posts).toEqual([]);
});

test('new draft does not inherit prior published revision test results',async({page})=>{
 const s=await seed(page);s.resource.revisions.push({...structuredClone(s.resource.revisions[0]),revisionId:'revision:2',digest:'b'.repeat(64),state:'DRAFT'});s.resource.currentDraftRevisionId='revision:2';
 await page.route('**/impact',route=>route.fulfill({json:{result:{current:{revisionId:'revision:2',digest:'b'.repeat(64)},changes:[],authorizedUses:[],testCoverage:{ready:false,checks:[]},dependencies:{incoming:[],outgoing:[],limitations:[]}}}}));
 await page.goto(href);await expect(page.getByText('尚无当前修订的契约样例测试记录。')).toBeVisible();expect(s.posts).toEqual([]);
});
for(const mode of ['wrong-test-id','duplicate-case','different-revision'] as const)test('stored case binding is not inferred: '+mode,async({page})=>{
 const s=await seed(page);const cases=s.resource.savedTests as unknown as Array<Record<string,unknown>>;
 if(mode==='wrong-test-id')s.resource.testResults[1].testId='case:absent';
 if(mode==='duplicate-case')cases.push({...cases[1],input:{source:'OTHER_INPUT'}});
 if(mode==='different-revision'){cases[1].revisionId='revision:other';cases[1].revisionDigest='b'.repeat(64);}
 await page.goto(href);await expect(page.getByRole('region',{name:'已存输入',exact:true})).toContainText('未记录');await expect(page.getByRole('region',{name:'预期结果',exact:true})).toContainText('未记录');await expect(page.getByRole('region',{name:'实际结果',exact:true})).toContainText('count：2');expect(s.posts).toEqual([]);
});
test('selected historical result uses its own saved case and exact revision',async({page})=>{
 const s=await seed(page);s.resource.revisions.push({...structuredClone(s.resource.revisions[0]),revisionId:'revision:2',digest:'b'.repeat(64),state:'DRAFT'});s.resource.currentDraftRevisionId='revision:2';
 await page.goto('/skills?'+new URLSearchParams({managedResource:skillId,resourceSection:'impact'}));
 const row=page.getByRole('article',{name:'维护测试使用记录'}).getByRole('row').filter({hasText:'样例one'});
 await row.getByRole('button',{name:'查看维护测试结果'}).click();
 await expect(page.getByRole('region',{name:'所选契约样例结果'})).toContainText('历史修订');await expect(page.getByRole('region',{name:'已存输入',exact:true})).toContainText('合成资料one');await expect(page.locator('.rd-test-list').getByRole('button',{name:/样例one/})).toHaveAttribute('aria-pressed','true');expect(s.posts).toEqual([]);
});
