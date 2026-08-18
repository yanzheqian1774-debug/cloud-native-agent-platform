import type { WorkflowNode } from "../types/workflow";

interface NodeInspectorProps {
  node: WorkflowNode;
  onClose: () => void;
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "—";
  }

  return new Date(value).toLocaleString();
}

function EvidenceBlock({
  children,
  empty = false,
}: {
  children: React.ReactNode;
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
  const { execution } = node;

  const hasFailureEvidence =
    execution.reason !== null ||
    execution.message !== null ||
    execution.retryable !== null;

  return (
    <aside className="node-inspector">
      <div className="node-inspector-header">
        <div>
          <div className="eyebrow">Node Inspector</div>
          <h2>{node.name}</h2>
        </div>

        <button
          className="inspector-close"
          type="button"
          onClick={onClose}
          aria-label="Close node inspector"
        >
          ×
        </button>
      </div>

      <div className="inspector-status-row">
        <span
          className={`phase phase-${execution.phase.toLowerCase()}`}
        >
          {execution.phase}
        </span>
      </div>

      <section className="inspector-section">
        <h3>Identity</h3>

        <dl className="inspector-summary">
          <div>
            <dt>Agent</dt>
            <dd>{node.agent.name}</dd>
          </div>

          <div>
            <dt>Task</dt>
            <dd>{execution.taskRef ?? "—"}</dd>
          </div>
        </dl>
      </section>

      <section className="inspector-section">
        <h3>Execution</h3>

        <dl className="inspector-summary">
          <div>
            <dt>Attempts</dt>
            <dd>{execution.attempts ?? "—"}</dd>
          </div>

          <div>
            <dt>Timeout</dt>
            <dd>{node.timeoutSeconds}s</dd>
          </div>

          <div>
            <dt>Started</dt>
            <dd>{formatTimestamp(execution.startedAt)}</dd>
          </div>

          <div>
            <dt>Completed</dt>
            <dd>{formatTimestamp(execution.completedAt)}</dd>
          </div>
        </dl>
      </section>

      <section className="inspector-section">
        <h3>Input</h3>

        <div className="inspector-field">
          <div className="inspector-field-label">
            Declared Input
          </div>

          <EvidenceBlock
            empty={execution.declaredInput.length === 0}
          >
            {execution.declaredInput || "—"}
          </EvidenceBlock>
        </div>

        <div className="inspector-field">
          <div className="inspector-field-label">
            Resolved Input
          </div>

          <EvidenceBlock
            empty={execution.resolvedInput === null}
          >
            {execution.resolvedInput ?? "—"}
          </EvidenceBlock>
        </div>

        <div className="inspector-field">
          <div className="inspector-field-label">
            Upstream Results
          </div>

          {execution.upstreamResults.length === 0 ? (
            <EvidenceBlock empty>—</EvidenceBlock>
          ) : (
            <div className="upstream-results">
              {execution.upstreamResults.map((upstream) => (
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
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="inspector-section">
        <h3>Output</h3>

        <div className="inspector-field">
          <div className="inspector-field-label">
            Result
          </div>

          <EvidenceBlock empty={execution.result === null}>
            {execution.result ?? "—"}
          </EvidenceBlock>
        </div>
      </section>

      {hasFailureEvidence ? (
        <section className="inspector-section inspector-failure">
          <h3>Failure</h3>

          <dl className="inspector-summary">
            <div>
              <dt>Reason</dt>
              <dd>{execution.reason ?? "—"}</dd>
            </div>

            <div>
              <dt>Retryable</dt>
              <dd>
                {execution.retryable === null
                  ? "—"
                  : execution.retryable
                    ? "true"
                    : "false"}
              </dd>
            </div>
          </dl>

          <div className="inspector-field">
            <div className="inspector-field-label">
              Message
            </div>

            <EvidenceBlock
              empty={execution.message === null}
            >
              {execution.message ?? "—"}
            </EvidenceBlock>
          </div>
        </section>
      ) : null}
    </aside>
  );
}
