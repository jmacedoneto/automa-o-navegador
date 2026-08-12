/**
 * AutoPilot Recorder - Content Script v2.3
 *
 * Fixes for ERP with Select2 + Bootstrap Datepicker:
 *  - Select2 fires jQuery events, NOT native DOM change events.
 *    Solution: snapshot all <select> values before every click,
 *    then compare 150ms later → records whichever select changed.
 *  - Bootstrap Datepicker also doesn't reliably fire blur.
 *    Same snapshot approach for date inputs.
 *  - Lookup fields (lupa/search popup): captures button click + fill.
 */

// ── Selector generation ──────────────────────────────────────────────────────
function getBestSelector(el) {
  if (!el || el === document.body) return "body";
  const tag = el.tagName.toLowerCase();

  if (el.id) {
    const id = el.id;
    const autoGen = /^\d+$/.test(id) ||
      /^[0-9a-f]{8}-[0-9a-f]{4}/.test(id) ||
      /\d{4,}/.test(id);
    if (!autoGen) return `#${CSS.escape(id)}`;
  }
  if (el.name) return `${tag}[name="${CSS.escape(el.name)}"]`;
  const preferredData = ["data-testid","data-cy","data-id","data-field","data-name"];
  for (const attr of preferredData) {
    const val = el.getAttribute(attr);
    if (val) return `[${attr}="${CSS.escape(val)}"]`;
  }
  const ariaLabel = el.getAttribute("aria-label");
  if (ariaLabel) return `[aria-label="${CSS.escape(ariaLabel)}"]`;
  if (el.placeholder) return `${tag}[placeholder="${CSS.escape(el.placeholder)}"]`;
  if (el.title && el.title.length < 60) return `[title="${CSS.escape(el.title)}"]`;
  if (tag === "input" && (el.type === "submit" || el.type === "button") && el.value)
    return `input[value="${CSS.escape(el.value)}"]`;
  if (["button","a","li","option","label"].includes(tag)) {
    const text = (el.innerText || el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 40);
    if (text && text.length > 1)
      return `${tag}:has-text("${text.replace(/"/g, '\\"')}")`;
  }
  return buildStructuralSelector(el);
}

function buildStructuralSelector(el) {
  const parts = [];
  let node = el;
  for (let depth = 0; depth < 5 && node && node !== document.body; depth++) {
    const tag = node.tagName.toLowerCase();
    if (node.id && !/\d{4,}/.test(node.id)) { parts.unshift(`#${CSS.escape(node.id)}`); break; }
    let part = tag;
    if (node.parentNode) {
      const sibs = Array.from(node.parentNode.children).filter(c => c.tagName === node.tagName);
      if (sibs.length > 1) part += `:nth-of-type(${sibs.indexOf(node) + 1})`;
    }
    parts.unshift(part);
    node = node.parentNode;
  }
  return parts.join(" > ");
}

function getDesc(el, action) {
  const tag = el.tagName.toLowerCase();
  const text = (el.innerText || el.value || el.title || el.placeholder || el.getAttribute("aria-label") || "").trim().slice(0, 40);
  if (action === "hover")       return `Hover em ${text ? `"${text}"` : tag}`;
  if (action === "click")       return `Clique em ${text ? `"${text}"` : tag}`;
  if (action === "type")        return `Digitar em ${el.name || el.placeholder || el.id || tag}`;
  if (action === "selectOption")return `Selecionar "${text}" em ${el.name || el.id || "select"}`;
  return action;
}

// ── Overlay ──────────────────────────────────────────────────────────────────
let overlay = null;
function showOverlay(count) {
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "__ap_ov__";
    overlay.style.cssText = "position:fixed;bottom:20px;right:20px;z-index:2147483647;background:rgba(239,68,68,.95);color:#fff;font-family:sans-serif;font-size:13px;font-weight:700;padding:8px 14px;border-radius:20px;box-shadow:0 4px 12px rgba(0,0,0,.5);display:flex;align-items:center;gap:8px;user-select:none;pointer-events:none";
    document.body.appendChild(overlay);
    if (!document.getElementById("__ap_css__")) {
      const s = document.createElement("style");
      s.id = "__ap_css__";
      s.textContent = "@keyframes __ap_p{0%,100%{opacity:1}50%{opacity:.3}}";
      document.head.appendChild(s);
    }
  }
  overlay.innerHTML = `<span style="width:8px;height:8px;border-radius:50%;background:#fff;animation:__ap_p 1s infinite;display:inline-block"></span> Gravando — ${count} passo${count!==1?"s":""}`;
}
function hideOverlay() { if (overlay) { overlay.remove(); overlay = null; } }

// ── State ────────────────────────────────────────────────────────────────────
let recording = false;
let stepCount = 0;

function checkState() {
  chrome.runtime.sendMessage({ action: "getState" }, (res) => {
    if (chrome.runtime.lastError) return;
    const was = recording;
    recording = !!(res && res.isRecording);
    stepCount = res ? res.stepsCount : 0;
    recording ? showOverlay(stepCount) : hideOverlay();
    if (recording && !was) startObserver();
    if (!recording && was) stopObserver();
  });
}
setInterval(checkState, 2000);
checkState();

// ── Auto-start: detecta parâmetros __autopilot_* na URL ─────────────────────
(function autoStartIfRequested() {
  const params = new URLSearchParams(window.location.search);
  const sessionId = params.get("__autopilot_session");
  const apiBase   = params.get("__autopilot_api");
  const redirect  = params.get("__autopilot_redirect");
  if (!sessionId || !apiBase) return;

  // Remove os parâmetros da URL sem recarregar
  const clean = new URL(window.location.href);
  clean.searchParams.delete("__autopilot_session");
  clean.searchParams.delete("__autopilot_api");
  clean.searchParams.delete("__autopilot_redirect");
  window.history.replaceState({}, "", clean.toString());

  // Inicia gravação passando sessionId e apiBase para o background
  chrome.runtime.sendMessage(
    { action: "startRecording", sessionId, apiBase },
    () => {
      recording = true;
      showOverlay(0);
      startObserver();
      // Redireciona para a URL fornecida; se não houver, abre página em branco
      if (redirect && redirect !== window.location.href) {
        window.location.href = decodeURIComponent(redirect);
      } else {
        window.location.href = "about:blank";
      }
    }
  );
})();

function sendStep(stepData) {
  chrome.runtime.sendMessage({ action: "addStep", stepData }, () => {
    if (chrome.runtime.lastError) return;
    stepCount++;
    if (recording) showOverlay(stepCount);
  });
}

// ── Snapshot helpers (for Select2 / Datepicker detection) ────────────────────
function snapshotSelects() {
  const m = new Map();
  document.querySelectorAll("select").forEach(s => {
    if (s.id || s.name) m.set(s.id || s.name, s.value);
  });
  return m;
}

function snapshotDateInputs() {
  const m = new Map();
  document.querySelectorAll("input.datePicker, input[type='date'], input[data-provide='datepicker']").forEach(i => {
    if (i.id || i.name) m.set(i.id || i.name, i.value);
  });
  return m;
}

let prevSelects = new Map();
let prevDates = new Map();

// ── Click listener ───────────────────────────────────────────────────────────
document.addEventListener("mousedown", () => {
  if (!recording) return;
  prevSelects = snapshotSelects();
  prevDates = snapshotDateInputs();
}, true);

document.addEventListener("click", (e) => {
  if (!recording) return;

  // ── After click: detect Select2 / Datepicker value changes ──
  setTimeout(() => {
    // Check selects
    const cur = snapshotSelects();
    for (const [key, val] of cur) {
      if (val && val !== (prevSelects.get(key) ?? "")) {
        const el = document.getElementById(key) || document.querySelector(`select[name="${key}"]`);
        const selText = el ? (el.options[el.selectedIndex]?.text || val).trim() : val;
        sendStep({
          action: "selectOption",
          selector: el?.id ? `#${el.id}` : `select[name="${key}"]`,
          value: val,
          description: `Selecionar "${selText}" em ${el?.title || el?.name || key}`,
          waitTime: 500,
        });
      }
    }
    prevSelects = cur;

    // Check date inputs
    const curD = snapshotDateInputs();
    for (const [key, val] of curD) {
      if (val && val !== (prevDates.get(key) ?? "")) {
        const el = document.getElementById(key) || document.querySelector(`input[name="${key}"]`);
        sendStep({
          action: "type",
          selector: el?.id ? `#${el.id}` : `input[name="${key}"]`,
          value: val,
          description: `Data "${val}" em ${el?.title || el?.name || key}`,
          waitTime: 300,
        });
      }
    }
    prevDates = curD;
  }, 150);

  // ── Capture the click itself ──
  const origin = e.target;
  if (!origin || origin === document.body || origin === document.documentElement) return;

  const tag0 = origin.tagName?.toLowerCase();
  const type0 = (origin.type || "").toLowerCase();

  // Skip text inputs (captured on blur) and native selects (captured via snapshot)
  if (tag0 === "input" && ["text","password","email","number","search","tel","url"].includes(type0)) return;
  if (tag0 === "select") return;
  if (tag0 === "textarea") return;

  // Skip Select2 internal — value change captured via snapshot
  if (origin.closest?.(".select2-container, .select2-dropdown, .select2-results")) return;

  // Skip Bootstrap Datepicker calendar cells
  if (origin.closest?.(".datepicker, .datepicker-dropdown")) return;

  // Walk up looking for a well-identified clickable element (button, link, role, etc.)
  let target = origin;
  while (target && target !== document.body) {
    if (isClickable(target)) {
      sendStep({
        action: "click",
        selector: getBestSelector(target),
        description: getDesc(target, "click"),
        waitTime: 800,
      });
      return;
    }
    target = target.parentElement;
  }

  // Fallback: nenhum elemento padrão encontrado — grava o clique no alvo original.
  // Isso captura dropdowns customizados, widgets dinâmicos e qualquer elemento não-padrão.
  sendStep({
    action: "click",
    selector: getBestSelector(origin),
    description: getDesc(origin, "click"),
    waitTime: 800,
  });
}, true);

function isClickable(el) {
  if (!el || el === document.body) return false;
  const tag = el.tagName.toLowerCase();
  const role = (el.getAttribute("role") || "").toLowerCase();
  const type = (el.type || "").toLowerCase();
  if (["a","button","label"].includes(tag)) return true;
  if (tag === "input" && ["checkbox","radio","submit","button","reset","image"].includes(type)) return true;
  if (["button","menuitem","menuitemcheckbox","menuitemradio","option","radio",
       "checkbox","tab","switch","treeitem","gridcell","link"].includes(role)) return true;
  if (tag === "option") return true;
  try { if (getComputedStyle(el).cursor === "pointer") return true; } catch (_) {}
  if (el.closest?.("[role='dialog'],[role='alertdialog'],[role='listbox']," +
                    "[role='menu'],[role='menubar'],[role='tree']," +
                    ".modal,.popup,.dropdown-menu")) return true;
  return false;
}

// ── Blur: text inputs ────────────────────────────────────────────────────────
document.addEventListener("blur", (e) => {
  if (!recording) return;
  const t = e.target;
  if (!t) return;
  const tag = t.tagName.toLowerCase();
  const type = (t.type || "text").toLowerCase();
  if (tag !== "input" && tag !== "textarea") return;
  if (!["text","password","email","number","search","tel","url"].includes(type) && tag !== "textarea") return;
  const value = t.value;
  if (!value || value === "[Não selecionado]") return;
  sendStep({
    action: "type",
    selector: getBestSelector(t),
    value,
    description: getDesc(t, "type"),
    waitTime: 500,
  });
}, true);

// ── Native select fallback ────────────────────────────────────────────────────
document.addEventListener("change", (e) => {
  if (!recording) return;
  const t = e.target;
  if (!t || t.tagName.toLowerCase() !== "select") return;
  // Only if not already handled by snapshot (Select2 wouldn't reach here)
  const val = t.value;
  if (!val) return;
  const selText = (t.options[t.selectedIndex]?.text || val).trim();
  sendStep({
    action: "selectOption",
    selector: getBestSelector(t),
    value: val,
    description: `Selecionar "${selText}" em ${t.title || t.name || t.id || "select"}`,
    waitTime: 500,
  });
}, true);

// ── Hover detection (MutationObserver) ───────────────────────────────────────
let lastHoveredEl = null;
let lastHoverTime = 0;
let lastHoverSel = "";
let mutObs = null;

function isMenuLike(el) {
  if (!el || el === document.body) return false;
  const tag = el.tagName?.toLowerCase();
  const role = (el.getAttribute?.("role") || "").toLowerCase();
  if (["menuitem","menuitemcheckbox","menuitemradio","tab","treeitem"].includes(role)) return true;
  if (el.closest?.("nav,[role='menu'],[role='menubar'],[role='navigation'],[role='tablist'],header")) return true;
  if (tag === "li" && el.closest?.("ul,ol")) return true;
  return false;
}

function isHoverTrigger(el) {
  if (!el || el === document.body) return false;
  if (isMenuLike(el)) return true;
  try { if (getComputedStyle(el).cursor === "pointer") return true; } catch (_) {}
  return false;
}

function onMutation(mutations) {
  if (!recording || !lastHoveredEl) return;
  if (Date.now() - lastHoverTime > 1200) return;
  const changed = mutations.some(m =>
    (m.type === "childList" && m.addedNodes.length > 0) ||
    (m.type === "attributes" && ["class","style","hidden","aria-expanded","aria-hidden","data-state","data-open","data-visible","data-show"].includes(m.attributeName))
  );
  if (!changed) return;
  const sel = getBestSelector(lastHoveredEl);
  if (sel === lastHoverSel) return;
  lastHoverSel = sel;
  sendStep({ action: "hover", selector: sel, description: getDesc(lastHoveredEl, "hover"), waitTime: 800 });
  lastHoveredEl = null;
}

function startObserver() {
  if (mutObs) return;
  mutObs = new MutationObserver(onMutation);
  mutObs.observe(document.body, {
    childList: true, subtree: true, attributes: true,
    attributeFilter: ["class","style","hidden","aria-expanded","aria-hidden","data-state","data-open","data-visible"],
  });
}
function stopObserver() { if (mutObs) { mutObs.disconnect(); mutObs = null; } }

document.addEventListener("mouseover", (e) => {
  if (!recording) return;
  let t = e.target;
  for (let i = 0; i < 5 && t && t !== document.body; i++) {
    if (isHoverTrigger(t)) { lastHoveredEl = t; lastHoverTime = Date.now(); return; }
    t = t.parentElement;
  }
}, true);

chrome.runtime.onMessage.addListener((req) => {
  if (req.action === "_stepsUpdated") { stepCount = req.stepsCount; if (recording) showOverlay(stepCount); }
});
