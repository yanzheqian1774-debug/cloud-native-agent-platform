import {useState} from "react";
import {inspectGrantRequest,readDraftContextAdmission,type DraftAssistanceResult} from "../api/businessWorkspace";
import {WorkbenchErrorNotice} from "./WorkbenchErrorNotice";

export function DraftAuthorizationStatus({result}:{result:DraftAssistanceResult}){
  const [busy,setBusy]=useState(false),[status,setStatus]=useState<string[]>([]),[error,setError]=useState<unknown>(null);
  async function inspect(){
    setBusy(true);setError(null);
    try{
      const ids=[result.requestAuthorizationRequestId,result.modelAuthorizationRequestId];
      const grants=await Promise.all(ids.map(id=>id?inspectGrantRequest(id):Promise.resolve(null)));
      const context=await readDraftContextAdmission(result.contextId);
      const labels=["草稿辅助","模型调用"];
      setStatus([...grants.map((grant,i)=>`${labels[i]}：${grant?.state==="APPROVED"?"已批准；调用时仍核验有效性":grant?.state==="REJECTED"?"已拒绝":grant?"等待独立决定":"尚无申请"}`),`context 准入：${context.status==="ACTIVE"?"当前有效":"尚未生效或已失效"}`]);
    }catch(reason){setError(reason)}finally{setBusy(false)}
  }
  return <section aria-label="只读授权状态"><button type="button" disabled={busy} onClick={()=>void inspect()}>{busy?"正在查询…":"查看授权状态（只读）"}</button><p>只读取原申请和准入，不提交正文、不派发模型。批准记录不替代调用时的有效权限核验。</p>{status.map(text=><p key={text}>{text}</p>)}{error!==null&&<WorkbenchErrorNotice error={error} operation="刷新 AI 草稿辅助"/>}</section>;
}
