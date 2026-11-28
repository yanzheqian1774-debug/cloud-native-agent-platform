import {skillOperationLabel} from './capabilityLabels';
import {formatTime} from '../journey/formatTime';

type Basis={schemaVersion:'resource-version-basis.v1';revisionId:string;revisionDigest:string;executionAuthority:'NONE';businessAcceptance:'NOT_ESTABLISHED';tests:{scope:'ISOLATED_SYNTHETIC_ONLY_NOT_BUSINESS_ACCEPTANCE';ready:boolean;operations:{operation:string;passed:boolean;caseCount:number}[]};publication:{recorded:boolean;publishedAt:string|null;basisType:'POLICY'|'HUMAN'|'UNKNOWN'}};
const object=(value:unknown):Record<string,unknown>|null=>value!==null&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:null;
function verified(value:unknown,revision:string,digest:string):Basis|null{
 const b=object(value),tests=object(b?.tests),publication=object(b?.publication);
 if(!b||b.schemaVersion!=='resource-version-basis.v1'||b.revisionId!==revision||b.revisionDigest!==digest||b.executionAuthority!=='NONE'||b.businessAcceptance!=='NOT_ESTABLISHED'||tests?.scope!=='ISOLATED_SYNTHETIC_ONLY_NOT_BUSINESS_ACCEPTANCE'||typeof tests.ready!=='boolean'||!Array.isArray(tests.operations)||!publication||typeof publication.recorded!=='boolean'||!['POLICY','HUMAN','UNKNOWN'].includes(String(publication.basisType))||(publication.publishedAt!==null&&(typeof publication.publishedAt!=='string'||!Number.isFinite(Date.parse(publication.publishedAt)))))return null;
 const rows=tests.operations;
 if(rows.some(value=>{const row=object(value);return !row||typeof row.operation!=='string'||typeof row.passed!=='boolean'||!Number.isInteger(row.caseCount)||Number(row.caseCount)<0}))return null;
 if(tests.ready&&(!rows.length||rows.some(row=>!row.passed||row.caseCount===0)))return null;
 return value as Basis;
}
export function ResourceVersionBasis({value,revision,digest}:{value:unknown;revision:string;digest:string}){
 const basis=verified(value,revision,digest);
 if(!basis)return <><h2>测试与发布依据</h2><p>当前读取接口未返回本版本测试与发布校验回执，无法据此判断测试是否通过或当前是否可执行。历史成功不代表当前执行授权。</p></>;
 const operations=basis.tests.operations,hasResults=operations.some(row=>row.caseCount>0);
 return <><h2>测试与发布依据</h2><p>{basis.tests.ready?'本版本合成契约测试通过。':hasResults?'本版本合成契约测试尚未全部通过。':'本版本未记录合成契约测试结果。'}</p>{hasResults&&<ul>{operations.map(row=><li key={row.operation}>{skillOperationLabel(row.operation)}：{row.caseCount?`${row.caseCount} 项${row.passed?'通过':'尚未全部通过核验'}`:'未覆盖'}</li>)}</ul>}{hasResults&&<details><summary>查看操作代码</summary><ul>{operations.map(row=><li key={row.operation}><code>{row.operation}</code></li>)}</ul></details>}<p>{basis.publication.recorded?`本版本已发布${basis.publication.publishedAt?'，时间：'+formatTime(basis.publication.publishedAt):'，时间未记录'}；${basis.publication.basisType==='POLICY'?'依据资源策略发布':basis.publication.basisType==='HUMAN'?'依据人工核阅发布':'发布依据类型尚未核实'}。`:'本版本未读回发布记录。'}</p><p>合成契约测试与发布记录不代表业务成果已接受，也不授予当前执行权限。</p></>;
}
