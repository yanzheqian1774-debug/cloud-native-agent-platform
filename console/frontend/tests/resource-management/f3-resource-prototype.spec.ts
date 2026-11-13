import {expect,test} from '@playwright/test';
import {fixture,skillId} from '../helpers/resourceMaintenanceFixture';
test('F3 reference-sized candidate overview content and maintenance captures',async({page},info)=>{
 const state=await fixture(page,true);state.resource.name='自然日延期与阈值判定';state.resource.revisions[0].state='PUBLISHED';state.resource.revisions[0].content.description='按自然日核对延期；缺日期保持未知。';state.resource.publishedRevisionId='revision:1';state.resource.currentDraftRevisionId=null;state.resource.lifecycleState='PUBLISHED';
 await page.setViewportSize({width:1440,height:900});await page.goto('/skills?managedResource='+encodeURIComponent(skillId));await expect(page.getByRole('heading',{name:'用途与交付'})).toBeVisible();await page.screenshot({path:info.outputPath('candidate-overview-1440.png')});
 await page.getByRole('tab',{name:'内容与定义'}).click();await page.screenshot({path:info.outputPath('candidate-content-1440.png')});
 await page.getByRole('button',{name:'历史记录',exact:true}).click();await expect(page.getByRole('heading',{name:'版本记录',exact:true})).toBeVisible();await page.screenshot({path:info.outputPath('candidate-history-1440.png')});
 await page.getByRole('button',{name:'返回内容',exact:true}).click();await page.getByRole('button',{name:'测试与验证',exact:true}).click();await expect(page.getByRole('region',{name:'技能真实测试'})).toBeVisible();await page.screenshot({path:info.outputPath('candidate-maintenance-1440.png')});
 expect(state.posts).toEqual([]);
});
