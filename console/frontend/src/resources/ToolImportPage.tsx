import {useEffect,useRef,useState} from 'react';
import {Link} from 'react-router-dom';
import {NavigationIcon} from '../components/NavigationIcon';
import {getWorkbenchSession,workbenchPrincipalKey} from '../api/digitalEmployees';
import {checkToolImportAccess,encodeToolSource,previewToolImport,readToolReceipt,saveToolImport,ToolRequestError} from '../api/toolDefinitions';
import type {ToolPreview,ToolReceipt,ToolSource,ToolContent} from '../api/toolDefinitions';
import {readToolBuffer,writeToolBuffer,clearToolBuffers} from './toolDraftBuffer';
import './ToolsWorkspace.css';
type ImportBuffer={effects?:Record<string,ToolContent['sideEffect']>;stage?:'choose'|'source'|'preview';mode:ToolSource['kind'];input:string;file:{name:string;contentBase64:string}|null;preview:ToolPreview|null;selected:string[];pending:string|null;receipt:ToolReceipt|null;source:ToolSource|null};

export function ToolImportPage(){
 const [effects,setEffects]=useState<Record<string,ToolContent['sideEffect']>>({});
 const [stage,setStage]=useState<'choose'|'source'|'preview'>('choose');
 const [principal,setPrincipal]=useState(''),[expired,setExpired]=useState(false),[mode,setMode]=useState<ToolSource['kind']>('API');
 const [input,setInput]=useState(''),[file,setFile]=useState<{name:string;contentBase64:string}|null>(null),[preview,setPreview]=useState<ToolPreview|null>(null),[selected,setSelected]=useState<string[]>([]);
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[receipt,setReceipt]=useState<ToolReceipt|null>(null),[pending,setPending]=useState<string|null>(null);
 const abort=useRef(new AbortController()),inFlight=useRef(false),source=useRef<ToolSource|null>(null);
 useEffect(()=>{
  const controller=new AbortController();abort.current=controller;
  const expire=()=>{controller.abort();setExpired(true);clearToolBuffers();setInput('');setFile(null);setPreview(null);setReceipt(null);source.current=null;setPrincipal('')};
  window.addEventListener('workbench-session-expired',expire);
  getWorkbenchSession(controller.signal).then(async session=>{const key=workbenchPrincipalKey(session);await checkToolImportAccess(key,controller.signal);if(!controller.signal.aborted){const buffer=readToolBuffer<ImportBuffer>(key,'import');if(buffer){setEffects(buffer.effects??{});setStage(buffer.stage??(buffer.preview?'preview':'source'));setMode(buffer.mode);setInput(buffer.input);setFile(buffer.file);setPreview(buffer.preview);setSelected(buffer.selected);setPending(buffer.pending);setReceipt(buffer.receipt);source.current=buffer.source}setPrincipal(key)}}).catch(()=>{if(!controller.signal.aborted)setError('无法读取当前导入资格，请核对登录和权限。')});
  return()=>{controller.abort();window.removeEventListener('workbench-session-expired',expire)};
 },[]);
 function buffer(nextPending=pending):ImportBuffer{return {effects,stage,mode,input,file,preview,selected,pending:nextPending,receipt,source:source.current}}
 useEffect(()=>{if(principal&&!expired){try{writeToolBuffer(principal,'import',{effects,stage,mode,input,file,preview,selected,pending,receipt,source:source.current})}catch{/* Explicit save checks storage before issuing a command. */}}},[principal,expired,effects,stage,mode,input,file,preview,selected,pending,receipt]);
 const newCount=preview?.operations.filter(op=>selected.includes(op.name)&&!op.existing).length??0;
 const reuseCount=selected.length-newCount;
 const locked=busy||!!pending||!!receipt;
 function resetPreview(){setEffects({});setPreview(null);setSelected([]);source.current=null;setError('')}
 async function run(action:()=>Promise<void>){
  if(inFlight.current||!principal||expired)return;
  inFlight.current=true;setBusy(true);setError('');
  try{await action()}catch(e){if(!abort.current.signal.aborted)setError(e instanceof ToolRequestError&&e.outcomeUnknown?'保存结果尚未确认，请读取保存记录；不会自动重复提交。':e instanceof ToolRequestError&&e.status===403?'当前没有此操作权限，已保留输入。':'操作未完成，请核对文件格式、权限或连接后再试。')}
  finally{inFlight.current=false;if(!abort.current.signal.aborted)setBusy(false)}
 }
 async function parse(){
  const value:ToolSource={kind:mode,contentBase64:file?.contentBase64??encodeToolSource(new TextEncoder().encode(input))};
  const result=await previewToolImport(value,principal,abort.current.signal);
  if(abort.current.signal.aborted)return;
  source.current=value;setPreview(result);setEffects(Object.fromEntries(result.operations.map(op=>[op.name,op.sideEffect as ToolContent['sideEffect']])));setStage('preview');setSelected(result.operations.map(item=>item.name));
 }
 async function save(){
  if(!source.current||!selected.length)return;
  const commandId=crypto.randomUUID();writeToolBuffer(principal,'import',buffer(commandId));setPending(commandId);
  try{const result=await saveToolImport({...source.current,selected,effects:Object.fromEntries(selected.filter(name=>!preview?.operations.find(op=>op.name===name)?.existing).map(name=>[name,effects[name]??'UNCONFIRMED'])),expectedVersions:{},commandId},principal,abort.current.signal);if(!abort.current.signal.aborted){setReceipt(result);setPending(null)}}
  catch(e){if(e instanceof ToolRequestError&&!e.outcomeUnknown)setPending(null);throw e}
 }
 if(expired)return <main className="f3-tools-workspace f3-tool-maintenance"><h1>接入 / 导入工具</h1><p role="alert">登录已失效，请重新登录后继续。当前页面已清除文件内容。</p></main>;
 return <main className="f3-tools-workspace f3-tool-maintenance"><Link to="/tools">返回工具</Link><header className="f3-tools-heading"><div><h1>{stage==='choose'?'接入工具':stage==='source'?'导入工具描述':'核对导入内容'}</h1><p>复用已有连接，或从 API 与平台插件包建立工具草稿。</p></div></header>
 <p>单份文件或内容不超过 100 KB；ZIP 最多 20 个文件，解压后的内容合计不超过 100 KB。</p>
 {!receipt&&stage==='choose'&&<div className="f3-tool-import-split"><section className="f3-tool-detail"><h2>选择接入来源</h2><div className="f3-tool-source-row"><span className="f3-tool-source-icon"><NavigationIcon name="skill"/></span><div><h3>从 API 导入</h3><p>OpenAPI 3.x JSON · 参数与返回映射</p></div><button className="f3-tool-secondary" disabled={!principal} onClick={()=>{if(mode!=='API'){setInput('');setFile(null);resetPreview()}setMode('API');setStage('source')}}>选择 API 描述</button></div><div className="f3-tool-source-row"><span className="f3-tool-source-icon"><NavigationIcon name="mcp"/></span><div><h3>引用 MCP 工具</h3><p>同一工具身份 · 保留连接与授权</p></div><Link className="f3-tool-secondary" to="/tools">选择 MCP 操作</Link></div><div className="f3-tool-source-row"><span className="f3-tool-source-icon"><NavigationIcon name="agent"/></span><div><h3>导入平台插件包</h3><p>平台清单与包内容预览 · 不执行代码</p></div><button className="f3-tool-secondary" disabled={!principal} onClick={()=>{if(mode!=='PLUGIN'&&mode!=='PLUGIN_ZIP'){setInput('');setFile(null);resetPreview();setMode('PLUGIN')}setStage('source')}}>选择插件包</button></div></section><aside className="f3-tool-detail"><h2>接入后怎么使用</h2><ol><li>选择操作：核对输入、输出与来源</li><li>明确权限与影响：凭据仅引用</li><li>验证候选：结构、实际调用与场景分别检查</li><li>发布与引用：由维护者管理绑定</li></ol><p className="f3-tool-note">当前阶段支持保存和编辑草稿；验证、发布和执行仍待接通。</p></aside></div>}
 {!receipt&&stage!=='choose'&&<>{stage==='source'&&<><button disabled={locked} onClick={()=>setStage('choose')}>返回接入方式</button><section className="f3-tool-detail"><h2>选择来源</h2><label>接入方式<select aria-label="接入方式" value={mode} disabled={locked} onChange={e=>{setMode(e.target.value as ToolSource['kind']);setFile(null);setInput('');resetPreview()}}><option value="API">API 描述（OpenAPI 3.x JSON）</option><option value="PLUGIN">平台插件清单（JSON）</option><option value="PLUGIN_ZIP">平台插件包（ZIP）</option></select></label><p><Link to="/tools">查看并复用已有 MCP 来源工具</Link></p>
 <p>目前支持部分 OpenAPI JSON 和平台插件格式；暂不支持 YAML 或任意第三方插件。不支持的内容会在预览中列出，保存草稿不会安装或执行工具。</p>
 <label>选择文件<input aria-label="选择文件" type="file" disabled={locked} accept={mode==='PLUGIN_ZIP'?'.zip':'.json'} onChange={e=>{const picked=e.target.files?.[0];e.target.value='';if(!picked)return;void run(async()=>{if(picked.size>100000)throw new ToolRequestError('IMPORT_SIZE_LIMIT',422);const contentBase64=encodeToolSource(new Uint8Array(await picked.arrayBuffer()));if(abort.current.signal.aborted)return;setFile({name:picked.name,contentBase64});setInput('');resetPreview()})}}/></label>
 {file?<p>已选择：{file.name} <button disabled={locked} onClick={()=>{setFile(null);resetPreview()}}>移除文件</button></p>:mode!=='PLUGIN_ZIP'&&<label>或粘贴描述内容<textarea aria-label="或粘贴描述内容" rows={10} value={input} disabled={locked} onChange={e=>{setInput(e.target.value);resetPreview()}}/></label>}
 <button disabled={locked||!principal||(!file&&!input.trim())} onClick={()=>void run(parse)}>解析并预览</button></section></>}
 {preview&&stage==='preview'&&<section className="f3-tool-detail"><button disabled={locked} onClick={()=>setStage('source')}>返回来源</button><h2>核对导入操作</h2><p>重复导入将复用已有工具，保留原草稿和已发布版本；需要修改时进入草稿编辑。</p><div className="f3-tool-table"><table><thead><tr><th>选择</th><th>操作与来源</th><th>输入 / 输出</th><th>执行影响</th></tr></thead><tbody>{preview.operations.map(op=><tr key={op.name}><td><input type="checkbox" aria-label={'选择 '+op.name} disabled={locked} checked={selected.includes(op.name)} onChange={e=>setSelected(items=>e.target.checked?[...items,op.name]:items.filter(n=>n!==op.name))}/></td><td><strong>{op.name}</strong><p>{op.description||'用途尚待补充'}</p><small>{op.source.kind==='API'?'API 描述':'平台插件'} · {op.existing?'已存在，将复用已有工具':'将新增草稿'}</small></td><td><p>{op.inputSchema?'已提供输入声明':'输入待补充'} → {op.outputSchema?'已提供输出声明':'输出待补充'}</p><details><summary>输入输出与待适配依据</summary><pre>{JSON.stringify({input:op.inputSchema,output:op.outputSchema,issues:op.blockingIssues},null,2)}</pre></details>{op.blockingIssues.length>0&&<p>{op.blockingIssues.length} 项内容待适配，尚不能据此发布或执行。</p>}</td><td>{op.existing?<p>保留已有声明；在草稿中编辑。</p>:<select aria-label={op.name+'执行影响'} disabled={locked} value={effects[op.name]??'UNCONFIRMED'} onChange={e=>setEffects(value=>({...value,[op.name]:e.target.value as ToolContent['sideEffect']}))}><option value="UNCONFIRMED">待核对</option><option value="read-only">只读</option><option value="creates-file">生成文件</option><option value="external-write">外部写入</option></select>}</td></tr>)}</tbody></table></div>{Boolean(preview.files?.length)&&<section aria-label="插件包文件预览"><h3>插件包文件</h3><ul>{preview.files!.map(file=><li key={file.path}>{file.path} · {file.bytes} 字节</li>)}</ul><p>已解析文件清单，未运行包内代码。运行环境验证仍待完成。</p></section>}<p className="f3-tool-note">行为声明仅供核对；真实权限、执行影响和幂等性仍需后端验证。待核对内容可保留在草稿中。</p>{newCount>0?<button disabled={locked||!selected.length} onClick={()=>void run(save)}>{reuseCount?`新增 ${newCount} 项草稿并复用 ${reuseCount} 项已有工具`:'保存所选草稿'}</button>:<div><p>所选 {reuseCount} 项均为已有工具，可直接继续维护，不产生新的导入命令。</p>{preview.operations.filter(op=>selected.includes(op.name)&&op.existing).map(op=><p key={op.name}><Link to={'/tools/draft?'+new URLSearchParams({id:op.existing!.toolId,revision:op.existing!.revisionId})}>{reuseCount===1?'查看已有工具':'继续维护 '+op.name}</Link></p>)}</div>}</section>}</>}
 {busy&&<p role="status">正在核对并处理，请稍候…</p>}{error&&<p role="alert">{error}</p>}
 {pending&&<section><p>保存结果待确认。请保持当前页面，先读取保存记录。</p><button disabled={busy} onClick={()=>void run(async()=>{const result=await readToolReceipt(pending,principal,abort.current.signal);if(!abort.current.signal.aborted){setReceipt(result);setPending(null)}})}>读取保存记录</button></section>}
 {receipt&&<section><h2>草稿已保存或已复用</h2><button disabled={busy} onClick={()=>{setReceipt(null);setPending(null);setInput('');setFile(null);resetPreview();setStage('choose')}}>继续导入其他工具</button><p>尚未完成验证、发布或执行。</p>{receipt.items.map(item=><p key={item.toolId}><Link to={'/tools/draft?'+new URLSearchParams({id:item.toolId,revision:item.revisionId})}>{item.changed?'查看保存的草稿':'查看已有草稿'}</Link></p>)}</section>}
 </main>;
}
