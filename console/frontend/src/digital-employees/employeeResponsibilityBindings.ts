import type {EmployeeMember,ResponsibilityBinding} from '../api/digitalEmployees';
export const exactMemberKey=(m:EmployeeMember)=>JSON.stringify([m.kind,m.resourceId,m.revisionId,m.digest]);
export const bindingKey=(b:ResponsibilityBinding)=>JSON.stringify([b.responsibility,exactMemberKey(b.member)]);
export const validResponsibilityBinding=(b:ResponsibilityBinding,duties:string[],members:EmployeeMember[])=>duties.filter(d=>d===b.responsibility).length===1&&members.some(m=>exactMemberKey(m)===exactMemberKey(b.member));
