import {DeliveryArtifactView} from './DeliveryArtifactView';
import {TabularArtifactView} from './TabularArtifactView';
import {NativeLoopTrace} from './NativeLoopTrace';
import {nativeDataReport,nativeDataExecutorMatches} from './nativeDataReport';
import {RememberedDetails} from './RememberedDetails';
export function NativeDataArtifactView({content,query='',viewKey='native-data',participant}:{content:string;query?:string;viewKey?:string;participant:unknown}){
 if(!nativeDataExecutorMatches(content,participant))return <p role="alert">报告执行资源与本次任务不一致，暂不展示结果。</p>;
 let stage:unknown;try{stage=JSON.parse(content)}catch{stage=null}
 if(stage&&typeof stage==='object'&&'operation' in stage&&stage.operation!=='RENDER_REPORT')return <pre>{content}</pre>;
 const value=nativeDataReport(content);
 if(!value)return <p role="alert">报告核验依据不完整或与本次资料不一致，暂不展示分析结果。原产物记录保留。</p>;
 return <section aria-label="自主资料分析结果"><p>依据本次资料快照核对并形成报告；不代表业务问题已解决或批准后续操作。</p>{value.kind==='synthetic-delivery-output.v1'?<DeliveryArtifactView content={value.content} query={query} inline viewKey={viewKey+':report'}/>:<TabularArtifactView content={value.content}/>}<RememberedDetails viewKey={viewKey} name="native-data-trace" summary="查看逐步分析过程与核验依据"><NativeLoopTrace loop={value.loop}/></RememberedDetails></section>;
}
