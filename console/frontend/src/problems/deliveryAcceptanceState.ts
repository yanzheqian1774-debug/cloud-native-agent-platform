import {artifactMatchesSource} from './artifactProvenance';
import type {ExecutionView} from '../api/preparedExecution';
export function readableDeliveryPackage(view:ExecutionView){
 const a=view.deliveryAcceptance;
 if(!a||a.status==='UNAVAILABLE'||!['NOT_RECORDED','ACCEPTED','RETRACTED','SUPERSEDED'].includes(a.status)||!a.package||!Array.isArray(a.package.snapshot?.artifacts))return false;
 const items=a.package.snapshot.artifacts;
 return view.artifacts.every(x=>x.contentAccess==='AUTHORIZED'&&typeof x.content==='string'&&artifactMatchesSource(x.content,view.preparation.source_snapshot))&&typeof view.workflowRunId==='string'&&!!view.workflowRunId&&a.package.preparationDigest===view.digest&&a.package.workflowRunId===view.workflowRunId&&/^[a-f0-9]{64}$/.test(a.packageDigest)&&Number.isInteger(a.version)&&a.version>=0&&items.length>0&&items.every(x=>x&&typeof x.artifact_id==='string'&&typeof x.digest==='string')&&new Set(items.map(x=>x.artifact_id)).size===items.length&&JSON.stringify(items.map(x=>[x.artifact_id,x.digest]).sort())===JSON.stringify(view.artifacts.map(x=>[x.artifact_id,x.digest]).sort());
}
export function acceptedDelivery(view:ExecutionView){
 const a=view.deliveryAcceptance;
 return readableDeliveryPackage(view)&&!!a&&a.status==='ACCEPTED'&&a.event?.action==='ACCEPT_DELIVERY'&&a.event.preparationDigest===view.digest&&a.event.workflowRunId===view.workflowRunId&&a.event.packageDigest===a.packageDigest&&a.event.version===a.version&&typeof a.event.actorId==='string'&&a.event.actorId.startsWith('human:');
}
