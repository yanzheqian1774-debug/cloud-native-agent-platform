import type {ExecutionView} from '../api/preparedExecution';
import {artifactMatchesSource} from './artifactProvenance';
const object=(v:unknown):v is Record<string,unknown>=>Boolean(v)&&typeof v==='object'&&!Array.isArray(v);
export const ruleStatusLabels:Record<string,string>={SATISFIED:'满足',MISSING:'缺失',UNKNOWN:'待确认',CONFLICT:'冲突'};
export type RuleResult={scope:string;documentTitle:string;rulesDigest:string;sourceDigest:string;businessConclusion?:string;findings:{ruleCode:string;ruleName:string;status:string;field?:string|null;section?:string;evidence:{documentId:string;line:number;text:string}[]}[]};
export function documentRuleResult(value:unknown):RuleResult|null{
 if(!object(value)||value.schemaVersion!=='document-rule-result.v1'||typeof value.scope!=='string'||typeof value.documentTitle!=='string'||typeof value.rulesDigest!=='string'||typeof value.sourceDigest!=='string'||!Array.isArray(value.findings)||!value.findings.length)return null;
 if(!value.findings.every(f=>object(f)&&typeof f.ruleCode==='string'&&typeof f.ruleName==='string'&&typeof f.status==='string'&&Object.hasOwn(ruleStatusLabels,f.status)&&Array.isArray(f.evidence)&&f.evidence.every(e=>object(e)&&typeof e.documentId==='string'&&Number.isInteger(e.line)&&Number(e.line)>0&&typeof e.text==='string'))||new Set(value.findings.map(f=>f.ruleCode)).size!==value.findings.length)return null;
 return value as RuleResult;
}
export function ruleCounts(result:RuleResult){return Object.entries(ruleStatusLabels).map(([code,label])=>`${result.findings.filter(f=>f.status===code).length} 项${label}`).join(' · ')}
export function ruleBusinessConclusion(result:RuleResult){
 return result.findings.some(f=>f.status!=='SATISFIED')?'已识别需要处理的问题，现有结果不足以判定整体满足要求。':result.businessConclusion==='UNDETERMINED'?'现有结果不足以判定整体满足要求；业务结论尚无法确定。':'本次适用规则均已匹配，不代表整体业务要求或审批已经通过。';
}
export function ruleFindingsSummary(result:RuleResult){
 const issues=result.findings.filter(f=>f.status!=='SATISFIED').map(f=>{
  const subject=typeof f.field==='string'&&f.field?f.field:typeof f.section==='string'&&f.section?f.section:`检查项「${f.ruleName}」`;
  return f.status==='MISSING'?`${subject}缺失`:f.status==='CONFLICT'?`${subject}存在冲突`:`${subject}尚待确认`;
 });
 return issues.length?issues.join('；')+'。':'本次适用规则均已匹配；不代表技术验证或业务审批通过。';
}
export function reportRuleResult(view:ExecutionView){
 const artifacts=view.artifacts.filter(a=>artifactMatchesSource(a.content??'',view.preparation.source_snapshot));
 for(const a of artifacts){if(a.contentAccess!=='AUTHORIZED'||!a.content)continue;try{const v:unknown=JSON.parse(a.content);if(object(v)&&v.schemaVersion==='document-review-output.v1'&&v.operation==='RENDER_REPORT'&&object(v.documentReview)){const r=documentRuleResult(v.documentReview.ruleResult),b=v.documentReview.ruleBinding;if(r&&object(b)&&b.schema_version==='document-semantics-binding.v1'&&b.scope===r.scope&&object(b.ontology)&&typeof b.ontology.revision_id==='string'&&typeof b.ontology.digest==='string')return r}}catch{/* No substitute findings for unreadable artifacts. */}}
 return null;
}

export function documentBusinessSummary(view:ExecutionView){const r=reportRuleResult(view);return r?ruleFindingsSummary(r)+ruleBusinessConclusion(r):null}
