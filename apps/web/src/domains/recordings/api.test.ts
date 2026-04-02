import { describe, expect, it } from "vitest";
import { buildRecordingSessionRequest } from "./api";

describe("recording api", () => {
  it("creates the payload expected by the orchestration api", () => {
    expect(buildRecordingSessionRequest("auto-1")).toEqual({
      automation_id: "auto-1",
    });
  });
});
