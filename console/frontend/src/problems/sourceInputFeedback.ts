import type {ConversationInputSourceReference,SourceInputObservation} from '../api/draftAssistanceTypes';
type SourceIdentity=Pick<ConversationInputSourceReference,"source"|"sourceSchema">&{sourceContentDigest?:string};
export function sameSelectedSource(a:SourceIdentity|undefined|null,b:SourceIdentity|undefined|null){return Boolean(a&&b&&a.sourceContentDigest&&b.sourceContentDigest&&a.source.resource_id===b.source.resource_id&&a.source.revision_id===b.source.revision_id&&a.source.digest===b.source.digest&&a.sourceContentDigest===b.sourceContentDigest&&a.sourceSchema===b.sourceSchema)}
export function sourceInputFeedback(observation:SourceInputObservation|undefined,capability:string|undefined){
 if(observation?.state==='BODY_CONTEXT')return undefined;
 if(observation?.state==='METADATA_ONLY')return {title:'系统待接续资料处理',detail:'已核实本次回答使用了所选资料的信息，未包含资料正文。资料选择已保留，无需重复上传或重新描述。'+(capability==='METADATA_ONLY'?'当前正文接入尚未启用。':capability==='BODY_SUPPORTED'?'当前已具备正文接入能力，本次旧回答尚未重新处理。':'当前可用的正文接入能力仍需核对。')};
 return {title:'资料处理状态待核对',detail:'所选资料已保留，但尚未核实本次回答使用的资料上下文。当前无需重复上传；系统不会自动重新提交问题。'};
}
