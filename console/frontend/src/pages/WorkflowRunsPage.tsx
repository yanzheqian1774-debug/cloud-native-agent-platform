import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listWorkflows } from "../api/workflows";
import {
  formatPhase,
  formatTimestamp,
} from "../i18n/presentation";
import { useI18n } from "../i18n/useI18n";
import type { WorkflowRunSummary } from "../types/workflow";

export function WorkflowRunsPage() {
  const { locale, t } = useI18n();

  const [workflows, setWorkflows] =
    useState<WorkflowRunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const response = await listWorkflows();
        setWorkflows(response.items);
      } catch (loadError) {
        setError(
          loadError instanceof Error
            ? loadError.message
            : t("workflow.loadFailed"),
        );
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, [t]);

  if (loading) {
    return (
      <main className="page">
        {t("workflow.loading")}
      </main>
    );
  }

  if (error) {
    return (
      <main className="page">
        <h1>{t("workflow.title")}</h1>
        <div className="error">{error}</div>
      </main>
    );
  }

  return (
    <main className="page">
      <header className="page-header">
        <div>
          <div className="eyebrow">
            {t("app.name")}
          </div>

          <h1>{t("workflow.title")}</h1>

          <p>{t("workflow.description")}</p>
        </div>
      </header>

      <section className="panel">
        {workflows.length === 0 ? (
          <div className="empty-state">
            {t("workflow.empty")}
          </div>
        ) : (
          <table className="workflow-table">
            <thead>
              <tr>
                <th>{t("workflow.workflow")}</th>
                <th>{t("workflow.namespace")}</th>
                <th>{t("workflow.status")}</th>
                <th>{t("workflow.tasks")}</th>
                <th>{t("workflow.created")}</th>
              </tr>
            </thead>

            <tbody>
              {workflows.map((workflow) => (
                <tr
                  key={`${workflow.namespace}/${workflow.name}`}
                >
                  <td className="workflow-name">
                    <Link
                      className="workflow-link"
                      to={`/workflows/${encodeURIComponent(
                        workflow.namespace,
                      )}/${encodeURIComponent(workflow.name)}`}
                    >
                      {workflow.name}
                    </Link>
                  </td>

                  <td>{workflow.namespace}</td>

                  <td>
                    <span
                      className={`phase phase-${workflow.phase.toLowerCase()}`}
                    >
                      {formatPhase(workflow.phase, t)}
                    </span>
                  </td>

                  <td>{workflow.taskCount}</td>

                  <td>
                    {formatTimestamp(
                      workflow.createdAt,
                      locale,
                      t,
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
