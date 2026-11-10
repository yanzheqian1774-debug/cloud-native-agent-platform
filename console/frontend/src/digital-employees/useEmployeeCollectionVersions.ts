import {employeeReadFeedback} from './employeeReadFeedback';
import {useEffect,useMemo,useRef,useState} from 'react';
import {getEmployeeAuthoring,getWorkbenchSession,workbenchPrincipalKey,type EmployeeAuthoring,type EmployeeDefinitionSummary} from '../api/digitalEmployees';
import {verifyEmployeeAuthoring} from './useEmployeeAuthoring';

export function useEmployeeCollectionVersions(items:EmployeeDefinitionSummary[],enabled:boolean){
 const [version,setVersion]=useState(0);
 const parents=useMemo(()=>[...new Map(items.map(item=>[item.employeeDefinitionId,item])).values()],[items]);
 const base=JSON.stringify(parents.map(p=>[p.employeeDefinitionId,p.employeeDefinitionRevisionId,p.employeeDefinitionDigest]));
 const key=JSON.stringify([version,base]);
 const cache=useRef<{base:string;actor:string;values:Record<string,EmployeeAuthoring|null>}|null>(null);
 const [state,setState]=useState<{key:string;values:Record<string,EmployeeAuthoring|null>;errors?:Record<string,string>;stale?:Record<string,boolean>;ready:boolean}>({key:'',values:{},ready:false});
 useEffect(()=>{
  if(!enabled||!parents.length)return;
  const controller=new AbortController();const batchSignal=AbortSignal.any([controller.signal,AbortSignal.timeout(20000)]);let valid=true;
  const withdraw=()=>{valid=false;cache.current=null;controller.abort();setState({key,values:{},ready:true})};
  window.addEventListener('workbench-session-expired',withdraw);
  void (async()=>{
   const values:Record<string,EmployeeAuthoring|null>={},errors:Record<string,string>={},stale:Record<string,boolean>={};let next=0;
   try{
    const before=workbenchPrincipalKey(await getWorkbenchSession(AbortSignal.any([controller.signal,AbortSignal.timeout(8000)])));
    const previous=cache.current?.base===base&&cache.current.actor===before?cache.current.values:{};
    if(valid)setState({key,values:previous,stale:Object.fromEntries(Object.keys(previous).map(id=>[id,true])),ready:false});
    await Promise.all(Array.from({length:Math.min(3,parents.length)},async()=>{
     while(valid&&!batchSignal.aborted&&next<parents.length){const parent=parents[next++],signal=AbortSignal.any([batchSignal,AbortSignal.timeout(8000)]);try{values[parent.employeeDefinitionId]=verifyEmployeeAuthoring(await getEmployeeAuthoring(parent,signal),parent)}catch(error){values[parent.employeeDefinitionId]=signal.aborted&&signal.reason?.name==='TimeoutError'?previous[parent.employeeDefinitionId]??null:null;stale[parent.employeeDefinitionId]=!!values[parent.employeeDefinitionId];errors[parent.employeeDefinitionId]=employeeReadFeedback(error,signal)}}
    }));
    if(workbenchPrincipalKey(await getWorkbenchSession(AbortSignal.any([controller.signal,AbortSignal.timeout(8000)])))!==before)throw Error('IDENTITY_CHANGED');
    if(valid){for(const parent of parents)if(!(parent.employeeDefinitionId in values))errors[parent.employeeDefinitionId]="本轮读取尚未完成，可重新核对。";cache.current={base,actor:before,values:Object.fromEntries(Object.entries(values).filter(([id])=>!stale[id]))};setState({key,values,errors,stale,ready:true})}
   }catch{cache.current=null;if(valid)setState({key,values:{},ready:true})}
  })();
  return()=>{valid=false;controller.abort();window.removeEventListener('workbench-session-expired',withdraw)};
 },[key,base,parents,enabled]);
 return {...(enabled&&state.key===key?state:{key,values:{},ready:parents.length===0}),refresh:()=>setVersion(v=>v+1)};
}
