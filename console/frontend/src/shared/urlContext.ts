import { defaultSelectedExecutionContext } from "./executionSnapshotFixture.ts";
import type { SelectedExecutionContextValue, SharedExecutionSnapshot } from "./executionSnapshotTypes.ts";

export const URL_CONTEXT_KEYS = [
  "kind", "resourceId", "revisionId", "digest", "view", "evidenceId",
  "relationshipId", "claimKey", "factKey", "businessStepId", "query",
  "kindFilter", "lifecycleFilter", "timeFrom", "timeTo", "returnTo",
] as const;

export type UrlContextKey = typeof URL_CONTEXT_KEYS[number];
export type UrlContextView = "product" | "technical" | "evidence";
export type CanonicalUrlContext = Partial<Record<UrlContextKey, string>> & { view?: UrlContextView };
export type UrlContextResult = { state: "VALID"; context: CanonicalUrlContext } | { state: "INVALID"; reason: "INVALID_URL_CONTEXT" };

const VIEWS = new Set(["product", "technical", "evidence"]);
const INTERNAL_ROUTES = [
  "/dashboard", "/catalog", "/relationships", "/attention", "/digital-employees",
  "/agents", "/skills", "/mcp", "/knowledge", "/workflow-definitions",
  "/runtime-profiles", "/product-view", "/technical-view", "/evidence",
];

export function isAllowedReturnTo(value: string): boolean {
  if (!value.startsWith("/") || value.startsWith("//")) return false;
  const [path,rawQuery=""] = value.split("?",2);
  const sensitive=/(secret|token|credential|pass.word|authorization|api[-_]?key)/i;
  if ([...new URLSearchParams(rawQuery).keys()].some(key=>sensitive.test(key))) return false;
  return INTERNAL_ROUTES.some(route => path === route || path.startsWith(`${route}/`));
}

export function parseUrlContext(search: string): UrlContextResult {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const valuesByKey: Partial<Record<UrlContextKey,string>> = {};
  for (const key of URL_CONTEXT_KEYS) {
    const values = params.getAll(key);
    if (values.length > 1) return { state: "INVALID", reason: "INVALID_URL_CONTEXT" };
    if (values[0]) {
      if (values[0].length > 2048 || [...values[0]].some(character=>character.charCodeAt(0)<32)) return { state: "INVALID", reason: "INVALID_URL_CONTEXT" };
      valuesByKey[key] = values[0];
    }
  }
  const context = valuesByKey as CanonicalUrlContext;
  if ([...params.keys()].some(key => !URL_CONTEXT_KEYS.includes(key as UrlContextKey))) return { state: "INVALID", reason: "INVALID_URL_CONTEXT" };
  if (context.view && !VIEWS.has(context.view)) return { state: "INVALID", reason: "INVALID_URL_CONTEXT" };
  if (context.returnTo && !isAllowedReturnTo(context.returnTo)) return { state: "INVALID", reason: "INVALID_URL_CONTEXT" };
  const tuple = [context.resourceId, context.revisionId, context.digest];
  if (tuple.some(Boolean) && !tuple.every(Boolean)) return { state: "INVALID", reason: "INVALID_URL_CONTEXT" };
  return { state: "VALID", context };
}

export function serializeUrlContext(context: CanonicalUrlContext): string {
  const params = new URLSearchParams();
  for (const key of URL_CONTEXT_KEYS) {
    const value = context[key];
    if (value) params.set(key, value);
  }
  return params.toString();
}

export function withUrlContext(context: CanonicalUrlContext, updates: CanonicalUrlContext): CanonicalUrlContext {
  const next = { ...context, ...updates };
  return Object.fromEntries(Object.entries(next).filter(([, value]) => Boolean(value))) as CanonicalUrlContext;
}

const KEYS: (keyof SelectedExecutionContextValue)[] = ["employeeId", "revisionId", "workId", "workflowId", "taskId", "executionId", "graphSnapshotId"];

export function serializeSelectedContext(value: SelectedExecutionContextValue): string {
  const params = new URLSearchParams();
  KEYS.forEach((key) => params.set(key, value[key]));
  return params.toString();
}

export function parseSelectedContext(search: string, snapshot: SharedExecutionSnapshot): SelectedExecutionContextValue {
  const params = new URLSearchParams(search);
  const suppliedKeys = [...params.keys()];
  if (suppliedKeys.length === 0) return { ...defaultSelectedExecutionContext };
  if (
    suppliedKeys.length !== KEYS.length
    || !suppliedKeys.every((key) => KEYS.includes(key as keyof SelectedExecutionContextValue))
    || KEYS.some((key) => params.getAll(key).length !== 1)
  ) return { ...defaultSelectedExecutionContext };
  const candidate = Object.fromEntries(KEYS.map((key) => [key, params.get(key)])) as unknown as SelectedExecutionContextValue;
  const validEmployee = snapshot.employees.some((employee) => employee.id === candidate.employeeId);
  const stableKeys = KEYS.filter((key) => key !== "employeeId");
  if (!validEmployee || stableKeys.some((key) => candidate[key] !== snapshot.selectedContext[key])) return { ...defaultSelectedExecutionContext };
  return candidate;
}
