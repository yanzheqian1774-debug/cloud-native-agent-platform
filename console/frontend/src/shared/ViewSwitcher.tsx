import { NavLink } from "react-router-dom";
import { useI18n } from "../i18n/useI18n";
import { useLocation } from "react-router-dom";
import { parseUrlContext, serializeSelectedContext } from "./urlContext";
import { resourceViewLink } from "./ResourceContext";
import { useSelectedExecution } from "./SelectedExecutionContext";

export function ViewSwitcher() {
  const { t } = useI18n();
  const { search } = useLocation();
  const { selection }=useSelectedExecution();
  const query=serializeSelectedContext(selection);
  const parsed = parseUrlContext(search);
  if (parsed.state === "INVALID" || !parsed.context.resourceId) return <nav className="view-switcher" aria-label={t("nav.views")}>
    <NavLink to={`/product?${query}`}>{t("nav.productView")}</NavLink>
    <NavLink to={`/technical?${query}`}>{t("nav.technicalView")}</NavLink>
  </nav>;
  return <nav className="view-switcher" aria-label={t("nav.views")}>
    <NavLink to={resourceViewLink(parsed.context,"product")}>{t("nav.productView")}</NavLink>
    <NavLink to={resourceViewLink(parsed.context,"technical")}>{t("nav.technicalView")}</NavLink>
    <NavLink to={resourceViewLink(parsed.context,"evidence")}>Evidence</NavLink>
  </nav>;
}
