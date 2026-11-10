import {useEffect,useMemo,useState} from 'react';
import {getEmployeeAuthoring,getWorkbenchSession,workbenchPrincipalKey,type EmployeeAuthoring,type EmployeeDefinitionSummary} from '../api/digitalEmployees';
import {verifyEmployeeAuthoring} from './useEmployeeAuthoring';

export function useEmployeeCollectionVersions(items:EmployeeDefinitionSummary[],enabled:boolean){
 const parents=useMemo(()=>[...new Map(items.map(item=>[item.employeeDefinitionId,item])).values()],[items]);
 const key=JSON.stringify(parents.map(p=>[p.employeeDefinitionId,p.employeeDefinitionRevisionId,p.employeeDefinitionDigest]));
 const [state,setState]=useState<{key:string;values:Record<string,EmployeeAuthoring|null>;ready:boolean}>({key:'',values:{},ready:false});
 useEffect(()=>{
  if(!enabled||!parents.length)return;
  const controller=new AbortController();let valid=true;
  const withdraw=()=>{valid=false;controller.abort();setState({key,values:{},ready:true})};
  window.addEventListener('workbench-session-expired',withdraw);
  void (async()=>{
   const values:Record<string,EmployeeAuthoring|null>={};let next=0;
   try{
    const before=workbenchPrincipalKey(await getWorkbenchSession(controller.signal));
    await Promise.all(Array.from({length:Math.min(3,parents.length)},async()=>{
     while(valid&&next<parents.length){const parent=parents[next++];try{values[parent.employeeDefinitionId]=verifyEmployeeAuthoring(await getEmployeeAuthoring(parent,controller.signal),parent)}catch{values[parent.employeeDefinitionId]=null}}
    }));
    if(workbenchPrincipalKey(await getWorkbenchSession(controller.signal))!==before)throw Error('IDENTITY_CHANGED');
    if(valid)setState({key,values,ready:true});
   }catch{if(valid)setState({key,values:{},ready:true})}
  })();
  return()=>{valid=false;controller.abort();window.removeEventListener('workbench-session-expired',withdraw)};
 },[key,parents,enabled]);
 return enabled&&state.key===key?state:{key,values:{},ready:false};
}
