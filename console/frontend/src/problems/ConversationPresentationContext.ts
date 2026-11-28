import {createContext} from 'react';

// A current-page presentation hint; never a routing, work or permission decision.
export const ConversationPresentationContext=createContext<{pureAnswer:boolean;setPureAnswer:(value:boolean,principal:string,scope:string)=>void}|null>(null);
