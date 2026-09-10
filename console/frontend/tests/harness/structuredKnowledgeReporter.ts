import type {
  FullConfig,
  FullResult,
  Reporter,
  Suite,
  TestCase,
  TestResult,
} from "@playwright/test/reporter";
import type { TestInfo } from "@playwright/test";
import { mkdir, rename, writeFile } from "node:fs/promises";
import { dirname } from "node:path";

export const KNOWLEDGE_OPERATION_IDS = [
  "KNOWLEDGE_GOVERNED_CREATE_PUBLISH",
  "KNOWLEDGE_INDEX_RETRIEVE",
  "KNOWLEDGE_UPDATE",
  "KNOWLEDGE_RESTART_READBACK",
  "KNOWLEDGE_PURGE_RECOVERY",
] as const;

export const KNOWLEDGE_RESULT_STATES = ["EXPECTED", "UNEXPECTED"] as const;

export type KnowledgeOperationId = (typeof KNOWLEDGE_OPERATION_IDS)[number];
export type KnowledgeResultState = (typeof KNOWLEDGE_RESULT_STATES)[number];

export type KnowledgeOperationResult = {
  operationId: KnowledgeOperationId;
  resultState: KnowledgeResultState;
  structuredHttpStatus?: number;
};

const attachmentName = "knowledge-operation-result.v1";
const attachmentContentType =
  "application/vnd.agent-platform.knowledge-operation-result.v1+json";
const scenarioByIdentity: Readonly<Record<string, string>> = {
  "knowledge-workbench.spec.ts\0completes the real Knowledge lifecycle, retrieval, recovery and purge journey":
    "KNOWLEDGE_WORKBENCH_LIFECYCLE",
  "knowledge-workbench.spec.ts\0isolates late retrieval responses and preserves filter and exact revision context":
    "KNOWLEDGE_WORKBENCH_LATE_RESPONSE_CONTEXT",
  "knowledge-workbench.spec.ts\0validates real form inputs and keeps denied and service failures distinct at mobile width":
    "KNOWLEDGE_WORKBENCH_INPUT_DENIAL_MOBILE",
  "wave-3b-product-technical-evidence.spec.ts\0proves all twelve Wave 3B real-service browser journeys":
    "WAVE_3B_REAL_SERVICE_JOURNEYS",
};

const diagnosticOperationByStepTitle: Readonly<Record<string, string>> = {
  KNOWLEDGE_INDEX_SUBMIT: "KNOWLEDGE_INDEX_SUBMIT",
  KNOWLEDGE_INDEX_READY: "KNOWLEDGE_INDEX_READY",
  KNOWLEDGE_INDEX_AUTHORITY_READBACK: "KNOWLEDGE_INDEX_AUTHORITY_READBACK",
  KNOWLEDGE_RETRIEVAL_SUBMIT: "KNOWLEDGE_RETRIEVAL_SUBMIT",
  KNOWLEDGE_RETRIEVAL_RESULT_RENDERED: "KNOWLEDGE_RETRIEVAL_RESULT_RENDERED",
  KNOWLEDGE_RETRIEVAL_CITATION_VERIFIED: "KNOWLEDGE_RETRIEVAL_CITATION_VERIFIED",
  KNOWLEDGE_SEARCH_RESULT_RENDERED: "KNOWLEDGE_SEARCH_RESULT_RENDERED",
  KNOWLEDGE_EVALUATION_RECORDED: "KNOWLEDGE_EVALUATION_RECORDED",
  KNOWLEDGE_SUMMARY_RECORDED: "KNOWLEDGE_SUMMARY_RECORDED",
  KNOWLEDGE_IMPORT_PREVIEW: "KNOWLEDGE_IMPORT_PREVIEW",
  KNOWLEDGE_IMPORT_EXECUTE: "KNOWLEDGE_IMPORT_EXECUTE",
  KNOWLEDGE_IMPORT_RETRY: "KNOWLEDGE_IMPORT_RETRY",
  KNOWLEDGE_DUPLICATE_REVIEW: "KNOWLEDGE_DUPLICATE_REVIEW",
  KNOWLEDGE_SCOPE_DENIAL_READBACK: "KNOWLEDGE_SCOPE_DENIAL_READBACK",
  WAVE3B_SETUP_BACKEND_READY: "WAVE3B_SETUP_BACKEND_READY",
  WAVE3B_SETUP_SKILL_PUBLISHED: "WAVE3B_SETUP_SKILL_PUBLISHED",
  WAVE3B_SETUP_MCP_SELECTED: "WAVE3B_SETUP_MCP_SELECTED",
  WAVE3B_SETUP_KNOWLEDGE_INDEXED: "WAVE3B_SETUP_KNOWLEDGE_INDEXED",
  WAVE3B_SETUP_RUNTIME_PUBLISHED: "WAVE3B_SETUP_RUNTIME_PUBLISHED",
  WAVE3B_SETUP_WORKFLOW_PUBLISHED: "WAVE3B_SETUP_WORKFLOW_PUBLISHED",
  WAVE3B_SETUP_AGENT_PUBLISHED: "WAVE3B_SETUP_AGENT_PUBLISHED",
  WAVE3B_SETUP_TRACEABILITY_READBACK: "WAVE3B_SETUP_TRACEABILITY_READBACK",
  "1 context-preserving catalog round trip": "WAVE3B_01_CATALOG_ROUND_TRIP",
  "2 claim Evidence fact business-step chain": "WAVE3B_02_EVIDENCE_CHAIN",
  "3 fact reverses to exact claim": "WAVE3B_03_FACT_TO_CLAIM",
  "4 Agent retains five exact bindings": "WAVE3B_04_AGENT_BINDINGS",
  "5 Workflow task edge and lifecycle Evidence survive":
    "WAVE3B_05_WORKFLOW_EVIDENCE",
  "6 Runtime remains declaration-only": "WAVE3B_06_RUNTIME_DECLARATION",
  "7 Knowledge routine precedes advanced": "WAVE3B_07_KNOWLEDGE_HIERARCHY",
  WAVE3B_08_NAVIGATION: "WAVE3B_08_NAVIGATION",
  WAVE3B_08_MAKE_STALE: "WAVE3B_08_MAKE_STALE",
  WAVE3B_08_CONFLICT_WRITE: "WAVE3B_08_CONFLICT_WRITE",
  WAVE3B_08_ERROR_UI: "WAVE3B_08_ERROR_UI",
  WAVE3B_08_AUTHORITATIVE_READBACK: "WAVE3B_08_AUTHORITATIVE_READBACK",
  WAVE3B_08_EXPLICIT_RECOVERY: "WAVE3B_08_EXPLICIT_RECOVERY",
  WAVE3B_08_FINAL_ASSERTION: "WAVE3B_08_FINAL_ASSERTION",
  "9 denied and absent are nondisclosing": "WAVE3B_09_BOUNDED_DISCLOSURE",
  "10 unavailable backend shows no false success": "WAVE3B_10_BACKEND_UNAVAILABLE",
  WAVE3B_10_BACKEND_READY: "WAVE3B_10_BACKEND_READY",
  WAVE3B_11_ENTER_TECHNICAL_PAGE: "WAVE3B_11_ENTER_TECHNICAL_PAGE",
  WAVE3B_11_RESTART_READINESS: "WAVE3B_11_RESTART_READINESS",
  WAVE3B_11_RELOAD: "WAVE3B_11_RELOAD",
  WAVE3B_11_REVISION_IDENTITY_CHECK: "WAVE3B_11_REVISION_IDENTITY_CHECK",
  WAVE3B_12_MOBILE_NAVIGATION: "WAVE3B_12_MOBILE_NAVIGATION",
  WAVE3B_12_OPEN_EVIDENCE: "WAVE3B_12_OPEN_EVIDENCE",
  WAVE3B_12_CLOSE_FOCUS_CHECK: "WAVE3B_12_CLOSE_FOCUS_CHECK",
  WAVE3B_12_CLOSE_ACTION: "WAVE3B_12_CLOSE_ACTION",
  WAVE3B_12_CLAIM_FOCUS_RESTORED: "WAVE3B_12_CLAIM_FOCUS_RESTORED",
  WAVE3B_12_USER_FOCUS_TRANSFER_SETUP:
    "WAVE3B_12_USER_FOCUS_TRANSFER_SETUP",
  WAVE3B_12_USER_FOCUS_TRANSFER: "WAVE3B_12_USER_FOCUS_TRANSFER",
  WAVE3B_12_USER_FOCUS_PRESERVED: "WAVE3B_12_USER_FOCUS_PRESERVED",
};

const diagnosticOperationsByScenario: Readonly<Record<string, readonly string[]>> = {
  KNOWLEDGE_WORKBENCH_LIFECYCLE: [
    "KNOWLEDGE_INDEX_SUBMIT",
    "KNOWLEDGE_INDEX_READY",
    "KNOWLEDGE_INDEX_AUTHORITY_READBACK",
    "KNOWLEDGE_RETRIEVAL_SUBMIT",
    "KNOWLEDGE_RETRIEVAL_RESULT_RENDERED",
    "KNOWLEDGE_RETRIEVAL_CITATION_VERIFIED",
    "KNOWLEDGE_SEARCH_RESULT_RENDERED",
    "KNOWLEDGE_EVALUATION_RECORDED",
    "KNOWLEDGE_SUMMARY_RECORDED",
    "KNOWLEDGE_IMPORT_PREVIEW",
    "KNOWLEDGE_IMPORT_EXECUTE",
    "KNOWLEDGE_IMPORT_RETRY",
    "KNOWLEDGE_DUPLICATE_REVIEW",
    "KNOWLEDGE_SCOPE_DENIAL_READBACK",
  ],
  WAVE_3B_REAL_SERVICE_JOURNEYS: [
    "WAVE3B_SETUP_BACKEND_READY",
    "WAVE3B_SETUP_SKILL_PUBLISHED",
    "WAVE3B_SETUP_MCP_SELECTED",
    "WAVE3B_SETUP_KNOWLEDGE_INDEXED",
    "WAVE3B_SETUP_RUNTIME_PUBLISHED",
    "WAVE3B_SETUP_WORKFLOW_PUBLISHED",
    "WAVE3B_SETUP_AGENT_PUBLISHED",
    "WAVE3B_SETUP_TRACEABILITY_READBACK",
    "WAVE3B_01_CATALOG_ROUND_TRIP",
    "WAVE3B_02_EVIDENCE_CHAIN",
    "WAVE3B_03_FACT_TO_CLAIM",
    "WAVE3B_04_AGENT_BINDINGS",
    "WAVE3B_05_WORKFLOW_EVIDENCE",
    "WAVE3B_06_RUNTIME_DECLARATION",
    "WAVE3B_07_KNOWLEDGE_HIERARCHY",
    "WAVE3B_08_NAVIGATION",
    "WAVE3B_08_MAKE_STALE",
    "WAVE3B_08_CONFLICT_WRITE",
    "WAVE3B_08_ERROR_UI",
    "WAVE3B_08_AUTHORITATIVE_READBACK",
    "WAVE3B_08_EXPLICIT_RECOVERY",
    "WAVE3B_08_FINAL_ASSERTION",
    "WAVE3B_09_BOUNDED_DISCLOSURE",
    "WAVE3B_10_BACKEND_UNAVAILABLE",
    "WAVE3B_10_BACKEND_READY",
    "WAVE3B_11_ENTER_TECHNICAL_PAGE",
    "WAVE3B_11_RESTART_READINESS",
    "WAVE3B_11_RELOAD",
    "WAVE3B_11_REVISION_IDENTITY_CHECK",
    "WAVE3B_12_MOBILE_NAVIGATION",
    "WAVE3B_12_OPEN_EVIDENCE",
    "WAVE3B_12_CLOSE_FOCUS_CHECK",
    "WAVE3B_12_CLOSE_ACTION",
    "WAVE3B_12_CLAIM_FOCUS_RESTORED",
    "WAVE3B_12_USER_FOCUS_TRANSFER_SETUP",
    "WAVE3B_12_USER_FOCUS_TRANSFER",
    "WAVE3B_12_USER_FOCUS_PRESERVED",
  ],
};

type SafeTestStatus = "FAILED" | "INTERRUPTED" | "TIMED_OUT";
type SafeErrorClass =
  | "ASSERTION"
  | "INTERRUPTED"
  | "NAVIGATION"
  | "TIMEOUT"
  | "UNKNOWN";

type SafeFailure = {
  testPath: string;
  scenarioId: string;
  testStatus: SafeTestStatus;
  errorClass: SafeErrorClass;
  lastCompletedOperationId: string;
  firstFailureOperationId: string;
};

type DiagnosticResult = {
  test: TestCase;
  result: TestResult;
  operations: KnowledgeOperationResult[];
};

function hasExactKeys(value: Record<string, unknown>) {
  const keys = Object.keys(value).sort();
  const allowed = value.structuredHttpStatus === undefined
    ? ["operationId", "resultState"]
    : ["operationId", "resultState", "structuredHttpStatus"];
  return keys.length === allowed.length
    && keys.every((key, index) => key === allowed.sort()[index]);
}

export function normalizeKnowledgeOperationResult(
  value: unknown,
): KnowledgeOperationResult {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("knowledge operation result must be an object");
  }
  const candidate = value as Record<string, unknown>;
  if (!hasExactKeys(candidate)) {
    throw new Error("knowledge operation result contains an unsupported field");
  }
  if (!KNOWLEDGE_OPERATION_IDS.includes(
    candidate.operationId as KnowledgeOperationId,
  )) {
    throw new Error("knowledge operation ID is not closed");
  }
  if (!KNOWLEDGE_RESULT_STATES.includes(
    candidate.resultState as KnowledgeResultState,
  )) {
    throw new Error("knowledge result state is not closed");
  }
  if (candidate.structuredHttpStatus !== undefined && (
    typeof candidate.structuredHttpStatus !== "number"
    || !Number.isInteger(candidate.structuredHttpStatus)
    || candidate.structuredHttpStatus < 100
    || candidate.structuredHttpStatus > 599
  )) {
    throw new Error("structured HTTP status must be an integer from 100 through 599");
  }
  return candidate as KnowledgeOperationResult;
}

export function orderKnowledgeOperationResults(values: readonly unknown[]) {
  const results = values.map(normalizeKnowledgeOperationResult);
  const operationOrder = new Map(
    KNOWLEDGE_OPERATION_IDS.map((operationId, index) => [operationId, index]),
  );
  const seen = new Set<KnowledgeOperationId>();
  for (const result of results) {
    if (seen.has(result.operationId)) {
      throw new Error("knowledge operation result is duplicated");
    }
    seen.add(result.operationId);
  }
  return results.toSorted(
    (left, right) => operationOrder.get(left.operationId)!
      - operationOrder.get(right.operationId)!,
  );
}

export function firstUnexpectedKnowledgeOperation(values: readonly unknown[]) {
  return orderKnowledgeOperationResults(values).find(
    (result) => result.resultState === "UNEXPECTED",
  );
}

export async function attachKnowledgeOperationResult(
  testInfo: TestInfo,
  value: KnowledgeOperationResult,
) {
  const result = normalizeKnowledgeOperationResult(value);
  await testInfo.attach(attachmentName, {
    body: Buffer.from(JSON.stringify(result), "utf8"),
    contentType: attachmentContentType,
  });
}

async function attachWithoutReplacingFailure(
  testInfo: TestInfo,
  value: KnowledgeOperationResult,
) {
  try {
    await attachKnowledgeOperationResult(testInfo, value);
  } catch {
    // Diagnostic attachment failure must not replace the tested operation result.
  }
}

export async function runKnowledgeOperation<T>(
  testInfo: TestInfo,
  operationId: KnowledgeOperationId,
  operation: () => Promise<T>,
  structuredHttpStatusFromResult?: (result: T) => number | undefined,
) {
  try {
    const result = await operation();
    const structuredHttpStatus = structuredHttpStatusFromResult?.(result);
    await attachWithoutReplacingFailure(testInfo, {
      operationId,
      resultState: "EXPECTED",
      ...(structuredHttpStatus === undefined ? {} : { structuredHttpStatus }),
    });
    return result;
  } catch (error) {
    await attachWithoutReplacingFailure(testInfo, {
      operationId,
      resultState: "UNEXPECTED",
    });
    throw error;
  }
}

export function operationResultsFromTestResult(
  result: Pick<TestResult, "attachments">,
) {
  return orderKnowledgeOperationResults(result.attachments
    .filter(
      (attachment) => attachment.name === attachmentName
        && attachment.contentType === attachmentContentType,
    )
    .map((attachment) => {
      if (!attachment.body) {
        throw new Error("knowledge operation attachment body is required");
      }
      return JSON.parse(attachment.body.toString("utf8")) as unknown;
    }));
}

function safeIdentity(test: TestCase) {
  const normalizedPath = test.location.file.replaceAll("\\", "/");
  const marker = "/console/frontend/tests/e2e/";
  const markerIndex = normalizedPath.lastIndexOf(marker);
  const suffix = markerIndex === -1
    ? ""
    : normalizedPath.slice(markerIndex + marker.length);
  const testPath = suffix
    && !suffix.includes("..")
    && /^[A-Za-z0-9][A-Za-z0-9._/-]*\.spec\.ts$/.test(suffix)
    ? `console/frontend/tests/e2e/${suffix}`
    : "UNKNOWN";
  const scenarioId = scenarioByIdentity[`${suffix}\0${test.title}`];
  return { testPath, scenarioId: scenarioId ?? "UNKNOWN" };
}

export function diagnosticProgressFromTestResult(
  result: Pick<TestResult, "steps">,
  scenarioId: string,
  operations: readonly KnowledgeOperationResult[] = [],
) {
  let lastCompletedOperationId = "UNKNOWN";
  let firstFailureOperationId = "UNKNOWN";
  const steps = result.steps ?? [];
  for (const step of steps) {
    const operationId = diagnosticOperationByStepTitle[step.title];
    if (!operationId) continue;
    if (step.error) {
      firstFailureOperationId = operationId;
      break;
    }
    lastCompletedOperationId = operationId;
  }
  if (firstFailureOperationId === "UNKNOWN") {
    const ordered = orderKnowledgeOperationResults(operations);
    const failureIndex = ordered.findIndex(
      (operation) => operation.resultState === "UNEXPECTED",
    );
    if (failureIndex >= 0) {
      firstFailureOperationId = ordered[failureIndex].operationId;
      lastCompletedOperationId = lastCompletedOperationId === "UNKNOWN" && failureIndex > 0
        ? ordered[failureIndex - 1].operationId
        : lastCompletedOperationId;
    }
  }
  if (firstFailureOperationId === "UNKNOWN") {
    const expected = diagnosticOperationsByScenario[scenarioId] ?? [];
    const completed = new Set(steps
      .filter((step) => !step.error)
      .map((step) => diagnosticOperationByStepTitle[step.title])
      .filter((operationId): operationId is string => operationId !== undefined));
    firstFailureOperationId = expected.find(
      (operationId) => !completed.has(operationId),
    ) ?? "UNKNOWN";
  }
  return { lastCompletedOperationId, firstFailureOperationId };
}

function safeStatus(status: TestResult["status"]): SafeTestStatus {
  if (status === "timedOut") return "TIMED_OUT";
  if (status === "interrupted") return "INTERRUPTED";
  return "FAILED";
}

function safeErrorClass(result: TestResult): SafeErrorClass {
  if (result.status === "timedOut") return "TIMEOUT";
  if (result.status === "interrupted") return "INTERRUPTED";
  const transient = result.errors
    .map((error) => `${error.name ?? ""} ${error.message ?? ""}`)
    .join(" ")
    .toLowerCase();
  if (/timeout|timed out/.test(transient)) return "TIMEOUT";
  if (/net::err_|navigation|page\.goto/.test(transient)) return "NAVIGATION";
  if (/expect\(|locator|tobe|tohave|assert/.test(transient)) return "ASSERTION";
  return "UNKNOWN";
}

async function writePrivateJson(outputPath: string, value: unknown) {
  const temporaryPath = `${outputPath}.${process.pid}.tmp`;
  await mkdir(dirname(outputPath), { recursive: true, mode: 0o700 });
  await writeFile(temporaryPath, `${JSON.stringify(value)}\n`, {
    encoding: "utf8",
    mode: 0o600,
  });
  await rename(temporaryPath, outputPath);
}

async function writeWithoutAffectingTests(outputPath: string | undefined, value: unknown) {
  if (!outputPath) return;
  try {
    await writePrivateJson(outputPath, value);
  } catch {
    // CI enforces artifact presence separately; reporter I/O never changes test status.
  }
}

class StructuredKnowledgeReporter implements Reporter {
  private selected = 0;
  private readonly attempts = new Map<string, DiagnosticResult[]>();

  onBegin(_config: FullConfig, suite: Suite) {
    this.selected = suite.allTests().length;
  }

  async onTestEnd(test: TestCase, result: TestResult) {
    let operations: KnowledgeOperationResult[];
    try {
      operations = operationResultsFromTestResult(result);
    } catch {
      operations = [];
    }
    const attempts = this.attempts.get(test.id) ?? [];
    attempts.push({ test, result, operations });
    this.attempts.set(test.id, attempts);

    if (operations.length > 0) {
      await writeWithoutAffectingTests(
        process.env.KNOWLEDGE_STRUCTURED_REPORT_PATH,
        operations,
      );
    }
    await this.writeDiagnostic("RUNNING");
  }

  async onEnd(result: FullResult) {
    const completionState = result.status === "passed"
      ? "PASSED"
      : result.status === "timedout"
        ? "TIMED_OUT"
        : result.status === "interrupted"
          ? "INTERRUPTED"
          : "FAILED";
    await this.writeDiagnostic(completionState);
  }

  private async writeDiagnostic(completionState: string) {
    const finalAttempts = [...this.attempts.values()]
      .map((attempts) => attempts.at(-1)!)
      .sort((left, right) => left.test.id.localeCompare(right.test.id));
    const failures: SafeFailure[] = finalAttempts
      .filter(({ result }) => ["failed", "timedOut", "interrupted"].includes(result.status))
      .map(({ test, result, operations }) => {
        const identity = safeIdentity(test);
        const progress = diagnosticProgressFromTestResult(
          result,
          identity.scenarioId,
          operations,
        );
        return {
          ...identity,
          testStatus: safeStatus(result.status),
          errorClass: safeErrorClass(result),
          ...progress,
        };
      });
    const passed = finalAttempts.filter(({ result }) => result.status === "passed").length;
    const skipped = finalAttempts.filter(({ result }) => result.status === "skipped").length;
    const failed = failures.length;
    const flaky = [...this.attempts.values()].filter((attempts) =>
      attempts.length > 1
      && attempts.at(-1)?.result.status === "passed"
      && attempts.slice(0, -1).some(({ result }) => result.status !== "passed")
    ).length;
    await writeWithoutAffectingTests(
      process.env.KNOWLEDGE_DIAGNOSTIC_REPORT_PATH,
      {
        schemaVersion: 1,
        completionState,
        counts: {
          selected: this.selected,
          executed: passed + failed,
          passed,
          failed,
          skipped,
          flaky,
        },
        failures,
      },
    );
  }
}

export default StructuredKnowledgeReporter;
