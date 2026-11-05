import {useEffect,useState,type RefObject} from "react";
const storageKey=(key:string,name:string)=>`work-view.v1:${key}:${name}`;
export function readViewString(key:string|undefined,name:string,fallback=""){
 if(!key)return fallback;
 try{const value=sessionStorage.getItem(storageKey(key,name));return value!==null&&value.length<4000?value:fallback}catch{return fallback}
}
export function saveViewString(key:string|undefined,name:string,value:string){
 if(!key)return;
 try{sessionStorage.setItem(storageKey(key,name),value)}catch{/* View storage never grants or blocks owner access. */}
}
export function useViewString(key:string|undefined,name:string,fallback=""){
 const [value,setValue]=useState(()=>readViewString(key,name,fallback));
 const update=(next:string)=>{setValue(next);saveViewString(key,name,next)};
 return [value,update] as const;
}
export function useWorkScroll(ref:RefObject<HTMLElement|null>,key:string|undefined,ready:boolean){
 useEffect(()=>{
  const node=ref.current;if(!node||!key||!ready)return;
  const top=Number(readViewString(key,"scroll","0"));node.scrollTop=Number.isFinite(top)?top:0;
  const save=()=>saveViewString(key,"scroll",String(node.scrollTop));
  node.addEventListener("scroll",save);return()=>node.removeEventListener("scroll",save);
 },[key,ready,ref]);
}
