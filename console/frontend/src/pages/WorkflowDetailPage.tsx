import { useEffect, useState } from "react";
import { NodeInspector } from "../components/NodeInspector";
import { WorkflowDag } from "../components/WorkflowDag";
import {
  Link,
  useParams,
} from "react-router-dom";

import { getWorkflow } from "../api/workflows";
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
  const [workflow, setWorkflow] =
    useState<WorkflowExecutionDetail | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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
              : "Failed to load workflow",
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
  }, [namespace, name]);

  if (loading) {
    return (
      <main className="page">
        Loading workflow...
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
          ← Workflow Runs
        </Link>

        <div className="error">
          {error ?? "Workflow not found"}
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
        ← Workflow Runs
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
          {workflow.phase}
        </span>
      </header>

      <section className="workflow-summary">
        <div>
          <span>Tasks</span>
          <strong>{workflow.taskCount}</strong>
        </div>

        <div>
          <span>Created</span>
          <strong>
            {workflow.createdAt
              ? new Date(
                  workflow.createdAt,
                ).toLocaleString()
              : "—"}
          </strong>
        </div>

        <div>
          <span>Started</span>
          <strong>
            {workflow.startedAt
              ? new Date(
                  workflow.startedAt,
                ).toLocaleString()
              : "—"}
          </strong>
        </div>

        <div>
          <span>Completed</span>
          <strong>
            {workflow.completedAt
              ? new Date(
                  workflow.completedAt,
                ).toLocaleString()
              : "—"}
          </strong>
        </div>
      </section>

      <section className="detail-section">
        <div className="section-heading">
          <div>
            <h2>Execution DAG</h2>
            <p>
              Workflow topology and current node execution state.
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
              selectedNodeName={selectedNode?.name ?? null}
              onSelectNode={setSelectedNode}
            />
          </div>

          {selectedNode ? (
            <NodeInspector
              node={selectedNode}
              onClose={() => setSelectedNode(null)}
            />
          ) : null}
        </div>
      </section>

      <section className="detail-section">
        <div className="section-heading">
          <div>
            <h2>Dependencies</h2>
            <p>
              Control and data dependencies declared by the workflow.
            </p>
          </div>
        </div>

        <div className="panel">
          <table className="workflow-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Target</th>
                <th>Type</th>
              </tr>
            </thead>

            <tbody>
              {workflow.edges.map((edge, index) => (
                <tr
                  key={`${edge.source}-${edge.target}-${edge.type}-${index}`}
                >
                  <td>{edge.source}</td>
                  <td>{edge.target}</td>
                  <td>{edge.type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

export function WorkflowDetailPage() {
  const { namespace, name } = useParams();

  if (!namespace || !name) {
    return (
      <main className="page">
        <Link
          className="back-link"
          to="/workflows"
        >
          ← Workflow Runs
        </Link>

        <div className="error">
          Invalid workflow route
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
