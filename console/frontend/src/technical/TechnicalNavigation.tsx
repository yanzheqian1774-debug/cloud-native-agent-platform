import { useI18n } from "../i18n/useI18n";

const sections = ["identity", "graph", "runtime", "capability", "outcome"] as const;

export function TechnicalNavigation({ active, onSelect }: { active: string; onSelect: (section: string) => void }) {
  const { t } = useI18n();
  return <nav className="technical-nav" aria-label={t("technical.nav.label")}>
    {sections.map((section) => <button key={section} className={active === section ? "active" : ""} aria-current={active === section ? "page" : undefined} onClick={() => onSelect(section)}>{t(`technical.nav.${section}` as never)}</button>)}
  </nav>;
}
