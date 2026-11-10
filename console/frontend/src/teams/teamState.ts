import type {SaveTeamCommand,TeamDetail,TeamRecord,WorkbenchSession} from '../api/digitalEmployees';
function canonical(v:unknown):string{
 if(typeof v==='string')return JSON.stringify(v.normalize('NFC'));
 if(v===null||typeof v==='number'||typeof v==='boolean')return JSON.stringify(v);
 if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';
 if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical((v as Record<string,unknown>)[k])).join(',')+'}';
 throw Error('团队内容尚未核实。');
}
export async function teamDigest(record:TeamRecord){const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(record)));return [...new Uint8Array(bytes)].map(x=>x.toString(16).padStart(2,'0')).join('')}
export function teamRecord(session:WorkbenchSession,c:SaveTeamCommand):TeamRecord{return {schemaVersion:'team-definition.v1',scope:{namespace:session.principal.tenantId,security_domain:session.principal.securityDomain},team_id:c.teamId,revision_id:c.revisionId,title:c.title,goal:c.goal,owner_id:c.ownerId,members:c.members.map(m=>({employee_definition_id:m.employeeDefinitionId,employee_revision_id:m.employeeRevisionId,employee_digest:m.employeeDigest,responsibility:m.responsibility,handoff:m.handoff})),predecessor_revision_id:c.predecessorRevisionId}}
export async function verifyTeam(session:WorkbenchSession,detail:TeamDetail,id:string,revision:string,expectedDigest?:string){const r=detail.revision;if(r.schemaVersion!=='team-definition.v1'||r.team_id!==id||r.revision_id!==revision||r.scope.namespace!==session.principal.tenantId||r.scope.security_domain!==session.principal.securityDomain||await teamDigest(r)!==detail.digest||(expectedDigest&&detail.digest!==expectedDigest)||!Number.isInteger(detail.aggregateVersion)||detail.aggregateVersion<1)throw Error('团队版本与读取依据不一致，请重新核对。');return detail}
