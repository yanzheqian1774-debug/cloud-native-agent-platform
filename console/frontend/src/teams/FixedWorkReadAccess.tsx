import {useEffect,useRef,useState} from 'react';
import {DigitalEmployeeRequestError,getWorkbenchSession,prepareFixedWorkRead,workbenchPrincipalKey,type WorkbenchSession} from '../api/digitalEmployees';
import type {FixedItem,FixedTeam} from '../api/fixedWorkDrafts';

export function FixedWorkReadAccess({team,item,session,onReady}:{team:FixedTeam;item:FixedItem;session:WorkbenchSession;onReady:()=>void}){
 const principal=workbenchPrincipalKey(session),storageKey='fixed-work-read:'+principal+':'+item.digest;
 const [pending,setPending]=useState(()=>{const old=sessionStorage.getItem(storageKey);return old&&/^fixed-read:[a-f0-9-]{36}$/.test(old)?old:null});
 const [busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[detail,setDetail]=useState('');
 const live=useRef(true),flight=useRef(false),controller=useRef<AbortController|null>(null);
 useEffect(()=>{live.current=true;const withdraw=()=>{live.current=false;controller.current?.abort();setNotice('登录已失效，请重新登录后核对读取权限。');setBusy(false)};window.addEventListener('workbench-session-expired',withdraw);return()=>{live.current=false;controller.current?.abort();window.removeEventListener('workbench-session-expired',withdraw)}},[]);
 async function prepare(newRead=false){if(flight.current||!live.current)return;flight.current=true;setBusy(true);setDetail('');const abort=new AbortController();controller.current=abort;
 try{if(workbenchPrincipalKey(await getWorkbenchSession(abort.signal))!==principal)throw Error('登录身份已变化。');if(!live.current||abort.signal.aborted)return;
 const key=(!newRead&&pending)||'fixed-read:'+crypto.randomUUID();sessionStorage.setItem(storageKey,key);setPending(key);
 const value=await prepareFixedWorkRead(team,item.draft.workId,item.draft.revisionId,{workDigest:item.digest,commandId:key},principal,abort.signal);
 if(workbenchPrincipalKey(await getWorkbenchSession(abort.signal))!==principal)throw Error('登录身份已变化。');if(!live.current||abort.signal.aborted)return;
 if(value.workDigest!==item.digest||!['READ_READY','NO_RECORD'].includes(value.state)||(value.state==='READ_READY'&&(!value.runId||!value.preparationDigest||!/^[a-f0-9]{64}$/.test(value.preparationDigest))))throw Error('读取准备回执尚未核对一致。');
 sessionStorage.removeItem(storageKey);setPending(null);setNotice(value.state==='READ_READY'?'只读访问已核对，记录按当前权限显示。':'当前工作版本尚无执行记录。');onReady();
 }catch(e){if(live.current){setNotice('只读访问尚未核对完成。原工作不会因此重跑，可先刷新记录或按原请求继续核对。');setDetail(e instanceof DigitalEmployeeRequestError?e.reasonCode:e instanceof Error?e.message:'READ_ACCESS_UNVERIFIED')}}finally{flight.current=false;if(live.current)setBusy(false)}}
 return <div className="f3-fixed-read-access"><button disabled={busy} onClick={()=>void prepare()}>{busy?'正在核对读取权限…':pending?'按原请求继续核对读取权限':'读取最近执行与结果'}</button>{['IDEMPOTENCY_PAYLOAD_MISMATCH','RESOURCE_POLICY_DECISION_EXPIRED'].includes(detail)&&<button disabled={busy} onClick={()=>void prepare(true)}>按当前记录重新核对只读权限</button>}<p>仅核对当前账号对本工作最近一次执行及已有结果的读取权限，不启动或重跑工作。</p>{notice&&<p role="status">{notice}</p>}{detail&&<details><summary>技术详情</summary><code>{detail}</code></details>}</div>;
}
