import { describe, expect, it } from "vitest";
import type { AutomationMode, FallbackPolicy } from "@autopilot/shared";

describe("shared contracts", () => {
  it("exposes the automation modes used by the web app", () => {
    const modes: AutomationMode[] = ["gravado", "hibrido", "livre_ai"];

    expect(modes).toHaveLength(3);
  });

  it("requires bounded fallback policy values", () => {
    const policy: FallbackPolicy = {
      maxTentativasIa: 2,
      timeoutTotalSegundos: 20,
      pausaQuandoFalhar: true,
    };

    expect(policy.maxTentativasIa).toBeGreaterThan(0);
  });
});
