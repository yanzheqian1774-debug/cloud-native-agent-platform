import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
const fixture=JSON.parse(readFileSync(new URL('./actual-result.json',import.meta.url),'utf8'));
for(const width of [1440,390])test(`saved result consistent at ${width}`,async({page},info)=>{
 const posts:string[]=[];await page.setViewportSize({width,height:1000});
 await page.route('**/api/workbench/**',route=>{if(route.request().method()!=='GET')posts.push(route.request().method());return route.fulfill({json:{result:fixture.progress}})});
 await page.goto('/tests/result-summary/preview.html');
 const main=page.getByRole('region',{name:'文档规则核对结果'}),rail=page.getByRole('region',{name:'实时执行过程'});
 await expect(main).toContainText('唯一上线负责人存在冲突；影响范围尚待确认；回退步骤缺失。');
 await expect(main).toContainText('业务结论：尚无法确定。核对工作已完成');
 await expect(main.getByRole('heading',{name:'检查项：影响范围已明确'})).toBeVisible();
 await expect(main).toContainText('1 项满足 · 1 项缺失 · 1 项待确认 · 1 项冲突');
 await expect(rail).toContainText('本步核对：1 项满足 · 1 项缺失 · 1 项待确认 · 1 项冲突');
 await expect(rail).not.toContainText('待补充 2 项');await expect(rail).not.toContainText('仍需后续核验');await expect(rail).not.toContainText('等待完成核验');
 await expect(rail).toContainText('执行已完成');
 await main.getByText('查看规则版本与原文依据').click();await expect(main).toContainText(fixture.review.ruleBinding.ontology.digest);
 await page.screenshot({path:info.outputPath(`result-${width}.png`),fullPage:true});
 await page.reload();await expect(main).toContainText('业务结论：尚无法确定');expect(posts).toEqual([]);
});

test('summary does not infer findings from unreadable, mismatched or malformed reports',async({page})=>{
 await page.route('**/api/workbench/**',route=>route.fulfill({json:{result:fixture.progress}}));
 await page.goto('/tests/result-summary/preview.html');
 const results=await page.evaluate(async({review})=>{
  const modulePath='/src/problems/documentRuleSummary.ts';
  const {documentBusinessSummary}=await import(modulePath);
  const report={schemaVersion:'document-review-output.v1',operation:'RENDER_REPORT',documentReview:review,sourceSnapshot:review.sourceSnapshot};
  const base={preparation:{source_snapshot:review.sourceSnapshot},artifacts:[{contentAccess:'AUTHORIZED',content:JSON.stringify(report)}]};
  return [documentBusinessSummary({...base,artifacts:[{...base.artifacts[0],contentAccess:'DENIED'}]}),documentBusinessSummary({...base,preparation:{source_snapshot:{...review.sourceSnapshot,digest:'0'.repeat(64)}}}),documentBusinessSummary({...base,artifacts:[{...base.artifacts[0],content:'{bad json'}]})];
 },{review:fixture.review});
 expect(results).toEqual([null,null,null]);
});
