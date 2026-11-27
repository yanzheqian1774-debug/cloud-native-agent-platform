import {test,expect} from '@playwright/test';
for(const width of [1440,390])test(`authorized verified report inline and refresh ${width}`,async({page},info)=>{
 const writes:string[]=[];await page.route('**/api/**',route=>{writes.push(route.request().method());return route.abort()});
 await page.setViewportSize({width,height:1000});await page.goto('/tests/native-data-result/preview.html');
 const report=page.getByRole('region',{name:'自主资料分析结果'});await expect(report).toBeVisible();
 await expect(report.getByRole('table').first()).toBeVisible();
 await expect(report).toContainText('2026-09-20');await expect(report).toContainText('A');
 await expect(report).toContainText('60');await expect(report).toContainText('15');
 await report.getByText('查看逐步分析过程与核验依据').click();await expect(report).toContainText('核对对应原始行');await expect(report).toContainText('独立核验通过');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width+1);
 await page.screenshot({path:info.outputPath(`native-result-${width}.png`),fullPage:true});
 await page.reload();await expect(report).toContainText('不代表业务问题已解决');expect(writes).toEqual([]);
});
for(const mode of ['raw-only','report-mismatch','source-mismatch','adapter-mismatch','executor-mismatch','unreadable'])test(`cannot promote ${mode} to report`,async({page})=>{
 await page.goto('/tests/native-data-result/preview.html?mode='+mode);
 await expect(page.getByRole('region',{name:'自主资料分析结果'})).toHaveCount(0);
 await expect(page.getByRole('table')).toHaveCount(0);
});

// Legacy text artifacts have no native executor claim; preserve their original reader.
test('legacy plain text keeps original artifact reader',async()=>{
 const {nativeDataExecutorMatches,nativeDataReport}=await import('../../src/problems/nativeDataReport');
 expect(nativeDataExecutorMatches('原始文本成果',undefined)).toBe(true);
 expect(nativeDataReport('原始文本成果')).toBeNull();
});
