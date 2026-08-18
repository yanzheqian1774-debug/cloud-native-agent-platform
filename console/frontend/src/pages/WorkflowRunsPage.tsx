import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listWorkflows } from "../api/workflows";
import type { WorkflowRunSummary } from "../types/workflow";

export function WorkflowRunsPage() {
  const [workflows, setWorkflows] = useState<WorkflowRunSummary[]>([]);
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
            : "Failed to load workflows",
        );
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, []);

  if (loading) {
    return <main className="page">Loading workflows...</main>;
  }

  if (error) {
    return (
      <main className="page">
        <h1>Workflow Runs</h1>
        <div className="error">{error}</div>
      </main>
    );
  }

  return (
    <main className="page">
      <header className="page-header">
        <div>
          <div className="eyebrow">AgentOS Console</div>
          <h1>Workflow Runs</h1>
          <p>
            Inspect multi-agent workflow executions running on Kubernetes.
          </p>
        </div>
      </header>

      <section className="panel">
        {workflows.length === 0 ? (
          <div className="empty-state">
            No workflow executions found.
          </div>
        ) : (
          <table className="workflow-table">
            <thead>
              <tr>
                <th>Workflow</th>
                <th>Namespace</th>
                <th>Status</th>
                <th>Tasks</th>
                <th>Created</th>
              </tr>
            </thead>

            <tbody>
              {workflows.map((workflow) => (
                <tr key={`${workflow.namespace}/${workflow.name}`}>
                  <td className="workflow-name">
                    <Link
                      className="workflow-link"
                      to={`/workflows/${encodeURIComponent(workflow.namespace)}/${encodeURIComponent(workflow.name)}`}
                    >
                      {workflow.name}
                    </Link>
                  </td>
                  <td>{workflow.namespace}</td>
                  <td>
                    <span
                      className={`phase phase-${workflow.phase.toLowerCase()}`}
                    >
                      {workflow.phase}
                    </span>
                  </td>
                  <td>{workflow.taskCount}</td>
                  <td>
                    {workflow.createdAt
                      ? new Date(workflow.createdAt).toLocaleString()
                      : "—"}
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
