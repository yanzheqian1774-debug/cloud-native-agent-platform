import {
  DEFAULT_LOCALE,
  messages,
  type Locale,
  type MessageKey,
} from "./messages";

type MessageCatalog = Record<
  Locale,
  Partial<Record<MessageKey, string>>
>;

const catalog: MessageCatalog = messages;

export function translate(
  locale: Locale,
  key: MessageKey,
): string {
  return (
    catalog[locale][key] ??
    catalog[DEFAULT_LOCALE][key] ??
    key
  );
}
