// Summaries reflect stored values only; missing input is not reconstructed from a digest.
function summary(value:unknown,depth=0):string {
 if(value===null||value===undefined)return '未记录，无法从现有结果还原。';
 if(depth>=2&&typeof value==='object')return Array.isArray(value)?`${value.length} 项`:'已保存对象（见完整内容）';
 if(Array.isArray(value))return `${value.length} 项；${value.slice(0,3).map(v=>summary(v,depth+1)).join('；')}`;
 if(typeof value==='object'){const entries=Object.entries(value);return entries.length?entries.slice(0,5).map(([key,v])=>`${key}：${summary(v,depth+1)}`).join('；')+(entries.length>5?'；其余字段见完整内容':''):'已记录空对象';}
 const text=String(value);return text.length>160?text.slice(0,160)+'…':text;
}
export function SavedTestSummary({label,value}:{label:string;value:unknown}) {
 return <section className="rm-saved-test-summary" aria-label={label}><h4>{label}</h4><p>{summary(value)}</p>{value!==undefined&&value!==null&&<details><summary>完整{label}</summary><pre>{JSON.stringify(value,null,2)}</pre></details>}</section>;
}
