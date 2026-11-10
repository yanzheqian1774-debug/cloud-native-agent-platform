import type {ReactNode} from 'react';
import {useViewString} from './workViewState';

/** View-only disclosure state; never an execution or authorization receipt. */
export function RememberedDetails({viewKey,name,summary,children,className}:{viewKey?:string;name:string;summary:ReactNode;children:ReactNode;className?:string}){
 const [value,setValue]=useViewString(viewKey,name,'closed');
 const open=value==='open';
 return <details className={className} open={open} onToggle={e=>{if(e.currentTarget.open!==open)setValue(e.currentTarget.open?'open':'closed')}}><summary>{summary}</summary>{children}</details>;
}
