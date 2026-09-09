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
const knowledgeSpec =
  "console/frontend/tests/e2e/knowledge-workbench.spec.ts" as const;
const scenarioByTitle: Readonly<Record<string, string>> = {
  "completes the real Knowledge lifecycle, retrieval, recovery and purge journey":
    "KNOWLEDGE_WORKBENCH_LIFECYCLE",
  "isolates late retrieval responses and preserves filter and exact revision context":
    "KNOWLEDGE_WORKBENCH_LATE_RESPONSE_CONTEXT",
  "validates real form inputs and keeps denied and service failures distinct at mobile width":
    "KNOWLEDGE_WORKBENCH_INPUT_DENIAL_MOBILE",
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
  firstFailureOperationId: KnowledgeOperationId | "UNKNOWN";
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
  const scenarioId = scenarioByTitle[test.title];
  if (testPath !== knowledgeSpec || !scenarioId) {
    return { testPath, scenarioId: "UNKNOWN" };
  }
  return { testPath: knowledgeSpec, scenarioId };
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
        return {
          ...identity,
          testStatus: safeStatus(result.status),
          errorClass: safeErrorClass(result),
          firstFailureOperationId:
            firstUnexpectedKnowledgeOperation(operations)?.operationId ?? "UNKNOWN",
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
