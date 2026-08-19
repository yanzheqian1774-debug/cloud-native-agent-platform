import type { ReactNode } from "react";

import {
  formatBoolean,
  formatPhase,
  formatReason,
  formatTimestamp,
} from "../i18n/presentation";
import { useI18n } from "../i18n/useI18n";
import type { WorkflowNode } from "../types/workflow";

interface NodeInspectorProps {
  node: WorkflowNode;
  onClose: () => void;
}

function EvidenceBlock({
  children,
  empty = false,
}: {
  children: ReactNode;
  empty?: boolean;
}) {
  return (
    <pre
      className={[
        "inspector-evidence",
        empty ? "inspector-evidence-empty" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </pre>
  );
}

export function NodeInspector({
  node,
  onClose,
}: NodeInspectorProps) {
  const { locale, t } = useI18n();
  const { execution } = node;

  const hasFailureEvidence =
    execution.reason !== null ||
    execution.message !== null ||
    execution.retryable !== null;

  const notAvailable = t("common.notAvailable");

  return (
    <aside className="node-inspector">
      <div className="node-inspector-header">
        <div>
          <div className="eyebrow">
            {t("node.inspector")}
          </div>

          <h2>{node.name}</h2>
        </div>

        <button
          className="inspector-close"
          type="button"
          onClick={onClose}
          aria-label={t("common.close")}
        >
          ×
        </button>
      </div>

      <div className="inspector-status-row">
        <span
          className={`phase phase-${execution.phase.toLowerCase()}`}
        >
          {formatPhase(execution.phase, t)}
        </span>
      </div>

      <section className="inspector-section">
        <h3>{t("node.identity")}</h3>

        <dl className="inspector-summary">
          <div>
            <dt>{t("node.agent")}</dt>
            <dd>{node.agent.name}</dd>
          </div>

          <div>
            <dt>{t("node.task")}</dt>
            <dd>
              {execution.taskRef ?? notAvailable}
            </dd>
          </div>
        </dl>
      </section>

      <section className="inspector-section">
        <h3>{t("node.execution")}</h3>

        <dl className="inspector-summary">
          <div>
            <dt>{t("node.attempts")}</dt>
            <dd>
              {execution.attempts ?? notAvailable}
            </dd>
          </div>

          <div>
            <dt>{t("node.timeout")}</dt>
            <dd>{node.timeoutSeconds}s</dd>
          </div>

          <div>
            <dt>{t("node.started")}</dt>
            <dd>
              {formatTimestamp(
                execution.startedAt,
                locale,
                t,
              )}
            </dd>
          </div>

          <div>
            <dt>{t("node.completed")}</dt>
            <dd>
              {formatTimestamp(
                execution.completedAt,
                locale,
                t,
              )}
            </dd>
          </div>
        </dl>
      </section>

      <section className="inspector-section">
        <h3>{t("node.input")}</h3>

        <div className="inspector-field">
          <div className="inspector-field-label">
            {t("node.declaredInput")}
          </div>

          <EvidenceBlock
            empty={execution.declaredInput.length === 0}
          >
            {execution.declaredInput || notAvailable}
          </EvidenceBlock>
        </div>

        <div className="inspector-field">
          <div className="inspector-field-label">
            {t("node.resolvedInput")}
          </div>

          <EvidenceBlock
            empty={execution.resolvedInput === null}
          >
            {execution.resolvedInput ?? notAvailable}
          </EvidenceBlock>
        </div>

        <div className="inspector-field">
          <div className="inspector-field-label">
            {t("node.upstreamResults")}
          </div>

          {execution.upstreamResults.length === 0 ? (
            <EvidenceBlock empty>
              {notAvailable}
            </EvidenceBlock>
          ) : (
            <div className="upstream-results">
              {execution.upstreamResults.map(
                (upstream) => (
                  <div
                    className="upstream-result"
                    key={upstream.task}
                  >
                    <div className="upstream-result-task">
                      {upstream.task}
                    </div>

                    <EvidenceBlock>
                      {upstream.result}
                    </EvidenceBlock>
                  </div>
                ),
              )}
            </div>
          )}
        </div>
      </section>

      <section className="inspector-section">
        <h3>{t("node.output")}</h3>

        <div className="inspector-field">
          <div className="inspector-field-label">
            {t("node.result")}
          </div>

          <EvidenceBlock
            empty={execution.result === null}
          >
            {execution.result ?? notAvailable}
          </EvidenceBlock>
        </div>
      </section>

      {hasFailureEvidence ? (
        <section className="inspector-section inspector-failure">
          <h3>{t("node.failure")}</h3>

          <dl className="inspector-summary">
            <div>
              <dt>{t("node.reason")}</dt>
              <dd>
                {formatReason(
                  execution.reason,
                  t,
                )}
              </dd>
            </div>

            <div>
              <dt>{t("node.retryable")}</dt>
              <dd>
                {formatBoolean(
                  execution.retryable,
                  t,
                )}
              </dd>
            </div>
          </dl>

          <div className="inspector-field">
            <div className="inspector-field-label">
              {t("node.message")}
            </div>

            <EvidenceBlock
              empty={execution.message === null}
            >
              {execution.message ?? notAvailable}
            </EvidenceBlock>
          </div>
        </section>
      ) : null}
    </aside>
  );
}
