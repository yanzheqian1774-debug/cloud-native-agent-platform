export type KnowledgeRevision = {
  revisionId: string;
  state: string;
  digest: string;
  content: {
    name: string;
    source: { sourceId: string; kind: string; provenance: string };
    documents: Array<{
      documentId: string;
      contentDigest: string;
      chunks: Array<{ chunkId: string; contentDigest: string; content: string }>;
    }>;
  };
};
export type KnowledgeResource = {
  knowledgeId: string;
  name: string;
  aggregateVersion: number;
  lifecycleState: string;
  archived: boolean;
  currentDraftRevisionId: string | null;
  publishedRevisionId: string | null;
  activeIndexSnapshotId: string | null;
  revisions: KnowledgeRevision[];
  ingestionJobs: Array<{ jobId: string; status: string; highWaterMark: number }>;
  indexSnapshots: Array<{ snapshotId: string; indexDigest: string; status: string }>;
  retrievals: Array<{
    retrievalId: string;
    authorizationDecisionId: string;
    snapshotId: string;
    citations: Array<{
      citationId: string;
      sourceId: string;
      provenance: string;
      documentId: string;
      chunkId: string;
      content: string;
    }>;
  }>;
  purge: { status: string; remainingSnapshotIds: string[] } | null;
  limitations: string[];
};
export type KnowledgeProjection = { knowledge:KnowledgeResource;productProjection:Record<string,unknown>;technicalProjection:Record<string,unknown> };
export class KnowledgeRequestError extends Error {
  reasonCode: string;
  status: number;
  constructor(reasonCode: string, status: number) {
    super(reasonCode);
    this.reasonCode = reasonCode;
    this.status = status;
  }
}
export type KnowledgeControlledState = "validation error"|"denied"|"not found"|"conflict"|"stale"|"backend unavailable"|"partial"|"retryable"|"recovery required"|"unsupported";
export const knowledgeControlledState=(error:KnowledgeRequestError):KnowledgeControlledState=>error.status===403?"denied":error.status===404?"not found":error.status===409?(error.reasonCode.includes("STALE")?"stale":"conflict"):error.status===422?"validation error":error.status===501?"unsupported":error.status>=500?"backend unavailable":"retryable";
async function request<T>(path:string,init?:RequestInit):Promise<T>{let response:Response;try{response=await fetch(path,{...init,headers:{Accept:"application/json","Content-Type":"application/json",...init?.headers}})}catch{throw new KnowledgeRequestError("KNOWLEDGE_NETWORK_UNAVAILABLE",503)}const body=await response.json().catch(()=>null);if(!response.ok)throw new KnowledgeRequestError(body?.detail?.reasonCode??"KNOWLEDGE_UNAVAILABLE",response.status);return body as T}
const root="/api/internal/v0.2.2/knowledge";
export const listKnowledge=()=>request<KnowledgeResource[]>(root);
export const getKnowledge=(id:string)=>request<KnowledgeProjection>(`${root}/${encodeURIComponent(id)}`);
export const createKnowledge=()=>request<KnowledgeProjection>(root,{method:"POST",body:JSON.stringify({name:"Supplier Quality Procedures",source:{sourceId:"source:supplier-quality",documentId:"document:8d-procedure",kind:"TEXT",provenance:"human:quality-owner",content:"Containment begins immediately after a supplier defect.\n\nRoot cause evidence must cite the verified procedure."}})});
export const knowledgeAction=(id:string,action:string,expectedVersion:number,digest?:string)=>request<KnowledgeProjection>(`${root}/${encodeURIComponent(id)}/${action}`,{method:"POST",body:JSON.stringify({expectedVersion,...(digest?{digest}:{})})});
export const createKnowledgeSuccessor = (id: string, expectedVersion: number, content: string) =>
  request<KnowledgeProjection>(`${root}/${encodeURIComponent(id)}/successors`, { method: "POST", body: JSON.stringify({ expectedVersion, content }) });
export const retrieveKnowledge = (id: string, expectedVersion: number, query: string, authorization = "ALLOW") =>
  request<KnowledgeProjection>(`${root}/${encodeURIComponent(id)}/retrievals`, { method: "POST", body: JSON.stringify({ expectedVersion, query, authorization, authorizationDecisionId: `authorization:${crypto.randomUUID()}` }) });
export const purgeKnowledge = (id: string, expectedVersion: number, authorizationId: string, reasonClassification: string) =>
  request<KnowledgeProjection | { purge: Record<string, unknown> }>(`${root}/${encodeURIComponent(id)}/purge`, {
    method: "POST",
    body: JSON.stringify({ expectedVersion, authorizationId, reasonClassification }),
  });
export type KnowledgeSearchResult = { classification:string;topK:number;tokenizerVersion:string;retrievalPolicyVersion:string;fusion:{algorithm:string;k:number};results:Array<{rank:number;score:number;classification:string;lexicalRank:number|null;semanticRank:number|null;citation:{knowledgeId:string;revisionId:string;documentId:string;chunkId:string;content:string;sourceId:string;provenance:string}}> };
export type KnowledgeDashboard = { authorizedKnowledgeCount:number;authorizedChunkCount:number;activeSnapshotCount:number;evaluationRunCount:number;duplicateCandidateCount:number;summaryCount:number;authority:string;semanticIndex:string };
export type QualityEntity = { namespace:string;securityDomain:string;entityType:string;entityId:string;digest:string;body:Record<string,unknown>;decision?:QualityEntity|null };
export type KnowledgeMetadata = Record<"knowledgeId"|"sourceId"|"documentId"|"contentType"|"revisionId"|"snapshotId",string[]>;
export type KnowledgeSearchFilters = Partial<Record<"knowledgeId"|"sourceId"|"documentId"|"contentType"|"revisionId"|"snapshotId",string>>;
export const getKnowledgeDashboard=()=>request<KnowledgeDashboard>(`${root}/operations/dashboard`);
export const getKnowledgeMetadata=()=>request<KnowledgeMetadata>(`${root}/operations/metadata`);
export const searchKnowledge=(query:string,mode:"LEXICAL"|"SEMANTIC"|"HYBRID",topK=5,filters:KnowledgeSearchFilters={})=>request<KnowledgeSearchResult>(`${root}/operations/search`,{method:"POST",body:JSON.stringify({query,mode,topK,...filters})});
export const evaluateKnowledge=(query:string,expectedChunkIds:string[],mode:"LEXICAL"|"SEMANTIC"|"HYBRID"="HYBRID",comparisonToRunId?:string)=>request<QualityEntity>(`${root}/operations/evaluations`,{method:"POST",body:JSON.stringify({datasetVersion:"1",mode,topK:5,cases:[{caseId:"workbench-case",query,expectedChunkIds}],...(comparisonToRunId?{comparisonToRunId}:{})})});
export const summarizeKnowledge=(knowledgeId:string)=>request<Record<string,unknown>>(`${root}/${encodeURIComponent(knowledgeId)}/operations/summaries`,{method:"POST"});
export const scanKnowledgeDuplicates=()=>request<QualityEntity[]>(`${root}/operations/duplicates/scan`,{method:"POST"});
export const getKnowledgeDuplicateQueue=()=>request<QualityEntity[]>(`${root}/operations/duplicates`);
export const decideKnowledgeDuplicate=(candidateId:string,classification:"DUPLICATE"|"DISTINCT"|"NEEDS_INVESTIGATION")=>request<QualityEntity>(`${root}/operations/duplicates/decisions`,{method:"POST",body:JSON.stringify({candidateId,classification})});
export const previewKnowledgeImport=(format:"txt"|"md"|"jsonl",content:string)=>request<QualityEntity>(`${root}/operations/imports/preview`,{method:"POST",body:JSON.stringify({format,content})});
export const executeKnowledgeImport=(jobId:string)=>request<QualityEntity>(`${root}/operations/imports/${encodeURIComponent(jobId)}/execute`,{method:"POST"});
export const exportKnowledge=()=>request<Record<string,unknown>>(`${root}/operations/export`);
