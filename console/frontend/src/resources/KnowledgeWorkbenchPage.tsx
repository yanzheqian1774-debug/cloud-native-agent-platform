import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  createKnowledge, createKnowledgeSuccessor, getKnowledge, knowledgeAction, listKnowledge,
  purgeKnowledge, retrieveKnowledge, KnowledgeRequestError, knowledgeControlledState,
  knowledgeErrorMessage, getKnowledgeDashboard, searchKnowledge, evaluateKnowledge,
  summarizeKnowledge, scanKnowledgeDuplicates, previewKnowledgeImport, exportKnowledge,
  executeKnowledgeImport, getKnowledgeDuplicateQueue, getKnowledgeMetadata,
  decideKnowledgeDuplicate, listKnowledgeEvaluations, parseKnowledgeDocument,
  type KnowledgeInput, type KnowledgeProjection, type KnowledgeResource,
  type KnowledgeDashboard, type KnowledgeSearchResult, type KnowledgeMetadata, type QualityEntity,
  type ParsedDocumentPreview,
} from "../api/knowledgeResources";
import { KnowledgeTechnicalProjection } from "./KnowledgeTechnicalProjection";
import { knowledgeLocation, knowledgeTime } from "./knowledgePresentation";
import "./KnowledgeWorkbenchPage.css";

const emptyInput = (): KnowledgeInput => ({name:"",source:{kind:"TEXT",sourceDescription:"",externalReference:"",content:""}});
const bytes = (text: string) => new TextEncoder().encode(text.normalize("NFC")).length;
function contentError(text: string): string | null {
  const normalized = text.normalize("NFC").replace(/\r\n?/g,"\n");
  if (!normalized.trim()) return "请输入知识正文。";
  if (bytes(normalized) > 512 * 1024) return "正文不能超过512 KiB。";
  if ([...normalized].some(char => /\p{Cc}/u.test(char) && char !== "\n" && char !== "\t")) return "正文包含不允许的控制字符。";
  if (normalized.split(/\n\s*\n/).some(part => bytes(part.trim()) > 4096)) return "单个段落不能超过4 KiB，请分段后提交。";
  return null;
}
function inputError(input: KnowledgeInput): string | null {
  if (!input.name.trim() || bytes(input.name) > 500 || /\p{Cc}/u.test(input.name)) return "名称不能为空、包含控制字符或超过500 UTF-8字节。";
  if (!input.source.sourceDescription?.trim() || bytes(input.source.sourceDescription) > 2000) return "请填写来源说明，且不超过2000 UTF-8字节。";
  if (input.source.externalReference && bytes(input.source.externalReference) > 2000) return "外部编号不能超过2000 UTF-8字节。";
  return contentError(input.source.content);
}
const labels: Record<string,string> = {DRAFT:"草稿",VALIDATED:"已校验",HUMAN_REVIEWED:"已人工审阅",PUBLISHED:"已发布",AVAILABLE:"可用",ARCHIVED:"已归档",RECOVERY_REQUIRED:"需要恢复",COMPLETED:"已完成",PARTIAL:"部分完成",PREVIEW:"预览",FAILED:"失败",ACTIVE:"生效"};
const status = (value: string) => `${labels[value] ?? value} · ${value}`;

export function KnowledgeWorkbenchPage() {
  const [params] = useSearchParams();
  const [reload,setReload] = useState(0);
  return <KnowledgeWorkbench key={`${params.get("resourceId") ?? ""}:${reload}`} refresh={()=>setReload(value=>value+1)}/>;
}

function KnowledgeWorkbench({refresh}:{refresh:()=>void}) {
  const [params,setParams] = useSearchParams();
  const id = params.get("resourceId") ?? "";
  const filter = params.get("q") ?? "";
  const revisionId = params.get("revisionId") ?? "";
  const returnFocus = params.get("returnFocus") === "list";
  const view = params.get("view") === "technical" ? "TECHNICAL" : "PRODUCT";
  const [items,setItems] = useState<KnowledgeResource[]>([]);
  const [selected,setSelected] = useState<KnowledgeProjection|null>(null);
  const [dashboard,setDashboard] = useState<KnowledgeDashboard|null>(null);
  const [metadata,setMetadata] = useState<KnowledgeMetadata|null>(null);
  const [state,setState] = useState<"LOADING"|"READY"|"SAVING"|"ERROR">("LOADING");
  const [error,setError] = useState<KnowledgeRequestError|null>(null);
  const [notice,setNotice] = useState("");
  const [fieldError,setFieldError] = useState("");
  const [input,setInput] = useState<KnowledgeInput>(emptyInput);
  const [createMode,setCreateMode] = useState<"UPLOAD"|"TEXT">("UPLOAD");
  const [selectedFile,setSelectedFile] = useState<File|null>(null);
  const [parsePreview,setParsePreview] = useState<ParsedDocumentPreview|null>(null);
  const [dragActive,setDragActive] = useState(false);
  const [successorContent,setSuccessorContent] = useState("");
  const [query,setQuery] = useState("");
  const [searchMode,setSearchMode] = useState<"LEXICAL"|"SEMANTIC"|"HYBRID">("HYBRID");
  const [searchFilters,setSearchFilters] = useState<Record<string,string>>({});
  const [searchResult,setSearchResult] = useState<KnowledgeSearchResult|null>(null);
  const [evaluations,setEvaluations] = useState<QualityEntity[]>([]);
  const [evaluationRun,setEvaluationRun] = useState<QualityEntity|null>(null);
  const [operationResult,setOperationResult] = useState<unknown>(null);
  const [importFormat,setImportFormat] = useState<"txt"|"md"|"jsonl">("txt");
  const [importContent,setImportContent] = useState("");
  const [importJob,setImportJob] = useState<QualityEntity|null>(null);
  const [duplicateQueue,setDuplicateQueue] = useState<QualityEntity[]>([]);
  const [authorizationId,setAuthorizationId] = useState("");
  const [reasonClassification,setReasonClassification] = useState("");
  const [recovery,setRecovery] = useState<{attemptedVersion:number; authoritativeVersion:number}|null>(null);
  const epoch = useRef(0), locked = useRef(false);
  const createDialog = useRef<HTMLDialogElement>(null), purgeDialog = useRef<HTMLDialogElement>(null);
  const createTrigger = useRef<HTMLButtonElement>(null), purgeTrigger = useRef<HTMLButtonElement>(null);
  const listHeading = useRef<HTMLHeadingElement>(null);
  const detailHeading = useRef<HTMLHeadingElement>(null);
  const value = selected?.knowledge.knowledgeId === id ? selected.knowledge : undefined;
  const busy = state === "SAVING" || state === "LOADING";
  const selectedIdentity = value?.knowledgeId;
  useEffect(() => {if (selectedIdentity) detailHeading.current?.focus();}, [selectedIdentity]);

  function navigate(values: Record<string,string>, replace = false) {
    const next = new URLSearchParams(params);
    Object.entries(values).forEach(([key,val]) => val ? next.set(key,val) : next.delete(key));
    setParams(next,{replace});
  }
  // Every read/action belongs to one resource generation. Navigation invalidates late responses.
  useEffect(() => {
    const generation = epoch;
    const ticket = ++generation.current;
    Promise.all([listKnowledge(),getKnowledgeDashboard(),getKnowledgeMetadata(),id ? getKnowledge(id) : Promise.resolve(null)])
      .then(([resources,summary,filters,projection]) => {
        if (ticket !== epoch.current) return;
        setItems(resources); setDashboard(summary); setMetadata(filters); setSelected(projection); setState("READY");
        if (!id && returnFocus) listHeading.current?.focus();
      }).catch(reason => {if(ticket === epoch.current) {setError(asError(reason)); setState("ERROR");}});
    return () => {generation.current = ticket + 1;};
  },[id,returnFocus]);

  function asError(reason: unknown) {return reason instanceof KnowledgeRequestError ? reason : new KnowledgeRequestError("KNOWLEDGE_UNAVAILABLE",503);}
  async function run<T>(operation:()=>Promise<T>, apply:(result:T)=>void, message="操作已由后端记录。") {
    if (locked.current) return;
    locked.current = true;
    const ticket = epoch.current, captured = value;
    setState("SAVING"); setError(null); setNotice(""); setFieldError("");
    try {
      const result = await operation();
      if (ticket !== epoch.current) return;
      apply(result); setNotice(message);
      const [summary, filters] = await Promise.allSettled([getKnowledgeDashboard(), getKnowledgeMetadata()]);
      if (ticket !== epoch.current) return;
      setDashboard(summary.status === "fulfilled" ? summary.value : null);
      setMetadata(filters.status === "fulfilled" ? filters.value : null);
      setState("READY");
    } catch (reason) {
      if (ticket !== epoch.current) return;
      const failure = asError(reason); setError(failure); setState("ERROR");
      if (knowledgeControlledState(failure) === "stale" && captured) {
        try {
          const authoritative = await getKnowledge(captured.knowledgeId);
          if (ticket !== epoch.current) return;
          setSelected(authoritative); setRecovery({attemptedVersion:captured.aggregateVersion,authoritativeVersion:authoritative.knowledge.aggregateVersion});
        } catch (fetchError) {if(ticket === epoch.current) setError(asError(fetchError));}
      }
    } finally {if(ticket === epoch.current) locked.current = false;}
  }
  function applyProjection(projection: KnowledgeProjection) {
    setSelected(projection);
    setItems(current => current.some(item => item.knowledgeId === projection.knowledge.knowledgeId)
      ? current.map(item => item.knowledgeId === projection.knowledge.knowledgeId ? projection.knowledge : item)
      : [...current,projection.knowledge]);
  }
  function act(action: string,digest?: string) {
    if(value) void run(()=>knowledgeAction(value.knowledgeId,action,value.aggregateVersion,digest),applyProjection);
  }
  function create() {
    const problem = inputError(input); if(problem) {setFieldError(problem); return;}
    void run(()=>createKnowledge(input),projection=>{
      createDialog.current?.close(); setInput(emptyInput()); setSelectedFile(null); setParsePreview(null);
      navigate({resourceId:projection.knowledge.knowledgeId,revisionId:"",digest:""});
    },"知识草稿已创建，系统身份已由后端生成；尚未校验、发布或索引。");
  }
  function chooseFile(file: File | undefined) {
    if (!file) return;
    setSelectedFile(file); setParsePreview(null); setFieldError("");
    if (file.size > 8*1024*1024) {setFieldError("文件超过 8 MiB 上限，未提交解析。");return;}
    void run(()=>parseKnowledgeDocument(file),preview=>{
      setParsePreview(preview);
      setInput(current=>({
        name: current.name || preview.fileName.replace(/\.(pdf|docx)$/i,""),
        source:{
          ...current.source,
          kind:preview.detectedFormat,
          fileName:preview.fileName,
          mediaType:preview.detectedMediaType,
          parserVersion:preview.parserVersion,
          content:preview.content,
          contentDigest:preview.contentDigest,
          segments:preview.segments,
        },
      }));
    },"解析预览已生成；原文件未保存，确认后只创建知识草稿。");
  }
  function switchCreateMode(mode:"UPLOAD"|"TEXT") {
    setCreateMode(mode); setFieldError(""); setSelectedFile(null); setParsePreview(null);
    setInput(emptyInput());
  }
  function successor() {
    if(!value) return;
    const problem = contentError(successorContent); if(problem) {setFieldError(problem); return;}
    void run(()=>createKnowledgeSuccessor(value.knowledgeId,value.aggregateVersion,successorContent),projection=>{
      applyProjection(projection); setSuccessorContent(""); navigate({revisionId:"",digest:""},true);
    },"后继草稿已创建，已发布历史保持不变。");
  }
  function validQuery() {
    if(!query.trim() || bytes(query)>2000 || /\p{Cc}/u.test(query)) {setFieldError("检索词不能为空、包含控制字符或超过2000 UTF-8字节。");return false;} return true;
  }
  function retrieve(authorization="ALLOW") {
    if(value && validQuery()) void run(()=>retrieveKnowledge(value.knowledgeId,value.aggregateVersion,query,authorization),applyProjection,"检索已记录；请核对返回引用，空结果不代表已引用。");
  }
  function search() {
    if(value && validQuery()) void run(()=>searchKnowledge(query,searchMode,5,{...searchFilters,knowledgeId:value.knowledgeId}),setSearchResult,"检索实验已完成；结果不代表执行Evidence。");
  }
  function previewImport() {
    const size = bytes(importContent);
    if(!importContent.trim() || size > (importFormat === "jsonl" ? 5 : 1)*1024*1024) {setFieldError("请输入导入内容；TXT/Markdown最多1 MiB，JSONL最多5 MiB。后台仍会校验逐条记录。");return;}
    setImportJob(null);
    void run(()=>previewKnowledgeImport(importFormat,importContent),setImportJob,"预览已生成，尚未导入；仅后端接受的记录可创建草稿。");
  }
  function purge() {
    if(!value) return;
    if(!authorizationId.trim() || !reasonClassification.trim()) {setFieldError("请输入授权标识和非敏感原因分类。");return;}
    void run(()=>purgeKnowledge(value.knowledgeId,value.aggregateVersion,authorizationId,reasonClassification),result=>{
      purgeDialog.current?.close();
      if("knowledge" in result) {applyProjection(result);setOperationResult(result);}
      else {setSelected(null);setItems(current=>current.filter(item=>item.knowledgeId!==value.knowledgeId));setOperationResult(result);}
    },"清除响应已收到，请核对完成或需要恢复状态；不得自动重放。");
  }
  const currentRevision = value?.revisions.find(item=>item.revisionId === (value.currentDraftRevisionId ?? value.publishedRevisionId));
  const shownRevision = revisionId ? value?.revisions.find(item=>item.revisionId===revisionId) : currentRevision;
  const exactMismatch = !!value && (!!revisionId && !shownRevision || !!params.get("digest") && params.get("digest") !== shownRevision?.digest);
  const importBody = importJob?.body as {status?:string;processedCount?:number;recordCount?:number;inputRecordCount?:number;previewRejectedCount?:number;acceptedCount?:number;rejectedCount?:number;retryable?:boolean;records?:Array<{name:string;content:string}>;importedKnowledgeIds?:string[]}|undefined;
  const latestJob = value?.ingestionJobs.at(-1);
  const needsRecovery = value?.lifecycleState === "RECOVERY_REQUIRED";
  const source = shownRevision?.content.source;
  const latestRecordedAt = value?.facts?.at(-1)?.recordedAt ?? shownRevision?.createdAt;
  const visible = items.filter(item=>`${item.name} ${item.knowledgeId} ${item.lifecycleState}`.toLowerCase().includes(filter.toLowerCase()));

  return <main className="agent-workbench knowledge-workbench">
    <header><p className="eyebrow">企业 Knowledge 资源工作台</p><h1>知识中心</h1><p>管理知识来源、不可变修订、检索与引用。生命周期由后端持有。</p></header>
    <nav className="knowledge-zones" aria-label="知识中心操作分区"><a href="#document-list">文档列表</a><a href="#document-detail">文档详情与处理记录</a><a href="#retrieval-test">检索测试与出处</a><a href="#advanced-management">高级管理</a></nav>
    {state==="LOADING"&&<p role="status">正在读取授权知识资源…</p>}
    {state==="SAVING"&&<p role="status">正在提交，请勿重复操作…</p>}
    {notice&&<div role="status" className="notice">{notice}<button onClick={()=>setNotice("")}>关闭提示</button></div>}
    {error&&<div role="alert"><strong>{knowledgeErrorMessage(error)}</strong><code>{error.reasonCode}</code><button disabled={busy} onClick={refresh}>重新读取权威数据</button></div>}
    {fieldError&&<p role="alert">{fieldError}</p>}
    {recovery&&<section role="alert" aria-label="Guided conflict recovery"><h2>版本已更新，请明确恢复输入</h2><p>尝试版本 {recovery.attemptedVersion}；权威版本 {recovery.authoritativeVersion}。正文仍保留在当前输入框，未自动重放操作。</p><button onClick={()=>{setRecovery(null);setError(null);}}>核对后保留输入</button><button onClick={()=>{setSuccessorContent("");setRecovery(null);setError(null);}}>丢弃保留输入</button></section>}
    <section className="agent-dashboard" aria-label="Knowledge quality dashboard"><article><strong>{dashboard?.authorizedKnowledgeCount ?? "—"}</strong><span>授权知识包</span></article><article><strong>{dashboard?.activeSnapshotCount ?? "—"}</strong><span>生效索引快照</span></article><article><strong>{dashboard?.authority ?? "尚未读取"}</strong><span>后端权威来源</span></article></section>
    <div className="agent-layout"><aside id="document-list"><div className="agent-list-heading"><h2 ref={listHeading} tabIndex={-1}>文档列表</h2><button ref={createTrigger} disabled={busy} onClick={()=>{setFieldError("");createDialog.current?.showModal();}}>上传或创建文档</button></div><label>筛选文档<input type="search" value={filter} onChange={e=>navigate({q:e.target.value},true)}/></label>
      {!visible.length&&state==="READY"?<p>没有符合条件的授权文档。</p>:<ul className="agent-list">{visible.map(item=>{const updated=knowledgeTime(item.facts?.at(-1)?.recordedAt??item.revisions.at(-1)?.createdAt,"list");return <li key={item.knowledgeId}><button disabled={state==="SAVING"} aria-pressed={id===item.knowledgeId} onClick={()=>navigate({resourceId:item.knowledgeId,revisionId:"",digest:"",view:"product",returnFocus:""})}><strong>{item.name}</strong><span>{status(item.lifecycleState)} · v{item.aggregateVersion}</span><small title={updated.raw??undefined}>{updated.display}</small></button></li>;})}</ul>}
    </aside><section className="agent-detail" id="document-detail">{!value?<><h2>选择文档</h2><p>选择后查看来源、修订、处理记录、检索和生命周期操作。</p>{operationResult!=null&&<pre>{JSON.stringify(operationResult,null,2)}</pre>}</>:<>
      <header><p>{status(value.lifecycleState)} · {value.archived?"已归档":"活动记录"}</p><h2 ref={detailHeading} tabIndex={-1}>{value.name}</h2><span className="technical-value">{value.knowledgeId}</span><p>聚合版本 {value.aggregateVersion}</p><button disabled={busy} onClick={()=>{navigate({resourceId:"",revisionId:"",digest:"",returnFocus:"list"});}}>返回筛选列表</button></header>
      {needsRecovery&&<p role="alert">RECOVERY_REQUIRED：跨存储操作尚未证明完成，不能声称可用或已清除。</p>}
      <nav aria-label="Knowledge projection"><button aria-pressed={view==="PRODUCT"} onClick={()=>navigate({view:"product"},true)}>产品视图</button><button aria-pressed={view==="TECHNICAL"} onClick={()=>navigate({view:"technical"},true)}>技术视图</button></nav>
      {view==="TECHNICAL"?<KnowledgeTechnicalProjection projection={selected!}/>:<>
      <section className="knowledge-stages" aria-label="文档处理阶段"><h3>处理阶段</h3><ol><li><strong>上传</strong><span>{source?.fileName?"已接收并完成瞬时解析；原文件未保存":"非文件入口或未记录文件"}</span></li><li><strong>解析</strong><span>{source?.parserVersion?`已解析 · ${source.parserVersion}`:"不适用或无解析事实"}</span></li><li><strong>校验／发布</strong><span>{status(currentRevision?.state??"DRAFT")}</span></li><li><strong>索引</strong><span>{latestJob?`${status(latestJob.status)} · ${latestJob.jobId}`:"尚未开始"}</span></li><li><strong>可检索</strong><span>{value.activeIndexSnapshotId&&value.lifecycleState==="AVAILABLE"?`是 · ${value.activeIndexSnapshotId}`:"否"}</span></li></ol></section>
      <section className="agent-section"><h3>来源与修订详情</h3><label>查看修订<select value={revisionId || ""} onChange={e=>navigate({revisionId:e.target.value,digest:""})}><option value="">当前工作修订</option>{value.revisions.map(item=><option key={item.revisionId} value={item.revisionId}>{status(item.state)} · {item.revisionId}</option>)}</select></label>
        {exactMismatch?<p role="alert">指定修订或摘要不匹配，不能用其他修订替代。</p>:shownRevision&&<><dl><dt>中文显示名称</dt><dd>{source?.fileName??value.name}</dd><dt>来源说明</dt><dd>{source?.sourceDescription??"未提供"}</dd><dt>外部编号／URL</dt><dd>{source?.externalReference??"未提供"}</dd><dt>系统来源身份</dt><dd className="technical-value">{source?.sourceId}</dd><dt>系统出处标识</dt><dd className="technical-value">{source?.provenance}</dd><dt>来源类型</dt><dd>{source?.kind}</dd><dt>精确修订</dt><dd className="technical-value">{shownRevision.revisionId}</dd><dt>前驱修订</dt><dd>{shownRevision.predecessorRevisionId ?? "初始修订"}</dd><dt>状态</dt><dd>{status(shownRevision.state)}</dd><dt>记录时间</dt><dd><time dateTime={latestRecordedAt}>{knowledgeTime(latestRecordedAt,"detail").display}</time></dd></dl><details><summary>原始 UTC 与技术摘要</summary><p>{latestRecordedAt??"未记录"}</p><code>{shownRevision.digest}</code></details>{shownRevision.content.documents.map(document=><details key={document.documentId}><summary>文档正文与片段</summary><p className="technical-value">系统文档身份 {document.documentId}</p><p>文档摘要 {document.contentDigest}</p>{document.chunks.map(chunk=><article key={chunk.chunkId}><small>{knowledgeLocation(chunk.location)}</small><code>{chunk.chunkId} · {chunk.contentDigest}</code><p className="knowledge-content">{chunk.content}</p></article>)}</details>)}</>}
      </section>
      <fieldset disabled={busy || !!recovery || exactMismatch}><legend>当前工作修订操作（历史修订只读）</legend><p>{currentRevision?.revisionId} · {currentRevision?.digest}</p><div className="agent-actions">
        {currentRevision?.state==="DRAFT"&&<button onClick={()=>act("validation")}>校验草稿</button>}
        {currentRevision?.state==="VALIDATED"&&<button onClick={()=>act("reviews",currentRevision.digest)}>人工审阅精确摘要</button>}
        {currentRevision?.state==="HUMAN_REVIEWED"&&<button onClick={()=>act("publications",currentRevision.digest)}>发布不可变修订</button>}
      </div></fieldset>
      <fieldset disabled={busy || !!recovery}><legend>索引、重建与恢复</legend><dl><dt>最近导入任务</dt><dd>{latestJob ? `${latestJob.jobId} · ${latestJob.status}` : "尚未开始"}</dd><dt>当前快照</dt><dd>{value.activeIndexSnapshotId ?? "未建立索引"}</dd></dl><div className="agent-actions">
        {value.publishedRevisionId&&!needsRecovery&&<button onClick={()=>act("ingestion")}>导入并建立索引</button>}
        {value.activeIndexSnapshotId&&!needsRecovery&&<button onClick={()=>act("rebuild")}>重建派生索引</button>}
        {needsRecovery&&!value.purge&&<button onClick={()=>act("recovery")}>恢复索引任务</button>}
        {value.purge?.status==="RECOVERY_REQUIRED"&&<p>清除尚未完成。请通过下方清除确认重新核对授权后重试；不会执行索引恢复代替清除。</p>}
      </div></fieldset>
      <section id="retrieval-test"><h3>检索测试与出处</h3><p>检索只返回片段与出处，不调用模型生成答案。范围筛选由后端执行。</p><fieldset disabled={busy || !!recovery}><legend>单文档授权检索</legend><label>中文问题<input value={query} onChange={e=>setQuery(e.target.value)}/></label><div className="agent-actions"><button disabled={!value.activeIndexSnapshotId} onClick={()=>retrieve()}>检索当前文档</button><button onClick={()=>retrieve("DENY")}>验证拒绝披露</button></div></fieldset>
      <section className="agent-section" aria-label="Workbench retrieval history"><h3>检索记录与原文出处</h3><p>这些记录不是Attempt级Evidence，也不代表业务执行已采用引用。无HTTP契约的Attempt操作：NOT_CONNECTED。</p>{value.retrievals.length===0?<p>尚无检索记录。</p>:[...value.retrievals].reverse().map(retrieval=>{const recorded=knowledgeTime(retrieval.recordedAt,"detail");return <details key={retrieval.retrievalId} open={retrieval===value.retrievals.at(-1)}><summary>{recorded.display} · {retrieval.retrievalId}</summary><dl><dt>授权决定</dt><dd>{retrieval.authorizationDecisionId}</dd><dt>索引快照</dt><dd>{retrieval.snapshotId}</dd><dt>查询摘要</dt><dd>{retrieval.queryDigest}</dd><dt>原始 UTC</dt><dd>{retrieval.recordedAt}</dd></dl>{retrieval.citations.length===0?<p>无召回结果，本次未产生引用。</p>:retrieval.citations.map(citation=><article key={citation.citationId} className="citation-card"><strong>原文出处 · {source?.fileName??value.name}</strong><p>{knowledgeLocation(citation.location)} · 精确修订 {citation.revisionId}</p><p className="knowledge-content">{citation.content}</p><details><summary>技术身份</summary><dl>{Object.entries(citation).filter(([key])=>key!=="content"&&key!=="location").map(([key,val])=><div key={key}><dt>{key}</dt><dd>{String(val)}</dd></div>)}</dl></details></article>)}</details>;})}</section>
      <fieldset disabled={busy} aria-label="Search Playground"><legend>范围检索与质量评估</legend><label>检索方式<select value={searchMode} onChange={e=>setSearchMode(e.target.value as typeof searchMode)}><option>LEXICAL</option><option>SEMANTIC</option><option>HYBRID</option></select></label><div className="agent-dashboard">{metadata&&(["sourceId","documentId","contentType","revisionId","snapshotId"] as const).map(key=><label key={key}>{key}<select aria-label={`Filter ${key}`} value={searchFilters[key]??""} onChange={e=>setSearchFilters(current=>({...current,[key]:e.target.value}))}><option value="">任意授权值</option>{metadata[key].map(option=><option key={option}>{option}</option>)}</select></label>)}</div>
        <button onClick={search}>执行检索实验</button><button disabled={!searchResult} onClick={()=>void run(()=>evaluateKnowledge(query,searchResult?.results.map(item=>item.citation.chunkId)??[],searchMode,evaluationRun?.entityId),setEvaluationRun)}>{evaluationRun?"比较评估记录":"评估当前结果"}</button><button onClick={()=>void run(listKnowledgeEvaluations,setEvaluations,"评估历史已读取。")}>查询评估历史</button>
        {searchResult&&<><p>{searchResult.classification} · {searchResult.tokenizerVersion}</p><p>分数含义：{searchResult.scoreMeaning}。这是排序信号，不是正确率。</p>{searchResult.results.length===0?<p>检索成功，但没有符合后端范围筛选的授权结果。</p>:<div className="retrieval-results">{searchResult.results.map(item=><article key={`${item.citation.revisionId}:${item.citation.chunkId}`} className="citation-card"><h4>排名 {item.rank}</h4><p>排序分数 {item.score} · {searchResult.scoreMeaning}</p><p><strong>{item.citation.fileName??item.citation.sourceDescription??value.name}</strong> · 精确修订 {item.citation.revisionId} · {knowledgeLocation(item.citation.location)}</p><blockquote>{item.citation.content}</blockquote><details><summary>技术身份</summary><code>{item.citation.knowledgeId} / {item.citation.sourceId} / {item.citation.documentId} / {item.citation.chunkId}</code></details></article>)}</div>}</>}
        {evaluationRun&&<article aria-label="Evaluation comparison"><h4>评估记录（当前召回作为期望集，不代表独立质量验收）</h4><pre>{JSON.stringify(evaluationRun,null,2)}</pre></article>}{evaluations.map(item=><details key={item.entityId}><summary>{item.entityId}</summary><pre>{JSON.stringify(item.body,null,2)}</pre></details>)}
      </fieldset></section>
      <section id="advanced-management"><h3>高级管理</h3><p>评估、重建、恢复、导出与清理保留原能力；高影响操作仍服从后端状态和权限。</p><fieldset disabled={busy} aria-label="Knowledge operations"><legend>摘要、重复项审查与导出</legend><button onClick={()=>void run(()=>summarizeKnowledge(value.knowledgeId),setOperationResult)}>生成抽取式摘要</button><button onClick={()=>void run(async()=>{await scanKnowledgeDuplicates();return getKnowledgeDuplicateQueue();},setDuplicateQueue)}>扫描重复项</button><button onClick={()=>void run(getKnowledgeDuplicateQueue,setDuplicateQueue,"审查历史已读取。")}>查询重复项审查历史</button><button onClick={()=>void run(exportKnowledge,setOperationResult)}>导出授权事实</button><p>摘要：DETERMINISTIC_EXTRACTIVE_V1，模型NOT_APPLICABLE。重复项判定仅记录决定，不删除、合并或重写正文。</p>
        {duplicateQueue.length>0&&<div aria-label="Duplicate review queue">{duplicateQueue.map(candidate=><article key={candidate.entityId}><p>{String(candidate.body.classification)} candidate · {candidate.entityId}</p><pre>{JSON.stringify(candidate.body,null,2)}</pre>{candidate.decision?<p>人工决定已记录</p>:<div className="agent-actions">{(["DUPLICATE","DISTINCT","NEEDS_INVESTIGATION"] as const).map((classification,index)=><button key={classification} onClick={()=>void run(async()=>{await decideKnowledgeDuplicate(candidate.entityId,classification);return getKnowledgeDuplicateQueue();},setDuplicateQueue)}>{["判定重复","判定不同","需要调查"][index]}</button>)}</div>}</article>)}</div>}
        {operationResult!=null&&<pre>{JSON.stringify(operationResult,null,2)}</pre>}
      </fieldset>
      <fieldset disabled={busy}><legend>导入知识草稿</legend><label>导入格式<select value={importFormat} onChange={e=>{setImportFormat(e.target.value as typeof importFormat);setImportJob(null);}}><option value="txt">TXT</option><option value="md">Markdown</option><option value="jsonl">JSONL</option></select></label><label>导入内容<textarea aria-label="导入内容" rows={6} value={importContent} onChange={e=>{setImportContent(e.target.value);setImportJob(null);}}/></label><p>JSONL每行包含name和content。预览不保证每条内容可入库；导入仅创建草稿。</p><button onClick={previewImport}>预览导入</button>
        {importJob&&<article aria-label="Import execution"><h4>导入状态 {importBody?.status}</h4><p>{importJob.entityId}</p><dl><dt>输入记录数</dt><dd>{importBody?.inputRecordCount}</dd><dt>预览接受／拒绝</dt><dd>{importBody?.recordCount} / {importBody?.previewRejectedCount}</dd><dt>已处理</dt><dd>{importBody?.processedCount??0}</dd><dt>已创建草稿</dt><dd>{importBody?.acceptedCount??0}</dd><dt>拒绝记录数</dt><dd>{importBody?.rejectedCount??importBody?.previewRejectedCount??0}</dd><dt>允许重试</dt><dd>{String(importBody?.retryable??false)}</dd></dl><details><summary>后端接受的预览内容</summary><pre>{JSON.stringify(importBody?.records ?? [],null,2)}</pre></details><p>接口仅返回拒绝数量，不提供逐条失败原因；不会编造失败明细。</p><button disabled={importBody?.status==="COMPLETED"} onClick={()=>void run(async()=>({job:await executeKnowledgeImport(importJob.entityId),resources:await listKnowledge()}),result=>{setImportJob(result.job);setItems(result.resources);},"导入响应已收到；请核对状态、成功与拒绝数量。")}>{importBody?.status==="PARTIAL"?"重试部分导入":"执行已确认预览"}</button>{importBody?.importedKnowledgeIds?.map(importedId=><button key={importedId} onClick={()=>navigate({resourceId:importedId,revisionId:"",digest:""})}>查看导入草稿 {importedId}</button>)}</article>}
      </fieldset>
      {value.publishedRevisionId&&!value.currentDraftRevisionId&&<fieldset disabled={busy || !!recovery}><legend>创建后继修订</legend><p>只更新源正文，已发布修订保持不可变，需要重新校验、人工审阅和发布。</p><label>后继正文<textarea aria-label="后继正文" rows={5} value={successorContent} onChange={e=>setSuccessorContent(e.target.value)}/></label><button onClick={successor}>创建后继草稿</button></fieldset>}
      <fieldset disabled={busy || !!recovery}><legend>归档与合规清除</legend><p>归档保留修订、引用和审计历史。合规清除会移除载荷及派生向量，仅保留非敏感墓碑，必须提供授权标识。</p><button disabled={value.archived} onClick={()=>act("archive")}>归档知识包</button><button ref={purgeTrigger} onClick={()=>{setFieldError("");purgeDialog.current?.showModal();}}>审查清除影响</button></fieldset></section>
      </>}
    </>}</section></div>
    <dialog ref={createDialog} aria-labelledby="knowledge-create-title" onClose={()=>createTrigger.current?.focus()}><form onSubmit={e=>{e.preventDefault();create();}}><h2 id="knowledge-create-title">上传或创建知识文档</h2><div role="tablist" aria-label="文档创建方式"><button type="button" role="tab" aria-selected={createMode==="UPLOAD"} onClick={()=>switchCreateMode("UPLOAD")}>上传 PDF／DOCX</button><button type="button" role="tab" aria-selected={createMode==="TEXT"} onClick={()=>switchCreateMode("TEXT")}>粘贴文字</button></div>{fieldError&&<p role="alert">{fieldError}</p>}{error&&<p role="alert">{knowledgeErrorMessage(error)} · {error.reasonCode}</p>}<fieldset disabled={busy}><label>文档标题<input autoFocus required value={input.name} onChange={e=>setInput({...input,name:e.target.value})}/></label><label>来源说明<input required value={input.source.sourceDescription??""} onChange={e=>setInput({...input,source:{...input.source,sourceDescription:e.target.value}})} placeholder="例如：供应商质量管理制度"/></label><label>可选外部编号或 URL<input value={input.source.externalReference??""} onChange={e=>setInput({...input,source:{...input.source,externalReference:e.target.value}})}/></label>{createMode==="UPLOAD"?<><div className={`document-dropzone ${dragActive?"active":""}`} onDragEnter={event=>{event.preventDefault();setDragActive(true);}} onDragOver={event=>event.preventDefault()} onDragLeave={()=>setDragActive(false)} onDrop={event=>{event.preventDefault();setDragActive(false);chooseFile(event.dataTransfer.files[0]);}}><label>选择或拖入文档<input aria-label="选择 PDF 或 DOCX" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={event=>chooseFile(event.target.files?.[0])}/></label><p>最大 8 MiB，解析最长 10 秒。扩展名不是唯一类型依据。</p>{selectedFile&&<p>{selectedFile.name} · {selectedFile.size} 字节 · {selectedFile.type||"未声明类型"}</p>}</div>{parsePreview&&<article className="parse-preview" aria-label="解析预览"><h3>解析成功：{parsePreview.detectedFormat}</h3><p>{parsePreview.segments.length} 个文字片段 · {parsePreview.parseDurationMs} ms</p><p role="note">原文件未保存。确认后仅保存下方提取文字和真实定位。</p>{parsePreview.limitations.map(item=><p key={item}>{item}</p>)}<div className="preview-content">{parsePreview.segments.map((segment,index)=><article key={`${index}:${segment.content}`}><small>{knowledgeLocation(segment.location)}</small><p>{segment.content}</p></article>)}</div></article>}</>:<label>知识正文<textarea aria-label="知识正文" required rows={8} value={input.source.content} onChange={e=>setInput({...input,source:{...input.source,content:e.target.value,segments:undefined,contentDigest:undefined}})}/></label>}<p>系统来源 ID、文档 ID、知识 ID 和修订 ID 均由后端 owner 生成。创建只产生草稿，不代表发布或索引成功。</p><button type="submit" disabled={createMode==="UPLOAD"&&!parsePreview}>{createMode==="UPLOAD"?"从解析结果创建草稿":"创建文字草稿"}</button></fieldset><button type="button" disabled={state==="SAVING"} onClick={()=>createDialog.current?.close()}>取消</button></form></dialog>
    <dialog ref={purgeDialog} aria-labelledby="knowledge-purge-title" onClose={()=>purgeTrigger.current?.focus()}><form onSubmit={e=>{e.preventDefault();purge();}}><h2 id="knowledge-purge-title">授权合规清除</h2><p>将移除源正文、文档、分块及派生向量；可能部分完成并需要恢复。不会自动重放。</p>{error&&<p role="alert">{knowledgeErrorMessage(error)} · {error.reasonCode}</p>}<fieldset disabled={busy}><label>授权标识<input required value={authorizationId} onChange={e=>setAuthorizationId(e.target.value)}/></label><label>非敏感原因分类<input required value={reasonClassification} onChange={e=>setReasonClassification(e.target.value)}/></label><button type="submit">确认授权清除</button></fieldset><button type="button" disabled={state==="SAVING"} onClick={()=>purgeDialog.current?.close()}>取消</button></form></dialog>
  </main>;
}
