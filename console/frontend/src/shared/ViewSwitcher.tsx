import { NavLink } from "react-router-dom";
import { useI18n } from "../i18n/useI18n";
import { useSelectedExecution } from "./SelectedExecutionContext";
import { serializeSelectedContext } from "./urlContext";

export function ViewSwitcher() {
  const { t } = useI18n();
  const { selection } = useSelectedExecution();
  const query = serializeSelectedContext(selection);
  return <nav className="view-switcher" aria-label={t("nav.views")}>
    <NavLink to={`/product?${query}`}>{t("nav.productView")}</NavLink>
    <NavLink to={`/technical?${query}`}>{t("nav.technicalView")}</NavLink>
  </nav>;
}
