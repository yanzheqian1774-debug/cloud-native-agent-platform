import {useRef,type KeyboardEvent} from 'react';

export function useConversationSubmitKey(canSend:boolean){
 const composing=useRef(false);
 return {
  onCompositionStart:()=>{composing.current=true},
  onCompositionEnd:()=>{composing.current=false},
  onKeyDown:(event:KeyboardEvent<HTMLTextAreaElement>)=>{
   if(event.key!=='Enter'||event.shiftKey||event.altKey||event.ctrlKey||event.metaKey||composing.current||event.nativeEvent.isComposing||event.keyCode===229)return;
   event.preventDefault();event.stopPropagation();
   if(!event.repeat&&canSend)event.currentTarget.form?.requestSubmit();
  },
 };
}
