import {NativeLoopTrace,type NativeLoopResult} from './NativeLoopTrace';
import {RememberedDetails} from './RememberedDetails';
import './DocumentArtifactView.css';
type Line={line:number;text:string};
type Finding={section:string;status:string;requirement:{documentId:string;line:number;text:string;body:Line[]};evidence:null|{documentId:string;line:number;heading:string;body:Line[]}};
type Review={scope:string;findings:Finding[];missingSections:string[];incompleteSections:string[]};
const object=(v:unknown):v is Record<string,unknown>=>Boolean(v)&&typeof v==='object'&&!Array.isArray(v);
const lines=(v:unknown)=>Array.isArray(v)&&v.every(l=>object(l)&&Number.isInteger(l.line)&&Number(l.line)>0&&typeof l.text==='string');
function valid(v:unknown):v is Review{
 if(!object(v)||typeof v.scope!=='string'||!Array.isArray(v.findings)||!Array.isArray(v.missingSections)||!Array.isArray(v.incompleteSections)||![...v.missingSections,...v.incompleteSections].every(s=>typeof s==='string'))return false;
 return v.findings.every(f=>object(f)&&typeof f.section==='string'&&typeof f.status==='string'&&object(f.requirement)&&typeof f.requirement.documentId==='string'&&Number.isInteger(f.requirement.line)&&Number(f.requirement.line)>0&&typeof f.requirement.text==='string'&&lines(f.requirement.body)&&(f.evidence===null||(object(f.evidence)&&typeof f.evidence.documentId==='string'&&Number.isInteger(f.evidence.line)&&Number(f.evidence.line)>0&&typeof f.evidence.heading==='string'&&lines(f.evidence.body))));
}
function FindingView({finding:f,viewKey}:{finding:Finding;viewKey?:string}){
 const label=f.status==='MISSING'?'缺失':f.status==='INCOMPLETE'?'待补充':f.status==='PRESENT_NOT_VALIDATED'?'已提供，正确性待核验':'检查状态待核实';
 return <article className="document-finding"><header><h4>{f.section}</h4><span className={f.status==='MISSING'||f.status==='INCOMPLETE'?'document-warning':'document-status'}>{label}</span></header><p>{f.requirement.body.map(l=>l.text).join(' ')||f.requirement.text}</p><RememberedDetails key={viewKey+f.section} viewKey={viewKey} name={'finding:'+f.section} summary={f.evidence?'对照原文与规范':'查看规范与核查范围'} className="document-citation"><h5>规范依据</h5><p>{f.requirement.documentId} · 第 {f.requirement.line} 行：{f.requirement.text}</p>{f.requirement.body.map(l=><p key={l.line}>第 {l.line} 行：{l.text}</p>)}<h5>提交文档</h5>{f.evidence?<><p>{f.evidence.documentId} · 第 {f.evidence.line} 行：{f.evidence.heading}</p><blockquote>{f.evidence.body.map(l=><p key={l.line}>第 {l.line} 行：{l.text}</p>)}</blockquote></>:<p>{f.status==='MISSING'?'已核对完整提交文档，未找到此标题；没有可引用的缺失原文。':'原记录未提供对应原文，不据此认定该章节缺失。'}</p>}</RememberedDetails></article>;
}
export function DocumentArtifactView({content,viewKey}:{content:string;viewKey?:string}){
 let value:{nativeLoop?:NativeLoopResult;documentReview?:unknown};try{value=JSON.parse(content)}catch{return <p role="alert">文档检查结果暂不可读。</p>}
 if(!object(value))return <p role="alert">文档检查结果暂不可读。</p>;
 const r=value.documentReview;if(!r)return <p>文档已读取或校验，尚未形成最终检查结果。</p>;
 if(!valid(r))return <p role="alert">文档检查结果格式尚未核实，未生成替代结论。</p>;
 if(!r.findings.length)return <p>未取得可核对的章节记录，尚不能给出完整性结论。</p>;
 if(new Set(r.findings.map(f=>f.section)).size!==r.findings.length)return <p role="alert">章节记录存在重复，检查结论尚待核实。</p>;
 const missing=r.findings.filter(f=>f.status==='MISSING'),incomplete=r.findings.filter(f=>f.status==='INCOMPLETE'),provided=r.findings.filter(f=>f.status==='PRESENT_NOT_VALIDATED'),unknown=r.findings.filter(f=>!['MISSING','INCOMPLETE','PRESENT_NOT_VALIDATED'].includes(f.status));
 const consistent=JSON.stringify(missing.map(f=>f.section).sort())===JSON.stringify([...r.missingSections].sort())&&JSON.stringify(incomplete.map(f=>f.section).sort())===JSON.stringify([...r.incompleteSections].sort());
 if(!consistent)return <p role="alert">文档检查汇总与逐项记录不一致，请核对原报告。</p>;
 return <section aria-label="文档检查结果" className="document-business-result"><p className="document-eyebrow">检查结论 · 材料完整性</p><h3>结果摘要</h3><p className="document-lead">{missing.length?`缺少${missing.map(f=>f.section).join('、')}。`:''}{incomplete.length?`${incomplete.map(f=>f.section).join('、')}尚未补全。`:''}{!missing.length&&!incomplete.length?(unknown.length?'部分检查状态尚待核实。':'本次检查未发现缺失或待补充章节。'):''}</p><p>按已确认的{r.scope}规范检查。缺失 {missing.length} 项，待补充 {incomplete.length} 项。</p>{[...missing,...incomplete,...unknown].map(f=><FindingView key={f.section} finding={f} viewKey={viewKey}/>)}{provided.length>0&&<RememberedDetails key={viewKey+':provided'} viewKey={viewKey} name="provided" className="document-provided" summary={`另有 ${provided.length} 项已提供：${provided.map(f=>f.section).join('、')}`}><p>文本已提供，不代表技术正确或审核通过。</p>{provided.map(f=><FindingView key={f.section} finding={f} viewKey={viewKey}/>)}</RememberedDetails>}<p className="document-limitation">检查完成不等于批准上线，也不代表技术验证通过。</p>{value.nativeLoop&&Array.isArray(value.nativeLoop.trace)&&<RememberedDetails key={viewKey+':trace'} viewKey={viewKey} name="trace" className="document-trace" summary="查看执行过程与核验记录"><NativeLoopTrace loop={value.nativeLoop}/></RememberedDetails>}</section>;
}
