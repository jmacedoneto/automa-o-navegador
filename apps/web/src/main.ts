export function createAppMarkup() {
  return `
    <main style="font-family: system-ui, sans-serif; padding: 2rem;">
      <h1>Autopilot Platform</h1>
      <p>The workspace shell is ready.</p>
    </main>
  `;
}

export function mountApp(root: HTMLElement | null) {
  if (root) {
    root.innerHTML = createAppMarkup();
  }
}

if (typeof document !== "undefined") {
  mountApp(document.getElementById("root"));
}
