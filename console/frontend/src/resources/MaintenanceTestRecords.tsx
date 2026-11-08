import type {SkillMcpResource} from '../api/skillMcpResources';
import {formatTime} from '../journey/formatTime';
type Test={resultId:string;revisionId:string;revisionDigest:string;operation?:string;caseName?:string;status:string;actualExecution?:boolean;verificationLevel?:string;recordedAt?:string};
export function MaintenanceTestRecords({resource,onInspect}:{resource:SkillMcpResource;onInspect?:(id:string)=>void}){
 if(resource.kind!=='skill')return null;
 const rows=((resource.testResults??[]) as unknown as Test[]).filter(t=>t.actualExecution===true&&t.verificationLevel==='ISOLATED_SYNTHETIC_EXECUTOR'&&resource.revisions.some(r=>r.revisionId===t.revisionId&&r.digest===t.revisionDigest));
 return <article className="rd-card" aria-label="维护测试使用记录"><h2>维护测试记录</h2><p>这些是平台保存的实际维护测试，使用明确的合成测试输入；与业务调用、Run和真实销售结果分别记录。</p>{rows.length?<div className="rd-table-scroll"><table><thead><tr><th>操作与用例</th><th>准确修订</th><th>结果</th><th>记录</th></tr></thead><tbody>{[...rows].reverse().map(t=><tr key={t.resultId}><td>{t.operation} · {t.caseName}</td><td>{t.revisionId===resource.publishedRevisionId?'当前发布修订':t.revisionId===resource.currentDraftRevisionId?'当前草稿':'历史修订'}<small>{t.revisionId}</small></td><td>{t.status==='PASSED'?'通过':t.status==='FAILED'?'未通过':'未确认'}</td><td>{t.recordedAt&&<span>{formatTime(t.recordedAt)}</span>}{onInspect&&<button type="button" onClick={()=>onInspect(t.resultId)}>查看维护测试结果</button>}</td></tr>)}</tbody></table></div>:<p>当前没有读回可核对的实际维护测试记录。</p>}</article>;
}
