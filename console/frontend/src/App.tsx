import {
  BrowserRouter,
  Navigate,
  NavLink,
  Route,
  Routes,
} from "react-router-dom";
import { useEffect, useState } from "react";

import { ConsoleShell } from "./components/ConsoleShell";
import { WorkflowDetailPage } from "./pages/WorkflowDetailPage";
import { WorkflowRunsPage } from "./pages/WorkflowRunsPage";
import { ProductViewPage } from "./pages/ProductViewPage";
import { SelectedExecutionContext } from "./shared/SelectedExecutionContext";
import { TechPage } from "./pages/Technical\u0056iewPage";
import "./styles/app.css";
import { ExecutionPreviewError, fetchExecutionPreview, type PreviewMode } from "./api/executionPreview";
import { configureProductPreview, loadLiveProductPreview } from "./product/adapter";
import { configureTechnicalPreview, loadLiveTechnicalPreview } from "./technical/adapter";
import type { SharedExecutionSnapshot } from "./shared/executionSnapshotTypes";

type AppPreviewState = "LOADING" | "READY" | "DENIED" | "NOT_FOUND" | "AUTHORITY_MISSING" | "ERROR";

function configuredMode(): PreviewMode {
  return import.meta.env.VITE_EXECUTION_PREVIEW_MODE === "live" ? "live" : "synthetic-preview";
}

function LiveExecutionView({ snapshot, context }: { snapshot: SharedExecutionSnapshot; context: "PRODUCT" | "TECHNICAL" }) {
  const product = loadLiveProductPreview();
  const technical = loadLiveTechnicalPreview();
  if (product.platformExecutionIdentity !== technical.selectedContext.executionId || product.graphSnapshotId !== technical.selectedContext.graphSnapshotId) {
    throw new Error("CROSS_VIEW_IDENTITY_MISMATCH");
  }
  return <main className={context === "PRODUCT" ? "product-page" : "technical-page"}>
    <nav className="view-switcher" aria-label="Product and Technical views"><NavLink to="/product">Product View</NavLink><NavLink to="/technical">Technical View</NavLink></nav>
    <header className={context === "PRODUCT" ? "product-hero" : "technical-hero"}><p className="eyebrow">AUTHORIZED LIVE TECHNICAL PREVIEW</p><h1>{context === "PRODUCT" ? "Execution Product View" : "Execution Technical View"}</h1><p>Sibling projection over one authorized, fixed-high-water execution snapshot.</p></header>
    <section className="preview-warning" role="status"><strong>LIVE · {snapshot.readModelState}</strong><span>Never backed by synthetic fixture data.</span></section>
    <section className="product-section panel-pad" aria-labelledby="live-identity"><h2 id="live-identity">Shared execution identity</h2><dl className="evidence-list"><dt>Platform Execution Identity</dt><dd className="stable-id">{snapshot.selectedContext.executionId}</dd><dt>Shared snapshot identity</dt><dd className="stable-id">{snapshot.sharedSnapshotId}</dd><dt>Canonical Graph identity</dt><dd className="stable-id">{snapshot.selectedContext.graphSnapshotId}</dd><dt>Read-model state</dt><dd className="stable-id">{snapshot.readModelState}</dd></dl></section>
    <section className="product-section panel-pad" aria-labelledby="live-outcome"><h2 id="live-outcome">Authorization and outcome</h2><dl className="evidence-list"><dt>Decision</dt><dd className="stable-id">{snapshot.authorization.decision}</dd><dt>Reason code</dt><dd className="stable-id">{snapshot.authorization.reasonCode}</dd><dt>Provider calls</dt><dd>{snapshot.authorization.providerCallCount}</dd><dt>Execution outcome</dt><dd className="stable-id">{snapshot.outcome.status}</dd></dl>{snapshot.outcome.status !== "PASS" && <p role="alert">This execution is not presented as a verified success.</p>}{snapshot.readModelState !== "COMPLETE" && <p role="alert">The execution outcome is preserved, but this evidence snapshot is not complete and must not be treated as verified complete.</p>}</section>
    <section className="product-section panel-pad" aria-labelledby="live-graph"><h2 id="live-graph">Canonical Graph evidence</h2><p>{snapshot.nodes.length} nodes · {(snapshot.canonicalRelations ?? []).length} relations. Relations are rendered exactly as supplied by the authorized snapshot.</p>{(snapshot.canonicalRelations ?? []).map((relation) => <details key={relation.relation_id}><summary className="stable-id">{relation.source_node_id} → {relation.target_node_id}</summary><p className="stable-id">{relation.relation_types.join(" · ")} · {relation.declared_cardinality} · {relation.evidence_ids.join(", ")}</p></details>)}</section>
    <section className="product-section panel-pad" aria-labelledby="live-evidence"><h2 id="live-evidence">Evidence and citations</h2><p className="stable-id">{(snapshot.authorizedEvidenceReferences ?? []).map((item) => item.referenceIdentity).join(", ") || "NO_EVIDENCE_REFERENCES"}</p><p className="stable-id">{(snapshot.authorizedCitations ?? []).map((item) => item.referenceIdentity).join(", ") || "NO_AUTHORIZED_CITATIONS"}</p>{snapshot.limitations.map((code) => <p className="stable-id" key={code}>{code}</p>)}</section>
  </main>;
}

function App() {
  const technicalPath = "/technical";
  const mode = configuredMode();
  const [previewState, setPreviewState] = useState<AppPreviewState>(mode === "live" ? "LOADING" : "READY");
  const [reasonCode, setReasonCode] = useState(mode === "live" ? "PREVIEW_LOADING" : "SYNTHETIC_PREVIEW_EXPLICIT");
  const [liveSnapshot, setLiveSnapshot] = useState<SharedExecutionSnapshot | null>(null);
  useEffect(() => {
    if (mode === "synthetic-preview") {
      configureProductPreview(mode);
      configureTechnicalPreview(mode);
      return;
    }
    const controller = new AbortController();
    const namespace = import.meta.env.VITE_EXECUTION_PREVIEW_NAMESPACE ?? "agent-workloads";
    const workflow = import.meta.env.VITE_EXECUTION_PREVIEW_WORKFLOW ?? "example-workflow";
    const task = import.meta.env.VITE_EXECUTION_PREVIEW_TASK ?? "example-task";
    fetchExecutionPreview(namespace, workflow, task, controller.signal).then((snapshot) => {
      configureProductPreview("live", snapshot);
      configureTechnicalPreview("live", snapshot);
      setLiveSnapshot(snapshot);
      setReasonCode(snapshot.readModelState ?? "ERROR");
      setPreviewState("READY");
    }).catch((error: unknown) => {
      if (controller.signal.aborted) return;
      const failure = error instanceof ExecutionPreviewError ? error : new ExecutionPreviewError("ERROR", "PREVIEW_INTERNAL_ERROR");
      setReasonCode(failure.reasonCode);
      setPreviewState(failure.state);
    });
    return () => controller.abort();
  }, [mode]);
  if (previewState !== "READY") {
    return <main className="product-page"><section className="preview-warning" role={previewState === "LOADING" ? "status" : "alert"} aria-live="polite"><strong>{mode.toUpperCase()} · {previewState}</strong><span className="stable-id">{reasonCode}</span></section></main>;
  }
  if (mode === "live" && liveSnapshot) {
    return <BrowserRouter><ConsoleShell><Routes><Route path="/" element={<Navigate to="/product" replace />} /><Route path="/product" element={<LiveExecutionView snapshot={liveSnapshot} context="PRODUCT" />} /><Route path={technicalPath} element={<LiveExecutionView snapshot={liveSnapshot} context="TECHNICAL" />} /><Route path="*" element={<Navigate to="/product" replace />} /></Routes></ConsoleShell></BrowserRouter>;
  }
  return (
    <BrowserRouter>
      <SelectedExecutionContext>
        <ConsoleShell>
        <div className="preview-warning" role="status"><strong>{mode === "live" ? `LIVE · ${reasonCode}` : "SYNTHETIC · NON-AUTHORITATIVE"}</strong></div>
        <Routes>
          <Route
            path="/"
            element={
              <Navigate
                to="/product"
                replace
              />
            }
          />

          <Route path="/product" element={<ProductViewPage />} />

          <Route path={technicalPath} element={<TechPage />} />

          <Route
            path="/workflows"
            element={<WorkflowRunsPage />}
          />

          <Route
            path="/workflows/:namespace/:name"
            element={<WorkflowDetailPage />}
          />
        </Routes>
        </ConsoleShell>
      </SelectedExecutionContext>
    </BrowserRouter>
  );
}

export default App;
