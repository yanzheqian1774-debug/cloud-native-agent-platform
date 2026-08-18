import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import { WorkflowDetailPage } from "./pages/WorkflowDetailPage";
import { WorkflowRunsPage } from "./pages/WorkflowRunsPage";
import "./styles/app.css";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={<Navigate to="/workflows" replace />}
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
    </BrowserRouter>
  );
}

export default App;
