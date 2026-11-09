import {useEffect,useState} from 'react';

export function DevelopmentAdministratorNotice({identity,path}:{identity:string|null;path:string}) {
 const [verified,setVerified]=useState<string|null>(null);
 useEffect(()=>{
  if(identity!=='human:development-admin')return;
  let pending:AbortController|undefined;
  const refresh=()=>{
   pending?.abort();const controller=new AbortController();pending=controller;
   fetch('/api/workbench/v1/development-administrator',{credentials:'same-origin',signal:controller.signal})
    .then(async response=>{
     if(!response.ok){if(!controller.signal.aborted)setVerified(null);return;}
     const body=await response.json();
     if(!controller.signal.aborted)setVerified(body.result?.enabled===true&&body.result.subject===identity?path:null);
    }).catch(()=>{if(!controller.signal.aborted)setVerified(null)});
  };
  refresh();window.addEventListener('focus',refresh);
  return()=>{pending?.abort();window.removeEventListener('focus',refresh)};
 },[identity,path]);
 if(identity!=='human:development-admin'||verified!==path)return null;
 return <aside role="note" aria-label="开发超级管理员" style={{margin:'12px 24px',padding:'12px 16px',background:'#eaf3ff',border:'1px solid #b5d4ff',borderRadius:8,color:'#174c87'}}><strong>开发超级管理员 · devadmin</strong><span> 可访问全部测试资源和会话，无需逐项资源审批。操作记录为管理员本人。</span></aside>;
}
