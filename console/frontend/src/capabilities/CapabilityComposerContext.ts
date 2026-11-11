import {createContext} from 'react';

export const CapabilityComposerContext=createContext<{rail:HTMLElement|null;work:string|null;selectWork:(message:string)=>void;target:HTMLElement|null;active:string|null;select:(message:string|null)=>void}|null>(null);
