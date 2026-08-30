import type { LivePlanningJourney } from "../shared/livePlanningJourneyTypes";

export type SupplierQualityDemoState =
  | "DENIED"
  | "NOT_FOUND"
  | "AUTHORITY_MISSING"
  | "STALE"
  | "CONFLICT"
  | "ERROR";

export class SupplierQualityDemoError extends Error {
  readonly state: SupplierQualityDemoState;
  readonly reasonCode: string;

  constructor(state: SupplierQualityDemoState, reasonCode: string) {
    super(reasonCode);
    this.state = state;
    this.reasonCode = reasonCode;
  }
}

export interface SupplierQualityDemoStart {
  schemaVersion: 1;
  scenarioId: "s5-v0.2-supplier-quality-v1";
  namespace: "s5-v02-supplier-quality-demo";
  journeyId: string;
  resetConfirmationToken: string;
  replayed: boolean;
  live: LivePlanningJourney;
}

function record(value: unknown, reasonCode: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new SupplierQualityDemoError("ERROR", reasonCode);
  }
  return value as Record<string, unknown>;
}

function validate(payload: unknown): SupplierQualityDemoStart {
  const root = record(payload, "DEMO_START_ENVELOPE_INVALID");
  const live = record(root.live, "DEMO_LIVE_JOURNEY_INVALID");
  const product = record(live.product, "DEMO_PRODUCT_PROJECTION_INVALID");
  const technical = record(
    live.technical,
    "DEMO_TECHNICAL_PROJECTION_INVALID",
  );
  if (
    root.schemaVersion !== 1 ||
    root.scenarioId !== "s5-v0.2-supplier-quality-v1" ||
    root.namespace !== "s5-v02-supplier-quality-demo" ||
    typeof root.journeyId !== "string" ||
    root.journeyId !== live.journeyId ||
    live.provenance !== "LIVE_EXECUTION" ||
    JSON.stringify(product.identity) !== JSON.stringify(technical.identity) ||
    JSON.stringify(product.revision) !== JSON.stringify(technical.revision)
  ) {
    throw new SupplierQualityDemoError(
      "ERROR",
      "DEMO_CROSS_VIEW_AUTHORITY_INVALID",
    );
  }
  return root as unknown as SupplierQualityDemoStart;
}

export async function startSupplierQualityDemo(
  replayIdentity: string,
  signal?: AbortSignal,
): Promise<SupplierQualityDemoStart> {
  let response: Response;
  try {
    response = await fetch("/api/internal/demo/v1/supplier-quality-journeys", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        scenarioId: "s5-v0.2-supplier-quality-v1",
        replayIdentity,
        locale: "en",
      }),
      signal,
    });
  } catch {
    throw new SupplierQualityDemoError(
      "ERROR",
      "DEMO_START_NETWORK_UNAVAILABLE",
    );
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = record(
      record(payload, "DEMO_START_ERROR_INVALID").detail,
      "DEMO_START_ERROR_INVALID",
    );
    if (typeof detail.state !== "string" || typeof detail.reasonCode !== "string") {
      throw new SupplierQualityDemoError("ERROR", "DEMO_START_ERROR_INVALID");
    }
    throw new SupplierQualityDemoError(
      detail.state as SupplierQualityDemoState,
      detail.reasonCode,
    );
  }
  return validate(payload);
}

export async function resetSupplierQualityDemo(
  started: SupplierQualityDemoStart,
): Promise<void> {
  const response = await fetch(
    `/api/internal/demo/v1/supplier-quality-journeys/${encodeURIComponent(started.journeyId)}`,
    {
      method: "DELETE",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        scenarioId: started.scenarioId,
        namespace: started.namespace,
        tenantId: "tenant-a",
        securityDomain: "supplier-quality",
        confirmationToken: started.resetConfirmationToken,
      }),
    },
  );
  if (!response.ok) {
    throw new SupplierQualityDemoError("ERROR", "DEMO_RESET_FAILED");
  }
}
