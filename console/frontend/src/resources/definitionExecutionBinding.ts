import type {ExecutionView} from '../api/preparedExecution';
import {readDirectoryResource,type DirectoryItem} from '../api/resourceDirectory';
import {getEmployeeDefinition} from '../api/digitalEmployees';
import type {ResourceReadContext} from './resourceReadContext';

/** Recheck exact resource READ and the original saved reference, never a latest version. */
export async function verifyDefinitionExecution(view:ExecutionView,context:ResourceReadContext,signal:AbortSignal){
 const ref=context.reference,kind=context.referenceKind??'skill';
 if(kind==='skill')return view.preparation.participants.some(p=>p.skill.reference.resource_id===ref.resource_id&&p.skill.reference.revision_id===ref.revision_id&&p.skill.reference.digest===ref.digest);
 const detail=await readDirectoryResource({kind,identity:ref.resource_id,revisionId:ref.revision_id} as DirectoryItem,signal);
 if(detail.kind!==kind||detail.identity!==ref.resource_id||detail.revision?.revisionId!==ref.revision_id||detail.revision?.digest!==ref.digest)return false;
 if(kind==='knowledge'){const source=view.preparation.source_snapshot;return source.resource_id===ref.resource_id&&source.revision_id===ref.revision_id&&source.digest===ref.digest}
 for(const participant of view.preparation.participants){
  const r=participant.definition,employee=await getEmployeeDefinition(r.resource_id,r.revision_id,signal);
  if(employee.employeeDefinitionId!==r.resource_id||employee.employeeDefinitionRevisionId!==r.revision_id||employee.employeeDefinitionDigest!==r.digest)throw Error('RESOURCE_EXECUTION_BINDING_MISMATCH');
  if(employee.members.some(m=>m.kind==='AGENT'&&m.resourceId===ref.resource_id&&m.revisionId===ref.revision_id&&m.digest.replace(/^sha256:/,'')===ref.digest))return true;
 }
 return false;
}
