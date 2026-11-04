import {useEffect,useLayoutEffect,useRef} from 'react';

/** Schedule reads only; callbacks must never dispatch commands. */
export function useAutomaticReadback({identity,enabled,read,interval=2500}:{
 identity:string;enabled:boolean;read:()=>Promise<boolean>;interval?:number;
}){
 const callback=useRef(read);
 useLayoutEffect(()=>{callback.current=read},[read]);
 useEffect(()=>{
  if(!enabled)return;
  let active=true,running=false,failures=0;
  let timer:ReturnType<typeof setTimeout>|undefined;
  function schedule(){
   if(active&&document.visibilityState!=='hidden'){
    timer=setTimeout(()=>void tick(),Math.min(interval*2**failures,15000));
   }
  }
  async function tick(){
   if(!active||running||document.visibilityState==='hidden')return;
   running=true;
   try{
    const again=await callback.current();failures=0;
    if(!again)active=false;
   }catch{failures=Math.min(failures+1,3)}
   finally{running=false;schedule()}
  }
  function visibility(){
   if(timer)clearTimeout(timer);
   if(document.visibilityState!=='hidden')void tick();
  }
  document.addEventListener('visibilitychange',visibility);
  schedule();
  return()=>{
   active=false;if(timer)clearTimeout(timer);
   document.removeEventListener('visibilitychange',visibility);
  };
 },[identity,enabled,interval]);
}
