import {createContext,useContext,useEffect,useRef} from 'react';

export type RoutedOwnerTarget={kind:'NATIVE'|'PLANNING'|'UNDERSTANDING';journalVersion?:number;journeyKey?:string;problemId?:string;invocationId:string;contextId?:string;turnId?:string;turnVersion?:number;aggregateVersion?:number;questionKey?:string;questionDigest?:string;executionDigest?:string};
export type RoutedOwnerReceipt=boolean|{state:'REJECTED'|'UNKNOWN'|'ACCEPTED'};
export type RoutedOwner={target:RoutedOwnerTarget;onAnswer:(text:string,messageId:string,receipt?:{requestKey:string})=>Promise<RoutedOwnerReceipt>};
export type ConversationRoutingValue={enabled:boolean;send?:(text:string)=>Promise<boolean>;registerOwner:(owner:RoutedOwner)=>()=>void};
export const ConversationRoutingContext=createContext<ConversationRoutingValue>({enabled:false,registerOwner:()=>()=>{}});
/** Registration is presentation wiring, never permission to answer an owner. */
export function useConversationRouteOwner(owner:RoutedOwner|null){
 const {enabled,registerOwner}=useContext(ConversationRoutingContext),latest=useRef(owner);
 useEffect(()=>{latest.current=owner},[owner]);
 const identity=owner?JSON.stringify(owner.target):'';
 useEffect(()=>{
  if(!enabled||!identity)return;
  const target=JSON.parse(identity) as RoutedOwnerTarget;
  return registerOwner({target,onAnswer:(text,message,receipt)=>JSON.stringify(latest.current?.target)===identity?latest.current!.onAnswer(text,message,receipt):Promise.resolve({state:'REJECTED'})});
 },[enabled,registerOwner,identity]);
 return enabled;
}
