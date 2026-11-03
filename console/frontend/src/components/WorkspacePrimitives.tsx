import { useId, type ReactNode, type KeyboardEvent } from "react";

export function PageHeader({eyebrow,title,description,actions}:{eyebrow?:string;title:string;description?:ReactNode;actions?:ReactNode}) {
  return <header className="px-shared-page-header"><div>{eyebrow&&<p className="px-eyebrow">{eyebrow}</p>}<h1>{title}</h1>{description&&<p>{description}</p>}</div>{actions&&<div className="px-page-actions">{actions}</div>}</header>;
}

export function WorkspaceTabs<T extends string>({label,value,tabs,onChange,children}:{label:string;value:T;tabs:readonly {value:T;label:string}[];onChange:(value:T)=>void;children:ReactNode}) {
  const id=useId();
  const select=(event:KeyboardEvent<HTMLButtonElement>,index:number)=>{
    let next:number;
    if(event.key==="ArrowRight")next=(index+1)%tabs.length;
    else if(event.key==="ArrowLeft")next=(index+tabs.length-1)%tabs.length;
    else if(event.key==="Home")next=0;
    else if(event.key==="End")next=tabs.length-1;
    else return;
    event.preventDefault();onChange(tabs[next].value);
    document.getElementById(`${id}-tab-${tabs[next].value}`)?.focus();
  };
  return <><div className="px-shared-tabs" role="tablist" aria-label={label}>{tabs.map((tab,index)=><button type="button" role="tab" key={tab.value} id={`${id}-tab-${tab.value}`} aria-selected={value===tab.value} aria-controls={`${id}-panel`} tabIndex={value===tab.value?0:-1} onKeyDown={e=>select(e,index)} onClick={()=>onChange(tab.value)}>{tab.label}</button>)}</div><section id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-tab-${value}`} tabIndex={0}>{children}</section></>;
}

export function StatusBadge({tone="neutral",children}:{tone?:"neutral"|"info"|"success"|"warning"|"danger";children:ReactNode}) {
  return <span className={`px-status ${tone}`}>{children}</span>;
}
