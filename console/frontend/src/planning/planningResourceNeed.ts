import type {Semantics} from './api';

/** Optional declarations still need an exact binding when a task uses them. */
export function needsResourceSelection(semantics:Semantics){
 const used=new Set(semantics.tasks.flatMap(task=>[task.employee_requirement_id,...task.requirement_ids]));
 return semantics.requirements.some(r=>!r.selected&&(r.required||used.has(r.requirement_id)));
}
