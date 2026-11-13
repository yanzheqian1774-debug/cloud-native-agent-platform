import {useEffect,useLayoutEffect,useRef,useState,type UIEvent} from 'react';
import {readConversationView,writeConversationView} from './conversationViewState';

type Anchor={node:Element;offset:number};
export function useConversationScroll({newMessageKey,startAtTop,viewScope,viewId}:{newMessageKey:string;startAtTop:boolean;viewScope?:string;viewId?:string}){
 const stream=useRef<HTMLDivElement>(null),following=useRef(!startAtTop),restoring=useRef(false),anchor=useRef<Anchor|null>(null);
 const [away,setAway]=useState(false),[unread,setUnread]=useState(false);
 const previousKey=useRef(newMessageKey),first=useRef(true),programmatic=useRef(false),expectedScroll=useRef<number|null>(null),interaction=useRef(0),awaitingReply=useRef(false);
 function capture(){const n=stream.current;if(!n)return;const top=n.getBoundingClientRect().top;const candidates=n.querySelectorAll('.private-message p,.private-message tr,.private-message h1,.private-message h2,.private-message h3,.private-message header,.private-message summary,.px-message p,.journey-progress p');const item=Array.from(candidates).find(e=>e.getBoundingClientRect().bottom>top+2);anchor.current=item?{node:item,offset:item.getBoundingClientRect().top-top}:null}
 function save(){const n=stream.current;if(n&&viewScope&&viewId&&!restoring.current)writeConversationView(viewScope,viewId,{scrollTop:n.scrollTop})}
 function position(){const n=stream.current;if(!n)return;programmatic.current=true;if(following.current&&!restoring.current)n.scrollTop=n.scrollHeight;else if(!restoring.current&&anchor.current?.node.isConnected)n.scrollTop+=anchor.current.node.getBoundingClientRect().top-n.getBoundingClientRect().top-anchor.current.offset;expectedScroll.current=n.scrollTop;programmatic.current=false;const off=n.scrollHeight-n.clientHeight-n.scrollTop>72;setAway(off);if(!off)setUnread(false);save()}
 function latest(){awaitingReply.current=true;following.current=true;restoring.current=false;anchor.current=null;setUnread(false);setAway(false);const token=++interaction.current;position();requestAnimationFrame(()=>{if(token===interaction.current)position()})}
 function onScroll(event:UIEvent<HTMLDivElement>){const n=event.currentTarget;const off=n.scrollHeight-n.scrollTop-n.clientHeight>72;setAway(off);if(!programmatic.current&&!restoring.current){if(expectedScroll.current===null||Math.abs(expectedScroll.current-n.scrollTop)>1)following.current=!off;if(off)capture();save()}if(!off)setUnread(false)}
 useLayoutEffect(()=>{
  const n=stream.current;if(!n)return;
  const saved=viewScope&&viewId?readConversationView(viewScope,viewId).scrollTop:undefined;
  restoring.current=saved!==undefined;following.current=saved===undefined&&!startAtTop;
  let frame:number|undefined,replyFrame:number|undefined;
  let pendingReply:{messageId:string;token:number}|null=null;
  let preview=Array.from(n.querySelectorAll('.journey-progress,.native-live-progress')).map(e=>e.textContent).join('\n');
  const restoreOrPosition=()=>{if(restoring.current&&saved!==undefined){programmatic.current=true;n.scrollTop=saved;expectedScroll.current=n.scrollTop;programmatic.current=false;setAway(n.scrollHeight-n.scrollTop-n.clientHeight>72);capture()}else position()};
  const schedule=()=>{if(frame===undefined)frame=requestAnimationFrame(()=>{frame=undefined;restoreOrPosition()})};
  const resize=new ResizeObserver(schedule);resize.observe(n);const observeChildren=()=>{for(const child of n.children)resize.observe(child)};observeChildren();
  const changes=new MutationObserver(()=>{observeChildren();const next=Array.from(n.querySelectorAll('.journey-progress,.native-live-progress')).map(e=>e.textContent).join('\n');if(next&&next!==preview&&!following.current&&!restoring.current)setUnread(true);preview=next;schedule();if(pendingReply)placeReply()});
  changes.observe(n,{subtree:true,childList:true,characterData:true});
  const stopRestore=()=>{awaitingReply.current=false;pendingReply=null;expectedScroll.current=null;restoring.current=false;interaction.current++;capture()};
  const wheel=()=>{stopRestore();following.current=false};
  const touch=()=>{stopRestore();following.current=false};
  const key=(event:KeyboardEvent)=>{if(['ArrowUp','PageUp','Home','PageDown','ArrowDown','End'].includes(event.key)){stopRestore();following.current=false}};
  const pointer=(event:PointerEvent)=>{stopRestore();if(event.clientX>=n.getBoundingClientRect().left+n.clientWidth)following.current=false};
  const details=(event:MouseEvent)=>{const summary=(event.target as Element).closest('summary');if(!summary||!n.contains(summary))return;stopRestore();following.current=false;anchor.current={node:summary,offset:summary.getBoundingClientRect().top-n.getBoundingClientRect().top};schedule()};
  const accepted=(event:Event)=>{const id=(event as CustomEvent<{conversation:string}>).detail?.conversation;if(id&&viewId?.startsWith('private:'+id+':'))latest()};
  function placeReply(){
   if(replyFrame!==undefined||!pendingReply)return;
   replyFrame=requestAnimationFrame(()=>{
    replyFrame=undefined;const value=pendingReply;if(!value)return;
    if(value.token!==interaction.current||(!following.current&&!awaitingReply.current)||restoring.current){pendingReply=null;return;}
    const message=document.getElementById('conversation-message-'+value.messageId);if(!message||!n!.contains(message))return;
    const top=n!.getBoundingClientRect().top,box=message.getBoundingClientRect();
    programmatic.current=true;n!.scrollTop+=box.top-top-12;expectedScroll.current=n!.scrollTop;programmatic.current=false;
    following.current=false;awaitingReply.current=false;pendingReply=null;anchor.current={node:message,offset:message.getBoundingClientRect().top-top};
    setAway(n!.scrollHeight-n!.clientHeight-n!.scrollTop>72);setUnread(false);save();
   });
  }
  const replyReady=(event:Event)=>{
   const value=(event as CustomEvent<{conversation:string;messageId:string}>).detail;
   if(!value?.messageId||!viewId?.startsWith('private:'+value.conversation+':'))return;
   if((!following.current&&!awaitingReply.current)||restoring.current){setUnread(true);return;}
   pendingReply={messageId:value.messageId,token:interaction.current};placeReply();
  };

  n.addEventListener('wheel',wheel,{passive:true});n.addEventListener('touchstart',touch,{passive:true});n.addEventListener('keydown',key);n.addEventListener('pointerdown',pointer);n.addEventListener('click',details,true);window.addEventListener('conversation-message-sent',accepted);window.addEventListener('conversation-reply-ready',replyReady);
  restoreOrPosition();
  return()=>{resize.disconnect();changes.disconnect();if(frame!==undefined)cancelAnimationFrame(frame);if(replyFrame!==undefined)cancelAnimationFrame(replyFrame);n.removeEventListener('wheel',wheel);n.removeEventListener('touchstart',touch);n.removeEventListener('keydown',key);n.removeEventListener('pointerdown',pointer);n.removeEventListener('click',details,true);window.removeEventListener('conversation-message-sent',accepted);window.removeEventListener('conversation-reply-ready',replyReady)};
 // The observers read mutable refs; recreate only when the persisted view changes.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[viewScope,viewId]);
 useEffect(()=>{const changed=previousKey.current!==newMessageKey;previousKey.current=newMessageKey;if(first.current){first.current=false;return}if(restoring.current)return;if(following.current)position();else if(changed)setUnread(true);
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[newMessageKey]);
 return {stream,away,unread,onScroll,latest};
}
export function notifyConversationSend(conversation:string){window.dispatchEvent(new CustomEvent('conversation-message-sent',{detail:{conversation}}))}

export function notifyConversationReply(conversation:string,messageId:string){window.dispatchEvent(new CustomEvent('conversation-reply-ready',{detail:{conversation,messageId}}))}
