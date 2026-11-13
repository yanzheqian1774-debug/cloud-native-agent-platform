import {WorkbenchRequestError} from '../api/businessWorkspace';
export type AdoptionFeedback={title:string;detail:string;technical:string};
export type AdoptionStage='READ'|'SUBMIT'|'RECEIPT'|'JOURNAL';
// These owner guards reject before the adoption record is appended. HTTP status
// alone cannot prove whether an adoption was committed. Even a guard rejection
// cannot exclude another tab having committed the same answer; keep readback.
const prewriteGuards=new Set(['UNDERSTANDING_ADOPTION_RESULT_NOT_ADOPTABLE','UNDERSTANDING_ADOPTION_BUDGET_UNRESOLVED','UNDERSTANDING_ADOPTION_SOURCE_CHANGED','UNDERSTANDING_ADOPTION_QUESTION_CHANGED']);
export function adoptionFeedback(error:unknown,stage:AdoptionStage):AdoptionFeedback{
 const technical=String(error),code=error instanceof WorkbenchRequestError?error.reasonCode:'';
 if(stage==='RECEIPT')return {title:'正在核对回答与原问题的对应关系',detail:'已收到接续返回，但与原问题的对应关系尚未核对完成。原记录保留，不重复提交或调用模型。',technical};
 if(stage==='JOURNAL')return {title:'正在核对原会话接续记录',detail:'已读到回答采用回执，但尚未确认原会话更新。回答已保留，将先核对已有记录，不重新调用模型。',technical};
 if(stage==='SUBMIT'&&error instanceof WorkbenchRequestError&&error.status>=400&&error.status<500&&prewriteGuards.has(code))return {title:'本次接续校验未通过',detail:'原问题和回答均已保留，将先核对是否已有接续记录。无需重新提问，也无需修改回答来解决平台校验问题。',technical};
 if(error instanceof WorkbenchRequestError&&[401,403].includes(error.status))return {title:'当前无法核对回答的接续记录',detail:'访问校验未通过，原问题和回答仍保留。访问恢复后先读取原记录，再确认是否需要继续。',technical};
 if(stage==='READ')return {title:'暂时无法读取回答的接续记录',detail:'尚不能确认回答是否已接回原问题。原记录保留，读取恢复前不重复提交。',technical};
 return {title:'正在核对回答是否已接回',detail:'本次接续的返回状态尚未确认。先读取原接续记录，不重复提交，也不重新调用模型。',technical};
}
