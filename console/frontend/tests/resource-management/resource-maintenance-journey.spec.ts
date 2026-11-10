import {expect,test,type Page} from '@playwright/test';
import {fixture,skillContent,reportText,source,principal,operations,skillId,employeeId} from '../helpers/resourceMaintenanceFixture';
async function create(page: Page) { await page.getByRole('button', { name: '新建Skill', exact: true }).click(); await page.getByLabel('名称', { exact: true }).fill('资源维护完整路径核验'); await page.getByLabel('用途说明', { exact: true }).fill('维护原用途'); await page.getByLabel('能力名称', { exact: true }).fill('READ_DATA'); await page.getByLabel('办理说明', { exact: true }).fill('核对来源'); await page.getByText('高级配置与输入输出契约', { exact: true }).click(); await page.getByLabel('配置对象', { exact: true }).fill(JSON.stringify(skillContent)); await page.getByRole('button', { name: '保存草稿', exact: true }).click(); }
async function openTestForm(page:Page){
 await page.getByRole('tab',{name:'测试',exact:true}).click();
 await expect(page.getByRole('tabpanel',{name:'测试',exact:true})).toBeVisible();
 const details=page.getByRole('region',{name:'技能真实测试'}).locator('details').filter({has:page.getByText('填写或修改测试用例',{exact:true})});
 if(await details.getAttribute('open')===null)await details.locator('summary').click();
 await expect(page.getByLabel('测试名称',{exact:true})).toBeVisible();
}
async function runTest(page:Page,operation='READ_DATA',pass=true){
 await openTestForm(page);
 await page.getByLabel('测试名称',{exact:true}).fill('覆盖核验');
 await page.getByLabel('测试操作',{exact:true}).selectOption(operation);
 await page.getByLabel('测试输入数据',{exact:true}).fill(JSON.stringify({schemaVersion:'sales-diagnostic-input.v1',synthetic:true,sourceSnapshot:source,source:JSON.parse(reportText).source,dependencies:operation==='READ_DATA'?{}:{read:{...JSON.parse(reportText),operation:'READ_DATA'}}}));
 await page.getByLabel('测试预期结果',{exact:true}).fill(JSON.stringify({schemaVersion:'sales-diagnostic-output.v1',operation:pass?operation:'INTENTIONALLY_WRONG_EXPECTATION'}));
 await Promise.all([page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/resource-management/skill/commands')&&r.request().postDataJSON().action==='test'),page.getByRole('button',{name:'运行真实测试',exact:true}).click()]);
 await expect(page.getByRole('region',{name:'技能真实测试'})).toContainText(pass?'测试通过':'测试未通过');
 await expect(page.getByRole('button',{name:'读取原操作结果',exact:true})).toHaveCount(0);
}
test('maintenance draft edit failed test checked publication exact employee and saved result return form one journey', async ({ page }, info) => {
    const state = await fixture(page);
    await page.goto('/skills');
    await create(page);
    await expect(page.getByRole('region', { name: '当前资源配置' })).toContainText('维护原用途');
    await page.getByRole('button', { name: '编辑草稿', exact: true }).click();
    await page.getByLabel('用途说明', { exact: true }).fill('保留操作契约的新用途');
    await page.getByRole('button', { name: '保存草稿', exact: true }).click();
    await expect(page.getByRole('region', { name: '当前资源配置' })).toContainText('保留操作契约的新用途');
    await runTest(page, 'READ_DATA', false);
    await page.getByRole('tab', { name: '发布检查', exact: true }).click();
    await expect(page.getByRole('tabpanel',{name:'发布检查',exact:true})).toBeVisible();
    await page.getByRole('tabpanel',{name:'发布检查',exact:true}).getByRole('button', { name: '验证全部操作后发布', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('所有操作均需真实测试通过');
    expect(state.resource.publishedRevisionId).toBeNull();
    for (const operation of operations)
        await runTest(page, operation);
    await page.getByRole('tab', { name: '发布检查', exact: true }).click();
    await expect(page.getByRole('tabpanel',{name:'发布检查',exact:true})).toBeVisible();
    await page.getByRole('tabpanel',{name:'发布检查',exact:true}).getByRole('button', { name: '验证全部操作后发布', exact: true }).click();
    await expect(page.getByRole('link', { name: '查看发布版本与使用记录' })).toBeVisible();
    const beforeRead = state.posts.length;
    await page.getByRole('tab', { name: '使用追溯', exact: true }).click();
    await page.getByRole('link', { name: '查看引用员工' }).click();
    await expect(page.getByRole('heading', { name: '准确资源引用员工', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: '返回资源维护', exact: false })).toBeVisible();
    const member = page.getByRole('table').getByRole('link').filter({ hasText: skillId });
    await expect(member).toHaveAttribute('href', new RegExp('resourceRevision=revision%3A1'));
    await page.getByRole('link', { name: '返回资源维护', exact: false }).click();
    await expect(page.getByRole('tab', { name: '使用追溯', exact: true })).toHaveAttribute('aria-selected', 'true');
    await page.getByRole('link', { name: '查看发布版本与使用记录' }).click();
    await page.getByRole('button', { name: '已保存的同版本核对结果', exact: true }).click();
    await expect(page.getByRole('heading', { name: '已有执行的只读核对', exact: true })).toBeVisible();
    await expect(page.getByRole('region', { name: '销售诊断关键数据' })).toBeVisible();
    await page.getByRole('link', { name: '返回同一准确资源', exact: true }).click();
    await expect(page.getByRole('heading', { name: '资源维护完整路径核验', exact: true })).toBeVisible();
    expect(new URL(page.url()).searchParams.get('resourceRevision')).toBe('revision:1');
    expect(state.posts).toHaveLength(beforeRead);
    await page.getByRole('link', { name: '返回资源目录', exact: true }).click();
    await page.getByRole('article',{name:'资源维护完整路径核验',exact:true}).getByRole('link',{name:'维护当前配置',exact:true}).click();
    await page.getByRole('button', { name: '创建后继草稿', exact: true }).click();
    await expect.poll(() => state.resource.currentDraftRevisionId).toBe('revision:2');
    const pinned = await page.getByRole('link', { name: '查看发布版本与使用记录' }).getAttribute('href');
    expect(new URL(pinned!, page.url()).searchParams.get('resourceRevision')).toBe('revision:1');
    await page.getByRole('tab', { name: '版本', exact: true }).click();
    await expect(page.getByRole('heading', { name: '版本历史', exact: true })).toBeVisible();
    await expect(page.getByText('上一发布 → 当前修订', { exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: '查看引用员工', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '核对版本与影响', exact: true })).toBeEnabled();
    for (const width of [1280, 390]) {
        await page.setViewportSize({ width, height: 900 });
        await page.screenshot({ path: info.outputPath('resource-maintenance-journey-' + width + '.png') });
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    }
    expect(state.posts.every(p => typeof p.commandKey === 'string' && !('actor' in p) && !('tenant' in p))).toBe(true);
});
for (const action of ['edit', 'test', 'publish-tested'])
    test('lost ' + action + ' response reload recovers only its original typed key', async ({ page }) => {
        const state = await fixture(page, true);
        state.resource.testResults = operations.map(operation => ({ resultId: 'old-' + operation, revisionId: 'revision:1', revisionDigest: 'a'.repeat(64), operation, caseName: '覆盖核验', status: 'PASSED', actualExecution: true, verificationLevel: 'ISOLATED_SYNTHETIC_EXECUTOR', actual: { pass: true } }));
        state.loseNext = true;
        state.receiptReadable = false;
        await page.goto('/skills?managedResource=' + encodeURIComponent(skillId));
        await expect(page.getByRole('region', { name: '当前资源配置' })).toBeVisible();
        if (action === 'edit') {
            await page.getByRole('button', { name: '编辑草稿', exact: true }).click();
            await page.getByLabel('用途说明', { exact: true }).fill('响应丢失后的正式内容');
            await page.getByRole('button', { name: '保存草稿', exact: true }).click();
        }
        if (action === 'test') {
            await openTestForm(page);
            await page.getByLabel('测试预期结果', { exact: true }).fill(JSON.stringify({ operation: 'READ_DATA' }));
            await page.getByLabel('测试输入数据', { exact: true }).fill(JSON.stringify({ schemaVersion: 'sales-diagnostic-input.v1', synthetic: true, sourceSnapshot: source, source: JSON.parse(reportText).source, dependencies: {} }));
            await page.getByRole('button', { name: '运行真实测试', exact: true }).click();
        }
        if (action === 'publish-tested') {
            await page.getByRole('tab', { name: '发布检查', exact: true }).click();
            await expect(page.getByRole('tabpanel',{name:'发布检查',exact:true})).toBeVisible();
    await page.getByRole('tabpanel',{name:'发布检查',exact:true}).getByRole('button', { name: '验证全部操作后发布', exact: true }).click();
        }
        await expect(page.getByRole('button', { name: '读取原操作结果', exact: true })).toBeEnabled();
        const key = state.posts[0].commandKey;
        await page.reload();
        state.receiptReadable = true;
        await page.getByRole('button', { name: '读取原操作结果', exact: true }).click();
        await expect(page.getByText('已读回原操作及当前正式记录，没有再次提交。', { exact: true })).toBeVisible();
        expect(state.posts).toHaveLength(1);
        expect(state.gets.filter(p => p.includes('/commands/')).every(p => p.endsWith(String(key)))).toBe(true);
    });
for (const [field, value] of [['action', 'access'], ['kind', 'mcp'], ['commandKey', 'unrelated'], ['identity', 'skill:other'], ['aggregateVersion', 999], ['executionStarted', true], ['modelCalls', 1]])
    test('ordinary maintenance rejects mismatched ' + field + ' receipt and retains original key', async ({ page }) => {
        const state = await fixture(page);
        state.override = { [String(field)]: value };
        await page.goto('/skills');
        await create(page);
        await expect(page.getByRole('alert')).toContainText('操作回执与原请求不一致');
        await expect(page.getByRole('button', { name: '读取原操作结果', exact: true })).toBeVisible();
        await expect(page.getByRole('region', { name: '当前资源配置' })).toHaveCount(0);
        expect(state.posts).toHaveLength(1);
    });
test('account change before ordinary create sends no command and withdraws old view', async ({ page }) => { const state = await fixture(page); await page.goto('/skills'); await page.getByRole('button', { name: '新建Skill', exact: true }).click(); state.otherIdentity = true; await page.getByLabel('名称', { exact: true }).fill('不可跨账号创建'); await page.getByLabel('用途说明', { exact: true }).fill('核验'); await page.getByLabel('能力名称', { exact: true }).fill('READ_DATA'); await page.getByLabel('办理说明', { exact: true }).fill('核验'); await page.getByRole('button', { name: '保存草稿', exact: true }).click(); await expect(page.getByRole('region', { name: '资源配置状态' })).toContainText('当前未就绪'); expect(state.posts).toEqual([]); });
test('unsafe resource return cannot create an external or unrelated navigation link', async ({ page }) => { await fixture(page, true); await page.goto('/employees?employeeDefinitionId=' + employeeId + '&employeeDefinitionRevisionId=employee-revision%3Aconsumer&detail=1&section=capabilities&resourceBack=' + encodeURIComponent('https://foreign.invalid/skills?managedResource=x')); await expect(page.getByRole('heading', { name: '准确资源引用员工', exact: true })).toBeVisible(); await expect(page.getByRole('link', { name: '返回资源维护', exact: false })).toHaveCount(0); });
test('leaving after ordinary POST retains original intent and cannot restore detail in another view', async ({ page }) => {
    const state = await fixture(page);
    state.hold = true;
    await page.goto('/skills');
    await create(page);
    await expect.poll(() => state.posts.length).toBe(1);
    const key = state.posts[0].commandKey;
    await page.evaluate(() => { history.pushState({}, '', '/catalog'); window.dispatchEvent(new PopStateEvent('popstate')); });
    state.hold = false;
    state.release();
    await expect(page.getByRole('region', { name: '当前资源配置' })).toHaveCount(0);
    await page.goto('/skills');
    await page.getByRole('button', { name: '读取原操作结果', exact: true }).click();
    await expect(page.getByRole('region', { name: '当前资源配置' })).toContainText(state.resource.name);
    expect(state.posts).toHaveLength(1);
    expect(state.posts[0].commandKey).toBe(key);
});
test('fresh directory revocation withdraws a successful ordinary command result and never regrants', async ({ page }) => {
    const state = await fixture(page, true);
    await page.goto('/skills?managedResource=' + encodeURIComponent(skillId));
    await page.getByRole('button', { name: '编辑草稿', exact: true }).click();
    await page.getByLabel('用途说明', { exact: true }).fill('正式编辑结果');
    state.revoked = true;
    await page.getByRole('button', { name: '保存草稿', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('当前配置尚未获准读回');
    await expect(page.getByRole('region', { name: '当前资源配置' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '读取原操作结果', exact: true })).toBeVisible();
    expect(state.posts).toHaveLength(1);
});
test('legacy unknown ordinary key without binding is preserved and never replaced by create', async ({ page }) => {
    const state = await fixture(page);
    const marker = 'resource-management:' + principal.principalId + ':' + principal.tenantId + ':' + principal.securityDomain + ':skill';
    await page.addInitScript(({ marker }) => sessionStorage.setItem(marker, 'original-legacy-key'), { marker });
    await page.goto('/skills');
    await page.getByRole('button', { name: '读取原操作结果', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('原操作的核对依据尚未恢复');
    expect(await page.evaluate(marker => sessionStorage.getItem(marker), marker)).toBe('original-legacy-key');
    expect(state.posts).toEqual([]);
    await expect(page.getByRole('button', { name: '新建Skill', exact: true })).toBeDisabled();
});

test('late maintenance completion preserves the tab chosen while the command was running',async({page})=>{
 const state=await fixture(page,true);state.hold=true;await page.goto('/skills?managedResource='+encodeURIComponent(skillId));await page.getByRole('button',{name:'编辑草稿',exact:true}).click();await page.getByLabel('用途说明',{exact:true}).fill('保留当前页面位置');await page.getByRole('button',{name:'保存草稿',exact:true}).click();await expect.poll(()=>state.posts.length).toBe(1);await page.getByRole('tab',{name:'发布检查',exact:true}).click();state.hold=false;state.release();await expect(page.getByRole('button',{name:'读取原操作结果',exact:true})).toHaveCount(0);await expect(page.getByRole('tab',{name:'发布检查',exact:true})).toHaveAttribute('aria-selected','true');expect(new URL(page.url()).searchParams.get('resourceTab')).toBe('发布检查');expect(state.posts).toHaveLength(1);
});

test('expired policy service cannot invalidate a still-authenticated user session',async({page})=>{
 await fixture(page);await page.addInitScript(()=>window.addEventListener('workbench-session-expired',()=>sessionStorage.setItem('unexpected-session-expiry','yes')));await page.route('**/api/workbench/v1/resource-management/skill',r=>r.fulfill({status:401,json:{reasonCode:'AUTHENTICATION_REQUIRED'}}));await page.goto('/skills');await expect(page.getByRole('region',{name:'资源配置状态'})).toContainText('当前未就绪');expect(await page.evaluate(()=>sessionStorage.getItem('unexpected-session-expiry'))).toBeNull();await expect(page.getByRole('link',{name:'新会话',exact:true})).toBeVisible();
});
