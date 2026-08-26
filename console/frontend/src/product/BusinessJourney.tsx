import { useI18n } from "../i18n/useI18n";
import type { JourneyAction } from "./journey";
import type { JourneyState, ProductFixture } from "./types";

interface Props { fixture: ProductFixture; state: JourneyState; dispatch: (action: JourneyAction) => void }
export function BusinessJourney({ fixture, state, dispatch }: Props) {
  const { locale, t } = useI18n();
  return <section id="work" className="product-section journey-panel" aria-labelledby="journey-title">
    <div className="section-heading"><p className="eyebrow">{t("product.preview.label")}</p><h1 id="journey-title">{t("product.title")}</h1><p>{t("product.description")}</p></div>
    <ol className="stepper" aria-label={t("product.steps")}>{["QUESTION", "PLAN", "APPROVAL", "EXECUTION", "OUTCOME"].map((step, index) => <li key={step} aria-current={state.step === step ? "step" : undefined}><span>{index + 1}</span><b className="stable-id">{step}</b></li>)}</ol>
    <div className="question-box"><label htmlFor="business-question">{t("product.question.label")}</label><select id="business-question" value={state.question} onChange={(event) => dispatch({ type: "SELECT_QUESTION", question: event.target.value })}><option value="">{t("product.question.placeholder")}</option>{fixture.questions.map((key) => <option key={key} value={key}>{t(key as never)}</option>)}</select><button disabled={!state.question.trim()} onClick={() => dispatch({ type: "SHOW_PLAN" })}>{t("product.plan.create")}</button></div>
    {state.step !== "QUESTION" && <div className="plan-preview"><div className="section-heading"><h2>{t("product.plan.title")}</h2><p className="stable-id">{state.revision}</p></div><ol>{fixture.taskKeys.map((key, i) => <li key={key}><span>{new Intl.NumberFormat(locale).format(i + 1)}</span><div><strong>{t(key as never)}</strong><p>{t("product.plan.previewTask")}</p></div></li>)}</ol><p className="honesty-note">{t("product.instances.honesty")}</p></div>}
    {(state.step === "EXECUTION" || state.step === "OUTCOME") && <div className="progress-box"><div className="progress-heading"><strong>{t("product.execution.progress")}</strong><span><span className="stable-id">{state.execution}</span> · {new Intl.NumberFormat(locale, { style: "percent" }).format(state.execution === "COMPLETED" ? 1 : state.execution === "RUNNING" ? 0.62 : 0)}</span></div><progress value={state.execution === "COMPLETED" ? 100 : state.execution === "RUNNING" ? 62 : 0} max="100" /><p>{t("product.execution.synthetic")}</p></div>}
    <div className="action-row">{state.approval === "APPROVED" && state.execution === "NOT_STARTED" && <button onClick={() => dispatch({ type: "RUN" })}>{t("product.execution.present")}</button>}{state.execution === "RUNNING" && <button onClick={() => dispatch({ type: "COMPLETE" })}>{t("product.execution.finish")}</button>}</div>
    <div className="scenario-control"><label htmlFor="scenario">{t("product.scenario")}</label><select id="scenario" value={state.scenario} onChange={(event) => dispatch({ type: "SET_SCENARIO", scenario: event.target.value as JourneyState["scenario"] })}><option value="ALLOW">ALLOW</option><option value="DENY">DENY</option><option value="UNKNOWN">UNKNOWN</option><option value="FAILURE">FAILURE</option><option value="EMPTY">EMPTY</option><option value="LOADING">LOADING</option><option value="ERROR">ERROR</option></select></div>
  </section>;
}
