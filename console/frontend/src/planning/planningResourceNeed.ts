import type {Semantics,Proposal} from './api';

/** Optional declarations still need an exact binding when a task uses them. */
export function needsResourceSelection(semantics:Semantics,origin?:Proposal['origin']){
 // A Human supplement still carries its predecessor execution mapping. Only
 // the existing policy selection owner can form the planning successor.
 if(origin?.kind==='HUMAN_RESOURCE_SUPPLEMENT')return true;
 const used=new Set(semantics.tasks.flatMap(task=>[task.employee_requirement_id,...task.requirement_ids]));
 return semantics.requirements.some(r=>!r.selected&&(r.required||used.has(r.requirement_id)));
}
