/**
 * Builds a Playwright-trace-shaped JSON object from the recorded steps.
 *
 * Schema (subset of Playwright Trace Viewer export):
 *   {
 *     "title": "<automation_name>",
 *     "startTime": "<ISO timestamp>",
 *     "actions": [
 *       {"type": "navigate", "url": "<url>"},
 *       {"type": "click",   "selector": "<css>"},
 *       {"type": "type",     "selector": "<css>", "value": "<text>"},
 *       {"type": "wait_for", "selector": "<css>", "timeout_ms": 10000},
 *       {"type": "screenshot"}
 *     ]
 *   }
 */
window.TraceBuilder = (function() {
  function inferTitle(steps) {
    for (const s of steps || []) {
      if (s.action === "navigate" && s.url) {
        try {
          const u = new URL(s.url);
          return u.host.replace(/[^a-z0-9]+/gi, "_");
        } catch (_) { /* fall through */ }
      }
    }
    return "new_automation";
  }

  function build(steps) {
    const actions = [];
    for (const s of steps || []) {
      switch (s.action) {
        case "navigate":
          actions.push({ type: "navigate", url: s.url });
          break;
        case "click":
          actions.push({ type: "click", selector: s.selector });
          break;
        case "type":
          actions.push({ type: "type", selector: s.selector, value: s.value || "" });
          break;
        case "wait":
        case "wait_for":
          actions.push({
            type: "wait_for",
            selector: s.selector,
            timeout_ms: s.timeoutMs || s.timeout_ms || 10000,
          });
          break;
        case "selectOption":
          actions.push({ type: "select", selector: s.selector });
          break;
        default:
          // Unknown action types are dropped — recorder is heuristic, not strict.
          break;
      }
    }
    return {
      title: inferTitle(steps),
      startTime: new Date().toISOString(),
      actions: actions,
    };
  }

  return { build };
})();
