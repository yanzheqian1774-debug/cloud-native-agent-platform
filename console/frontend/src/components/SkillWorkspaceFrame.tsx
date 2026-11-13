import {FrozenNavigationIconContext} from './navigationIconTheme';
import {useLayoutEffect,useRef,type ReactNode} from 'react';

export function WorkspaceFrame({legacyProblems=false,navigationScope,journey=false,brand,home,workspace,navigation,identity,menu,breadcrumb,actions,children}:{legacyProblems?:boolean;navigationScope?:string;journey?:boolean;brand:ReactNode;home?:ReactNode;workspace:ReactNode;navigation:ReactNode;identity:ReactNode;menu:ReactNode;breadcrumb:ReactNode;actions:ReactNode;children:ReactNode}){
 const navigationRef=useRef<HTMLDivElement>(null);
 useLayoutEffect(()=>{
  const node=navigationRef.current;if(!node||!navigationScope)return;
  const key='f3-navigation-scroll:'+navigationScope;let restoring=true,timer:ReturnType<typeof setTimeout>|undefined;
  let saved=0;try{saved=Number(sessionStorage.getItem(key)??0)}catch{/* Optional view coordinates. */}
  const restore=()=>{if(restoring)node.scrollTop=saved};restore();
  const observer=new MutationObserver(restore);observer.observe(node,{childList:true,subtree:true});
  const stop=()=>{restoring=false;observer.disconnect()};
  const scroll=()=>{node.classList.add('is-scrolling');clearTimeout(timer);timer=setTimeout(()=>node.classList.remove('is-scrolling'),900);if(!restoring)try{sessionStorage.setItem(key,String(node.scrollTop))}catch{/* Optional view coordinates. */}};
  node.addEventListener('scroll',scroll);for(const event of ['wheel','pointerdown','keydown'])node.addEventListener(event,stop,{passive:true});
  return()=>{clearTimeout(timer);observer.disconnect();node.removeEventListener('scroll',scroll);for(const event of ['wheel','pointerdown','keydown'])node.removeEventListener(event,stop)};
 },[navigationScope]);
 return <div className={`px-shell skill-workspace-frame f3-workspace-frame${journey?" journey-shell":""}${legacyProblems?" f3-legacy-problems":""}`}><aside className="px-sidebar skill-frame-sidebar"><div className="skill-frame-brand"><FrozenNavigationIconContext value={true}>{brand}{home&&<span className="skill-frame-home">{home}</span>}</FrozenNavigationIconContext></div><div className="skill-frame-workspace">{workspace}</div><div className="skill-frame-navigation" ref={navigationRef}><FrozenNavigationIconContext value={true}>{navigation}</FrozenNavigationIconContext></div></aside><header className="px-topbar skill-frame-header"><div className="skill-frame-menu"><FrozenNavigationIconContext value={true}>{menu}</FrozenNavigationIconContext></div><div className="skill-frame-breadcrumb">{breadcrumb}</div><div className="skill-frame-actions">{actions}<div className="skill-frame-identity">{identity}</div></div></header><div className="px-content skill-frame-content">{children}</div></div>;
}

// Isolated skill previews reuse the production frame.
export const SkillWorkspaceFrame=WorkspaceFrame;
