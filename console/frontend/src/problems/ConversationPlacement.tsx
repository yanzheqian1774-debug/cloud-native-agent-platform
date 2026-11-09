import {type ReactNode} from 'react';
import {createPortal} from 'react-dom';

/** Presentation only: command and authorization owners remain in the caller. */
export function ConversationPlacement({target,children}:{target?:HTMLElement|null;children:ReactNode}){
 return target?createPortal(children,target):<>{children}</>;
}
