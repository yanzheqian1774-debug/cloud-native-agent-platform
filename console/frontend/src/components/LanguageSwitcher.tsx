import { useI18n } from "../i18n/useI18n";
import type { Locale } from "../i18n/messages";

const localeOptions: Array<{
  locale: Locale;
  label: string;
}> = [
  {
    locale: "en-US",
    label: "English",
  },
  {
    locale: "zh-CN",
    label: "中文",
  },
];

export function LanguageSwitcher() {
  const {
    locale,
    setLocale,
  } = useI18n();

  return (
    <div
      className="language-switcher"
      aria-label="Language"
    >
      {localeOptions.map((option) => (
        <button
          key={option.locale}
          type="button"
          className={
            locale === option.locale
              ? "language-option language-option-active"
              : "language-option"
          }
          onClick={() => setLocale(option.locale)}
          aria-pressed={locale === option.locale}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
