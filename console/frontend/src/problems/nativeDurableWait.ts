// Read-only projection of the already-authorized exact preparation response.
export type WaitQuestion={invocationId:string;questionKey:string;questionDigest:string;answer:string|null};
type Wait={invocationId:string;questionKey:string;questionDigest:string;state:string;humanExpiresAt:string;answerSaved:boolean;stopConfirmed:boolean};
const states=['QUIESCING','WAITING_FOR_USER','ANSWER_SAVED','CONTINUATION_CLAIMED','ADVANCING','COMPLETED','EXPIRED','BLOCKED'];
const unknown='本题的最新等待状态暂时无法核实，正在读取原记录；不会自动提交回答或重新执行。';
export type WaitView={text:string;canAnswer:boolean;active:boolean;priority:number};
export function durableQuestionState(value:unknown,question:WaitQuestion,runId:unknown,expectedRunId:unknown):WaitView|null{
 if(value===undefined)return null;
 const fail={text:unknown,canAnswer:false,active:true,priority:90};
 if(!Array.isArray(value)||value.length>32||typeof runId!=='string'||!runId||runId!==expectedRunId)return fail;
 const rows:Wait[]=[];
 for(const item of value){
  if(!item||typeof item!=='object')return fail;
  const w=item as Wait;
  if(![w.invocationId,w.questionKey,w.questionDigest].every(v=>typeof v==='string'&&v.length>0)||!states.includes(w.state)||typeof w.answerSaved!=='boolean'||typeof w.stopConfirmed!=='boolean'||typeof w.humanExpiresAt!=='string'||!Number.isFinite(Date.parse(w.humanExpiresAt)))return fail;
  if(rows.some(r=>r.invocationId===w.invocationId&&r.questionKey===w.questionKey))return fail;
  rows.push(w);
 }
 const same=rows.find(w=>w.invocationId===question.invocationId&&w.questionKey===question.questionKey);
 if(!same)return null; // Legacy question or a prior checkpoint, not the current wait.
 if(same.questionDigest!==question.questionDigest)return fail;
 const w=same;
 if(w.answerSaved!==(question.answer!==null))return fail;
 if(w.state==='EXPIRED')return {text:'本题等待期限已到，原问题和已有记录保留；不会自动重跑。',canAnswer:false,active:true,priority:50};
 if(w.state==='BLOCKED')return {text:'当前继续条件尚未满足，暂时无法接续本题；原问题、回答和记录已保留。',canAnswer:false,active:true,priority:60};
 if(w.state==='COMPLETED')return {text:'本题的等待处理已完成；整个任务是否完成，以实际工作步骤和结果为准。',canAnswer:false,active:false,priority:0};
 if(w.state==='ADVANCING')return w.answerSaved&&w.stopConfirmed?{text:'原任务已接续，正在按已保存的回答继续；实际进展以工作步骤为准。',canAnswer:false,active:true,priority:70}:fail;
 if(w.state==='CONTINUATION_CLAIMED')return w.answerSaved&&w.stopConfirmed?{text:'正在接续原任务，已保存的回答不会重复提交。',canAnswer:false,active:true,priority:70}:fail;
 if(w.answerSaved)return {text:w.stopConfirmed?'回答已保存，等待原任务续接；不会重复提交。':'回答已保存，正在准备续接原任务；无需再次提交。',canAnswer:false,active:true,priority:80};
 if(w.state==='ANSWER_SAVED')return fail;
 return {text:'需要你补充一个必要信息；原任务已保留，回答后在本会话继续。',canAnswer:true,active:true,priority:100};
}
