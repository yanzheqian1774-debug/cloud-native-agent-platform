import { useState } from "react";
import { useI18n } from "../i18n/useI18n";
import type { ProductEdge, ProductNode } from "./types";

interface Props { nodes: ProductNode[]; edges: ProductEdge[]; snapshotId: string; executionId: string }
export function ProductGraph({ nodes, edges, snapshotId, executionId }: Props) {
  const { t } = useI18n(); const [expanded, setExpanded] = useState<string | null>(null);
  const connected = new Set(edges.flatMap((edge) => [edge.source, edge.target]));
  return <section className="product-section panel-pad" aria-labelledby="graph-title"><div className="section-heading"><h2 id="graph-title">{t("product.graph.title")}</h2><p>{t("product.graph.description")}</p></div>
    <div className="identity-strip"><span>{t("product.graph.snapshot")}: <b className="stable-id">{snapshotId}</b></span><span>{t("product.execution.identity")}: <b className="stable-id">{executionId}</b></span></div>
    <ol className="business-graph">{nodes.map((node) => <li key={node.id}><span className="node-type">{node.type}</span><strong>{t(node.labelKey as never)}</strong><span className="status-with-icon">● <span className="stable-id">{node.phase}</span></span>{!connected.has(node.id) && <span className="disconnected-state">◇ {t("product.graph.disconnected")}</span>}</li>)}</ol>
    <div className="edge-list"><h3>{t("product.graph.relations")}</h3>{edges.map((edge) => <div className="edge-item" key={edge.id}><button className="edge-toggle" aria-expanded={expanded === edge.id} onClick={() => setExpanded(expanded === edge.id ? null : edge.id)}>{edge.rawRelations.map((r) => r.type).join(" / ")} <span>({edge.rawRelations.length})</span></button>
      {expanded === edge.id && <div className="edge-details">{edge.rawRelations.map((relation) => <dl key={relation.id}><dt>ID</dt><dd className="stable-id">{relation.id}</dd><dt>TYPE</dt><dd className="stable-id">{relation.type}</dd><dt>DIRECTION</dt><dd className="stable-id">{relation.direction}</dd><dt>CARDINALITY</dt><dd className="stable-id">{relation.cardinality}</dd><dt>EVIDENCE</dt><dd className="stable-id">{relation.evidenceIds.join(", ")}</dd></dl>)}</div>}</div>)}</div>
    <details><summary>{t("product.graph.technicalDetails")}</summary><p>{t("product.graph.hidden")}</p></details>
  </section>;
}
