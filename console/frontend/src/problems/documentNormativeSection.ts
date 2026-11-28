/** Display anchors from one saved artifact, never a published rule-to-clause proof. */
import {documentRuleResult} from './documentRuleSummary';
export type NormativeSection={documentId:string;documentTitle:string;headingLine:number;lines:{line:number;text:string}[]};
const object=(v:unknown):v is Record<string,unknown>=>Boolean(v)&&typeof v==='object'&&!Array.isArray(v);
const reference=(v:unknown)=>object(v)&&typeof v.resource_id==='string'&&Boolean(v.resource_id)&&typeof v.revision_id==='string'&&Boolean(v.revision_id)&&typeof v.digest==='string'&&/^[a-f0-9]{64}$/.test(v.digest);
const sameReference=(a:unknown,b:unknown)=>reference(a)&&reference(b)&&object(a)&&object(b)&&a.resource_id===b.resource_id&&a.revision_id===b.revision_id&&a.digest===b.digest;

export function documentNormativeSections(artifact:unknown):ReadonlyMap<string,NormativeSection>{
 const none=new Map<string,NormativeSection>();
 if(!object(artifact)||artifact.schemaVersion!=='document-review-output.v1'||!['ANALYZE_DATA','RENDER_REPORT'].includes(String(artifact.operation))||!object(artifact.documentReview)||!object(artifact.source))return none;
 const review=artifact.documentReview,result=documentRuleResult(review.ruleResult),binding=review.ruleBinding,source=artifact.source;
 if(!result||!object(binding)||binding.schema_version!=='document-semantics-binding.v1'||!reference(binding.ontology)||binding.scope!==result.scope||review.scope!==result.scope||!sameReference(artifact.sourceSnapshot,review.sourceSnapshot)||!sameReference(artifact.sourceSnapshot,binding.source)||source.schemaVersion!=='document-review-source.v1'||source.synthetic!==true||!Array.isArray(source.documents)||source.documents.length<2||source.documents.length>16)return none;
 const documents=source.documents;
 if(!documents.every(d=>object(d)&&typeof d.id==='string'&&Boolean(d.id)&&typeof d.title==='string'&&Boolean(d.title)&&typeof d.text==='string'&&d.text.length<=1048576&&['SUBMISSION','POLICY'].includes(String(d.role)))||new Set(documents.map(d=>d.id)).size!==documents.length)return none;
 const policies=documents.filter(d=>d.role==='POLICY');
 if(policies.some(d=>typeof d.scope!=='string'||!d.scope)||new Set(policies.map(d=>d.scope)).size!==policies.length)return none;
 const policy=policies.find(d=>d.id===review.policyId&&d.scope===result.scope);
 if(!policy||!documents.some(d=>d.role==='SUBMISSION'&&d.id===review.documentId))return none;
 const sections=new Map<string,NormativeSection[]>();
 let current:NormativeSection|undefined,fence:string|undefined;
 const originalLines=(policy.text as string).split(/\r\n|\n|\r/);
 if(originalLines.at(-1)==='')originalLines.pop();
 for(const [index,text] of originalLines.entries()){
  const marker=/^ {0,3}(`{3,}|~{3,})/.exec(text);
  if(marker){if(!fence)fence=marker[1];else if(marker[1][0]===fence[0]&&marker[1].length>=fence.length&&/^ {0,3}(`+|~+)\s*$/.test(text))fence=undefined;if(current)current.lines.push({line:index+1,text});continue;}
  if(!fence){
   const heading=/^##\s+(.+?)\s*$/.exec(text);
   if(heading){current={documentId:policy.id as string,documentTitle:policy.title as string,headingLine:index+1,lines:[{line:index+1,text}]};sections.set(heading[1],[...(sections.get(heading[1])??[]),current]);continue;}
   if(/^#\s+/.test(text))current=undefined;
  }
  if(current)current.lines.push({line:index+1,text});
 }
 const projected=new Map<string,NormativeSection>();
 for(const finding of result.findings){
  if(typeof finding.section!=='string'||!finding.section||finding.section.trim()!==finding.section)continue;
  const matches=sections.get(finding.section);
  if(matches?.length===1&&matches[0].lines.some(l=>l.line>matches[0].headingLine&&l.text.trim()))projected.set(finding.ruleCode,matches[0]);
 }
 return projected;
}
