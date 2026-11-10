import {useCallback,useEffect,useLayoutEffect,useRef,useState} from 'react';
import {getEmployeeAuthoring,getWorkbenchSession,workbenchPrincipalKey,type EmployeeAuthoring,type EmployeeDefinition,type EmployeeDefinitionSummary} from '../api/digitalEmployees';

export function verifyEmployeeAuthoring(value:EmployeeAuthoring,item:EmployeeDefinitionSummary & {aggregateVersion?:number}){
 if(value.basis!=='OWNER_FACT_ORDER'||value.executionStarted!==false||!Number.isInteger(value.aggregateVersion)||value.aggregateVersion<(item.aggregateVersion??0)||value.parent.employeeDefinitionId!==item.employeeDefinitionId||value.parent.employeeDefinitionRevisionId!==item.employeeDefinitionRevisionId||value.parent.employeeDefinitionDigest!==item.employeeDefinitionDigest)throw Error('员工版本依据不一致，请重新读取。');
 for(const key of ['head','publication','draft'] as const){
  const target=value[key];
  if(!target||!['AVAILABLE','NOT_AVAILABLE',...(key==='draft'?['NONE']:key==='publication'?['WITHDRAWN']:[])].includes(target.status))throw Error('员工版本状态尚未核实。');
  if(target.status==='AVAILABLE'){
   const d=target.definition;
   if(d.resourceKind!=='DIGITAL_EMPLOYEE_DEFINITION'||d.employeeDefinitionId!==item.employeeDefinitionId||!d.employeeDefinitionRevisionId||!d.employeeDefinitionDigest||d.aggregateVersion!==value.aggregateVersion||!Array.isArray(d.members)||!Array.isArray(d.responsibilities))throw Error('员工版本内容不一致。');
   if(d.employeeDefinitionRevisionId===item.employeeDefinitionRevisionId&&d.employeeDefinitionDigest!==item.employeeDefinitionDigest)throw Error('所选修订与当前版本依据不一致。');
   if(key==='publication'&&d.publicationState!=='PUBLISHED')throw Error('发布状态尚未核实。');
   if(key==='draft'&&(!['DRAFT','VALIDATED','APPROVED'].includes(d.lifecycleState??'')||value.head.status!=='AVAILABLE'||d.employeeDefinitionRevisionId!==value.head.definition.employeeDefinitionRevisionId||d.employeeDefinitionDigest!==value.head.definition.employeeDefinitionDigest))throw Error('修改草稿与当前版本不一致。');
  }
 }
 return value;
}
export function useEmployeeAuthoring(item:EmployeeDefinition|null,enabled:boolean){
 const identity=enabled&&item?JSON.stringify([item.employeeDefinitionId,item.employeeDefinitionRevisionId,item.employeeDefinitionDigest,item.aggregateVersion,item.lifecycleState]):'';
 const [state,setState]=useState<{identity:string;value?:EmployeeAuthoring;error?:string}>({identity:''});
 const generation=useRef(0),active=useRef<AbortController|null>(null),itemRef=useRef(item);
 useLayoutEffect(()=>{itemRef.current=item},[item]);
 const refresh=useCallback(async()=>{
  const selected=itemRef.current;if(!identity||!selected)return null;
  const token=++generation.current;active.current?.abort();const controller=new AbortController();active.current=controller;
  setState({identity});
  try{
   const before=workbenchPrincipalKey(await getWorkbenchSession(controller.signal));
   const value=verifyEmployeeAuthoring(await getEmployeeAuthoring(selected,controller.signal),selected);
   if(workbenchPrincipalKey(await getWorkbenchSession(controller.signal))!==before)throw Error('登录身份已变化，请重新打开员工。');
   if(token!==generation.current)return null;
   setState({identity,value});return value;
  }catch(error){if(token===generation.current)setState({identity,error:error instanceof Error?error.message:'当前版本暂未读回。'});return null}
 },[identity]);
 useEffect(()=>{
  const epoch=generation;
  void refresh();
  const withdraw=()=>{generation.current++;active.current?.abort();setState({identity,error:'登录已失效，请重新进入员工管理。'})};
  window.addEventListener('workbench-session-expired',withdraw);
  return()=>{epoch.current++;active.current?.abort();window.removeEventListener('workbench-session-expired',withdraw)};
 },[identity,refresh]);
 const current=state.identity===identity?state:null;
 return {value:current?.value,error:current?.error,refresh};
}
