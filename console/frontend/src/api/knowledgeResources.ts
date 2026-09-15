export type KnowledgeRevision = {
  revisionId: string;
  state: string;
  digest: string;
  predecessorRevisionId?: string;
  createdAt?: string;
  content: {
    name: string;
    source: {
      sourceId: string;
      kind: string;
      provenance: string;
      sourceDescription?: string;
      externalReference?: string;
      fileName?: string;
      mediaType?: string;
      parserVersion?: string;
    };
    documents: Array<{
      documentId: string;
      contentDigest: string;
      chunks: Array<{ chunkId: string; contentDigest: string; content: string; location?: { pageNumber?: number; paragraphNumber?: number } }>;
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
  ingestionJobs: Array<{ jobId: string; status: string; highWaterMark: number; startedAt?: string; completedAt?: string | null }>;
  indexSnapshots: Array<{ snapshotId: string; indexDigest: string; status: string; createdAt?: string }>;
  facts?: Array<{ factId: string; event: string; recordedAt?: string }>;
  retrievals: Array<{
    retrievalId: string;
    authorizationDecisionId: string;
    snapshotId: string;
    queryDigest: string;
    recordedAt: string;
    citations: Array<{
      citationId: string;
      knowledgeId: string;
      revisionId: string;
      revisionDigest: string;
      documentDigest: string;
      chunkDigest: string;
      sourceId: string;
      provenance: string;
      documentId: string;
      chunkId: string;
      content: string;
      location?: { pageNumber?: number; paragraphNumber?: number };
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
const fieldError = /^(INVALID_|EMPTY_|TEXT_LIMIT|SOURCE_LIMIT|CHUNK_LIMIT|IMPORT_SIZE|RESULT_LIMIT)/;
export const knowledgeControlledState = (error: KnowledgeRequestError): KnowledgeControlledState =>
  error.status === 403 ? "denied" : error.status === 404 ? "not found" :
  error.status === 422 || fieldError.test(error.reasonCode) ? "validation error" :
  error.status === 409 ? (error.reasonCode.includes("STALE") ? "stale" : "conflict") :
  error.status === 501 ? "unsupported" : error.status >= 500 ? "backend unavailable" : "retryable";
export const knowledgeErrorMessage = (error: KnowledgeRequestError): string => {
  const reasons: Record<string,string> = {
    DOCUMENT_UPLOAD_LIMIT_EXCEEDED: "文件超过 8 MiB 上限，未进入解析。",
    DOCUMENT_PARSE_TIMEOUT: "文档解析超过 10 秒上限，已终止处理。",
    DOCUMENT_TYPE_MISMATCH: "文件内容、扩展名或声明类型不一致。",
    UNSUPPORTED_DOCUMENT_TYPE: "仅支持含文字层的 PDF 和 .docx 文件。",
    CORRUPT_OR_UNSUPPORTED_PDF: "PDF 已损坏或使用当前解析器不支持的结构。",
    CORRUPT_OR_UNSUPPORTED_DOCX: "DOCX 已损坏或不是有效的 OOXML 文档。",
    PASSWORD_PROTECTED_DOCUMENT_UNSUPPORTED: "不支持密码保护的 PDF。",
    MACRO_ENABLED_DOCUMENT_UNSUPPORTED: "不接收启用宏的 Word 文档。",
    EMBEDDED_PROGRAM_UNSUPPORTED: "文档包含嵌入程序，已拒绝解析。",
    EMPTY_EXTRACTED_TEXT: "没有提取到文字；扫描 PDF 需要 OCR，当前不支持。",
    EXTRACTED_TEXT_LIMIT_EXCEEDED: "提取文字超过 512 KiB 上限。",
    PDF_PAGE_LIMIT_EXCEEDED: "PDF 超过 200 页上限。",
    DOCX_EXPANDED_SIZE_LIMIT_EXCEEDED: "DOCX 解压内容超过 16 MiB 上限。",
    DOCX_EXPANSION_RATIO_EXCEEDED: "DOCX 压缩比异常，已停止解析。",
  };
  if (reasons[error.reasonCode]) return reasons[error.reasonCode];
  const messages: Record<KnowledgeControlledState, string> = {
    "validation error": "字段格式或内容不符合要求，请检查输入后重新提交。",
    denied: "资源不可用或当前访问未获授权。", "not found": "资源不可用或当前访问未获授权。",
    stale: "资源版本已变化，请核对最新版本后明确决定是否再次操作。",
    conflict: "当前生命周期或操作条件不允许此操作，请核对权威状态。",
    "backend unavailable": "知识服务暂不可用，请稍后重新读取。提交结果可能尚未确认，请勿重复执行危险操作。",
    partial: "操作部分完成，请查看后端结果。", retryable: "操作未完成，请检查后端错误。",
    "recovery required": "操作需要恢复，请核对后端状态。", unsupported: "当前接口不支持此操作。",
  };
  return messages[knowledgeControlledState(error)];
};
async function request<T>(path:string,init?:RequestInit):Promise<T>{let response:Response;try{response=await fetch(path,{...init,headers:{Accept:"application/json","Content-Type":"application/json",...init?.headers}})}catch{throw new KnowledgeRequestError("KNOWLEDGE_NETWORK_UNAVAILABLE",503)}const body=await response.json().catch(()=>null);if(!response.ok)throw new KnowledgeRequestError(body?.detail?.reasonCode??"KNOWLEDGE_UNAVAILABLE",response.status);return body as T}
const root="/api/internal/v0.2.2/knowledge";
export const listKnowledge=()=>request<KnowledgeResource[]>(root);
export const getKnowledge=(id:string)=>request<KnowledgeProjection>(`${root}/${encodeURIComponent(id)}`);
export type ParsedLocation = { pageNumber?: number; paragraphNumber?: number };
export type ParsedDocumentPreview = {
  fileName: string;
  declaredMediaType: string;
  detectedFormat: "PDF" | "DOCX";
  detectedMediaType: string;
  sizeBytes: number;
  content: string;
  contentDigest: string;
  segments: Array<{ content: string; location: ParsedLocation }>;
  parserVersion: string;
  originalFilePersisted: false;
  parseDurationMs: number;
  parseTimeLimitSeconds: number;
  limitations: string[];
};
export type KnowledgeInput = { name: string; source: {sourceId?: string; documentId?: string; kind?: string; provenance?: string; sourceDescription?: string; externalReference?: string; fileName?: string; mediaType?: string; parserVersion?: string; contentDigest?: string; segments?: ParsedDocumentPreview["segments"]; content: string} };
export const createKnowledge=(input: KnowledgeInput)=>request<KnowledgeProjection>(root,{method:"POST",body:JSON.stringify(input)});
export async function parseKnowledgeDocument(file: File): Promise<ParsedDocumentPreview> {
  let response: Response;
  try {
    response = await fetch(`${root}/operations/documents/parse?fileName=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": file.type || "application/octet-stream" },
      body: file,
    });
  } catch {
    throw new KnowledgeRequestError("KNOWLEDGE_NETWORK_UNAVAILABLE",503);
  }
  const body = await response.json().catch(()=>null);
  if (!response.ok) throw new KnowledgeRequestError(body?.detail?.reasonCode??"DOCUMENT_PARSE_FAILED",response.status);
  return body as ParsedDocumentPreview;
}
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
export type KnowledgeSearchResult = { classification:string;scoreMeaning:string;topK:number;tokenizerVersion:string;retrievalPolicyVersion:string;fusion:{algorithm:string;k:number};results:Array<{rank:number;score:number;classification:string;lexicalRank:number|null;semanticRank:number|null;citation:{knowledgeId:string;revisionId:string;documentId:string;chunkId:string;content:string;sourceId:string;sourceDescription?:string;externalReference?:string;fileName?:string;provenance:string;location?:ParsedLocation}}> };
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

export const listKnowledgeEvaluations=()=>request<QualityEntity[]>(`${root}/operations/evaluations`);
