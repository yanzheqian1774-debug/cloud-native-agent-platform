import {useEffect,useRef,useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {readWorkbenchSession} from '../api/businessWorkspace';
import {continuationQuery} from '../api/conversationActions';
import * as api from './api';
/** Optional professional role selection; never a prerequisite for ordinary preparation. */
export function ResourceRoleChoice({id,revision,approved,continueWork=false}:{id:string;revision:number;approved:api.Confirmation;continueWork?:boolean}){
 const navigate=useNavigate(),epoch=useRef(0);
 const [options,setOptions]=useState<api.EmployeeOption[]>([]),[chosen,setChosen]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{const token=++epoch.current;api.resourceEmployeeOptions().then(v=>{if(token===epoch.current)setOptions(v.items)}).catch(e=>{if(token===epoch.current)setError(String(e.message))});return()=>{if(epoch.current===token)epoch.current=token+1}},[id,revision]);
 async function apply(){const selected=options.find(v=>v.employeeDefinitionId+'|'+v.employeeDefinitionRevisionId===chosen);if(!selected||busy)return;setBusy(true);setError('');const token=epoch.current;
  try{const session=await readWorkbenchSession();const ref={resource_id:selected.employeeDefinitionId,revision_id:selected.employeeDefinitionRevisionId,digest:selected.employeeDefinitionDigest};const storage='policy-role:'+JSON.stringify([session.principal.principalId,id,approved.digest,ref]);let key=sessionStorage.getItem(storage);if(!key){key=crypto.randomUUID();sessionStorage.setItem(storage,key)}const result=await api.selectEmployeeResources(id,approved,revision,ref,key,session.csrfToken);if(token===epoch.current)navigate(`/work/planning/${encodeURIComponent(id)}?revision=${result.confirmation.plan.source_proposal_revision}${continuationQuery()}`)}
  catch(e){if(token===epoch.current)setError(e instanceof Error?e.message:'角色变更尚未读回；原请求和历史保留')}
  finally{if(token===epoch.current)setBusy(false)}
 }
 return <section aria-label="后继角色资源选择"><h3>角色变更 · 原计划与成果保留</h3><p>此为可选专业入口。平台继续核对成员、资料范围与标准；同口径后继版本由策略确认，资源仍须验证发布后方可装配。{continueWork&&"在本次已授权范围内，核验通过后会接续只读执行与评价；旧任务和产物保留。"}</p><label>角色<select aria-label="后继准备使用的角色" value={chosen} disabled={busy} onChange={e=>setChosen(e.target.value)}><option value="">选择角色</option>{options.map(v=><option key={v.employeeDefinitionId+'|'+v.employeeDefinitionRevisionId} value={v.employeeDefinitionId+'|'+v.employeeDefinitionRevisionId}>{v.role} · {v.publicationState==='PUBLISHED'?'已发布':'待验证'}</option>)}</select></label><button type="button" disabled={busy||!chosen} onClick={()=>void apply()}>{busy?'正在核对后继准备…':(continueWork?'更新角色并接续只读办理':'用于后继资源准备')}</button>{error&&<p role="alert">{error}</p>}</section>;
}
