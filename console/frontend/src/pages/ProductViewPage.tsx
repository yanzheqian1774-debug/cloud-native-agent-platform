import { useEffect, useReducer, useState } from "react";
import { loadProductPreview } from "../product/adapter";
import { initialJourney, journeyReducer } from "../product/journey";
import { ProductNavigation } from "../product/ProductNavigation";
import { BusinessJourney } from "../product/BusinessJourney";
import { DigitalEmployeeDirectory } from "../product/DigitalEmployeeDirectory";
import { DraftDiffApproval } from "../product/DraftDiffApproval";
import { ProductGraph } from "../product/ProductGraph";
import { OutcomeEvidence } from "../product/OutcomeEvidence";
import { RuntimeSupport } from "../product/RuntimeSupport";
import { useI18n } from "../i18n/useI18n";
import { useSelectedExecution } from "../shared/SelectedExecutionContext";
import { LivePlanningJourney } from "../product/LivePlanningJourney";
import { InterventionFeedback } from "../product/InterventionFeedback";

const fixture = loadProductPreview();

export function ProductViewPage() {
  const { t } = useI18n(); const { selection, selectEmployee, selectRevision } = useSelectedExecution(); const [state, dispatch] = useReducer(journeyReducer, { ...initialJourney, selectedEmployeeId: selection.employeeId, revision: selection.revisionId }); const [active, setActive] = useState("work"); const [correction, setCorrection] = useState("");
  useEffect(() => { selectEmployee(state.selectedEmployeeId); selectRevision(state.revision); }, [state.selectedEmployeeId, state.revision, selectEmployee, selectRevision]);
  function navigate(section: string) { setActive(section); document.getElementById(section)?.scrollIntoView({ behavior: "smooth", block: "start" }); }
  const liveJourneyId = import.meta.env.VITE_LIVE_PLANNING_JOURNEY_ID as string | undefined;
  return <main className="product-page"><ProductNavigation active={active} onSelect={navigate} />
    {liveJourneyId && <LivePlanningJourney journeyId={liveJourneyId} />}
    {liveJourneyId && <InterventionFeedback journeyId={liveJourneyId} />}
    <div className="preview-warning" role="status"><strong>{fixture.classification.join(" · ")}</strong><span>{t("product.preview.warning")}</span></div>
    <BusinessJourney fixture={fixture} state={state} dispatch={dispatch} />
    <DigitalEmployeeDirectory employees={fixture.employees} selectedId={state.selectedEmployeeId} onSelect={(id) => dispatch({ type: "SELECT_EMPLOYEE", id })} />
    {state.step !== "QUESTION" && <DraftDiffApproval state={state} onApprove={() => dispatch({ type: "APPROVE" })} onReject={() => dispatch({ type: "REJECT" })} />}
    <ProductGraph nodes={fixture.nodes} edges={fixture.edges} snapshotId={fixture.graphSnapshotId} executionId={fixture.platformExecutionIdentity} />
    <RuntimeSupport />
    {(state.step === "OUTCOME" || state.scenario !== "ALLOW") && <OutcomeEvidence fixture={fixture} state={state} />}
    <section className="product-section panel-pad" aria-labelledby="correction-title"><div className="section-heading"><h2 id="correction-title">{t("product.correction.title")}</h2><p>{t("product.correction.description")}</p></div><label htmlFor="correction">{t("product.correction.label")}</label><textarea id="correction" value={correction} onChange={(event) => setCorrection(event.target.value)} placeholder={t("product.correction.placeholder")} /><button disabled={!correction.trim()} onClick={() => { dispatch({ type: "CORRECT", text: correction }); document.getElementById("approvals")?.scrollIntoView({ behavior: "smooth" }); }}>{t("product.correction.create")}</button></section>
  </main>;
}
