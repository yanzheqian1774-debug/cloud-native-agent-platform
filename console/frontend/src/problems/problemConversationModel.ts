export type ProblemDraft={title:string;description:string};
export type DraftPhase="DRAFT"|"EDITING"|"SUBMITTING"|"UNKNOWN"|"CANCELLED"|"CREATED";
export type DraftTurn={id:string;originalText:string;draft:ProblemDraft;version:number;phase:DraftPhase;source?:"AI_SYNTHETIC"|"AI_PROVIDER"|"MANUAL"};

export function suggestProblemTitle(value:string){
  const first=value.split(/\n|[。！？!?]/).map(item=>item.trim()).find(Boolean)??"待确认的问题";
  return first.slice(0,200);
}
