export type KnowledgeTimeDetail = "list" | "detail";

export type KnowledgeTimePresentation = {
  display: string;
  raw: string | null;
  timeZone: string | null;
  valid: boolean;
};

const explicitZone = /(Z|[+-]\d{2}:\d{2})$/;

export function knowledgeTime(
  value: string | null | undefined,
  detail: KnowledgeTimeDetail,
  configuredTimeZone?: string,
): KnowledgeTimePresentation {
  if (!value) return {display:"未记录",raw:null,timeZone:null,valid:false};
  if (!explicitZone.test(value)) {
    return {display:"时间含义不明确",raw:value,timeZone:null,valid:false};
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return {display:"时间格式无效",raw:value,timeZone:null,valid:false};
  }
  const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const timeZone = configuredTimeZone || browserZone;
  try {
    const display = new Intl.DateTimeFormat("zh-CN", {
      timeZone,
      year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",
      ...(detail === "detail" ? {second:"2-digit",timeZoneName:"short"} : {}),
      hour12:false,
    }).format(parsed).replaceAll("/","-");
    return {display,raw:value,timeZone,valid:true};
  } catch {
    return {display:"时区配置无效",raw:value,timeZone:null,valid:false};
  }
}

export function knowledgeLocation(location?: {pageNumber?:number;paragraphNumber?:number}): string {
  if (!location) return "片段位置未由解析器提供";
  const values = [];
  if (location.pageNumber) values.push(`第 ${location.pageNumber} 页`);
  if (location.paragraphNumber) values.push(`第 ${location.paragraphNumber} 段`);
  return values.length ? values.join(" · ") : "片段位置未由解析器提供";
}
