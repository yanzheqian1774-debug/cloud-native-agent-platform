import type {RoutedOwnerTarget} from './ConversationRoutingContext';
/** This receipt describes one supplement and its original accepting stage. */
export function routingReceiptNotice(text:string,target?:RoutedOwnerTarget,recovered=false){
 const excerpt=text.trim().replace(/\s+/g,' ').slice(0,80)+(text.trim().replace(/\s+/g,' ').length>80?'…':'');
 const stage=target?.kind==='UNDERSTANDING'?'资料理解':target?.kind==='PLANNING'?'方案准备':target?.kind==='NATIVE'?'当时的执行追问':'原处理阶段';
 return `补充“${excerpt}”已由${stage}接收。${recovered?'已核对原记录，没有再次提交。':''}后续问题请以当前工作中的提示为准。`;
}
