import { describe, expect, it } from "vitest";
import { routes } from "./app/router";

describe("routes", () => {
  it("registers the task 5 route shells", () => {
    expect(routes.map((route) => route.path)).toEqual([
      "/automations/:id",
      "/recordings/:id",
      "/runs",
    ]);
  });
});
