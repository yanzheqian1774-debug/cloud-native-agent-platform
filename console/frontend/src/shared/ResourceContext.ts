import { createContext, useContext } from "react";
import type { CanonicalUrlContext, UrlContextView } from "./urlContext";
import { serializeUrlContext, withUrlContext } from "./urlContext";

export const ResourceContext = createContext<CanonicalUrlContext>({});
export const useResourceContext = () => useContext(ResourceContext);

const VIEW_PATHS: Record<UrlContextView, string> = {
  product: "/product-view",
  technical: "/technical-view",
  evidence: "/evidence",
};

export function resourceViewLink(context: CanonicalUrlContext, view: UrlContextView): string {
  return `${VIEW_PATHS[view]}?${serializeUrlContext(withUrlContext(context, { view }))}`;
}
