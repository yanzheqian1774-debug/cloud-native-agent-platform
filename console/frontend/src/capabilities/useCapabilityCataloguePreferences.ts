import {useEffect,useRef,useState} from 'react';
import {CapabilityRequestError,readCapabilityPreferences,saveCapabilityPreferences,type CapabilityCatalogueState} from '../api/businessCapabilities';

const empty=():CapabilityCatalogueState=>({query:'',domain:'',layout:'cards',favoritesOnly:false,favorites:[],scrollTop:0,loadedCount:50});
// A failed/unknown write pauses autosave. Explicit reread reconciles with the
// owner, rather than creating another command or overwriting another session.
export function useCapabilityCataloguePreferences(principal:string){
 const [state,setState]=useState(empty),[version,setVersion]=useState(0),[ready,setReady]=useState(false),[error,setError]=useState(''),[saving,setSaving]=useState(false),[retry,setRetry]=useState(0),[savedFavorites,setSavedFavorites]=useState<string[]>([]);
 const current=useRef(state),dirty=useRef(false),pending=useRef(false),generation=useRef(0);
 useEffect(()=>{
  const epoch=++generation.current,controller=new AbortController();dirty.current=false;pending.current=false;
  const load=async()=>{
   setReady(false);setError('');setSaving(false);setSavedFavorites([]);const cleared=empty();current.current=cleared;setState(cleared);setVersion(0);
   if(!principal)return;
   try{
    const value=await readCapabilityPreferences(principal,controller.signal);
    if(epoch!==generation.current)return;
    if(!Number.isInteger(value.version)||!value.state||!Array.isArray(value.state.favorites))throw new Error('Invalid preferences');
    const restored={...empty(),...value.state};current.current=restored;setState(restored);setVersion(value.version);setSavedFavorites(value.state.favorites);setReady(true);
   }catch{if(epoch===generation.current)setError('暂时无法读取个人目录设置，请重新读取后继续保存。')}
  };
  void load();
  return()=>{controller.abort();generation.current=epoch+1};
 },[principal,retry]);
 useEffect(()=>{
  if(!ready||!dirty.current||pending.current||error)return;
  const epoch=generation.current;
  const timer=window.setTimeout(()=>{
   if(epoch!==generation.current||pending.current)return;
   pending.current=true;setSaving(true);
   const submitted=state,commandId=`capability-preferences:${crypto.randomUUID()}`;
   void saveCapabilityPreferences(principal,version,commandId,submitted).then(value=>{
    if(epoch!==generation.current)return;
    if(value.commandId!==commandId||value.version!==version+1)throw new Error('Unverified save');
    dirty.current=current.current!==submitted;pending.current=false;setSaving(dirty.current);setSavedFavorites(value.state.favorites);setVersion(value.version);
   }).catch(cause=>{
    if(epoch!==generation.current)return;
    pending.current=false;setSaving(false);
    setError(cause instanceof CapabilityRequestError&&cause.status===409?'目录设置已在其他位置更新，请重新读取后再修改。':'目录设置的保存结果尚未核实，请重新读取；不会自动重复提交。');
   });
  },350);
  return()=>window.clearTimeout(timer);
 },[state,version,ready,principal,error]);
 const update=(patch:Partial<CapabilityCatalogueState>)=>{
  if(!ready||error||Object.entries(patch).every(([key,value])=>JSON.stringify(current.current[key as keyof CapabilityCatalogueState])===JSON.stringify(value)))return;
  const next={...current.current,...patch};current.current=next;dirty.current=true;setSaving(true);setState(next);
 };
 return {state,update,ready,error,saving,favoritesReady:JSON.stringify(savedFavorites)===JSON.stringify(state.favorites),reload:()=>setRetry(n=>n+1)};
}
