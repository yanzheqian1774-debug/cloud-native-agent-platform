import {useContext,type ReactNode} from "react";
import {FrozenNavigationIconContext} from "./navigationIconTheme";
import {frozenF3NavigationPaths} from "./FrozenF3NavigationIcons";

export type NavigationIconName =
  | "network" | "skill" | "mcp" | "home" | "problem" | "employee" | "flow" | "knowledge" | "resource"
  | "record" | "manage" | "runtime" | "outcome" | "shield" | "agent"
  | "relationships" | "attention" | "applications" | "operations"
  | "model" | "usage" | "help" | "conversation" | "target" | "clock" | "calendar";

const paths: Record<NavigationIconName, ReactNode> = {
  network: <><rect x="16" y="16" width="6" height="6" rx="1"></rect><rect x="2" y="16" width="6" height="6" rx="1"></rect><rect x="9" y="2" width="6" height="6" rx="1"></rect><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"></path><path d="M12 12V8"></path></>,
  skill: <><path d="M4 12.15V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.706.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2h-3.35"></path><path d="M14 2v5a1 1 0 0 0 1 1h5"></path><path d="m5 16-3 3 3 3"></path><path d="m9 22 3-3-3-3"></path></>,
  mcp: <><path d="M12 22v-5"></path><path d="M15 8V2"></path><path d="M17 8a1 1 0 0 1 1 1v4a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1z"></path><path d="M9 8V2"></path></>,
  calendar: <><rect x="4" y="4" width="16" height="18" rx="2"/><path d="M8 2v5M16 2v5M4 10h16M8 14h2M14 14h2M8 18h2M14 18h2"/></>,
  clock: <><path d="M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0M12 5v8l5 2" /></>,
  target: <><path d="M22 12a10 10 0 1 1-6-9M17 12a5 5 0 1 1-5-5M12 12l10-10M17 2h5v5" /></>,
  conversation: <><path d="M3 4h18v13H9l-5 4v-4H3z" /></>,
  home: <><path d="M2 11 12 2l10 9M5 9v13h5v-7h4v7h5V9" /></>,
  problem: <><path d="M8 5H4v17h16V5h-4M8 2h8v6H8zM8 12h8M8 17h5" /></>,
  employee: <><path d="M16 6a4 4 0 1 1-8 0 4 4 0 0 1 8 0M4 22v-4a8 6 0 0 1 16 0v4z" /></>,
  flow: <><rect x="3" y="4" width="6" height="5" rx="1" /><rect x="15" y="15" width="6" height="5" rx="1" /><path d="M9 6.5h4a4 4 0 0 1 4 4V15M15 17.5h-4a4 4 0 0 1-4-4V9" /></>,
  knowledge: <><path d="M4 5.5A3.5 3.5 0 0 1 7.5 2H12v18H7.5A3.5 3.5 0 0 0 4 23V5.5Z" /><path d="M20 5.5A3.5 3.5 0 0 0 16.5 2H12v18h4.5A3.5 3.5 0 0 1 20 23V5.5Z" /></>,
  resource: <><path d="m2 7 10-5 10 5-10 5zM2 12l10 5 10-5M2 17l10 5 10-5" /></>,
  record: <><path d="M5 3h14v18H5zM9 8h6M9 12h6M9 16h4" /></>,
  manage: <><path d="M9 2h6l1 3 3 1 3 5-2 3v4l-4 3-3-1-3 1-5-3v-4l-2-3 3-5 3-1zM16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0" /></>,
  runtime: <><rect x="3" y="3" width="18" height="7" rx="2" /><rect x="3" y="14" width="18" height="7" rx="2" /><path d="M7 6.5h.01M7 17.5h.01M12 6.5h5M12 17.5h5" /></>,
  outcome: <><rect x="4" y="4" width="16" height="17" rx="2" /><path d="M9 4V2h6v2M8 12l3 3 5-6" /></>,
  shield: <><path d="m12 3 8 3v6c0 4-4 7-8 9-4-2-8-5-8-9V6l8-3Z" /><path d="m8 12 3 3 5-6" /></>,
  agent: <><path d="m12 2 9 5v10l-9 5-9-5V7l9-5ZM3 7l9 5 9-5M12 12v10" /></>,
  relationships: <><path d="M12 8v6M4 14h16M4 14v3M20 14v3M15 4a3 3 0 1 1-6 0 3 3 0 0 1 6 0M7 20a3 3 0 1 1-6 0 3 3 0 0 1 6 0M23 20a3 3 0 1 1-6 0 3 3 0 0 1 6 0" /></>,
  attention: <><path d="M5 17h14l-2-3V9a5 5 0 0 0-10 0v5l-2 3ZM10 21h4M12 2v2" /></>,
  applications: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M8 5V3h8v2M3 10h18M10 14h4M12 12v4" /></>,
  operations: <><path d="M2 3h20v15H2zM6 22h12M12 18v4M5 11h3l2-4 4 8 2-4h3" /></>,
  model: <><path d="m12 2 10 5-10 5L2 7l10-5ZM2 12l10 5 10-5M2 17l10 5 10-5" /></>,
  usage: <><path d="M3 6h18v15H3zM3 6V3h15v3M15 11h7v6h-7zM18 14h.1" /></>,
  help: <><circle cx="12" cy="12" r="9" /><path d="M9 9a3 3 0 1 1 4 2.8c-1 .4-1 1.2-1 2.2M12 17h.01" /></>,
};

export function NavigationIcon({ name }: { name: NavigationIconName }) {
  const frozen=useContext(FrozenNavigationIconContext);
  return <svg viewBox="0 0 24 24" aria-hidden="true">{frozen?(frozenF3NavigationPaths[name]??paths[name]):paths[name]}</svg>;
}
