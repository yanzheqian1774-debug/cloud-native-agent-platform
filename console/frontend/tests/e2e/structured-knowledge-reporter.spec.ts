import { expect, test } from "@playwright/test";
import type { TestInfo, TestResult } from "@playwright/test";
import {
  KNOWLEDGE_OPERATION_IDS,
  attachKnowledgeOperationResult,
  firstUnexpectedKnowledgeOperation,
  normalizeKnowledgeOperationResult,
  operationResultsFromTestResult,
  orderKnowledgeOperationResults,
  runKnowledgeOperation,
} from "../harness/structuredKnowledgeReporter";

type Attachment = TestResult["attachments"][number];

function attachmentCollector() {
  const attachments: Attachment[] = [];
  const testInfo = {
    attach: async (name: string, options: { body: Buffer; contentType: string }) => {
      attachments.push({ name, body: options.body, contentType: options.contentType });
    },
  } as unknown as TestInfo;
  return { attachments, testInfo };
}

test("real journey producer functions emit the five closed operations in deterministic order", async () => {
  const { attachments, testInfo } = attachmentCollector();
  for (const operationId of KNOWLEDGE_OPERATION_IDS.toReversed()) {
    await runKnowledgeOperation(testInfo, operationId, async () => undefined);
  }

  const results = operationResultsFromTestResult({ attachments });
  expect(results.map(({ operationId }) => operationId)).toEqual(KNOWLEDGE_OPERATION_IDS);
  expect(results.every(({ resultState }) => resultState === "EXPECTED")).toBe(true);
  expect(firstUnexpectedKnowledgeOperation(results)).toBeUndefined();
});

test("a bounded failure records the first unexpected operation and rethrows", async () => {
  const { attachments, testInfo } = attachmentCollector();
  const controlledFailure = new Error("controlled failure with HTTP 503 text");

  await expect(runKnowledgeOperation(
    testInfo,
    "KNOWLEDGE_UPDATE",
    async () => { throw controlledFailure; },
  )).rejects.toBe(controlledFailure);

  expect(firstUnexpectedKnowledgeOperation(operationResultsFromTestResult({ attachments }))).toEqual({
    operationId: "KNOWLEDGE_UPDATE",
    resultState: "UNEXPECTED",
  });
});

test("multiple unexpected results retain the deterministic first operation", () => {
  const results = [
    { operationId: "KNOWLEDGE_PURGE_RECOVERY", resultState: "UNEXPECTED" },
    { operationId: "KNOWLEDGE_INDEX_RETRIEVE", resultState: "UNEXPECTED" },
    { operationId: "KNOWLEDGE_GOVERNED_CREATE_PUBLISH", resultState: "EXPECTED" },
  ];
  expect(firstUnexpectedKnowledgeOperation(results)).toEqual({
    operationId: "KNOWLEDGE_INDEX_RETRIEVE",
    resultState: "UNEXPECTED",
  });
});

test("reporter output has only the closed field set and retains no browser artifacts", async () => {
  const { attachments, testInfo } = attachmentCollector();
  await attachKnowledgeOperationResult(testInfo, {
    operationId: "KNOWLEDGE_PURGE_RECOVERY",
    resultState: "UNEXPECTED",
    structuredHttpStatus: 202,
  });
  const [result] = operationResultsFromTestResult({ attachments });

  expect(Object.keys(result).sort()).toEqual([
    "operationId",
    "resultState",
    "structuredHttpStatus",
  ]);
  expect(attachments).toHaveLength(1);
  expect(attachments[0].name).toBe("knowledge-operation-result.v1");
  expect(attachments[0].path).toBeUndefined();
  expect(JSON.stringify(result)).not.toMatch(/trace|screenshot|video|error-context|playwright-report/i);
});

test("only explicitly typed integer HTTP status values from 100 through 599 are accepted", () => {
  for (const structuredHttpStatus of [100, 202, 399, 404, 599]) {
    expect(normalizeKnowledgeOperationResult({
      operationId: "KNOWLEDGE_PURGE_RECOVERY",
      resultState: "UNEXPECTED",
      structuredHttpStatus,
    }).structuredHttpStatus).toBe(structuredHttpStatus);
  }

  for (const structuredHttpStatus of ["202", true, 202.5, 99, 600]) {
    expect(() => normalizeKnowledgeOperationResult({
      operationId: "KNOWLEDGE_PURGE_RECOVERY",
      resultState: "UNEXPECTED",
      structuredHttpStatus,
    })).toThrow(/structured HTTP status/);
  }
  expect(normalizeKnowledgeOperationResult({
    operationId: "KNOWLEDGE_PURGE_RECOVERY",
    resultState: "UNEXPECTED",
  }).structuredHttpStatus).toBeUndefined();
});

test("free-form or sensitive provenance and non-status numbers fail closed", () => {
  const prohibited = [
    { title: "KNOWLEDGE_UPDATE" },
    { errorMessage: "request failed with 503" },
    { selector: "button.secret" },
    { url: "https://example.invalid/private" },
    { route: "/api/private" },
    { requestBody: { secret: true } },
    { responseBody: { payload: true } },
    { fixture: "supplier content" },
    { exitCode: 503 },
    { assertionCount: 503 },
  ];
  for (const extra of prohibited) {
    expect(() => normalizeKnowledgeOperationResult({
      operationId: "KNOWLEDGE_UPDATE",
      resultState: "UNEXPECTED",
      ...extra,
    })).toThrow(/unsupported field/);
  }
  expect(() => orderKnowledgeOperationResults([
    { operationId: "KNOWLEDGE_UPDATE", resultState: "EXPECTED" },
    { operationId: "KNOWLEDGE_UPDATE", resultState: "UNEXPECTED" },
  ])).toThrow(/duplicated/);
  expect(() => normalizeKnowledgeOperationResult({
    operationId: "Update failed at selector",
    resultState: "UNEXPECTED",
  })).toThrow(/ID is not closed/);
});
