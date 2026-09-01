import type { ReactNode } from "react";

export type ControlledStateKind = "loading"|"saving"|"empty"|"validation"|"denied"|"not-found"|"conflict"|"stale"|"unavailable"|"partial"|"retryable"|"recovery-required"|"unsupported";

export function ControlledState({kind,title,detail,action}:{kind:ControlledStateKind;title:string;detail?:string;action?:ReactNode}) {
  const alert = !["loading","saving","empty"].includes(kind);
  return <section className={`controlled-state controlled-state-${kind}`} role={alert?"alert":"status"} aria-live="polite" aria-busy={kind==="loading"||kind==="saving"}>
    <h2>{title}</h2>{detail&&<p>{detail}</p>}{action&&<div className="controlled-state-action">{action}</div>}
  </section>;
}
