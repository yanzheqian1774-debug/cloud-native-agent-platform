import {useEffect,useEffectEvent,useRef} from 'react';

/** Advance only within a live user continuation; saved phases never grant start intent. */
export function useCapabilityAdvance(enabled:boolean,identity:string,advance:()=>Promise<void>){
 const attempted=useRef<string|null>(null),run=useEffectEvent(advance);
 useEffect(()=>{
  if(!enabled||attempted.current===identity)return;
  const timer=setTimeout(()=>{attempted.current=identity;void run()},0);
  return()=>clearTimeout(timer);
 },[enabled,identity]);
}
