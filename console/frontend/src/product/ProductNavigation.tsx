import { useI18n } from "../i18n/useI18n";
interface Props { active: string; onSelect: (section: string) => void }
export function ProductNavigation({ active, onSelect }: Props) {
  const { t } = useI18n();
  return <nav className="product-nav" aria-label="Product View">
    {["employees", "work", "approvals", "outcomes"].map((item) =>
      <button key={item} className={active === item ? "active" : ""} onClick={() => onSelect(item)} data-message-key={`product.nav.${item}`}>
        {t(`product.nav.${item}` as never)}
      </button>)}
  </nav>;
}
