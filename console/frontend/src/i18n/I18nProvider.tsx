import {
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  DEFAULT_LOCALE,
  messages,
  type Locale,
  type MessageKey,
} from "./messages";
import {
  I18nContext,
  type I18nContextValue,
} from "./context";

interface I18nProviderProps {
  children: ReactNode;
}

export function I18nProvider({
  children,
}: I18nProviderProps) {
  const [locale, setLocale] =
    useState<Locale>(DEFAULT_LOCALE);

  const value = useMemo<I18nContextValue>(() => {
    function t(key: MessageKey): string {
      return (
        messages[locale][key] ??
        messages[DEFAULT_LOCALE][key] ??
        key
      );
    }

    return {
      locale,
      setLocale,
      t,
    };
  }, [locale]);

  return (
    <I18nContext.Provider value={value}>
      {children}
    </I18nContext.Provider>
  );
}
