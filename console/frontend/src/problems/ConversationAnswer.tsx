import {useRef,useState} from 'react';
import {useViewString} from './workViewState';

export function ConversationAnswer({storageKey,id,label,button,disabled,onAnswer,question,showQuestion=false}:{showQuestion?:boolean;storageKey:string;id:string;label:string;button:string;disabled:boolean;onAnswer:(text:string)=>Promise<boolean>;question?:string}){
 const [reply,setReply]=useViewString(storageKey,'answer');
 const [sending,setSending]=useState(false),flight=useRef(false);
 // Only offer explicit quoted alternatives from the actual question; never preselect.
 const quoted=[...new Map([...((question??'').matchAll(/《([^《》]{1,80})》|“([^“”]{1,80})”|"([^"\n]{1,80})"/g))].map(m=>[m[1]??m[2]??m[3],m[0]])).entries()];
 // Unquoted options are accepted only with an explicit selection verb and two bounded literal spans.
 const natural=question?.match(/(?:采用|适用|使用|选择)([^，,。？?\n]{1,60})[，,]?\s*还是\s*([^，,。？?\n]{1,60})[？?]?$/);
 const alternatives=natural?[natural[1].trim(),natural[2].trim()]:[];
 const choices=question?.includes('还是')&&quoted.length>=2&&quoted.length<=4?quoted:alternatives.length===2&&alternatives[0]!==alternatives[1]&&!alternatives.some(x=>/还是|是否|不要|不能|不应/.test(x))?alternatives.map(x=>[x,x]):[];
 async function send(){if(flight.current||disabled||!reply.trim())return;flight.current=true;setSending(true);try{if(await onAnswer(reply.trim()))setReply('')}finally{flight.current=false;setSending(false)}}
 return <form className="private-composer f3-answer" onSubmit={e=>{e.preventDefault();void send()}}>
 <label htmlFor={id}>{label}</label>{showQuestion&&question&&<p className="f3-composer-question">{question}</p>}{choices.length>0&&<div className="f3-answer-choices" role="group" aria-label="选择明确选项">{choices.map(c=><button type="button" key={c[0]} disabled={disabled||sending} aria-pressed={reply===c[1]} onClick={()=>setReply(c[1])}>{c[0]}</button>)}</div>}
 <textarea id={id} value={reply} disabled={disabled||sending} maxLength={1800} onChange={e=>setReply(e.target.value)} placeholder="在这里补充，回答后继续原任务"/>
 <button disabled={disabled||sending||!reply.trim()}>{sending?'正在提交…':button}</button><small>输入自动保留；发送后以实际接收状态为准。</small></form>;
}
