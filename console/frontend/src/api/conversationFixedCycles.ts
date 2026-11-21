import {conversationRequest} from './privateConversation';
import type {Ref} from './preparedExecution';
type CycleTiming={eventId:string;scheduledAt:string|null;plannedLocalDate:string|null;timezone:string};
export type ExecutingCycleEvent=CycleTiming&{phase:'EXECUTION';recordedAt:string;receiptDigest:string;readTargetDigest:string;preparationDigest:string;runId:string;sourceSnapshot:Ref;readState:'READABLE'|'READ_REQUIRED'|'UNVERIFIED';execution:null|{state:string;version:number}};
export type PlanningCycleEvent=CycleTiming&{phase:'PLANNING';recordedAt:string|null;discoveryDigest:string;receiptDigest:null;readTargetDigest:null;preparationDigest:null;runId:null;sourceSnapshot:null;readState:'UNVERIFIED';execution:null;planningState:'RECORDED'|'REQUIRES_REVIEW'|'PREPARED'};
export type FixedCycleEvent=ExecutingCycleEvent|PlanningCycleEvent;
export type FixedCyclePage={conversationId:string;state:'NO_BOUND_WORK'|'BOUND';bindingDigest:string;workTitle:string;work:Ref;problem:Ref;inputSource:unknown;trigger:{kind:string;timezone:string;localTime:string;cadence:string};items:FixedCycleEvent[];hasMore:boolean;nextCursor:string|null;partial:boolean;answerDelegation?:'UNAVAILABLE'};
export type CycleReadIdentity={conversationId:string;bindingDigest:string;workDigest:string;eventId:string;receiptDigest:string;preparationDigest:string;runId:string;commandId:string;readTargetDigest:string};
export type CycleReadReceipt=Omit<CycleReadIdentity,'readTargetDigest'>&{readTargetDigest:string|null}&{state:'NOT_PREPARED'|'READ_READY'|'EXPIRED'|'UNKNOWN';currentReadTargetDigest:string;readTargetRelation:'SAME'|'STRICT_SUPERSET'|'INCOMPATIBLE'};
const path=(conversation:string)=>'/'+encodeURIComponent(conversation)+'/fixed-work-activity';
export const readConversationCycles=(conversation:string,cursor:string|undefined,signal:AbortSignal)=>conversationRequest<FixedCyclePage>(path(conversation)+(cursor?'?'+new URLSearchParams({cursor}):''),undefined,undefined,signal);
export const readCycleAccessReceipt=(i:CycleReadIdentity,signal:AbortSignal)=>conversationRequest<CycleReadReceipt>(path(i.conversationId)+'/read-access?'+new URLSearchParams({commandId:i.commandId,eventId:i.eventId,receiptDigest:i.receiptDigest}),undefined,undefined,signal);
export const prepareCycleRead=(i:CycleReadIdentity,csrf:string,signal:AbortSignal,previousCommandId?:string)=>{const {conversationId,...body}=i;return conversationRequest<CycleReadReceipt>(path(conversationId)+'/read-access',csrf,{...body,...(previousCommandId?{previousCommandId}:{})},signal)};
const hash=(v:unknown)=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const ref=(v:Ref)=>v&&typeof v.resource_id==='string'&&!!v.resource_id&&typeof v.revision_id==='string'&&!!v.revision_id&&typeof v.digest==='string'&&!!v.digest;
export function verifyCyclePage(p:FixedCyclePage,conversation:string){
 if(p.conversationId!==conversation||!['NO_BOUND_WORK','BOUND'].includes(p.state)||!Array.isArray(p.items)||p.items.length>20||typeof p.partial!=='boolean'||typeof p.hasMore!=='boolean'||(p.hasMore&&(!p.nextCursor||typeof p.nextCursor!=='string')))throw Error('FIXED_CYCLE_PAGE_INVALID');
 if(p.state==='NO_BOUND_WORK'){if(p.items.length)throw Error('FIXED_CYCLE_UNBOUND_EVENTS');return p}
 if(typeof p.workTitle!=='string'||!p.workTitle.trim()||!hash(p.bindingDigest)||!ref(p.work)||!ref(p.problem)||!p.trigger||new Set(p.items.map(i=>i.eventId)).size!==p.items.length)throw Error('FIXED_CYCLE_BINDING_INVALID');
 for(const i of p.items){
  if(!i.eventId||typeof i.timezone!=='string'||!(i.phase==='PLANNING'&&i.recordedAt===null)&&!Number.isFinite(Date.parse(i.recordedAt??'')))throw Error('FIXED_CYCLE_EVENT_INVALID');
  if(i.phase==='PLANNING'){if(!hash(i.discoveryDigest)||i.runId!==null||i.preparationDigest!==null||i.receiptDigest!==null||i.readTargetDigest!==null||i.execution!==null||i.sourceSnapshot!==null||i.readState!=='UNVERIFIED'||!['RECORDED','REQUIRES_REVIEW','PREPARED'].includes(i.planningState))throw Error('FIXED_CYCLE_PLANNING_INVALID');continue}
  if(i.phase!=='EXECUTION'||!i.runId||!hash(i.receiptDigest)||!hash(i.readTargetDigest)||!hash(i.preparationDigest)||!ref(i.sourceSnapshot)||!['READABLE','READ_REQUIRED','UNVERIFIED'].includes(i.readState)||(i.readState!=='UNVERIFIED'&&(!i.scheduledAt||!Number.isFinite(Date.parse(i.scheduledAt)))))throw Error('FIXED_CYCLE_EXECUTION_INVALID');
 }
 return p;
}
export function verifyReadReceipt(value:CycleReadReceipt,expected:CycleReadIdentity){if(!['NOT_PREPARED','READ_READY','EXPIRED','UNKNOWN'].includes(value.state)||Object.entries(expected).some(([k,v])=>k!=='readTargetDigest'&&value[k as keyof CycleReadIdentity]!==v)||(value.state==='NOT_PREPARED'?(value.readTargetDigest!==null||value.currentReadTargetDigest!==expected.readTargetDigest||value.readTargetRelation!=='INCOMPATIBLE'):value.readTargetDigest!==expected.readTargetDigest))throw Error('FIXED_CYCLE_READ_RECEIPT_MISMATCH');return value}
