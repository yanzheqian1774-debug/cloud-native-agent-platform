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

export const SKILL_MCP_OPERATION_IDS = [
  "SKILL_MCP_BACKEND_READY",
  "SKILL_MCP_MCP_PUBLISHED",
  "SKILL_MCP_HEALTH_SUBMIT",
  "SKILL_MCP_HEALTH_HTTP_COMPLETION",
  "SKILL_MCP_HEALTH_UI_RENDERED",
  "SKILL_MCP_DISCOVERY_SUBMIT",
  "SKILL_MCP_DISCOVERY_HTTP_COMPLETION",
  "SKILL_MCP_DISCOVERY_SNAPSHOT_READBACK",
  "SKILL_MCP_DISCOVERY_UI_RENDERED",
  "SKILL_MCP_TOOL_SELECTION_SUBMIT",
  "SKILL_MCP_TOOL_SELECTION_HTTP_COMPLETION",
  "SKILL_MCP_TOOL_SELECTION_READBACK",
  "SKILL_MCP_REDISCOVERY_SUBMIT",
  "SKILL_MCP_REDISCOVERY_HTTP_COMPLETION",
  "SKILL_MCP_REDISCOVERY_SNAPSHOT_READBACK",
  "SKILL_MCP_REDISCOVERY_UI_RENDERED",
  "SKILL_MCP_RESELECTION_SUBMIT",
  "SKILL_MCP_RESELECTION_HTTP_COMPLETION",
  "SKILL_MCP_RESELECTION_READBACK",
  "SKILL_MCP_MCP_INVOCATION_SUBMIT",
  "SKILL_MCP_MCP_INVOCATION_HTTP_COMPLETION",
  "SKILL_MCP_MCP_INVOCATION_UI_RENDERED",
  "SKILL_MCP_SKILL_PUBLISHED",
  "SKILL_MCP_SKILL_DIRECTORY_DEFAULT_VIEW",
  "SKILL_MCP_SKILL_DIRECTORY_COMPACT_VIEW",
  "SKILL_MCP_SKILL_DIRECTORY_QUERY",
  "SKILL_MCP_SKILL_DIRECTORY_LIFECYCLE",
  "SKILL_MCP_SKILL_DIRECTORY_SELECTION",
  "SKILL_MCP_SKILL_QUERY_CONTEXT",
  "SKILL_MCP_SKILL_LIFECYCLE_CONTEXT",
  "SKILL_MCP_SKILL_RESOURCE_CONTEXT",
  "SKILL_MCP_SKILL_TEST_NAME_INPUT",
  "SKILL_MCP_SKILL_TEST_REQUEST_INPUT",
  "SKILL_MCP_SKILL_TEST_EXPECTED_INPUT",
  "SKILL_MCP_SKILL_TEST_SAVE",
  "SKILL_MCP_SKILL_TEST_RUN",
  "SKILL_MCP_SKILL_TEST_RESULT_RENDERED",
  "SKILL_MCP_BIND_SUBMIT",
  "SKILL_MCP_BIND_HTTP_COMPLETION",
  "SKILL_MCP_BIND_READBACK",
  "SKILL_MCP_SKILL_INVOCATION_SUBMIT",
  "SKILL_MCP_SKILL_INVOCATION_HTTP_COMPLETION",
  "SKILL_MCP_SKILL_INVOCATION_UI_RENDERED",
  "SKILL_MCP_FINAL_UI_INTERACTION",
] as const;

export type SkillMcpOperationId = (typeof SKILL_MCP_OPERATION_IDS)[number];
type ResultState = "EXPECTED" | "UNEXPECTED";
export type SkillMcpOperationResult = {
  operationId: SkillMcpOperationId;
  resultState: ResultState;
  structuredHttpStatus?: number;
};

const attachmentName = "skill-mcp-operation-result.v1";
const attachmentContentType =
  "application/vnd.agent-platform.skill-mcp-operation-result.v1+json";
const scenarioId = "SKILL_MCP_WORKBENCH_PUBLISH_BIND_AUTHORIZE";
const scenarioTitle = "publishes, binds and authorizes one bounded real capability test";
const scenarioFile = "skill-mcp-workbench.spec.ts";

function normalize(value: unknown): SkillMcpOperationResult {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("Skill/MCP operation result must be an object");
  }
  const candidate = value as Record<string, unknown>;
  const allowed = candidate.structuredHttpStatus === undefined
    ? ["operationId", "resultState"]
    : ["operationId", "resultState", "structuredHttpStatus"];
  const keys = Object.keys(candidate).sort();
  if (keys.length !== allowed.length
    || !keys.every((key, index) => key === allowed.sort()[index])) {
    throw new Error("Skill/MCP operation result contains an unsupported field");
  }
  if (!SKILL_MCP_OPERATION_IDS.includes(candidate.operationId as SkillMcpOperationId)) {
    throw new Error("Skill/MCP operation ID is not closed");
  }
  if (!(["EXPECTED", "UNEXPECTED"] as const).includes(candidate.resultState as ResultState)) {
    throw new Error("Skill/MCP result state is not closed");
  }
  if (candidate.structuredHttpStatus !== undefined && (
    typeof candidate.structuredHttpStatus !== "number"
    || !Number.isInteger(candidate.structuredHttpStatus)
    || candidate.structuredHttpStatus < 100
    || candidate.structuredHttpStatus > 599
  )) {
    throw new Error("structured HTTP status must be an integer from 100 through 599");
  }
  return candidate as SkillMcpOperationResult;
}

function order(values: readonly unknown[]) {
  const results = values.map(normalize);
  const positions = new Map(SKILL_MCP_OPERATION_IDS.map((id, index) => [id, index]));
  const seen = new Set<SkillMcpOperationId>();
  for (const result of results) {
    if (seen.has(result.operationId)) throw new Error("Skill/MCP result is duplicated");
    seen.add(result.operationId);
  }
  return results.sort((left, right) =>
    positions.get(left.operationId)! - positions.get(right.operationId)!);
}

export async function recordSkillMcpOperationResult(
  testInfo: TestInfo,
  value: SkillMcpOperationResult,
) {
  try {
    const result = normalize(value);
    await testInfo.attach(attachmentName, {
      body: Buffer.from(JSON.stringify(result), "utf8"),
      contentType: attachmentContentType,
    });
  } catch {
    // Diagnostics must never replace the tested operation result.
  }
}

function operationResults(result: Pick<TestResult, "attachments">) {
  return order(result.attachments
    .filter((attachment) => attachment.name === attachmentName
      && attachment.contentType === attachmentContentType)
    .map((attachment) => {
      if (!attachment.body) throw new Error("Skill/MCP attachment body is required");
      return JSON.parse(attachment.body.toString("utf8")) as unknown;
    }));
}

function safeIdentity(test: TestCase) {
  const normalized = test.location.file.replaceAll("\\", "/");
  const marker = "/console/frontend/tests/e2e/";
  const index = normalized.lastIndexOf(marker);
  const suffix = index === -1 ? "" : normalized.slice(index + marker.length);
  const testPath = suffix && !suffix.includes("..")
    && /^[A-Za-z0-9][A-Za-z0-9._/-]*\.spec\.ts$/.test(suffix)
    ? `console/frontend/tests/e2e/${suffix}`
    : "UNKNOWN";
  const known = suffix === scenarioFile && test.title === scenarioTitle;
  return { testPath, scenarioId: known ? scenarioId : "UNKNOWN" };
}

export function skillMcpDiagnosticProgress(
  result: Pick<TestResult, "steps">,
  knownScenario: boolean,
  operations: readonly SkillMcpOperationResult[] = [],
) {
  let lastCompletedOperationId = "UNKNOWN";
  let firstFailureOperationId = "UNKNOWN";
  const steps = result.steps ?? [];
  for (const step of steps) {
    if (!SKILL_MCP_OPERATION_IDS.includes(step.title as SkillMcpOperationId)) continue;
    if (step.error) {
      firstFailureOperationId = step.title;
      break;
    }
    lastCompletedOperationId = step.title;
  }
  if (firstFailureOperationId === "UNKNOWN") {
    const unexpected = order(operations).find((item) => item.resultState === "UNEXPECTED");
    if (unexpected) firstFailureOperationId = unexpected.operationId;
  }
  if (firstFailureOperationId === "UNKNOWN" && knownScenario) {
    const completed = new Set(steps
      .filter((step) => !step.error)
      .map((step) => step.title as SkillMcpOperationId)
      .filter((title) => SKILL_MCP_OPERATION_IDS.includes(title)));
    firstFailureOperationId = SKILL_MCP_OPERATION_IDS.find((id) => !completed.has(id))
      ?? "UNKNOWN";
  }
  return { lastCompletedOperationId, firstFailureOperationId };
}

function safeStatus(status: TestResult["status"]) {
  if (status === "timedOut") return "TIMED_OUT";
  if (status === "interrupted") return "INTERRUPTED";
  return "FAILED";
}

function safeErrorClass(result: TestResult) {
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

async function writeDiagnostic(outputPath: string | undefined, value: unknown) {
  if (!outputPath) return;
  try {
    const temporaryPath = `${outputPath}.${process.pid}.tmp`;
    await mkdir(dirname(outputPath), { recursive: true, mode: 0o700 });
    await writeFile(temporaryPath, `${JSON.stringify(value)}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    await rename(temporaryPath, outputPath);
  } catch {
    // Artifact retention is a separate gate; reporter I/O does not change tests.
  }
}

type Attempt = { test: TestCase; result: TestResult; operations: SkillMcpOperationResult[] };

class StructuredSkillMcpReporter implements Reporter {
  private selected = 0;
  private readonly attempts = new Map<string, Attempt[]>();

  onBegin(_config: FullConfig, suite: Suite) {
    this.selected = suite.allTests().length;
  }

  async onTestEnd(test: TestCase, result: TestResult) {
    let operations: SkillMcpOperationResult[] = [];
    try { operations = operationResults(result); } catch { /* sanitized UNKNOWN */ }
    const attempts = this.attempts.get(test.id) ?? [];
    attempts.push({ test, result, operations });
    this.attempts.set(test.id, attempts);
    await this.write("RUNNING");
  }

  async onEnd(result: FullResult) {
    const completion = result.status === "passed" ? "PASSED"
      : result.status === "timedout" ? "TIMED_OUT"
      : result.status === "interrupted" ? "INTERRUPTED" : "FAILED";
    await this.write(completion);
  }

  private async write(completionState: string) {
    const finalAttempts = [...this.attempts.values()]
      .map((attempts) => attempts.at(-1)!)
      .sort((left, right) => left.test.id.localeCompare(right.test.id));
    const failures = finalAttempts
      .filter(({ result }) => ["failed", "timedOut", "interrupted"].includes(result.status))
      .map(({ test, result, operations }) => {
        const identity = safeIdentity(test);
        return {
          ...identity,
          testStatus: safeStatus(result.status),
          errorClass: safeErrorClass(result),
          ...skillMcpDiagnosticProgress(result, identity.scenarioId === scenarioId, operations),
          http: operations.map(({ operationId, resultState, structuredHttpStatus }) => ({
            operationId,
            resultState,
            ...(structuredHttpStatus === undefined ? {} : { structuredHttpStatus }),
          })),
        };
      });
    const passed = finalAttempts.filter(({ result }) => result.status === "passed").length;
    const skipped = finalAttempts.filter(({ result }) => result.status === "skipped").length;
    const failed = failures.length;
    const flaky = [...this.attempts.values()].filter((attempts) => attempts.length > 1
      && attempts.at(-1)?.result.status === "passed"
      && attempts.slice(0, -1).some(({ result }) => result.status !== "passed")).length;
    await writeDiagnostic(process.env.SKILL_MCP_DIAGNOSTIC_REPORT_PATH, {
      schemaVersion: 1,
      completionState,
      counts: { selected: this.selected, executed: passed + failed, passed, failed, skipped, flaky },
      failures,
    });
  }
}

export default StructuredSkillMcpReporter;
