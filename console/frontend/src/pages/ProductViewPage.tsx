import { Link, NavLink, useLocation } from "react-router-dom";
import { useI18n } from "../i18n/useI18n";
import { QuestionToOutcomeJourney } from "../product/QuestionToOutcomeJourney";

export function ProductViewPage({ supplierQualityJourneyId, onJourneyStarted }: { supplierQualityJourneyId?: string; onJourneyStarted?: (id: string) => void }) {
  const { t } = useI18n();
  const { search } = useLocation();
  return <main className="product-page question-to-outcome-page"><nav className="demo-breadcrumb" aria-label="面包屑"><Link to="/workspace">工作台</Link><span>/</span><Link to="/tasks">任务</Link><span>/</span><strong>{supplierQualityJourneyId?"供应商质量整改":"提出问题"}</strong></nav><nav className="view-switcher" aria-label={t("nav.views")}><NavLink to={{ pathname: "/product", search }}>业务视图</NavLink><NavLink to={{ pathname: "/technical", search }}>技术视图</NavLink></nav><QuestionToOutcomeJourney journeyId={supplierQualityJourneyId} onJourneyStarted={onJourneyStarted} /></main>;
}
