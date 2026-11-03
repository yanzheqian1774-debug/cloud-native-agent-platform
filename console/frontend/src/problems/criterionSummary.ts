import type {CriterionRevision} from "../api/businessWorkspace";

/** Human-readable text only from the exact owner record; no evaluator inference. */
export function criterionSummary(item:CriterionRevision):string{
 for(const value of [item.measurement.rubric,item.applicability.description]){
  if(typeof value==="string"&&value.trim())return value;
 }
 return item.criterion_type==="DETERMINISTIC_BOOLEAN"?"布尔值标准，当前记录未提供文字说明":"当前记录未提供标准说明";
}
