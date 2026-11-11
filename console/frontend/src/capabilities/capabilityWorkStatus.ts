import type {PrivateMessage} from '../api/privateConversation';

export function capabilityWorkStatus(source:PrivateMessage,messages:PrivateMessage[]){
 const intents=messages.filter(m=>m.kind==='ACTION_INTENT'&&m.facts?.readable!==false&&m.facts?.action==='CREATE_PROBLEM'&&m.facts?.messageId===source.message_id&&m.facts?.source?.kind==='CAPABILITY');
 if(!intents.length)return {heading:'当前准备 · 未启动',detail:'目标与资料说明已保存，尚未启动任务或调用模型。'};
 const receipts=messages.filter(m=>m.kind==='OWNER_RECEIPT'&&m.facts?.readable!==false&&m.facts?.state==='SUCCEEDED'&&m.facts?.source?.kind==='PROBLEM'&&intents.some(i=>i.facts?.intentId===m.facts?.intentId));
 const targets=new Set(receipts.map(m=>m.facts?.source?.kind==='PROBLEM'?JSON.stringify(m.facts.source.target):''));
 if(targets.size===1&&intents.length===1)return {heading:'当前准备 · 目标已建立',detail:'业务目标已保存。可在本会话继续准备方案，并查看执行进展和返回结果。'};
 return {heading:'当前准备 · 待核验',detail:'本次创建意图已保存，尚未核实唯一创建结果。请在办理记录中核验原动作，避免重复提交。'};
}
