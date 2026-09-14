export type SuccessCriterionKind="HUMAN_EVALUATED";
export type SuccessCriterionDraft={text:string;kind:SuccessCriterionKind|null};
export type SuccessCriterionDraftPhase="DRAFT"|"EDITING"|"CONFIRMED"|"CANCELLED";
export type SuccessCriterionTurn={
  id:string;
  problemId:string;
  problemRevisionId:string;
  originalText:string;
  draft:SuccessCriterionDraft;
  version:number;
  phase:SuccessCriterionDraftPhase;
};

export function createSuccessCriterionTurn(problemId:string,problemRevisionId:string,text:string):SuccessCriterionTurn{
  return {id:crypto.randomUUID(),problemId,problemRevisionId,originalText:text,draft:{text,kind:null},version:1,phase:"DRAFT"};
}
