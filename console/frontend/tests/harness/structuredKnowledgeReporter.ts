import type {
  Reporter,
  TestCase,
  TestResult,
} from "@playwright/test/reporter";
import type { TestInfo } from "@playwright/test";
import { writeFile } from "node:fs/promises";

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
const attachmentContentType = "application/vnd.agent-platform.knowledge-operation-result.v1+json";
const outputFile = process.env.KNOWLEDGE_STRUCTURED_REPORT_PATH;

function hasExactKeys(value: Record<string, unknown>) {
  const keys = Object.keys(value).sort();
  const allowed = value.structuredHttpStatus === undefined
    ? ["operationId", "resultState"]
    : ["operationId", "resultState", "structuredHttpStatus"];
  return keys.length === allowed.length && keys.every((key, index) => key === allowed.sort()[index]);
}

export function normalizeKnowledgeOperationResult(value: unknown): KnowledgeOperationResult {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("knowledge operation result must be an object");
  }
  const candidate = value as Record<string, unknown>;
  if (!hasExactKeys(candidate)) throw new Error("knowledge operation result contains an unsupported field");
  if (!KNOWLEDGE_OPERATION_IDS.includes(candidate.operationId as KnowledgeOperationId)) {
    throw new Error("knowledge operation ID is not closed");
  }
  if (!KNOWLEDGE_RESULT_STATES.includes(candidate.resultState as KnowledgeResultState)) {
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
  const operationOrder = new Map(KNOWLEDGE_OPERATION_IDS.map((operationId, index) => [operationId, index]));
  const seen = new Set<KnowledgeOperationId>();
  for (const result of results) {
    if (seen.has(result.operationId)) throw new Error("knowledge operation result is duplicated");
    seen.add(result.operationId);
  }
  return results.toSorted(
    (left, right) => operationOrder.get(left.operationId)! - operationOrder.get(right.operationId)!,
  );
}

export function firstUnexpectedKnowledgeOperation(values: readonly unknown[]) {
  return orderKnowledgeOperationResults(values).find((result) => result.resultState === "UNEXPECTED");
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

export async function runKnowledgeOperation<T>(
  testInfo: TestInfo,
  operationId: KnowledgeOperationId,
  operation: () => Promise<T>,
  structuredHttpStatusFromResult?: (result: T) => number | undefined,
) {
  try {
    const result = await operation();
    const structuredHttpStatus = structuredHttpStatusFromResult?.(result);
    await attachKnowledgeOperationResult(testInfo, {
      operationId,
      resultState: "EXPECTED",
      ...(structuredHttpStatus === undefined ? {} : { structuredHttpStatus }),
    });
    return result;
  } catch (error) {
    await attachKnowledgeOperationResult(testInfo, { operationId, resultState: "UNEXPECTED" });
    throw error;
  }
}

export function operationResultsFromTestResult(result: Pick<TestResult, "attachments">) {
  return orderKnowledgeOperationResults(result.attachments
    .filter((attachment) => attachment.name === attachmentName && attachment.contentType === attachmentContentType)
    .map((attachment) => {
      if (!attachment.body) throw new Error("knowledge operation attachment body is required");
      return JSON.parse(attachment.body.toString("utf8")) as unknown;
    }));
}

class StructuredKnowledgeReporter implements Reporter {
  async onTestEnd(_test: TestCase, result: TestResult) {
    const operations = operationResultsFromTestResult(result);
    if (!outputFile || operations.length === 0) return;
    await writeFile(outputFile, `${JSON.stringify(operations)}\n`, { encoding: "utf8", mode: 0o600 });
  }
}

export default StructuredKnowledgeReporter;
