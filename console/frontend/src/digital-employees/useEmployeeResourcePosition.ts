import {useEffect,type RefObject} from 'react';
import {type EmployeeDefinition} from '../api/digitalEmployees';
import {readViewString,saveViewString} from '../problems/workViewState';
function resourceCardKey(card:Element){const href=card.querySelector<HTMLAnchorElement>('a[href]')?.href;if(!href)return '';const u=new URL(href);return JSON.stringify([u.pathname,u.searchParams.get('selected'),u.searchParams.get('resourceRevision')])}

/** View position only; exact employee/member reads remain the authority. */
export function useEmployeeResourcePosition(root:RefObject<HTMLElement|null>,item:EmployeeDefinition|null,section:string,professional:boolean,scope:string|undefined){
 const identity=item?JSON.stringify([item.employeeDefinitionId,item.employeeDefinitionRevisionId,item.employeeDefinitionDigest]):'';
 useEffect(()=>{
  if(!identity||!scope)return;
  let active=true,key:string|undefined,cleanupRestore=()=>{};
  const node=root.current;if(!node)return;
  const outer=node.closest<HTMLElement>('.skill-frame-content');
  const remember=(event:MouseEvent)=>{
   const link=(event.target as Element).closest<HTMLAnchorElement>('a[href]');if(!key||!link||!node.contains(link))return;
   const url=new URL(link.href);if(url.origin!==location.origin||!url.searchParams.has('employeeRef'))return;
   saveViewString(key,'resource-return',JSON.stringify({href:link.getAttribute('href'),detail:node.scrollTop,outer:outer?.scrollTop??0,expanded:[...node.querySelectorAll('.employee-resource-card')].filter(card=>card.querySelector('details[open]')).map(resourceCardKey)}));
  };
  const withdraw=()=>{active=false;cleanupRestore();key=undefined};
  node.addEventListener('click',remember,true);window.addEventListener('workbench-session-expired',withdraw);
  {
   if(!active)return;key=JSON.stringify([scope,identity,section,professional,'employee-resource-position']);
   let saved:{href:string;detail:number;outer:number;expanded?:string[]}|null=null;
   try{saved=JSON.parse(readViewString(key,'resource-return','null'))}catch{/* Invalid view state is ignored. */}
   if(saved&&typeof saved.href==='string'&&[saved.detail,saved.outer].every(n=>Number.isFinite(n)&&n>=0)){
   const position=saved;saveViewString(key,'resource-return','');
   let frame=0,done=false;
   const stop=()=>{done=true;observer?.disconnect();if(timer)clearTimeout(timer);cancelAnimationFrame(frame);node.removeEventListener('wheel',stop);node.removeEventListener('touchstart',stop);node.removeEventListener('keydown',stop)};
   cleanupRestore=stop;
   const restore=()=>{if(done||!active)return;const link=[...node.querySelectorAll<HTMLAnchorElement>('a[href]')].find(a=>a.getAttribute('href')===position.href);if(!link)return;const expanded=Array.isArray(position.expanded)?position.expanded.filter(k=>typeof k==='string').slice(0,100):[];for(const card of node.querySelectorAll('.employee-resource-card'))if(expanded.includes(resourceCardKey(card)))for(const detail of card.querySelectorAll('details'))detail.open=true;node.scrollTop=position.detail;if(outer)outer.scrollTop=position.outer;link.focus({preventScroll:true});if(Math.abs(node.scrollTop-position.detail)<2&&Math.abs((outer?.scrollTop??0)-position.outer)<2)stop()};
   node.addEventListener('wheel',stop,{passive:true});node.addEventListener('touchstart',stop,{passive:true});node.addEventListener('keydown',stop);
   const observer=new ResizeObserver(restore);observer.observe(node);for(const child of node.children)observer.observe(child);const timer=setTimeout(stop,3000);frame=requestAnimationFrame(restore);
   }
  }
  return()=>{withdraw();node.removeEventListener('click',remember,true);window.removeEventListener('workbench-session-expired',withdraw)};
 },[identity,section,professional,root,scope]);
}
