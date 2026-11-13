export function ontologyError(error: unknown): string {
  if (error instanceof SyntaxError) return "文件不是有效的JSON，请检查文件内容。原有内容未更改。";
  const code = error instanceof Error ? error.message : String(error);
  const messages: Record<string, string> = {
    ONTOLOGY_INDEPENDENT_REVIEW_REQUIRED: "编制人不能审核自己的修订，请由另一位有权限的审核人处理。",
    AUTHORIZATION_NOT_FOUND: "当前账号没有此操作权限，请联系权限管理员。",
    ONTOLOGY_VERSION_CONFLICT: "业务定义已有更新，请重新读取后再操作。",
    ONTOLOGY_NOT_FOUND: "当前业务定义或修订不存在，或不可见。",
    ONTOLOGY_PUBLISHED_VERSION_REQUIRED: "该修订尚未发布或已废弃，不能用于新的执行。",
  };
  return messages[code] ?? (/^[A-Z][A-Z0-9_]+$/.test(code) ? "操作未完成，请展开技术信息核对原因：" + code : code);
}

const dimensions: Record<string, string> = { region: "区域", channel: "渠道", product: "产品" };
export function dimensionName(value: string) { return dimensions[value] ?? value; }
export function reportTitle(name: string, values: Record<string, string> | undefined) {
  const names = Object.keys(values ?? {}).map(dimensionName);
  return name + (names.length ? " · 按" + names.join(" / ") : " · 按币种汇总");
}
export function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
export function validateOntologyImport(value: unknown) {
  if (isRecord(value) && value.schema_version === "business-document-rules.v1") {
    if (typeof value.name !== "string" || !value.name.trim() ||
        typeof value.business_owner !== "string" || typeof value.data_owner !== "string" ||
        typeof value.scope !== "string" || !value.scope.trim() || value.synthetic !== true ||
        !Array.isArray(value.mappings) || value.mappings.length !== 1 ||
        !Array.isArray(value.actions) || !value.actions.length ||
        !Array.isArray(value.rules) || !value.rules.length || value.rules.length > 32 ||
        value.rules.some(r => !isRecord(r) || typeof r.code !== "string" || typeof r.name !== "string" ||
          typeof r.section !== "string" || !r.section.trim() ||
          !["REQUIRED_SECTION", "SINGLE_VALUE_FIELD"].includes(String(r.kind)) ||
          (r.kind === "SINGLE_VALUE_FIELD" && (typeof r.field !== "string" || !r.field.trim())))) {
      throw new Error("文档规则包格式不完整，请核对名称、负责人、范围、规则与来源。原有内容未更改。");
    }
    return;
  }
  if (isRecord(value) && value.schema_version !== undefined && value.schema_version !== "business-ontology.v1") {
    throw new Error("暂不支持此业务定义格式，请核对文件版本。原有内容未更改。");
  }
  if (!isRecord(value) || typeof value.name !== "string" || !value.name.trim() ||
      typeof value.business_owner !== "string" || typeof value.data_owner !== "string" ||
      !isRecord(value.rules) || !Array.isArray(value.rules.included_kinds) ||
      value.rules.included_kinds.some(k => k !== "SALE" && k !== "RETURN") ||
      !Array.isArray(value.metrics) || !value.metrics.length ||
      value.metrics.some(m => !isRecord(m) || typeof m.code !== "string" || typeof m.name !== "string") ||
      !Array.isArray(value.objects) || !value.objects.length ||
      !Array.isArray(value.mappings) || !value.mappings.length) {
    throw new Error("定义包格式不完整，请提供业务名称、负责人、规则、指标、对象与来源映射。原有内容未更改。");
  }
}
export function validateDraftImport(value: unknown, identity: string, revision: string) {
  if (!isRecord(value) || !isRecord(value.business_semantics) ||
      !isRecord(value.business_semantics.ontology) || !Array.isArray(value.business_semantics.queries) ||
      !value.business_semantics.queries.length || !isRecord(value.semantics) ||
      typeof value.semantics.title !== "string" || !Array.isArray(value.semantics.boundaries) ||
      value.business_semantics.queries.some(q => !isRecord(q) || typeof q.metric !== "string" || !Array.isArray(q.dimensions))) {
    throw new Error("方案包格式不完整，请提供业务口径、指标查询和任务边界。原有方案未更改。");
  }
  if (value.business_semantics.ontology.resource_id !== identity || value.business_semantics.ontology.revision_id !== revision) {
    throw new Error("方案包与当前口径版本不一致，请选择相应修订后重新导入。");
  }
}

export function ontologyRevisionLabel(revision:string):string{if(revision.length<=28)return revision;const value=revision.startsWith('managed-')?revision.slice(8):revision;return `${value.slice(0,8)}…${value.slice(-8)}`;}
