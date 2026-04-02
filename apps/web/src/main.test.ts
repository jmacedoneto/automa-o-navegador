import { describe, expect, it } from "vitest";
import { createAppMarkup } from "./main";

describe("createAppMarkup", () => {
  it("returns the workspace shell content", () => {
    expect(createAppMarkup()).toContain("Autopilot Platform");
  });
});
