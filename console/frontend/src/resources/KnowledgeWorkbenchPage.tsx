import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  createKnowledge, createKnowledgeSuccessor, getKnowledge, knowledgeAction, listKnowledge,
  purgeKnowledge, retrieveKnowledge, KnowledgeRequestError, knowledgeControlledState,
  knowledgeErrorMessage, getKnowledgeDashboard, searchKnowledge, evaluateKnowledge,
  summarizeKnowledge, scanKnowledgeDuplicates, previewKnowledgeImport, exportKnowledge,
  executeKnowledgeImport, getKnowledgeDuplicateQueue, getKnowledgeMetadata,
  decideKnowledgeDuplicate, listKnowledgeEvaluations,
  type KnowledgeInput, type KnowledgeProjection, type KnowledgeResource,
  type KnowledgeDashboard, type KnowledgeSearchResult, type KnowledgeMetadata, type QualityEntity,
} from "../api/knowledgeResources";
import { KnowledgeTechnicalProjection } from "./KnowledgeTechnicalProjection";
import "./KnowledgeWorkbenchPage.css";

const emptyInput = (): KnowledgeInput => ({name:"",source:{sourceId:"",documentId:"",kind:"TEXT",provenance:"",content:""}});
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
  for (const [label,value] of [["来源ID",input.source.sourceId],["文档ID",input.source.documentId],["来源类型",input.source.kind],["出处标识",input.source.provenance]]) {
    if (!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$/.test(value)) return `${label}须以字母或数字开头，最多200个字符，仅允许字母、数字及 . _ : / -。`;
  }
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
      createDialog.current?.close(); setInput(emptyInput());
      navigate({resourceId:projection.knowledge.knowledgeId,revisionId:"",digest:""});
    },"知识草稿已创建，尚未发布。");
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
  const visible = items.filter(item=>`${item.name} ${item.knowledgeId} ${item.lifecycleState}`.toLowerCase().includes(filter.toLowerCase()));

  return <main className="agent-workbench knowledge-workbench">
    <header><p className="eyebrow">企业 Knowledge 资源工作台</p><h1>知识中心</h1><p>管理知识来源、不可变修订、检索与引用。生命周期由后端持有。</p></header>
    {state==="LOADING"&&<p role="status">正在读取授权知识资源…</p>}
    {state==="SAVING"&&<p role="status">正在提交，请勿重复操作…</p>}
    {notice&&<div role="status" className="notice">{notice}<button onClick={()=>setNotice("")}>关闭提示</button></div>}
    {error&&<div role="alert"><strong>{knowledgeErrorMessage(error)}</strong><code>{error.reasonCode}</code><button disabled={busy} onClick={refresh}>重新读取权威数据</button></div>}
    {fieldError&&<p role="alert">{fieldError}</p>}
    {recovery&&<section role="alert" aria-label="Guided conflict recovery"><h2>版本已更新，请明确恢复输入</h2><p>尝试版本 {recovery.attemptedVersion}；权威版本 {recovery.authoritativeVersion}。正文仍保留在当前输入框，未自动重放操作。</p><button onClick={()=>{setRecovery(null);setError(null);}}>核对后保留输入</button><button onClick={()=>{setSuccessorContent("");setRecovery(null);setError(null);}}>丢弃保留输入</button></section>}
    <section className="agent-dashboard" aria-label="Knowledge quality dashboard"><article><strong>{dashboard?.authorizedKnowledgeCount ?? "—"}</strong><span>授权知识包</span></article><article><strong>{dashboard?.activeSnapshotCount ?? "—"}</strong><span>生效索引快照</span></article><article><strong>{dashboard?.authority ?? "尚未读取"}</strong><span>后端权威来源</span></article></section>
    <div className="agent-layout"><aside><div className="agent-list-heading"><h2 ref={listHeading} tabIndex={-1}>知识包列表</h2><button ref={createTrigger} disabled={busy} onClick={()=>{setFieldError("");createDialog.current?.showModal();}}>创建知识源</button></div><label>筛选知识包<input type="search" value={filter} onChange={e=>navigate({q:e.target.value},true)}/></label>
      {!visible.length&&state==="READY"?<p>没有符合条件的授权知识包。</p>:<ul className="agent-list">{visible.map(item=><li key={item.knowledgeId}><button disabled={state==="SAVING"} aria-pressed={id===item.knowledgeId} onClick={()=>navigate({resourceId:item.knowledgeId,revisionId:"",digest:"",view:"product",returnFocus:""})}><strong>{item.name}</strong><span>{status(item.lifecycleState)} · v{item.aggregateVersion}</span></button></li>)}</ul>}
    </aside><section className="agent-detail">{!value?<><h2>选择知识包</h2><p>选择后查看来源、修订、检索记录和生命周期操作。</p>{operationResult!=null&&<pre>{JSON.stringify(operationResult,null,2)}</pre>}</>:<>
      <header><p>{status(value.lifecycleState)} · {value.archived?"已归档":"活动记录"}</p><h2 ref={detailHeading} tabIndex={-1}>{value.name}</h2><span className="technical-value">{value.knowledgeId}</span><p>聚合版本 {value.aggregateVersion}</p><button disabled={busy} onClick={()=>{navigate({resourceId:"",revisionId:"",digest:"",returnFocus:"list"});}}>返回筛选列表</button></header>
      {needsRecovery&&<p role="alert">RECOVERY_REQUIRED：跨存储操作尚未证明完成，不能声称可用或已清除。</p>}
      <nav aria-label="Knowledge projection"><button aria-pressed={view==="PRODUCT"} onClick={()=>navigate({view:"product"},true)}>产品视图</button><button aria-pressed={view==="TECHNICAL"} onClick={()=>navigate({view:"technical"},true)}>技术视图</button></nav>
      {view==="TECHNICAL"?<KnowledgeTechnicalProjection projection={selected!}/>:<>
      <nav aria-label="Knowledge information hierarchy"><ol><li><strong>日常检索与引用</strong><span>Routine: Search, Retrieval and Citations</span></li><li><strong>质量评估</strong><span>Quality Evaluation: evidence and comparison</span></li><li><strong>导入与重复项审查</strong><span>Managed operations: Import and Duplicate Review</span></li><li><strong>索引重建、清除与恢复</strong><span>Advanced high-impact: Rebuild, Purge and Recovery</span></li></ol></nav>
      <section className="agent-section"><h3>来源与修订详情</h3><label>查看修订<select value={revisionId || ""} onChange={e=>navigate({revisionId:e.target.value,digest:""})}><option value="">当前工作修订</option>{value.revisions.map(item=><option key={item.revisionId} value={item.revisionId}>{status(item.state)} · {item.revisionId}</option>)}</select></label>
        {exactMismatch?<p role="alert">指定修订或摘要不匹配，不能用其他修订替代。</p>:shownRevision&&<><dl><dt>来源ID</dt><dd>{shownRevision.content.source.sourceId}</dd><dt>来源类型</dt><dd>{shownRevision.content.source.kind}</dd><dt>出处</dt><dd>{shownRevision.content.source.provenance}</dd><dt>精确修订</dt><dd>{shownRevision.revisionId}</dd><dt>前驱修订</dt><dd>{shownRevision.predecessorRevisionId ?? "初始修订"}</dd><dt>状态</dt><dd>{status(shownRevision.state)}</dd></dl><label>精确修订摘要<input readOnly value={shownRevision.digest}/></label>{shownRevision.content.documents.map(document=><details key={document.documentId}><summary>文档 {document.documentId}</summary><p>文档摘要 {document.contentDigest}</p>{document.chunks.map(chunk=><article key={chunk.chunkId}><code>{chunk.chunkId} · {chunk.contentDigest}</code><p className="knowledge-content">{chunk.content}</p></article>)}</details>)}</>}
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
      <fieldset disabled={busy || !!recovery}><legend>授权检索</legend><label>检索词<input value={query} onChange={e=>setQuery(e.target.value)}/></label><div className="agent-actions"><button disabled={!value.activeIndexSnapshotId} onClick={()=>retrieve()}>执行授权检索</button><button onClick={()=>retrieve("DENY")}>验证拒绝披露</button></div></fieldset>
      <section className="agent-section" aria-label="Workbench retrieval history"><h3>工作台检索历史</h3><p>这些记录不是Attempt级Evidence，也不代表业务执行已采用引用。无HTTP契约的Attempt操作：NOT_CONNECTED。</p>{value.retrievals.length===0?<p>尚无检索记录。</p>:[...value.retrievals].reverse().map(retrieval=><details key={retrieval.retrievalId} open={retrieval===value.retrievals.at(-1)}><summary>{retrieval.recordedAt} · {retrieval.retrievalId}</summary><dl><dt>授权决定</dt><dd>{retrieval.authorizationDecisionId}</dd><dt>索引快照</dt><dd>{retrieval.snapshotId}</dd><dt>查询摘要</dt><dd>{retrieval.queryDigest}</dd></dl>{retrieval.citations.length===0?<p>无检索结果，本次未产生引用。</p>:retrieval.citations.map(citation=><article key={citation.citationId}><strong>CITATION · {citation.citationId}</strong><p className="knowledge-content">{citation.content}</p><dl>{Object.entries(citation).filter(([key])=>key!=="content").map(([key,val])=><div key={key}><dt>{key}</dt><dd>{val}</dd></div>)}</dl></article>)}</details>)}</section>
      <fieldset disabled={busy} aria-label="Search Playground"><legend>检索实验与质量评估</legend><label>检索方式<select value={searchMode} onChange={e=>setSearchMode(e.target.value as typeof searchMode)}><option>LEXICAL</option><option>SEMANTIC</option><option>HYBRID</option></select></label><div className="agent-dashboard">{metadata&&(["sourceId","documentId","contentType","revisionId","snapshotId"] as const).map(key=><label key={key}>{key}<select aria-label={`Filter ${key}`} value={searchFilters[key]??""} onChange={e=>setSearchFilters(current=>({...current,[key]:e.target.value}))}><option value="">任意授权值</option>{metadata[key].map(option=><option key={option}>{option}</option>)}</select></label>)}</div>
        <button onClick={search}>执行检索实验</button><button disabled={!searchResult} onClick={()=>void run(()=>evaluateKnowledge(query,searchResult?.results.map(item=>item.citation.chunkId)??[],searchMode,evaluationRun?.entityId),setEvaluationRun)}>{evaluationRun?"比较评估记录":"评估当前结果"}</button><button onClick={()=>void run(listKnowledgeEvaluations,setEvaluations,"评估历史已读取。")}>查询评估历史</button>
        {searchResult&&<><p>{searchResult.classification} · {searchResult.tokenizerVersion}</p>{searchResult.results.length===0?<p>没有符合筛选条件的授权结果。</p>:<table><thead><tr><th>排名／分数</th><th>知识引用与精确身份</th></tr></thead><tbody>{searchResult.results.map(item=><tr key={`${item.citation.revisionId}:${item.citation.chunkId}`}><td>{item.rank} / {item.score}</td><td>{item.citation.content}<p>{item.citation.knowledgeId} / {item.citation.revisionId} / {item.citation.documentId} / {item.citation.chunkId}</p></td></tr>)}</tbody></table>}</>}
        {evaluationRun&&<article aria-label="Evaluation comparison"><h4>评估记录（当前召回作为期望集，不代表独立质量验收）</h4><pre>{JSON.stringify(evaluationRun,null,2)}</pre></article>}{evaluations.map(item=><details key={item.entityId}><summary>{item.entityId}</summary><pre>{JSON.stringify(item.body,null,2)}</pre></details>)}
      </fieldset>
      <fieldset disabled={busy} aria-label="Knowledge operations"><legend>摘要、重复项审查与导出</legend><button onClick={()=>void run(()=>summarizeKnowledge(value.knowledgeId),setOperationResult)}>生成抽取式摘要</button><button onClick={()=>void run(async()=>{await scanKnowledgeDuplicates();return getKnowledgeDuplicateQueue();},setDuplicateQueue)}>扫描重复项</button><button onClick={()=>void run(getKnowledgeDuplicateQueue,setDuplicateQueue,"审查历史已读取。")}>查询重复项审查历史</button><button onClick={()=>void run(exportKnowledge,setOperationResult)}>导出授权事实</button><p>摘要：DETERMINISTIC_EXTRACTIVE_V1，模型NOT_APPLICABLE。重复项判定仅记录决定，不删除、合并或重写正文。</p>
        {duplicateQueue.length>0&&<div aria-label="Duplicate review queue">{duplicateQueue.map(candidate=><article key={candidate.entityId}><p>{String(candidate.body.classification)} candidate · {candidate.entityId}</p><pre>{JSON.stringify(candidate.body,null,2)}</pre>{candidate.decision?<p>人工决定已记录</p>:<div className="agent-actions">{(["DUPLICATE","DISTINCT","NEEDS_INVESTIGATION"] as const).map((classification,index)=><button key={classification} onClick={()=>void run(async()=>{await decideKnowledgeDuplicate(candidate.entityId,classification);return getKnowledgeDuplicateQueue();},setDuplicateQueue)}>{["判定重复","判定不同","需要调查"][index]}</button>)}</div>}</article>)}</div>}
        {operationResult!=null&&<pre>{JSON.stringify(operationResult,null,2)}</pre>}
      </fieldset>
      <fieldset disabled={busy}><legend>导入知识草稿</legend><label>导入格式<select value={importFormat} onChange={e=>{setImportFormat(e.target.value as typeof importFormat);setImportJob(null);}}><option value="txt">TXT</option><option value="md">Markdown</option><option value="jsonl">JSONL</option></select></label><label>导入内容<textarea aria-label="导入内容" rows={6} value={importContent} onChange={e=>{setImportContent(e.target.value);setImportJob(null);}}/></label><p>JSONL每行包含name和content。预览不保证每条内容可入库；导入仅创建草稿。</p><button onClick={previewImport}>预览导入</button>
        {importJob&&<article aria-label="Import execution"><h4>导入状态 {importBody?.status}</h4><p>{importJob.entityId}</p><dl><dt>输入记录数</dt><dd>{importBody?.inputRecordCount}</dd><dt>预览接受／拒绝</dt><dd>{importBody?.recordCount} / {importBody?.previewRejectedCount}</dd><dt>已处理</dt><dd>{importBody?.processedCount??0}</dd><dt>已创建草稿</dt><dd>{importBody?.acceptedCount??0}</dd><dt>拒绝记录数</dt><dd>{importBody?.rejectedCount??importBody?.previewRejectedCount??0}</dd><dt>允许重试</dt><dd>{String(importBody?.retryable??false)}</dd></dl><details><summary>后端接受的预览内容</summary><pre>{JSON.stringify(importBody?.records ?? [],null,2)}</pre></details><p>接口仅返回拒绝数量，不提供逐条失败原因；不会编造失败明细。</p><button disabled={importBody?.status==="COMPLETED"} onClick={()=>void run(async()=>({job:await executeKnowledgeImport(importJob.entityId),resources:await listKnowledge()}),result=>{setImportJob(result.job);setItems(result.resources);},"导入响应已收到；请核对状态、成功与拒绝数量。")}>{importBody?.status==="PARTIAL"?"重试部分导入":"执行已确认预览"}</button>{importBody?.importedKnowledgeIds?.map(importedId=><button key={importedId} onClick={()=>navigate({resourceId:importedId,revisionId:"",digest:""})}>查看导入草稿 {importedId}</button>)}</article>}
      </fieldset>
      {value.publishedRevisionId&&!value.currentDraftRevisionId&&<fieldset disabled={busy || !!recovery}><legend>创建后继修订</legend><p>只更新源正文，已发布修订保持不可变，需要重新校验、人工审阅和发布。</p><label>后继正文<textarea aria-label="后继正文" rows={5} value={successorContent} onChange={e=>setSuccessorContent(e.target.value)}/></label><button onClick={successor}>创建后继草稿</button></fieldset>}
      <fieldset disabled={busy || !!recovery}><legend>归档与合规清除</legend><p>归档保留修订、引用和审计历史。合规清除会移除载荷及派生向量，仅保留非敏感墓碑，必须提供授权标识。</p><button disabled={value.archived} onClick={()=>act("archive")}>归档知识包</button><button ref={purgeTrigger} onClick={()=>{setFieldError("");purgeDialog.current?.showModal();}}>审查清除影响</button></fieldset>
      </>}
    </>}</section></div>
    <dialog ref={createDialog} aria-labelledby="knowledge-create-title" onClose={()=>createTrigger.current?.focus()}><form onSubmit={e=>{e.preventDefault();create();}}><h2 id="knowledge-create-title">创建知识源</h2>{fieldError&&<p role="alert">{fieldError}</p>}{error&&<p role="alert">{knowledgeErrorMessage(error)} · {error.reasonCode}</p>}<fieldset disabled={busy}><label>名称<input autoFocus required value={input.name} onChange={e=>setInput({...input,name:e.target.value})}/></label>{([['sourceId','来源ID'],['documentId','文档ID'],['kind','来源类型'],['provenance','出处标识']] as const).map(([key,label])=><label key={key}>{label}<input required value={input.source[key]} onChange={e=>setInput({...input,source:{...input.source,[key]:e.target.value}})}/></label>)}<label>知识正文<textarea aria-label="知识正文" required rows={6} value={input.source.content} onChange={e=>setInput({...input,source:{...input.source,content:e.target.value}})}/></label><p>创建只产生草稿；后台负责校验、身份和摘要。</p><button type="submit">创建草稿</button></fieldset><button type="button" disabled={state==="SAVING"} onClick={()=>createDialog.current?.close()}>取消</button></form></dialog>
    <dialog ref={purgeDialog} aria-labelledby="knowledge-purge-title" onClose={()=>purgeTrigger.current?.focus()}><form onSubmit={e=>{e.preventDefault();purge();}}><h2 id="knowledge-purge-title">授权合规清除</h2><p>将移除源正文、文档、分块及派生向量；可能部分完成并需要恢复。不会自动重放。</p>{error&&<p role="alert">{knowledgeErrorMessage(error)} · {error.reasonCode}</p>}<fieldset disabled={busy}><label>授权标识<input required value={authorizationId} onChange={e=>setAuthorizationId(e.target.value)}/></label><label>非敏感原因分类<input required value={reasonClassification} onChange={e=>setReasonClassification(e.target.value)}/></label><button type="submit">确认授权清除</button></fieldset><button type="button" disabled={state==="SAVING"} onClick={()=>purgeDialog.current?.close()}>取消</button></form></dialog>
  </main>;
}
