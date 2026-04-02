import { createBrowserRouter } from "react-router-dom";
import AutomationEditorPage from "../pages/AutomationEditorPage";
import RecordingSessionPage from "../pages/RecordingSessionPage";
import ExecutionRunsPage from "../pages/ExecutionRunsPage";

export const routes = [
  { path: "/automations/:id", element: <AutomationEditorPage /> },
  { path: "/recordings/:id", element: <RecordingSessionPage /> },
  { path: "/runs", element: <ExecutionRunsPage /> },
];

export function createAppRouter() {
  return createBrowserRouter(routes);
}
