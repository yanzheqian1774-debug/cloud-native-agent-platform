/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { sharedExecutionSnapshot } from "./executionSnapshotFixture";
import type { SelectedExecutionContextValue } from "./executionSnapshotTypes";
import { parseSelectedContext } from "./urlContext";

interface ContextValue {
  selection: SelectedExecutionContextValue;
  selectEmployee: (employeeId: string) => void;
  selectRevision: (revisionId: string) => void;
}

const Context = createContext<ContextValue | null>(null);

export function SelectedExecutionContext({ children }: { children: ReactNode }) {
  const location = useLocation();
  const urlSelection = useMemo(() => parseSelectedContext(location.search, sharedExecutionSnapshot), [location.search]);
  const [localSelection, setSelection] = useState<{ search: string; value: SelectedExecutionContextValue } | null>(null);
  const selection = localSelection?.search === location.search ? localSelection.value : urlSelection;

  const value = useMemo<ContextValue>(() => ({
    selection,
    selectEmployee(employeeId) {
      if (sharedExecutionSnapshot.employees.some((employee) => employee.id === employeeId)) setSelection((current) => {
        const base = current?.search === location.search ? current.value : urlSelection;
        return { search: location.search, value: base.employeeId === employeeId ? base : { ...base, employeeId } };
      });
    },
    selectRevision(revisionId) {
      if ([sharedExecutionSnapshot.selectedContext.revisionId, sharedExecutionSnapshot.correctionRevision].includes(revisionId)) setSelection((current) => {
        const base = current?.search === location.search ? current.value : urlSelection;
        return { search: location.search, value: base.revisionId === revisionId ? base : { ...base, revisionId } };
      });
    },
  }), [selection, urlSelection, location.search]);

  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useSelectedExecution() {
  const value = useContext(Context);
  if (!value) throw new Error("SELECTED_EXECUTION_CONTEXT_REQUIRED");
  return value;
}
