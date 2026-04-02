import { createBrowserRouter } from "react-router-dom";
import AutomationEditorPage from "../pages/AutomationEditorPage";
import RecordingSessionPage from "../pages/RecordingSessionPage";
import ExecutionRunsPage from "../pages/ExecutionRunsPage";

export const router = createBrowserRouter([
  { path: "/automations/:id", element: <AutomationEditorPage /> },
  { path: "/recordings/:id", element: <RecordingSessionPage /> },
  { path: "/runs", element: <ExecutionRunsPage /> },
]);
