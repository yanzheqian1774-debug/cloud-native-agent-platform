import type {EmployeeCreateCommand,EmployeeDefinition,EmployeeCommandResult,WorkbenchSession} from '../api/digitalEmployees';

function canonical(value:unknown):string{
 if(typeof value==='string')return JSON.stringify(value.normalize('NFC'));
 if(value===null||typeof value==='boolean'||typeof value==='number')return JSON.stringify(value);
 if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
 if(typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical((value as Record<string,unknown>)[k])).join(',')+'}';
 throw Error('EMPLOYEE_SUCCESSOR_CONTENT_INVALID');
}
export async function successorDigest(session:WorkbenchSession,command:EmployeeCreateCommand){
 const record={schemaVersion:'digital-employee-composition.v1',namespace:session.principal.tenantId,securityDomain:session.principal.securityDomain,definitionId:command.employeeDefinitionId,revisionId:command.employeeDefinitionRevisionId,role:command.role,responsibilities:command.responsibilities,members:[...command.members].sort((a,b)=>a.kind<b.kind?-1:a.kind>b.kind?1:a.resourceId<b.resourceId?-1:a.resourceId>b.resourceId?1:0).map(m=>({kind:m.kind,resource_id:m.resourceId,revision_id:m.revisionId,digest:m.digest})),predecessorRevisionId:command.predecessorEmployeeRevisionId??null};
 const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(record)));return [...new Uint8Array(bytes)].map(v=>v.toString(16).padStart(2,'0')).join('');
}
export function verifySuccessor(value:EmployeeDefinition|EmployeeCommandResult,command:EmployeeCreateCommand,digest:string){
 if(value.resourceKind!=='DIGITAL_EMPLOYEE_DEFINITION'||value.employeeDefinitionId!==command.employeeDefinitionId||value.employeeDefinitionRevisionId!==command.employeeDefinitionRevisionId||value.employeeDefinitionDigest!==digest||!Number.isInteger(value.aggregateVersion)||(value.aggregateVersion??0)<command.expectedVersion+1)throw Error('EMPLOYEE_SUCCESSOR_RECEIPT_MISMATCH');
 if('members'in value){
  const sorted=(xs:EmployeeCreateCommand['members'])=>[...xs].sort((a,b)=>canonical(a).localeCompare(canonical(b)));
  if(value.role!==command.role||canonical(value.responsibilities)!==canonical(command.responsibilities)||canonical(sorted(value.members))!==canonical(sorted(command.members)))throw Error('EMPLOYEE_SUCCESSOR_CONTENT_MISMATCH');
 }
}
