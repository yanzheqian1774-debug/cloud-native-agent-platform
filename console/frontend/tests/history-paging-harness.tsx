import {useState} from 'react';
import {createRoot} from 'react-dom/client';
import {BrowserRouter} from 'react-router-dom';
import {PreparedExecutionPanel} from '../src/problems/PreparedExecutionPanel';
import type {ExecutionPhaseProjection} from '../src/api/preparedExecution';
export function InlineCallbackParent(){
 const [projection,setProjection]=useState<ExecutionPhaseProjection|null>(null),[renders,setRenders]=useState(0),[context,setContext]=useState(0);
 return <><output data-testid="projection">{projection?.state??'waiting'} / {renders}</output><button onClick={()=>setRenders(value=>value+1)}>父组件刷新</button><button onClick={()=>setContext(value=>value+1)}>切换查看上下文</button><PreparedExecutionPanel digest={'a'.repeat(64)} problemId="p" contextKey={'fixture:'+context} blocked={true} csrfToken="synthetic" readOnly onBusy={()=>{}} onProgress={value=>setProjection({...value})}/></>;
}
createRoot(document.getElementById('root')!).render(<BrowserRouter><InlineCallbackParent/></BrowserRouter>);
