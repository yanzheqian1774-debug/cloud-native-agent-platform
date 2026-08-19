import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import { ConsoleShell } from "./components/ConsoleShell";
import { WorkflowDetailPage } from "./pages/WorkflowDetailPage";
import { WorkflowRunsPage } from "./pages/WorkflowRunsPage";
import "./styles/app.css";

function App() {
  return (
    <BrowserRouter>
      <ConsoleShell>
        <Routes>
          <Route
            path="/"
            element={
              <Navigate
                to="/workflows"
                replace
              />
            }
          />

          <Route
            path="/workflows"
            element={<WorkflowRunsPage />}
          />

          <Route
            path="/workflows/:namespace/:name"
            element={<WorkflowDetailPage />}
          />
        </Routes>
      </ConsoleShell>
    </BrowserRouter>
  );
}

export default App;
