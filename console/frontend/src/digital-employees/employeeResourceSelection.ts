import type {EmployeeMember} from '../api/digitalEmployees';
export const employeeMemberKey=(member:EmployeeMember)=>JSON.stringify([member.kind,member.resourceId,member.revisionId,member.digest]);
export type EmployeeSelectionNames=Record<string,string>;
export const employeeMemberLabels:Record<EmployeeMember['kind'],string>={TOOL:'工具',AGENT:'执行职责',SKILL:'技能',MCP:'MCP连接',KNOWLEDGE:'知识与数据',WORKFLOW:'工作流',RUNTIME_PROFILE:'运行配置'};
