/** Display vocabulary only; API operation codes remain unchanged. */
export const capabilityLabels:Readonly<Record<string,string>>={READ_DATA:'读取资料',VALIDATE_DATA:'核对资料',SUMMARIZE:'汇总信息',ANALYZE_DATA:'分析变化',RENDER_REPORT:'形成报告'};
const skillOperations=new Set(['READ_DATA','VALIDATE_DATA','ANALYZE_DATA','RENDER_REPORT']);
export const skillOperationLabel=(code:string)=>skillOperations.has(code)?capabilityLabels[code]:code;
