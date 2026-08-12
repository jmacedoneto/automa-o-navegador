/**
 * Recorder popup glue — wires the "Export Trace" button to a file download.
 */
document.addEventListener("DOMContentLoaded", () => {
  const exportTraceBtn = document.getElementById("exportTraceBtn");
  if (!exportTraceBtn) return;
  exportTraceBtn.addEventListener("click", async () => {
    const { steps = [] } = await chrome.runtime.sendMessage({ action: "getSteps" });
    if (!steps.length) {
      showMsg("Nenhum passo gravado!", "error");
      return;
    }
    if (!window.TraceBuilder) {
      showMsg("TraceBuilder não carregou — recarregue a extensão.", "error");
      return;
    }
    const trace = window.TraceBuilder.build(steps);
    const blob = new Blob([JSON.stringify(trace, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "navrunner-trace.json";
    a.click();
    URL.revokeObjectURL(url);
    showMsg("✓ Trace exportado — faça upload no painel AutoPilot.", "success");
  });
});

function showMsg(text, kind) {
  const msgEl = document.getElementById("msg");
  if (msgEl) {
    msgEl.textContent = text;
    msgEl.style.color = kind === "success" ? "#16a34a" : "#dc2626";
    setTimeout(() => { msgEl.textContent = ""; }, 4000);
  }
}
