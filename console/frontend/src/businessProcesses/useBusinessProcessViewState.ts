import {useCallback,useEffect,type RefObject} from 'react';
const selectors=['.skill-frame-content','.bp-map-scroll','.bp-activity-inspector'];
type Snapshot={savedAt:number;open:string[];scroll:{selector:string;top:number;left:number}[];windowTop:number;windowLeft:number};
const validCoordinate=(n:number)=>Number.isFinite(n)&&n>=0&&n<=10000000;
export function useBusinessProcessViewState(root:RefObject<HTMLElement|null>,identity:string|null){
 const key=identity?'business-process-view:v1:'+identity:null;
 useEffect(()=>{
  if(!key||!root.current)return;
  let saved:Snapshot;
  try{const raw=sessionStorage.getItem(key);if(!raw)return;saved=JSON.parse(raw);if(!saved||Date.now()-saved.savedAt>30*60*1000||saved.savedAt>Date.now()||!Array.isArray(saved.open)||saved.open.some(v=>typeof v!=='string')||!Array.isArray(saved.scroll)||saved.scroll.some(v=>!v||!selectors.includes(v.selector)||!validCoordinate(v.top)||!validCoordinate(v.left))||!validCoordinate(saved.windowTop)||!validCoordinate(saved.windowLeft))return}catch{return}
  const node=root.current;let stopped=false;
  const restore=()=>{if(stopped)return;for(const item of node.querySelectorAll<HTMLDetailsElement>('details[data-bp-state-key]'))item.open=saved.open.includes(item.dataset.bpStateKey!);
   for(const item of saved.scroll){const target=item.selector==='.skill-frame-content'?node.closest<HTMLElement>(item.selector):node.querySelector<HTMLElement>(item.selector);if(target){target.scrollTop=item.top;target.scrollLeft=item.left}}
   window.scrollTo(saved.windowLeft,saved.windowTop);
  };
  const observer=new MutationObserver(restore);
  const stop=()=>{stopped=true;observer.disconnect()};
  restore();observer.observe(node,{childList:true,subtree:true});
  const timer=window.setTimeout(stop,30_000);
  for(const event of ['pointerdown','keydown','wheel','touchstart'])window.addEventListener(event,stop,{once:true,capture:true});
  return()=>{stop();clearTimeout(timer);for(const event of ['pointerdown','keydown','wheel','touchstart'])window.removeEventListener(event,stop,true)};
 },[key,root]);
 return useCallback(()=>{
  if(!key||!root.current)return;const node=root.current;
  const saved:Snapshot={savedAt:Date.now(),open:Array.from(node.querySelectorAll<HTMLDetailsElement>('details[data-bp-state-key][open]'),d=>d.dataset.bpStateKey!),scroll:selectors.flatMap(selector=>{const target=selector==='.skill-frame-content'?node.closest<HTMLElement>(selector):node.querySelector<HTMLElement>(selector);return target?[{selector,top:target.scrollTop,left:target.scrollLeft}]:[]}),windowTop:window.scrollY,windowLeft:window.scrollX};
  try{sessionStorage.setItem(key,JSON.stringify(saved))}catch{/* View position is optional; no business input or write is lost. */}
 },[key,root]);
}
