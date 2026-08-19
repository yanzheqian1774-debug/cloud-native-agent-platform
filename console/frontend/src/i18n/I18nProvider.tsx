import {
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  DEFAULT_LOCALE,
  type Locale,
} from "./messages";
import { translate } from "./translate";
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
    function t(
      key: Parameters<typeof translate>[1],
    ): string {
      return translate(locale, key);
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
