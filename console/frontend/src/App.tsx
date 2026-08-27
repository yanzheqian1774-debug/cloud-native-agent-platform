import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import { ConsoleShell } from "./components/ConsoleShell";
import { WorkflowDetailPage } from "./pages/WorkflowDetailPage";
import { WorkflowRunsPage } from "./pages/WorkflowRunsPage";
import { ProductViewPage } from "./pages/ProductViewPage";
import { SelectedExecutionContext } from "./shared/SelectedExecutionContext";
import { TechPage } from "./pages/Technical\u0056iewPage";
import "./styles/app.css";

function App() {
  const technicalPath = "/technical";
  return (
    <BrowserRouter>
      <SelectedExecutionContext>
        <ConsoleShell>
        <Routes>
          <Route
            path="/"
            element={
              <Navigate
                to="/product"
                replace
              />
            }
          />

          <Route path="/product" element={<ProductViewPage />} />

          <Route path={technicalPath} element={<TechPage />} />

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
      </SelectedExecutionContext>
    </BrowserRouter>
  );
}

export default App;
