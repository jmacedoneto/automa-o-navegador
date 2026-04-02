import { createElement } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import { createAppRouter } from "./app/router";

export function createAppRoot() {
  return createElement(RouterProvider, { router: createAppRouter() });
}

export function mountApp(rootElement: HTMLElement | null) {
  if (!rootElement) {
    return null;
  }

  const root = createRoot(rootElement);
  root.render(createAppRoot());
  return root;
}

if (typeof document !== "undefined") {
  mountApp(document.getElementById("root"));
}
