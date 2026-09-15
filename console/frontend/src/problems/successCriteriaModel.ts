export type SuccessCriterionKind="HUMAN_EVALUATED";
export type SuccessCriterionDraft={text:string;kind:SuccessCriterionKind|null};
export type SuccessCriterionDraftPhase="DRAFT"|"EDITING"|"SAVING_CRITERION"|"SAVING_SET"|"UNKNOWN_CRITERION"|"UNKNOWN_SET"|"CRITERION_FAILED"|"SET_FAILED"|"CONFLICT"|"SAVED"|"CANCELLED";
export type CriterionSource={successCriterionId:string;revisionId:string;revision:number};
export type CriteriaSetBase={setRevisionId:string;revision:number;orderedCriterionRevisionIds:string[]};
export type CriterionWritePayload={successCriterionId?:string;predecessorRevisionId?:string;expectedVersion?:number;criterionType:"HUMAN_EVALUATED";measurement:{rubric:string};requiredEvidenceKinds:string[];evaluatorType:string;evaluatorVersion:string;applicability:Record<string,unknown>};
export type CriteriaSetWritePayload={problemRevisionId:string;predecessorSetRevisionId?:string;orderedCriterionRevisionIds:string[];expectedVersion:number};
export type PendingCriterionSave={criterionPayload:CriterionWritePayload;criterionKey:string;setKey:string;problemRevisionId:string;expectedProblemVersion:number;setPayload?:CriteriaSetWritePayload;criterionRevisionId?:string};
export type SuccessCriterionTurn={id:string;problemId:string;problemRevisionId:string;originalText:string;draft:SuccessCriterionDraft;version:number;phase:SuccessCriterionDraftPhase;source?:CriterionSource;baseSet?:CriteriaSetBase;pending?:PendingCriterionSave};

export function createSuccessCriterionTurn(problemId:string,problemRevisionId:string,text:string,baseSet?:CriteriaSetBase,source?:CriterionSource):SuccessCriterionTurn{
  return {id:crypto.randomUUID(),problemId,problemRevisionId,originalText:text,draft:{text,kind:source?"HUMAN_EVALUATED":null},version:1,phase:"DRAFT",baseSet,source};
}
