import type { ReactNode } from "react";

export type NavigationIconName =
  | "home" | "problem" | "employee" | "flow" | "knowledge" | "resource"
  | "record" | "manage" | "runtime" | "outcome" | "shield" | "agent"
  | "relationships" | "attention" | "applications" | "operations"
  | "model" | "usage" | "help";

const paths: Record<NavigationIconName, ReactNode> = {
  home: <><path d="M3 10.5 12 3l9 7.5" /><path d="M5.5 9.5V21h13V9.5M9 21v-7h6v7" /></>,
  problem: <><path d="M4 5h16v12H8l-4 4V5Z" /><path d="M8 9h8M8 13h5" /></>,
  employee: <><circle cx="12" cy="8" r="3" /><path d="M5 21v-2a7 7 0 0 1 14 0v2M4 7h2M18 7h2M12 2v2" /></>,
  flow: <><rect x="3" y="4" width="6" height="5" rx="1" /><rect x="15" y="15" width="6" height="5" rx="1" /><path d="M9 6.5h4a4 4 0 0 1 4 4V15M15 17.5h-4a4 4 0 0 1-4-4V9" /></>,
  knowledge: <><path d="M4 5.5A3.5 3.5 0 0 1 7.5 2H12v18H7.5A3.5 3.5 0 0 0 4 23V5.5Z" /><path d="M20 5.5A3.5 3.5 0 0 0 16.5 2H12v18h4.5A3.5 3.5 0 0 1 20 23V5.5Z" /></>,
  resource: <><rect x="3" y="3" width="7" height="7" rx="2" /><rect x="14" y="3" width="7" height="7" rx="2" /><rect x="3" y="14" width="7" height="7" rx="2" /><rect x="14" y="14" width="7" height="7" rx="2" /></>,
  record: <><path d="M5 3h14v18H5zM9 8h6M9 12h6M9 16h4" /></>,
  manage: <><circle cx="12" cy="12" r="3" /><path d="M20 12a8 8 0 1 1-16 0 8 8 0 0 1 16 0ZM12 2v3M12 19v3M2 12h3M19 12h3" /></>,
  runtime: <><rect x="3" y="3" width="18" height="7" rx="2" /><rect x="3" y="14" width="18" height="7" rx="2" /><path d="M7 6.5h.01M7 17.5h.01M12 6.5h5M12 17.5h5" /></>,
  outcome: <><rect x="4" y="4" width="16" height="17" rx="2" /><path d="M9 4V2h6v2M8 12l3 3 5-6" /></>,
  shield: <><path d="m12 3 8 3v6c0 4-4 7-8 9-4-2-8-5-8-9V6l8-3Z" /><path d="m8 12 3 3 5-6" /></>,
  agent: <><path d="m12 2 9 5v10l-9 5-9-5V7l9-5ZM3 7l9 5 9-5M12 12v10" /></>,
  relationships: <><circle cx="12" cy="5" r="3" /><circle cx="5" cy="19" r="3" /><circle cx="19" cy="19" r="3" /><path d="m10 8-4 8M14 8l4 8M8 19h8" /></>,
  attention: <><path d="M5 17h14l-2-3V9a5 5 0 0 0-10 0v5l-2 3ZM10 21h4M12 2v2" /></>,
  applications: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M8 5V3h8v2M3 10h18M10 14h4M12 12v4" /></>,
  operations: <><path d="M2 12h5l3-8 4 16 3-8h5" /></>,
  model: <><path d="m12 2 10 5-10 5L2 7l10-5ZM2 12l10 5 10-5M2 17l10 5 10-5" /></>,
  usage: <><path d="M3 3v18h18M7 16v-5M12 16V7M17 16v-8" /></>,
  help: <><circle cx="12" cy="12" r="9" /><path d="M9 9a3 3 0 1 1 4 2.8c-1 .4-1 1.2-1 2.2M12 17h.01" /></>,
};

export function NavigationIcon({ name }: { name: NavigationIconName }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}
