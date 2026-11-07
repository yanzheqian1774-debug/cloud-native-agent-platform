import {expect,test} from '@playwright/test';

test('legacy resource profile keeps original Agent and Knowledge member destinations',async({page})=>{
 const principal={principalId:'human:legacy-definition-fixture',tenantId:'legacy-fixture',securityDomain:'isolated'};
 const employee={resourceKind:'DIGITAL_EMPLOYEE_DEFINITION',employeeDefinitionId:'employee:legacy',employeeDefinitionRevisionId:'employee-rev:legacy',employeeDefinitionDigest:'a'.repeat(64),aggregateVersion:1,role:'旧配置引用员工',responsibilities:['保留原入口'],publicationState:'PUBLISHED',lifecycleState:'PUBLISHED',members:[{kind:'AGENT',resourceId:'agent:legacy',revisionId:'agent-rev:legacy',digest:'b'.repeat(64)},{kind:'KNOWLEDGE',resourceId:'knowledge:legacy',revisionId:'knowledge-rev:legacy',digest:'c'.repeat(64)}]};
 await page.route('**/api/workbench/v1/**',async route=>{const path=new URL(route.request().url()).pathname;if(path.endsWith('/session'))return route.fulfill({json:{principal,session:{expiresAt:'2099-01-01',idleExpiresAt:'2099-01-01'},csrfToken:'fixture-only'}});const result=path.endsWith('/employees')?{items:[employee]}:path.includes('/employees/')?employee:path.includes('/agents/')?{definitionId:'agent:legacy',revisionId:'agent-rev:legacy',digest:'b'.repeat(64),name:'原Agent',role:{title:'核对员',duties:['保留原入口'],capabilities:['READ_DATA'],businessPurpose:'兼容核验'}}:null;return result?route.fulfill({json:{schemaVersion:'workbench-operation.v1',result,continuationIds:[]}}):route.fulfill({status:404,json:{reasonCode:'FIXTURE_ONLY'}})});
 await page.goto('/employees?employeeDefinitionId=employee%3Alegacy&employeeDefinitionRevisionId=employee-rev%3Alegacy&detail=1&section=capabilities');
 await expect(page.getByRole('heading',{name:'旧配置引用员工',exact:true})).toBeVisible();
 await expect(page.getByRole('link',{name:'agent:legacy',exact:true})).toHaveAttribute('href','/catalog?kind=AGENT&query=agent%3Alegacy');
 await expect(page.getByRole('link',{name:'knowledge:legacy',exact:true})).toHaveAttribute('href','/catalog?kind=KNOWLEDGE&query=knowledge%3Alegacy');
});
