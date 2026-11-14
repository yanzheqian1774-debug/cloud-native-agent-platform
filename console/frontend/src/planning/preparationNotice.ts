const notices:Record<string,string>={
 BLOCKED_CAPABILITY_READ_UNAVAILABLE:'方案准备暂时暂停：尚未完成执行资源的读取，不能据此判断缺少工具。已保存的问题理解和资料保留；本次准备尚未调用规划模型。请在读取恢复后重新核实。',
 BLOCKED_CAPABILITY_UNVERIFIED:'方案准备暂时暂停：执行资源的适用性尚未核实，不能据此判断缺少工具。已保存的问题理解和资料保留；本次准备尚未调用规划模型。请重新核实后继续。',
 QUESTION_INPUT_SERVICE_UNAVAILABLE:'方案准备服务暂不可用，已保存的问题理解和已确认资料均保留。本次准备尚未调用规划模型；服务恢复后可在原会话重新核实并继续。',
 QUESTION_INPUT_SERVICE_ACCESS_DENIED:'方案准备服务的访问校验未通过，已保存的问题理解和资料均保留。本次准备尚未调用规划模型；访问恢复后可重新核实并继续。',
};
export function preparationNotice(value:string|undefined){return Object.entries(notices).find(([code])=>value?.includes(code))?.[1]}
export function activityInputFailure(state:string){return preparationNotice(state)??(state==='BLOCKED_MISSING_COMPATIBLE_TOOLS'?'已核实的执行资源尚缺少本次所需工具，方案尚未开始生成。':state==='BLOCKED_ACTION_OUTSIDE_READONLY_CONTEXT'?'本次请求包含已授权只读分析之外的行动，未开始执行。':state==='BLOCKED_PROCESS_CONTEXT_NOT_AVAILABLE'?'尚未取得业务流程实例，不能虚构当前活动。':'当前未取得可读、已授权的业务来源，未开始规划或执行。')}
