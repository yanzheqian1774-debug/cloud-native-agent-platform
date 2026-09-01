import type { ReactNode } from "react";

import { NavLink } from "react-router-dom";

interface ConsoleShellProps {
  children: ReactNode;
}

export function ConsoleShell({
  children,
}: ConsoleShellProps) {
  return (
    <div className="console-shell">
      <header className="console-header">
        <div className="console-header-inner">
          <NavLink className="console-brand" to="/dashboard">
            <span className="console-brand-mark">
              A
            </span>

            <span>Cloud-Native Agent Platform<small>Enterprise Resource Console</small></span>
          </NavLink>
        </div>
      </header>

      <nav className="global-nav demo-primary-nav" aria-label="Primary product navigation">
        <NavLink to="/dashboard">Dashboard</NavLink>
        <NavLink to="/catalog">Resource Catalog</NavLink>
        <NavLink to="/digital-employees">Digital Employees</NavLink>
        <NavLink to="/attention">Attention</NavLink>
        <NavLink to="/relationships">Relationships</NavLink>
        <NavLink to="/problems">Business Questions</NavLink>
        <NavLink to="/technical">Technical View</NavLink>
      </nav>

      <div className="console-content">
        {children}
      </div>
    </div>
  );
}
