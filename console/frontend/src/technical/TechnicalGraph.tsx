import { useState } from "react";
import { useI18n } from "../i18n/useI18n";
import type { TechnicalProjection } from "../shared/executionSnapshotTypes";

export function TechnicalGraph({ view }: { view: TechnicalProjection }) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState<string | null>(null);
  const connected = new Set(view.edges.flatMap((edge) => [edge.source, edge.target]));
  return <section id="graph" className="technical-section panel-pad" aria-labelledby="technical-graph-title">
    <div className="section-heading"><h2 id="technical-graph-title">{t("technical.graph.title")}</h2><p>{t("technical.graph.description")}</p></div>
    <ol className="technical-node-grid">{view.nodes.map((node) => <li key={node.id}><span className="node-type">{node.type}</span><strong>{t(node.labelKey as never)}</strong><span className={`technical-state state-${node.phase.toLowerCase()}`}>● <span className="stable-id">{node.phase}</span></span><span className="stable-id">{node.id}</span>{!connected.has(node.id) && <span className="disconnected-state">◇ {t("technical.graph.disconnected")}</span>}</li>)}</ol>
    <div className="technical-edge-list"><h3>{t("technical.graph.relations")}</h3>{view.edges.map((edge) => <article key={edge.id} className="technical-edge"><button aria-expanded={expanded === edge.id} onClick={() => setExpanded(expanded === edge.id ? null : edge.id)}><span className="stable-id">{edge.source}</span> → <span className="stable-id">{edge.target}</span></button>{expanded === edge.id && <div className="edge-details">{edge.rawRelations.map((relation) => <dl key={relation.id}><dt>ID</dt><dd className="stable-id">{relation.id}</dd><dt>TYPE</dt><dd className="stable-id">{relation.type}</dd><dt>SOURCE</dt><dd className="stable-id">{relation.source}</dd><dt>TARGET</dt><dd className="stable-id">{relation.target}</dd><dt>DIRECTION</dt><dd className="stable-id">{relation.direction}</dd><dt>CARDINALITY</dt><dd className="stable-id">{relation.cardinality}</dd><dt>EVIDENCE</dt><dd className="stable-id">{relation.evidenceIds.join(", ")}</dd></dl>)}</div>}</article>)}</div>
  </section>;
}
