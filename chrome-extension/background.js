/**
 * AutoPilot Recorder - Background Service Worker v3
 * Suporte a sessão em tempo real com o painel do AutoPilot.
 */

let isRecording = false;
let steps = [];
let lastNavigatedUrl = "";
let sessionId = null;   // sessão ativa no painel
let apiBase = null;     // ex: https://navegador.apvsiguatemi.net/api

// ── Envia passo para o backend em tempo real ─────────────────────────────────
async function pushStep(step) {
  if (!sessionId || !apiBase) return;
  try {
    await fetch(`${apiBase}/automations/ext-session/${sessionId}/step`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(step),
    });
  } catch (_) {}
}

// ── Message handler ──────────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {

  if (request.action === "getState") {
    sendResponse({ isRecording, stepsCount: steps.length, steps, sessionId });
    return true;
  }

  if (request.action === "startRecording") {
    isRecording = true;
    steps = [];
    lastNavigatedUrl = "";
    sessionId = request.sessionId || null;
    apiBase = request.apiBase || null;
    // Não registra a URL inicial automaticamente — a primeira navegação real
    // será capturada pelo tabs.onUpdated quando o usuário acessar o site desejado.
    sendResponse({ isRecording, stepsCount: steps.length });
    return true;
  }

  if (request.action === "stopRecording") {
    isRecording = false;
    sendResponse({ isRecording, stepsCount: steps.length });
    return true;
  }

  if (request.action === "getSteps") {
    sendResponse({ steps });
    return true;
  }

  if (request.action === "clearSteps") {
    steps = [];
    lastNavigatedUrl = "";
    sessionId = null;
    sendResponse({ success: true });
    return true;
  }

  if (request.action === "deleteStep") {
    steps.splice(request.index, 1);
    sendResponse({ steps });
    return true;
  }

  if (request.action === "addStep" && isRecording) {
    const last = steps[steps.length - 1];
    const isDuplicate =
      last &&
      last.action === request.stepData.action &&
      last.selector === request.stepData.selector &&
      last.value === request.stepData.value;

    if (!isDuplicate) {
      steps.push({ ...request.stepData });
      chrome.storage.local.set({ recordedSteps: steps });
      pushStep(request.stepData);
      chrome.runtime.sendMessage({ action: "_stepsUpdated", stepsCount: steps.length }).catch(() => {});
    }
    sendResponse({ success: true });
    return true;
  }
});

// ── Auto-navigate on tab URL change ─────────────────────────────────────────
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (!isRecording) return;
  if (changeInfo.status !== "complete") return;
  if (!tab.url || tab.url.startsWith("chrome://") || tab.url === "about:blank") return;
  if (tab.url === lastNavigatedUrl) return;

  try {
    const prev = new URL(lastNavigatedUrl || "about:blank");
    const next = new URL(tab.url);
    if (prev.origin + prev.pathname + prev.search === next.origin + next.pathname + next.search) return;
  } catch (_) {}

  lastNavigatedUrl = tab.url;
  const last = steps[steps.length - 1];
  if (last && last.action === "navigate" && last.url === tab.url) return;

  const step = {
    action: "navigate",
    url: tab.url,
    description: `Navegar para ${tab.url}`,
    waitTime: 1500,
  };
  steps.push(step);
  chrome.storage.local.set({ recordedSteps: steps });
  pushStep(step);
  chrome.runtime.sendMessage({ action: "_stepsUpdated", stepsCount: steps.length }).catch(() => {});
});
