import { useEffect, useState } from "react";
import {
  Link,
  useParams,
} from "react-router-dom";

import { getWorkflow } from "../api/workflows";
import { NodeInspector } from "../components/NodeInspector";
import { WorkflowDag } from "../components/WorkflowDag";
import {
  formatEdgeType,
  formatPhase,
  formatTimestamp,
} from "../i18n/presentation";
import { useI18n } from "../i18n/useI18n";
import type {
  WorkflowExecutionDetail,
  WorkflowNode,
} from "../types/workflow";

function WorkflowDetailContent({
  namespace,
  name,
}: {
  namespace: string;
  name: string;
}) {
  const { locale, t } = useI18n();

  const [workflow, setWorkflow] =
    useState<WorkflowExecutionDetail | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] =
    useState<string | null>(null);

  const [selectedNode, setSelectedNode] =
    useState<WorkflowNode | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await getWorkflow(
          namespace,
          name,
        );

        if (!cancelled) {
          setWorkflow(response);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : t("workflow.loadFailed"),
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [namespace, name, t]);

  if (loading) {
    return (
      <main className="page">
        {t("workflow.loadingDetail")}
      </main>
    );
  }

  if (error || !workflow) {
    return (
      <main className="page">
        <Link
          className="back-link"
          to="/workflows"
        >
          ← {t("nav.workflowRuns")}
        </Link>

        <div className="error">
          {error ?? t("workflow.notFound")}
        </div>
      </main>
    );
  }

  return (
    <main className="page">
      <Link
        className="back-link"
        to="/workflows"
      >
        ← {t("nav.workflowRuns")}
      </Link>

      <header className="detail-header">
        <div>
          <div className="eyebrow">
            {workflow.namespace}
          </div>

          <h1>{workflow.name}</h1>
        </div>

        <span
          className={`phase phase-${workflow.phase.toLowerCase()}`}
        >
          {formatPhase(workflow.phase, t)}
        </span>
      </header>

      <section className="workflow-summary">
        <div>
          <span>{t("workflow.tasks")}</span>
          <strong>{workflow.taskCount}</strong>
        </div>

        <div>
          <span>{t("workflow.created")}</span>
          <strong>
            {formatTimestamp(
              workflow.createdAt,
              locale,
              t,
            )}
          </strong>
        </div>

        <div>
          <span>{t("workflow.started")}</span>
          <strong>
            {formatTimestamp(
              workflow.startedAt,
              locale,
              t,
            )}
          </strong>
        </div>

        <div>
          <span>{t("workflow.completed")}</span>
          <strong>
            {formatTimestamp(
              workflow.completedAt,
              locale,
              t,
            )}
          </strong>
        </div>
      </section>

      <section className="detail-section">
        <div className="section-heading">
          <div>
            <h2>
              {t("workflow.executionDag")}
            </h2>

            <p>
              {t(
                "workflow.executionDag.description",
              )}
            </p>
          </div>
        </div>

        <div
          className={[
            "workflow-execution-layout",
            selectedNode
              ? "workflow-execution-layout-inspecting"
              : "",
          ]
            .filter(Boolean)
            .join(" ")}
        >
          <div className="workflow-execution-main">
            <WorkflowDag
              nodes={workflow.nodes}
              edges={workflow.edges}
              selectedNodeName={
                selectedNode?.name ?? null
              }
              onSelectNode={setSelectedNode}
            />
          </div>

          {selectedNode ? (
            <NodeInspector
              node={selectedNode}
              onClose={() =>
                setSelectedNode(null)
              }
            />
          ) : null}
        </div>
      </section>

      <section className="detail-section">
        <div className="section-heading">
          <div>
            <h2>
              {t("workflow.dependencies")}
            </h2>

            <p>
              {t(
                "workflow.dependencies.description",
              )}
            </p>
          </div>
        </div>

        <div className="panel">
          <table className="workflow-table">
            <thead>
              <tr>
                <th>{t("workflow.source")}</th>
                <th>{t("workflow.target")}</th>
                <th>{t("workflow.type")}</th>
              </tr>
            </thead>

            <tbody>
              {workflow.edges.map(
                (edge, index) => (
                  <tr
                    key={`${edge.source}-${edge.target}-${edge.type}-${index}`}
                  >
                    <td>{edge.source}</td>
                    <td>{edge.target}</td>
                    <td>
                      {formatEdgeType(
                        edge.type,
                        t,
                      )}
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

export function WorkflowDetailPage() {
  const { t } = useI18n();
  const { namespace, name } = useParams();

  if (!namespace || !name) {
    return (
      <main className="page">
        <Link
          className="back-link"
          to="/workflows"
        >
          ← {t("nav.workflowRuns")}
        </Link>

        <div className="error">
          {t("workflow.invalidRoute")}
        </div>
      </main>
    );
  }

  return (
    <WorkflowDetailContent
      namespace={namespace}
      name={name}
    />
  );
}
