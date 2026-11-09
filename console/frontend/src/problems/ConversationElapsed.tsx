import {useEffect,useState} from 'react';
export function ConversationElapsed(){
 const [started]=useState(()=>Date.now()),[seconds,setSeconds]=useState(0);
 useEffect(()=>{const timer=setInterval(()=>setSeconds(Math.floor((Date.now()-started)/1000)),1000);return()=>clearInterval(timer)},[started]);
 return <p className="f3-elapsed" role="status">请求已受理 · 本页本阶段已等待 {seconds} 秒。进展返回后自动更新，无需重复发送。</p>;
}
