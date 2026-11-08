import {expect,type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
const plan = JSON.parse(readFileSync(new URL('../e2e/fixtures/delivery-plan.json', import.meta.url), 'utf8'));
export const skillContent = JSON.parse(readFileSync(new URL('../resource-management/fixtures/maintenance-skill.json', import.meta.url), 'utf8'));
export const reportText = readFileSync(new URL('../e2e/fixtures/sales-report.json', import.meta.url), 'utf8'), source = JSON.parse(reportText).sourceSnapshot;
export const principal = { principalId: 'human:maintenance-fixture', tenantId: 'maintenance-fixture', securityDomain: 'isolated' }, scope = { tenantId: principal.tenantId, securityDomain: principal.securityDomain };
const envelope=(result:unknown)=>({schemaVersion:'workbench-operation.v1',result,continuationIds:[]});
export const operations = ['READ_DATA', 'VALIDATE_DATA', 'SUMMARIZE', 'ANALYZE_DATA', 'RENDER_REPORT'];
export const skillId = 'skill-definition:maintenance', employeeId = 'employee-definition:consumer', runDigest = 'c'.repeat(64), problem = 'maintenance-problem';
const initial = () => ({ resourceId: skillId, kind: 'skill', name: '资源维护完整路径核验', aggregateVersion: 1, lifecycleState: 'DRAFT', enabled: true, archived: false, currentDraftRevisionId: 'revision:1' as string | null, publishedRevisionId: null as string | null, revisions: [{ revisionId: 'revision:1', predecessorRevisionId: null as string | null, digest: 'a'.repeat(64), state: 'DRAFT', content: { ...structuredClone(skillContent), description: '维护原用途' }, createdAt: '2026-11-08T00:00:00Z' }], testResults: [] as Record<string, unknown>[], savedTests: [], reviews: [], relationships: [], bindings: [], invocations: [], discoverySnapshots: [], toolSelections: [], healthObservations: [], driftRecords: [], limitations: [] });
export async function fixture(page: Page, seed = false) {
    const state = { resource: initial(), created: seed, otherIdentity: false, revoked: false, receiptReadable: true, loseNext: false, override: {} as Record<string, unknown>, posts: [] as Record<string, unknown>[], gets: [] as string[], receipt: null as Record<string, unknown> | null, hold: false, release: () => { } };
    const session = () => ({ schemaVersion:'workbench-session.v1',principal: { ...principal, ...(state.otherIdentity ? { principalId: 'human:other' } : {}) }, session: { expiresAt: '2099-01-01', idleExpiresAt: '2099-01-01' }, csrfToken: 'fixture-csrf' });
    const published = () => state.resource.revisions.find(r => r.revisionId === state.resource.publishedRevisionId);
    const item = () => { const r = published()!; return { kind: 'skill', identity: skillId, revisionId: r.revisionId, digest: r.digest, name: state.resource.name, state: 'PUBLISHED', enabled: true, isCurrentPublished: true, isCurrentDraft: false, createdAt: r.createdAt, executionReady: false }; };
    const employee = () => ({ resourceKind: 'DIGITAL_EMPLOYEE_DEFINITION', employeeDefinitionId: employeeId, employeeDefinitionRevisionId: 'employee-revision:consumer', employeeDefinitionDigest: 'd'.repeat(64), role: '准确资源引用员工', responsibilities: ['核对所引用版本'], publicationState: 'PUBLISHED', lifecycleState: 'PUBLISHED', aggregateVersion: 4, members: [{ kind: 'AGENT', resourceId: 'agent:consumer', revisionId: 'agent-revision:1', digest: 'e'.repeat(64) }, { kind: 'SKILL', resourceId: skillId, revisionId: 'revision:1', digest: published()?.digest ?? 'b'.repeat(64) }] });
    await page.route('**/api/workbench/v1/**', async (route) => {
        const req = route.request(), url = new URL(req.url()), path = url.pathname;
        if (req.method() === 'GET')
            state.gets.push(path);
        if (path.endsWith('/session'))
            return route.fulfill({ json: session() });
        if (path.endsWith('/resource-management/skill'))
            return route.fulfill({ json: { result: { subject: session().principal.principalId, scope, items: state.created && !state.revoked ? [state.resource] : [] } } });
        if (path.endsWith('/resource-management/skill/commands')) {
            const body = req.postDataJSON();
            state.posts.push(body);
            expect(req.headers()['x-csrf-token']).toBe('fixture-csrf');
            const r = state.resource;
            if (body.action === 'create') {
                state.created = true;
                r.name = body.name;
                r.revisions[0].content = body.content;
            }
            if (body.action === 'edit') {
                r.revisions.at(-1)!.content = body.content;
                r.revisions.at(-1)!.digest = 'b'.repeat(64);
            }
            if (body.action === 'test')
                r.testResults.push({ resultId: 'test:' + state.posts.length, revisionId: r.currentDraftRevisionId, revisionDigest: r.revisions.at(-1)!.digest, operation: body.operation, caseName: body.testName, status: body.expectedOutput.operation === body.operation ? 'PASSED' : 'FAILED', reasonCode: 'FIXTURE_EXECUTOR_COMPARISON', actualExecution: true, verificationLevel: 'ISOLATED_SYNTHETIC_EXECUTOR', actual: { ...JSON.parse(reportText), operation: body.operation } });
            if (body.action === 'publish-tested') {
                const checks = new Map<string, Record<string, unknown>>();
                for (const t of r.testResults)
                    if (t.revisionId === r.currentDraftRevisionId)
                        checks.set(String(t.operation), t);
                if (!operations.every(op => checks.get(op)?.status === 'PASSED'))
                    return route.fulfill({ status: 409, json: { reasonCode: 'CURRENT_OPERATION_TESTS_REQUIRED' } });
                r.revisions.at(-1)!.state = 'PUBLISHED';
                r.publishedRevisionId = r.currentDraftRevisionId;
                r.currentDraftRevisionId = null;
                r.lifecycleState = 'PUBLISHED';
            }
            if (body.action === 'successor') {
                r.currentDraftRevisionId = 'revision:2';
                r.revisions.push({ ...structuredClone(r.revisions[0]), revisionId: 'revision:2', predecessorRevisionId: 'revision:1', digest: 'f'.repeat(64), state: 'DRAFT' });
                r.lifecycleState = 'DRAFT';
            }
            r.aggregateVersion++;
            state.receipt = { schemaVersion: 'resource-management-receipt.v1', kind: 'skill', action: body.action, identity: skillId, commandKey: body.commandKey, aggregateVersion: r.aggregateVersion, resource: structuredClone(r), executionStarted: false, modelCalls: 0, credentialMaterial: 'NOT_INCLUDED', ...(body.action === 'publish-tested' ? { publicationVerification: { ready: true } } : {}), ...state.override };
            if (state.hold)
                await new Promise<void>(resolve => { state.release = resolve; });
            if (state.loseNext) {
                state.loseNext = false;
                return route.abort('failed');
            }
            return route.fulfill({ json: { result: state.receipt } });
        }
        if (path.includes('/resource-management/skill/commands/')) {
            if (!state.receiptReadable) return route.fulfill({status:503,json:{reasonCode:'RECEIPT_UNAVAILABLE'}});
            return state.receipt?.commandKey===decodeURIComponent(path.split('/').at(-1)!) ? route.fulfill({json:{result:state.receipt}}) : route.fulfill({status:404,json:{reasonCode:'COMMAND_NOT_FOUND'}});
        }
        if (path.endsWith('/impact'))
            return route.fulfill({ json: { result: { current: { revisionId: state.resource.currentDraftRevisionId ?? state.resource.publishedRevisionId, digest: state.resource.revisions.at(-1)!.digest }, previousPublished: state.resource.currentDraftRevisionId && published() ? {revisionId:published()!.revisionId,digest:published()!.digest} : null, changes: [], testCoverage: { ready: false, checks: [] }, olderTestsNotCurrent: state.resource.testResults.filter(t => t.revisionId !== (state.resource.currentDraftRevisionId ?? state.resource.publishedRevisionId)).length, authorizedUses: [], truncated: false, dependencies: { incoming: published() ? [{ kind: 'EMPLOYEE', identity: employeeId, revision: 'employee-revision:consumer', name: '准确资源引用员工', state: 'SAVED_REVISION', distance: 1, versionRelation: state.resource.currentDraftRevisionId ? 'OTHER_VERSION' : 'CURRENT_VERSION', targetRevision: 'revision:1' }] : [], outgoing: [], limitations: [], unresolvedDeclarations: [] } } } });
        if (path.endsWith('/resource-directory'))
            return route.fulfill({ json: { result: { subject: principal.principalId, scope, items: published() ? [item()] : [], nextCursor: null, executionAuthority: 'NONE' } } });
        if (path.includes('/resource-directory/skill/'))
            return route.fulfill({ json: { result: { ...item(), subject: principal.principalId, scope, revision: { ...published(), content: published()!.content }, usage: [{ digest: runDigest, title: '已保存的同版本核对结果', planVersion: 4, state: 'SUCCEEDED', problemId: problem }] } } });
        if (path.endsWith('/employees'))
            return route.fulfill({ json: envelope({items:[employee()]}) });
        if (path.includes('/employees/'))
            return route.fulfill({ json: envelope(employee()) });
        if (path.includes('/agents/'))
            return route.fulfill({ json: envelope({definitionId:'agent:consumer',revisionId:'agent-revision:1',digest:'e'.repeat(64),name:'引用员工Agent',role:{title:'核对员',duties:['核对来源'],businessPurpose:'核对',capabilities:['READ_DATA']}}) });
        if (path.includes('/prepared-executions/')) {
            const ref = { resource_id: skillId, revision_id: 'revision:1', digest: published()!.digest };
            return route.fulfill({ json: { result: { digest: runDigest, executionStarted: true, preparation: { plan_id: 'maintenance-plan', plan_version: 4, plan_digest: '9'.repeat(64), approval_id: 'fixture-only', source_snapshot: source, semantics: { ...plan.semantics, title: '已保存的同版本核对结果', target: { problem: { resource_id: problem, revision_id: '1', digest: '8'.repeat(64) } } }, participants: plan.semantics.tasks.map((t: {
                                task_id: string;
                                operation: string;
                            }) => ({ task_id: t.task_id, instance_id: 'fixture-instance', assignment_id: 'fixture-assignment', definition: ref, skill: { reference: ref, operation: t.operation }, profile: ref })) }, progress: { state: 'SUCCEEDED', version: 10, cancellation_request_id: null, tasks: plan.semantics.tasks.map((t: {
                                task_id: string;
                            }) => ({ task_id: t.task_id, state: 'SUCCEEDED', attempt_ordinal: 1, reason: null })) }, admission: { state: 'NOT_ADMITTED', reason: 'READ_ONLY_FIXTURE' }, resourceUses: [], artifacts: [{ artifact_id: 'saved-report', task_id: plan.semantics.tasks.at(-1).task_id, digest: '7'.repeat(64), bytes: reportText.length, created_at: '2026-11-08', contentAccess: 'AUTHORIZED', content: reportText }], events: [], outcome: null } } });
        }
        return route.fulfill({ status: 404, json: { reasonCode: 'FIXTURE_ROUTE_NOT_DEFINED' } });
    });
    return state;
}
