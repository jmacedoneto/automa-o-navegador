/**
 * AutoPilot Recorder - Popup v2
 */
document.addEventListener("DOMContentLoaded", async () => {
  const startBtn   = document.getElementById("startBtn");
  const stopBtn    = document.getElementById("stopBtn");
  const sendBtn    = document.getElementById("sendBtn");
  const exportBtn  = document.getElementById("exportBtn");
  const clearBtn   = document.getElementById("clearBtn");
  const statusLabel= document.getElementById("statusLabel");
  const stepBadge  = document.getElementById("stepBadge");
  const dot        = document.getElementById("dot");
  const msgEl      = document.getElementById("msg");
  const stepsList  = document.getElementById("stepsList");
  const configToggle = document.getElementById("configToggle");
  const configBody   = document.getElementById("configBody");
  const apiUrlInput  = document.getElementById("apiUrl");
  const automationIdInput = document.getElementById("automationId");
  const saveConfigBtn = document.getElementById("saveConfig");

  // ── Load saved config ────────────────────────────────────────────────────
  const stored = await chrome.storage.local.get(["apiUrl", "automationId"]);
  if (stored.apiUrl) apiUrlInput.value = stored.apiUrl;
  if (stored.automationId) automationIdInput.value = stored.automationId;

  // ── Config toggle ────────────────────────────────────────────────────────
  configToggle.addEventListener("click", () => configBody.classList.toggle("open"));
  saveConfigBtn.addEventListener("click", async () => {
    await chrome.storage.local.set({
      apiUrl: apiUrlInput.value.trim(),
      automationId: automationIdInput.value.trim(),
    });
    showMsg("Configurações salvas!", "success");
  });

  // ── Load initial state ───────────────────────────────────────────────────
  const state = await chrome.runtime.sendMessage({ action: "getState" });
  renderUI(state.isRecording, state.steps || []);

  // ── Listen for step updates from background ──────────────────────────────
  chrome.runtime.onMessage.addListener((request) => {
    if (request.action === "_stepsUpdated") {
      chrome.runtime.sendMessage({ action: "getState" }, (s) => {
        if (s) renderUI(s.isRecording, s.steps || []);
      });
    }
  });

  // ── Buttons ──────────────────────────────────────────────────────────────
  startBtn.addEventListener("click", async () => {
    await chrome.runtime.sendMessage({ action: "startRecording" });
    const s = await chrome.runtime.sendMessage({ action: "getState" });
    renderUI(true, s.steps || []);
  });

  stopBtn.addEventListener("click", async () => {
    await chrome.runtime.sendMessage({ action: "stopRecording" });
    const s = await chrome.runtime.sendMessage({ action: "getState" });
    renderUI(false, s.steps || []);
  });

  exportBtn.addEventListener("click", async () => {
    const { steps } = await chrome.runtime.sendMessage({ action: "getSteps" });
    if (!steps.length) { showMsg("Nenhum passo gravado!", "error"); return; }
    const blob = new Blob([JSON.stringify(steps, null, 2)], { type: "application/json" });
    const url  = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "automacao_passos.json"; a.click();
    URL.revokeObjectURL(url);
  });

  sendBtn.addEventListener("click", async () => {
    const { steps } = await chrome.runtime.sendMessage({ action: "getSteps" });
    if (!steps.length) { showMsg("Nenhum passo gravado!", "error"); return; }

    const cfg = await chrome.storage.local.get(["apiUrl", "automationId"]);
    if (!cfg.apiUrl || !cfg.automationId) {
      showMsg("Configure a URL e o ID da automação primeiro!", "error");
      configBody.classList.add("open");
      return;
    }

    sendBtn.disabled = true;
    statusLabel.textContent = "Enviando...";

    try {
      const url = `${cfg.apiUrl.replace(/\/$/, "")}/automations/${cfg.automationId}/import-steps`;
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(steps),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
      const data = await resp.json();
      showMsg(`✓ ${data.imported} passos importados com sucesso!`, "success");
      await chrome.runtime.sendMessage({ action: "clearSteps" });
      renderUI(false, []);
    } catch (err) {
      showMsg(`Erro: ${err.message}`, "error");
    } finally {
      sendBtn.disabled = false;
    }
  });

  clearBtn.addEventListener("click", async () => {
    await chrome.runtime.sendMessage({ action: "clearSteps" });
    renderUI(false, []);
  });

  // ── Render ───────────────────────────────────────────────────────────────
  function renderUI(rec, steps) {
    const count = steps.length;

    // Status bar
    dot.className = "dot " + (rec ? "recording" : (count > 0 ? "idle" : ""));
    statusLabel.textContent = rec ? "Gravando..." : (count > 0 ? "Gravação pausada" : "Pronto");
    stepBadge.textContent = `${count} passo${count !== 1 ? "s" : ""}`;

    // Buttons
    startBtn.style.display  = rec ? "none" : "flex";
    stopBtn.style.display   = rec ? "flex" : "none";
    sendBtn.style.display   = (!rec && count > 0) ? "flex" : "none";
    exportBtn.style.display = (!rec && count > 0) ? "flex" : "none";
    clearBtn.style.display  = (!rec && count > 0) ? "flex" : "none";

    // Steps list
    if (!count) {
      stepsList.innerHTML = '<div class="steps-empty">Nenhum passo ainda</div>';
      return;
    }
    stepsList.innerHTML = steps.map((step, i) => {
      const typeClass = step.action === "navigate" ? "navigate"
        : step.action === "click" ? "click"
        : step.action === "type" ? "type"
        : step.action === "selectOption" ? "select"
        : step.action === "hover" ? "hover"
        : "";
      const typeLabel = step.action === "navigate" ? "navegar"
        : step.action === "click" ? "clique"
        : step.action === "type" ? "digitar"
        : step.action === "selectOption" ? "select"
        : step.action === "hover" ? "hover"
        : step.action;
      const desc = step.description || step.selector || step.url || "";
      return `
        <div class="step-item">
          <span class="step-num">${i + 1}</span>
          <span class="step-badge-type ${typeClass}">${typeLabel}</span>
          <span class="step-desc" title="${escHtml(desc)}">${escHtml(desc.slice(0, 60))}</span>
          <span class="step-del" data-idx="${i}" title="Remover">✕</span>
        </div>`;
    }).join("");

    // Delete handlers
    stepsList.querySelectorAll(".step-del").forEach(btn => {
      btn.addEventListener("click", async () => {
        const idx = parseInt(btn.dataset.idx);
        const { steps: updated } = await chrome.runtime.sendMessage({ action: "deleteStep", index: idx });
        renderUI(rec, updated || []);
      });
    });

    // Auto-scroll to bottom
    stepsList.scrollTop = stepsList.scrollHeight;
  }

  function showMsg(text, type) {
    msgEl.textContent = text;
    msgEl.className = `msg ${type}`;
    setTimeout(() => { msgEl.className = "msg"; }, 4000);
  }

  function escHtml(s) {
    return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }
});
