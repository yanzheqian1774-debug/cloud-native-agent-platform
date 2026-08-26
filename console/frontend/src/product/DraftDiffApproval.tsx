import { useI18n } from "../i18n/useI18n";
import type { JourneyState } from "./types";

interface Props { state: JourneyState; onApprove: () => void; onReject: () => void }
export function DraftDiffApproval({ state, onApprove, onReject }: Props) {
  const { t } = useI18n();
  return <section id="approvals" className="product-section panel-pad" aria-labelledby="approval-title">
    <div className="section-heading"><h2 id="approval-title">{t("product.approval.title")}</h2><p>{t("product.approval.exact")}</p></div>
    <div className="revision-row"><div><span>{t("product.draft.revision")}</span><strong className="stable-id">{state.revision}</strong></div><div><span>{t("product.diff.classification")}</span><strong className="stable-id">{state.diffClassification}</strong></div><div><span>{t("product.approval.state")}</span><strong className="stable-id">{state.approval}</strong></div></div>
    {state.diffClassification === "MATERIAL" && <div className="diff-box"><del>Include all complaint categories</del><ins>{state.correction}</ins><span className="stable-id">FIELD_REPLACED</span></div>}
    <p>{t("product.approval.decidedAt")}: <span className="stable-id">{state.decidedAt ?? "NOT_DECIDED"}</span></p>
    <div className="action-row"><button onClick={onApprove}>{t("product.approve")}</button><button className="danger-button" onClick={onReject}>{t("product.reject")}</button></div>
  </section>;
}
