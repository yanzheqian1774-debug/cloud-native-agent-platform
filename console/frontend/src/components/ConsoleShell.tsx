import type { ReactNode } from "react";

import { LanguageSwitcher } from "./LanguageSwitcher";
import { useI18n } from "../i18n/useI18n";

interface ConsoleShellProps {
  children: ReactNode;
}

export function ConsoleShell({
  children,
}: ConsoleShellProps) {
  const { t } = useI18n();

  return (
    <div className="console-shell">
      <header className="console-header">
        <div className="console-header-inner">
          <div className="console-brand">
            <span className="console-brand-mark">
              A
            </span>

            <span>{t("app.name")}</span>
          </div>

          <LanguageSwitcher />
        </div>
      </header>

      <div className="console-content">
        {children}
      </div>
    </div>
  );
}
