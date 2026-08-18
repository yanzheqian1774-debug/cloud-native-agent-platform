import { useMemo } from "react";

import {
  buildDagLayout,
  DAG_NODE_HEIGHT,
  DAG_NODE_WIDTH,
} from "../lib/dag";
import type {
  NodePhase,
  WorkflowEdge,
  WorkflowNode,
} from "../types/workflow";

interface WorkflowDagProps {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

function phaseClassName(phase: NodePhase): string {
  return `phase phase-${phase.toLowerCase()}`;
}

export function WorkflowDag({
  nodes,
  edges,
}: WorkflowDagProps) {
  const layout = useMemo(
    () => buildDagLayout(nodes, edges),
    [nodes, edges],
  );

  const nodePositions = useMemo(
    () =>
      new Map(
        layout.nodes.map((positionedNode) => [
          positionedNode.node.name,
          positionedNode,
        ]),
      ),
    [layout.nodes],
  );

  if (layout.nodes.length === 0) {
    return (
      <div className="empty-state">
        No workflow nodes found.
      </div>
    );
  }

  return (
    <div className="workflow-dag-scroll">
      <div
        className="workflow-dag"
        style={{
          width: layout.width,
          height: layout.height,
        }}
      >
        <svg
          className="dag-edges"
          width={layout.width}
          height={layout.height}
          aria-hidden="true"
        >
          <defs>
            <marker
              id="dag-arrow"
              markerWidth="8"
              markerHeight="8"
              refX="7"
              refY="4"
              orient="auto"
              markerUnits="strokeWidth"
            >
              <path d="M 0 0 L 8 4 L 0 8 z" />
            </marker>
          </defs>

          {layout.edges.map((edge) => {
            const source = nodePositions.get(edge.source);
            const target = nodePositions.get(edge.target);

            if (!source || !target) {
              return null;
            }

            const sourceX =
              source.x + DAG_NODE_WIDTH / 2;
            const sourceY =
              source.y + DAG_NODE_HEIGHT;
            const targetX =
              target.x + DAG_NODE_WIDTH / 2;
            const targetY = target.y;

            const middleY =
              sourceY + (targetY - sourceY) / 2;

            const path = [
              `M ${sourceX} ${sourceY}`,
              `L ${sourceX} ${middleY}`,
              `L ${targetX} ${middleY}`,
              `L ${targetX} ${targetY}`,
            ].join(" ");

            const labelX =
              sourceX + (targetX - sourceX) / 2;
            const labelY = middleY - 8;

            return (
              <g
                key={`${edge.source}-${edge.target}`}
                className="dag-edge"
              >
                <path
                  d={path}
                  markerEnd="url(#dag-arrow)"
                />

                <text
                  x={labelX}
                  y={labelY}
                  textAnchor="middle"
                >
                  {edge.types.join(" + ")}
                </text>
              </g>
            );
          })}
        </svg>

        {layout.nodes.map(({ node, x, y }) => (
          <article
            key={node.name}
            className="dag-visual-node"
            style={{
              left: x,
              top: y,
              width: DAG_NODE_WIDTH,
              height: DAG_NODE_HEIGHT,
            }}
          >
            <div className="dag-visual-node-header">
              <strong>{node.name}</strong>

              <span
                className={phaseClassName(
                  node.execution.phase,
                )}
              >
                {node.execution.phase}
              </span>
            </div>

            <div className="dag-visual-node-agent">
              {node.agent.name}
            </div>

            <div className="dag-visual-node-footer">
              {node.execution.attempts === null
                ? "No task execution"
                : `${node.execution.attempts} attempt${
                    node.execution.attempts === 1
                      ? ""
                      : "s"
                  }`}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
