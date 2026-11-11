import {useEffectEvent,useLayoutEffect,type RefObject} from 'react';

export function useCapabilityCatalogueScroll(root:RefObject<HTMLElement|null>,active:boolean,viewKey:string,top:number,save:(top:number)=>void){
 const position=useEffectEvent(()=>top);
 const persist=useEffectEvent((value:number)=>save(value));
 useLayoutEffect(()=>{
  if(!active)return;
  const node=root.current?.closest<HTMLElement>('.skill-frame-content');if(!node)return;
  let ready=false;
  const frame=requestAnimationFrame(()=>{node.scrollTop=Math.min(position(),Math.max(0,node.scrollHeight-node.clientHeight));ready=true});
  const scroll=()=>{if(ready)persist(Math.round(node.scrollTop))};
  node.addEventListener('scroll',scroll,{passive:true});
  return()=>{ready=false;cancelAnimationFrame(frame);node.removeEventListener('scroll',scroll)};
 },[root,active,viewKey]);
}
