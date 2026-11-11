import {useEffect,useState} from 'react';
import {compareWorkflowRevisions,trustedWorkflowAuthoring,type WorkflowDefinition} from '../api/workflowDefinitions';

export function WorkflowVersionComparison({definition}:{definition:WorkflowDefinition}){
 const [attempt,setAttempt]=useState(0),[result,setResult]=useState<{key:string;value?:Record<string,unknown>;error?:boolean}|null>(null);
 const pair=definition.revisions.slice(-2),left=pair.length===2?pair[0].revisionId:null,right=pair.length===2?pair[1].revisionId:null;
 const id=definition.workflowDefinitionId,key=JSON.stringify([id,left,right,attempt]);
 useEffect(()=>{if(!left||!right)return;let active=true;void compareWorkflowRevisions(id,left,right).then(value=>{
  if(value.workflowDefinitionId!==id||value.leftRevisionId!==left||value.rightRevisionId!==right)throw new Error('comparison mismatch');
  if(active)setResult({key,value});
 }).catch(()=>{if(active)setResult({key,error:true})});return()=>{active=false}},[id,left,right,key]);
 const current=result?.key===key?result:null,value=current?.value;
 const ids=(field:string)=>Array.isArray(value?.[field])?(value[field] as unknown[]).filter((x):x is string=>typeof x==='string'):[];
 const name=(taskId:string)=>[...pair].reverse().flatMap(revision=>revision.content.tasks).find(task=>task.taskId===taskId)?.name??taskId;
 return <section aria-label="Workflow revision comparison"><h3>{trustedWorkflowAuthoring?'版本变化':'Revision comparison'}</h3>
 {pair.length<2?<p>尚无后续版本可比较。</p>:current?.error?<><p role="alert">暂时无法核对版本变化，请重新读取。</p><button onClick={()=>setAttempt(n=>n+1)}>重新核对版本变化</button></>:!value?<p role="status">正在核对固定版本…</p>:<>
 <p>{value.digestChanged?'两个版本的流程内容有变化。':'两个版本的流程内容一致。'}历史工作仍保留原有引用。</p>
 {(['addedTaskIds','removedTaskIds','changedTaskIds'] as const).map((field,index)=><div key={field}><h4>{['新增步骤','移除步骤','调整步骤'][index]}（{ids(field).length}）</h4>{ids(field).length?<ul>{ids(field).map(id=><li key={id}>{name(id)}</li>)}</ul>:<p>无</p>}</div>)}
 <p>以上是步骤变化摘要；其他字段变化仍需结合两个版本的内容核对。</p><details><summary>查看固定版本与比较依据</summary><p>{left} → {right}</p><pre className="technical-value">{JSON.stringify(value,null,2)}</pre></details>
 </>}
 </section>;
}
