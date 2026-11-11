import {useEffect,useState} from 'react';
import {getWorkbenchSession,workbenchPrincipalKey} from '../api/digitalEmployees';
import {checkBusinessProcessEditorAccess} from '../api/businessProcesses';
export type BusinessRelationAccess={principal:string;allowed:boolean;signal:AbortSignal|null;objectId:string};
export function useBusinessRelationAccess(objectId:string,enabled:boolean):BusinessRelationAccess{
 const [access,setAccess]=useState<BusinessRelationAccess>({principal:'',allowed:false,signal:null,objectId:''});
 useEffect(()=>{
  const controller=new AbortController();let active=true,epoch=0,identity='';
  const clear=()=>{active=false;controller.abort();setAccess({principal:'',allowed:false,signal:null,objectId})};
  const check=async()=>{const current=++epoch;
   setAccess(old=>({...old,allowed:false}));if(!enabled)return;
   try{const key=workbenchPrincipalKey(await getWorkbenchSession(AbortSignal.any([controller.signal,AbortSignal.timeout(30_000)])));
    if(!active||current!==epoch)return;if(identity&&identity!==key){window.dispatchEvent(new Event('workbench-session-expired'));return}identity=key;
    setAccess({principal:key,allowed:false,signal:controller.signal,objectId});
    await checkBusinessProcessEditorAccess('PROCESS',objectId,'REVISE',key,controller.signal);
    if(active&&current===epoch)setAccess({principal:key,allowed:true,signal:controller.signal,objectId});
   }catch{if(active&&current===epoch)setAccess(old=>({...old,allowed:false}))}
  };
  window.addEventListener('focus',check);window.addEventListener('workbench-session-expired',clear);void Promise.resolve().then(check);
  return()=>{active=false;controller.abort();window.removeEventListener('focus',check);window.removeEventListener('workbench-session-expired',clear)};
 },[objectId,enabled]);
 return access.objectId===objectId?access:{principal:'',allowed:false,signal:null,objectId};
}
