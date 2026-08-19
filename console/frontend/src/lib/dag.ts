import type {
  EdgeType,
  WorkflowEdge,
  WorkflowNode,
} from "../types/workflow";

export interface DagPositionedNode {
  node: WorkflowNode;
  layer: number;
  index: number;
  x: number;
  y: number;
}

export interface DagRenderedEdge {
  source: string;
  target: string;
  types: EdgeType[];
}

export interface DagLayout {
  nodes: DagPositionedNode[];
  edges: DagRenderedEdge[];
  width: number;
  height: number;
}

const NODE_WIDTH = 240;
const NODE_HEIGHT = 120;
const COLUMN_GAP = 80;
const ROW_GAP = 80;
const PADDING = 40;

function buildIncomingEdges(
  nodes: WorkflowNode[],
  edges: WorkflowEdge[],
): Map<string, string[]> {
  const nodeNames = new Set(nodes.map((node) => node.name));
  const incoming = new Map<string, string[]>();

  for (const node of nodes) {
    incoming.set(node.name, []);
  }

  for (const edge of edges) {
    if (
      !nodeNames.has(edge.source) ||
      !nodeNames.has(edge.target)
    ) {
      continue;
    }

    const dependencies = incoming.get(edge.target);

    if (
      dependencies &&
      !dependencies.includes(edge.source)
    ) {
      dependencies.push(edge.source);
    }
  }

  return incoming;
}

function calculateLayers(
  nodes: WorkflowNode[],
  edges: WorkflowEdge[],
): Map<string, number> {
  const incoming = buildIncomingEdges(nodes, edges);
  const layers = new Map<string, number>();

  function resolveLayer(
    nodeName: string,
    visiting: Set<string>,
  ): number {
    const existing = layers.get(nodeName);

    if (existing !== undefined) {
      return existing;
    }

    if (visiting.has(nodeName)) {
      return 0;
    }

    visiting.add(nodeName);

    const dependencies = incoming.get(nodeName) ?? [];

    const layer =
      dependencies.length === 0
        ? 0
        : Math.max(
            ...dependencies.map(
              (dependency) =>
                resolveLayer(
                  dependency,
                  new Set(visiting),
                ) + 1,
            ),
          );

    layers.set(nodeName, layer);

    return layer;
  }

  for (const node of nodes) {
    resolveLayer(node.name, new Set());
  }

  return layers;
}

function aggregateEdges(
  edges: WorkflowEdge[],
): DagRenderedEdge[] {
  const aggregated = new Map<string, DagRenderedEdge>();

  for (const edge of edges) {
    const key = `${edge.source}\u0000${edge.target}`;
    const existing = aggregated.get(key);

    if (existing) {
      if (!existing.types.includes(edge.type)) {
        existing.types.push(edge.type);
      }

      continue;
    }

    aggregated.set(key, {
      source: edge.source,
      target: edge.target,
      types: [edge.type],
    });
  }

  return Array.from(aggregated.values());
}

export function buildDagLayout(
  nodes: WorkflowNode[],
  edges: WorkflowEdge[],
): DagLayout {
  if (nodes.length === 0) {
    return {
      nodes: [],
      edges: [],
      width: 0,
      height: 0,
    };
  }

  const layers = calculateLayers(nodes, edges);
  const nodesByLayer = new Map<number, WorkflowNode[]>();

  for (const node of nodes) {
    const layer = layers.get(node.name) ?? 0;
    const layerNodes = nodesByLayer.get(layer) ?? [];

    layerNodes.push(node);
    nodesByLayer.set(layer, layerNodes);
  }

  const maxLayer = Math.max(...layers.values());
  const maxNodesInLayer = Math.max(
    ...Array.from(nodesByLayer.values()).map(
      (layerNodes) => layerNodes.length,
    ),
  );

  const width =
    PADDING * 2 +
    maxNodesInLayer * NODE_WIDTH +
    Math.max(0, maxNodesInLayer - 1) * COLUMN_GAP;

  const height =
    PADDING * 2 +
    (maxLayer + 1) * NODE_HEIGHT +
    maxLayer * ROW_GAP;

  const positionedNodes: DagPositionedNode[] = [];

  for (let layer = 0; layer <= maxLayer; layer += 1) {
    const layerNodes = nodesByLayer.get(layer) ?? [];
    const layerWidth =
      layerNodes.length * NODE_WIDTH +
      Math.max(0, layerNodes.length - 1) * COLUMN_GAP;

    const startX = (width - layerWidth) / 2;

    layerNodes.forEach((node, index) => {
      positionedNodes.push({
        node,
        layer,
        index,
        x: startX + index * (NODE_WIDTH + COLUMN_GAP),
        y: PADDING + layer * (NODE_HEIGHT + ROW_GAP),
      });
    });
  }

  return {
    nodes: positionedNodes,
    edges: aggregateEdges(edges),
    width,
    height,
  };
}

export const DAG_NODE_WIDTH = NODE_WIDTH;
export const DAG_NODE_HEIGHT = NODE_HEIGHT;
