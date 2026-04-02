import { describe, expect, it } from "vitest";
import type { AutomationMode, FallbackPolicy } from "@autopilot/shared";

describe("shared contracts", () => {
  it("resolves the shared package through the workspace boundary", async () => {
    const shared = await import("@autopilot/shared");

    expect(shared).toBeTypeOf("object");
  });

  it("exposes the automation modes used by the web app", () => {
    const modes: AutomationMode[] = ["gravado", "hibrido", "livre_ai"];

    expect(modes).toEqual(["gravado", "hibrido", "livre_ai"]);
  });

  it("requires bounded fallback policy values", () => {
    const policy: FallbackPolicy = {
      maxTentativasIa: 2,
      timeoutTotalSegundos: 20,
      pausaQuandoFalhar: true,
    };

    expect(policy.maxTentativasIa).toBeGreaterThan(0);
    expect(policy.timeoutTotalSegundos).toBeGreaterThan(0);
    expect(policy.pausaQuandoFalhar).toBe(true);
  });
});
