import type { Semantics } from "./api";

export const resourceKinds: Record<string, string> = {
  DIGITAL_EMPLOYEE: "数字员工", EMPLOYEE: "数字员工", EMPLOYEE_DEFINITION: "数字员工",
  SKILL: "Skill 技能", MCP: "MCP 工具", KNOWLEDGE: "知识", WORKFLOW: "工作流",
};

export function artifactLabel(id: string, plan: Semantics): string {
  const producer = plan.tasks.find(task => task.outputs.includes(id));
  // Preserve provided business labels; resolve opaque graph references without changing semantics.
  if (!/^A\d+\w*$/.test(id)) return id;
  return producer ? `${producer.title}结果` : "外部输入（名称待补充）";
}
