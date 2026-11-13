import {useCallback,useEffect,useLayoutEffect,useRef,useState} from 'react';
import {getEmployeeAuthoring,getManagementCollectionActions,getWorkbenchSession,readTeam,workbenchPrincipalKey,type EmployeeDefinition,type ManagementActions} from '../api/digitalEmployees';
export type ManagementTarget={kind:'teams';id:string;revision:string;digest:string;version:number}|{kind:'employees';item:EmployeeDefinition}|{kind:'teams'|'employees';collection:true};
const expected=(target:ManagementTarget):Record<string,string|number>|null=>'collection' in target?null:target.kind==='teams'?{teamId:target.id,revisionId:target.revision,digest:target.digest,aggregateVersion:target.version}:{employeeDefinitionId:target.item.employeeDefinitionId,employeeDefinitionRevisionId:target.item.employeeDefinitionRevisionId,employeeDefinitionDigest:target.item.employeeDefinitionDigest,aggregateVersion:target.item.aggregateVersion??0};
export function useManagementActions(target:ManagementTarget|null){
 const identity=JSON.stringify(target),latest=useRef(target);useLayoutEffect(()=>{latest.current=target},[target]);
 const principal=useRef<{identity:string;key:string}|null>(null);
 const active=useRef<AbortController|null>(null);
 const epoch=useRef(0),[state,setState]=useState<{identity:string;value?:ManagementActions;error?:string}>({identity:''});
 const refresh=useCallback(async()=>{const current=latest.current;if(!current)return null;const token=++epoch.current;active.current?.abort();const controller=new AbortController();active.current=controller;const signal=AbortSignal.any([controller.signal,AbortSignal.timeout(8000)]);setState({identity});try{
  const before=await getWorkbenchSession(signal);if(principal.current?.identity===identity&&principal.current.key!==workbenchPrincipalKey(before))throw Error('登录身份已变化。');let value:ManagementActions|undefined;
  if('collection' in current)value=await getManagementCollectionActions(current.kind,signal);else if(current.kind==='teams')value=(await readTeam(current.id,current.revision,signal)).maintenanceActions;else value=(await getEmployeeAuthoring(current.item,signal)).maintenanceActions;
  const after=await getWorkbenchSession(signal),target=expected(current);
  if(workbenchPrincipalKey(before)!==workbenchPrincipalKey(after)||!value||value.status==='UNAVAILABLE'||value.subjectId!==after.principal.principalId||value.tenantId!==after.principal.tenantId||value.securityDomain!==after.principal.securityDomain||value.authorityGranted!==false||value.executionStarted!==false||!Number.isInteger(value.generation)||!Number.isInteger(value.recoveryEpoch)||!Number.isFinite(Date.parse(value.readAt))||(target===null?value.target!==null:!value.target||Object.entries(target).some(([k,v])=>value!.target![k]!==v)))throw Error('当前操作资格尚未核实。');
  if(token!==epoch.current||JSON.stringify(latest.current)!==identity)return null;principal.current={identity,key:workbenchPrincipalKey(after)};setState({identity,value});return value;
 }catch{if(token===epoch.current)setState({identity,error:'当前操作资格尚未核实，可继续查看并保留未保存内容。'});return null}},[identity]);
 useEffect(()=>{const generation=epoch;void refresh();const withdraw=()=>{epoch.current++;active.current?.abort();setState({identity,error:'登录状态已变化，请重新核对。'})};const focus=()=>void refresh();window.addEventListener('workbench-session-expired',withdraw);window.addEventListener('focus',focus);return()=>{generation.current++;active.current?.abort();window.removeEventListener('workbench-session-expired',withdraw);window.removeEventListener('focus',focus)}},[identity,refresh]);
 const value=state.identity===identity?state.value:undefined;
 const allows=(action:string,v:ManagementActions|null|undefined=value)=>v?.actions?.[action]?.authorized===true&&v.actions[action].lifecycleEligible===true;
 return {allows,refresh,error:state.identity===identity?state.error:undefined,ready:!!value};
}
