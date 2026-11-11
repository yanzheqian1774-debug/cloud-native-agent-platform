type Scalar=string|number|boolean|null;
const scalar=(value:unknown):value is Scalar=>value===null||['string','number','boolean'].includes(typeof value);
const display=(value:Scalar)=>value===null?'未填写':typeof value==='boolean'?(value?'是':'否'):String(value);
const labels:Record<string,string>={schemaVersion:'资料格式',synthetic:'合成测试资料',periods:'期间',metric:'指标标识',products:'产品',source:'来源数据',rows:'数据记录',values:'记录字段',rowId:'记录编号',period:'期间',channel:'渠道',product:'产品',region:'区域',currency:'币种',netSales:'净销售额',cost:'成本',kind:'类型',status:'状态',provenance:'出处依据',sourceLine:'来源行号',source_line:'来源行号',snapshotDigest:'快照摘要',sourceBytesSha256:'原文摘要',sourceId:'来源标识',format:'保存格式',columnMapping:'字段映射',sourceSnapshot:'来源版本依据',title:'标题',name:'名称',description:'说明',documents:'文档',items:'条目'};
const label=(key:string)=>labels[key]??key;
function Value({value,depth=0}:{value:unknown;depth?:number}){
 if(scalar(value))return <span>{display(value)}</span>;
 if(depth>=5)return <p>更深层内容可在下方保存原文中核对。</p>;
 if(Array.isArray(value)){
  if(!value.length)return <p>空列表</p>;
  const rows=value.slice(0,50);
  const paths=(r:unknown,prefix:string[]=[]):string[][]|null=>{if(!r||typeof r!=='object'||Array.isArray(r))return null;const result:string[][]=[];for(const [k,v] of Object.entries(r)){if(scalar(v))result.push([...prefix,k]);else if(prefix.length<1){const nested=paths(v,[...prefix,k]);if(!nested)return null;result.push(...nested)}else return null}return result};
  const all=rows.map(r=>paths(r));
  if(all.every(p=>p!==null)){const keys=[...new Set(all.flatMap(p=>p!.map(k=>JSON.stringify(k))))];if(keys.length<=24)return <><p>共 {value.length} 条{value.length>50?'，当前显示前 50 条':''}</p><div className="knowledge-document-table"><table><thead><tr>{keys.map(k=><th key={k}>{(()=>{const path=JSON.parse(k) as string[];return path.length===2&&path[0]==='values'&&!keys.includes(JSON.stringify([path[1]]))?label(path[1]):path.map(label).join(' / ')})()}</th>)}</tr></thead><tbody>{rows.map((r,i)=><tr key={i}>{keys.map(k=>{const v=(JSON.parse(k) as string[]).reduce<unknown>((current,key)=>current&&typeof current==='object'&&Object.hasOwn(current,key)?(current as Record<string,unknown>)[key]:undefined,r);return <td key={k}>{scalar(v)?display(v):'未提供'}</td>})}</tr>)}</tbody></table></div></>}
  return <><p>共 {value.length} 条{value.length>50?'，当前显示前 50 条':''}</p><ol>{rows.map((v,i)=><li key={i}><Value value={v} depth={depth+1}/></li>)}</ol></>;
 }
 if(value&&typeof value==='object'){
  const metadata=new Set(['schemaVersion','provenance','sourceSnapshot','columnMapping','format','snapshotDigest','sourceBytesSha256','sourceId']),entries=Object.entries(value);
  if(!entries.length)return <p>空对象</p>;
  const fields=(items:[string,unknown][])=> <dl className="knowledge-structured-fields">{items.map(([k,v])=><div key={k}><dt>{label(k)}</dt><dd><Value value={v} depth={depth+1}/></dd></div>)}</dl>;
  const regular=entries.filter(([k])=>!metadata.has(k)),technical=entries.filter(([k])=>metadata.has(k));
  return <>{fields(regular)}{technical.length>0&&<details><summary>保存格式与版本依据</summary>{fields(technical)}</details>}</>;
 }
 return <span>未提供</span>;
}
export function StructuredKnowledgePreview({value}:{value:unknown}){return <section aria-label="结构化资料预览"><h3>结构化资料</h3><p>以下按保存字段展示，不代表已完成分析或核验。</p><Value value={value}/></section>}
