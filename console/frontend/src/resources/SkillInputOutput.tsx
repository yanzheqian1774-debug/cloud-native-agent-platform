import {useSearchParams} from 'react-router-dom';
import type {ResourceRevision,SkillMcpResource} from '../api/skillMcpResources';
import {ResourceVersionImpact} from './ResourceVersionImpact';
import './SkillInputOutput.css';

const record=(x:unknown):x is Record<string,unknown>=>!!x&&typeof x==='object'&&!Array.isArray(x);
const names:Record<string,string>={string:'文本',number:'数值',integer:'整数',boolean:'布尔值',object:'对象',array:'列表',null:'空值'};
const operationNames:Record<string,string>={READ_DATA:'读取数据',VALIDATE_DATA:'校验数据',CLASSIFY_OVERDUE:'逾期分类',SUMMARIZE:'汇总',ANALYZE_DATA:'分析',RECOMMEND:'核查建议',RENDER_REPORT:'生成报告'};
const pointer=(s:string)=>s.replace(/~/g,'~0').replace(/\//g,'~1');
const short=(x:unknown)=>{const s=JSON.stringify(x);return s&&s.length>120?s.slice(0,120)+'…（完整声明见原始契约）':s??'未声明'};
const declared=(x:unknown)=>typeof x==='string'&&x.length?x:'未声明';
function types(s:Record<string,unknown>){const t=Array.isArray(s.type)?s.type:typeof s.type==='string'?[s.type]:[];return t.length?t.map(x=>typeof x==='string'?(names[x]??x):'未识别类型').join(' / '):'未声明'}
function matches(value:unknown,type:unknown){return type==='null'?value===null:type==='object'?record(value):type==='array'?Array.isArray(value):type==='integer'?typeof value==='number'&&Number.isInteger(value):type==='number'?typeof value==='number':type==='string'?typeof value==='string':type==='boolean'?typeof value==='boolean':true}
function checks(s:Record<string,unknown>){const rows:string[]=[];if('const'in s)rows.push('固定值：'+short(s.const));if(Array.isArray(s.enum))rows.push('允许值：'+short(s.enum));for(const [k,label]of Object.entries({minimum:'最小值',maximum:'最大值',exclusiveMinimum:'大于',exclusiveMaximum:'小于',multipleOf:'倍数',minLength:'最短长度',maxLength:'最长长度',pattern:'模式',format:'格式声明（未验证）',minItems:'最少项数',maxItems:'最多项数',uniqueItems:'项目唯一',minProperties:'最少字段数',maxProperties:'最多字段数'}))if(k in s)rows.push(label+'：'+short(s[k]));if(s.additionalProperties===false)rows.push('不接受未声明字段');if(s.additionalProperties===true)rows.push('允许额外字段');return rows}
type Field={path:string;schemaPath:string;schema:unknown;required:boolean};
function project(schema:unknown){
 const fields:Field[]=[],notes=new Set<string>(),conflicts=new Set<string>();
 function visit(s:unknown,path:string,schemaPath:string,depth:number){
  if(!record(s))return;
  for(const key of ['$ref','oneOf','anyOf','allOf','not','if','then','else','dependentSchemas','patternProperties','unevaluatedProperties','prefixItems'])if(key in s)notes.add('含 '+key+'，字段表未完整解释；请核对原始契约。');
  const opaque=['$ref','oneOf','anyOf','allOf','not','if','then','else','patternProperties'].some(k=>k in s);
  const ts=Array.isArray(s.type)?s.type:typeof s.type==='string'?[s.type]:[];
  if(!opaque&&ts.length&&'const'in s&&!ts.some(t=>matches(s.const,t)))conflicts.add('固定值与明确声明的类型不一致：'+(path||'根值'));
  if(!opaque&&ts.length&&Array.isArray(s.enum)&&s.enum.length>0&&!s.enum.some(v=>ts.some(t=>matches(v,t))))conflicts.add('允许值中没有符合明确类型的值：'+(path||'根值'));
  if(ts.length>1&&(s.required||s.properties))notes.add('类型含其他分支；表中对象字段和必填约束仅适用于对象值，其他分支见原始契约。');
  if(s.items)notes.add('字段路径中的 /* 表示列表中的每一项，来源位置仍指向实际契约。');
  if(s.additionalProperties!==undefined&&typeof s.additionalProperties!=='boolean')notes.add('额外字段有独立契约，字段表未完整解释。');
  if(depth>=4){if(s.properties||s.items)notes.add('嵌套深度超过4层，后续字段请核对原始契约。');return}
  const props=record(s.properties)?s.properties:{},required=Array.isArray(s.required)?s.required.filter((x):x is string=>typeof x==='string'):[];
  if(s.required!==undefined&&(!Array.isArray(s.required)||s.required.some(x=>typeof x!=='string')))notes.add('必填列表结构未能完整读取，请核对原始契约。');
  if(s.properties!==undefined&&!record(s.properties))notes.add('properties不是可读取的字段对象。');
  if(ts.length&&!ts.includes('object')&&Object.keys(props).length)notes.add('此处声明为非对象类型，其对象字段约束不能当作该类型的实际字段。');
  for(const name of [...Object.keys(props),...required.filter(x=>!Object.hasOwn(props,x))]){
   if(fields.length>=80){notes.add('字段表最多展示80项，完整声明保留在原始契约。');return}
   const own=Object.hasOwn(props,name),p=path+'/'+pointer(name),sp=schemaPath+'/properties/'+pointer(name);fields.push({path:p,schemaPath:own?sp:schemaPath+'/required',schema:props[name],required:required.includes(name)});
   if(!own&&s.additionalProperties===false&&ts.length===1&&ts[0]==='object'&&!opaque)conflicts.add('必填字段未声明且额外字段被禁止：'+p);
   if(own)visit(props[name],p,sp,depth+1);
  }
  if(record(s.items))visit(s.items,path+'/*',schemaPath+'/items',depth+1);else if(s.items!==undefined&&typeof s.items!=='boolean')notes.add('列表项目契约未能完整投影。');
 }
 visit(schema,'','',0);return {fields,notes:[...notes],conflicts:[...conflicts]};
}
function SchemaTable({label,schema}:{label:string;schema:unknown}){
 const p=project(schema),s=record(schema)?schema:null;
 return <section className="s04-schema" aria-label={label}><h2>{label}</h2>
  {s?<p className="s04-root">根类型：{types(s)}{checks(s).length?'；'+checks(s).join('；'):''}</p>:<p className="s04-notice">{schema===false?'契约明确拒绝所有值。':schema===true?'契约未限制取值，不能推断业务字段。':'未声明可读取的契约，不能判断输入输出兼容。'}</p>}
  {p.conflicts.length>0&&<div role="alert" className="s04-warning"><strong>契约声明不一致，不能据此确认输入输出兼容。</strong><ul>{p.conflicts.map(x=><li key={x}>{x}</li>)}</ul></div>}
  {p.fields.length>0?<div className="s04-table-scroll" role="region" aria-label={label+'字段表'} tabIndex={0}><table><thead><tr><th>字段 / 路径</th><th>类型</th><th>必填</th><th>来源与说明</th><th>校验声明</th></tr></thead><tbody>{p.fields.map((f,i)=><tr key={f.path+'|'+i}><td><code>{f.path}</code></td><td>{record(f.schema)?types(f.schema):f.schema===false?'禁止取值':f.schema===true?'未限制':'未声明'}</td><td>{f.required?'是':'否'}</td><td>{record(f.schema)&&typeof f.schema.description==='string'?f.schema.description:'业务含义未声明'}<small>{label} {f.schemaPath}</small></td><td>{record(f.schema)?checks(f.schema).join('；')||'未声明额外校验':f.schema===false?'该字段不能取值':'字段契约未声明'}</td></tr>)}</tbody></table></div>:<p className="s04-notice">未声明可展开的对象字段；这不等于没有输入输出。根类型、组合或引用约束请核对原始契约。</p>}
  {p.notes.length>0&&<ul className="s04-notice">{p.notes.map(x=><li key={x}>{x}</li>)}</ul>}
  <details><summary>{label}原始 JSON 与完整约束</summary><pre>{schema===undefined?'未声明':JSON.stringify(schema,null,2)}</pre></details>
 </section>;
}
export function SkillInputOutput({resource,revision,onShowTab}:{resource:SkillMcpResource;revision:ResourceRevision;onShowTab:(name:string)=>void}){
 const [params,setParams]=useSearchParams(),operations=revision.content.operations??[],requested=params.get('resourceOperation'),selected=operations.find(x=>x.name===requested)??operations[0];
 const currentTests=resource.testResults.filter(x=>x.revisionId===revision.revisionId&&x.revisionDigest===revision.digest) as unknown as {operation?:string;actualExecution?:boolean;verificationLevel?:string;status:string;resultId:string}[];
 const tests=currentTests.filter(x=>x.operation===selected?.name),duplicates=selected&&operations.filter(x=>x.name===selected.name).length>1;
 return <div className="s04-workbench"><div className="s04-main rd-card"><header className="s04-heading"><div><h2>操作输入与输出</h2><p>读取本资源准确修订的声明；字段表不代表数据、权限或执行已验证。</p></div><label>查看操作<select aria-label="查看操作" value={selected?.name??''} disabled={!operations.length} onChange={e=>setParams(previous=>{const next=new URLSearchParams(previous);next.set('resourceOperation',e.target.value);return next},{replace:true})}>{operations.length?operations.map((op,i)=><option value={op.name} key={op.name+'|'+i}>{operationNames[op.name]?operationNames[op.name]+' · ':''}{op.name}</option>):<option value="">未声明操作</option>}</select></label></header>
  {requested&&!operations.some(x=>x.name===requested)&&<p className="s04-notice">链接中的操作不属于当前修订，已显示当前可读操作；没有沿用旧契约。</p>}
  <p className="s04-note">{Object.keys(revision.content.inputSchema??{}).length||Object.keys(revision.content.outputSchema??{}).length?'资源级契约与操作契约分别保留。':'资源级未声明统一字段；以下按各操作的准确契约展示，不能把空对象理解为无输入输出。'} 字段来源指契约位置；数据来源与业务映射未声明时不作推断。</p>
  {duplicates?<p role="alert" className="s04-warning">当前修订含重名操作，不能确定准确契约；请核对原始配置。</p>:selected?<><SchemaTable label="输入参数" schema={selected.inputSchema}/><SchemaTable label="输出参数" schema={selected.outputSchema}/></>:<p className="s04-notice">当前修订未声明操作，不能从能力名称推断输入输出。</p>}
  <details className="s04-resource-json"><summary>资源级与操作级原始配置</summary><pre>{JSON.stringify({inputSchema:revision.content.inputSchema??null,outputSchema:revision.content.outputSchema??null,operations},null,2)}</pre></details>
 </div><aside className="s04-context"><section className="rd-card"><h2>本次查看依据</h2><p><strong>{resource.name}</strong></p><p>{revision.revisionId===resource.publishedRevisionId?'当前查看已发布修订。':'当前查看草稿或历史修订；不作为已发布执行依据。'}</p><dl><dt>操作</dt><dd>{selected?.name??'未声明'}</dd><dt>执行器</dt><dd>{declared(selected?.executorId)}</dd><dt>执行器版本</dt><dd>{declared(selected?.executorRevision)}</dd><dt>副作用声明</dt><dd>{selected?.sideEffectClass==='READ_ONLY'?'只读':declared(selected?.sideEffectClass)}</dd></dl><details><summary>准确资源、修订与摘要</summary><dl><dt>资源</dt><dd>{resource.resourceId}</dd><dt>查看修订</dt><dd>{revision.revisionId}</dd><dt>查看摘要</dt><dd>{revision.digest}</dd><dt>发布修订</dt><dd>{resource.publishedRevisionId??'未发布'}</dd><dt>执行器配置摘要</dt><dd>{declared(selected?.executorConfigurationDigest)}</dd></dl></details></section>
 <section className="rd-card"><h2>已有测试依据</h2><p>本操作、当前准确修订：{tests.length}条已保存记录。</p><p>{tests.some(x=>x.actualExecution&&x.verificationLevel==='ISOLATED_SYNTHETIC_EXECUTOR')?'存在隔离合成执行记录，逐例结果请查看测试页。':'尚无可核验的隔离执行记录；不继承其他修订或声明检查。'}</p><p>测试记录与契约声明、发布及业务接受分别核对。</p><button onClick={()=>onShowTab('测试')}>查看已有测试</button></section>
 <ResourceVersionImpact resource={resource} active view="输入输出"/>
 </aside></div>;
}
