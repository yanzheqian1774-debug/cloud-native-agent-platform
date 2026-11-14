export const resourcePreparationLog='资源核验完成，正在核对执行启动条件。';
export function journeyLogText(value:string){return value==='资源核验完成，正在执行分析并生成结果。'?resourcePreparationLog:value}
export function executionReceiptLog(started:boolean){return started?'执行启动回执已返回，具体进展以任务记录为准。':'执行请求回执已返回，正在核对任务进展。'}
export function executionPreparationFeedback(phase:string,error:string|undefined,hasExecution:boolean,absenceVerified=false){
 if(hasExecution||!['RESOURCES','EXECUTE'].includes(phase)||!/(^|[^A-Z_])ONTOLOGY_EXECUTOR_BINDING_MISMATCH($|[^A-Z_])/.test(error??''))return undefined;
 return {executionPreparation:{absenceVerified},title:'执行准备暂停',railDetail:absenceVerified?'资源配置核对未通过，尚未执行。暂不需要补充资料。':'资源配置核对未通过，执行状态待核实。暂不需要补充资料。',detail:absenceVerified?'已完成问题理解和方案准备，执行前发现资源配置不一致，检查尚未开始。已有内容已保留，暂不需要补充资料。':'执行资源与检查规则的对应关系尚未通过校验，原问题和已保存方案均保留。正在核对原执行记录；是否已经启动尚待确认，不会自动重新提交，暂不需要补充资料。',technical:error};
}
