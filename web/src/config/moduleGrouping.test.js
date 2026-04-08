import { describe, expect, it } from "vitest";
import {
  chartModuleLabelsForScope,
  moduleRowTotal,
  sortModuleKeysLikeStackChart,
  treeChartLabelsUpToDepth,
} from "./moduleGrouping.js";

describe("moduleRowTotal", () => {
  it("sums severity counts", () => {
    expect(
      moduleRowTotal({
        BLOCKER: 2,
        HIGH: 1,
        MEDIUM: 0,
        LOW: 0,
        INFO: 0,
      }),
    ).toBe(3);
  });
  it("returns 0 for empty", () => {
    expect(moduleRowTotal(undefined)).toBe(0);
    expect(moduleRowTotal({})).toBe(0);
  });
});

describe("sortModuleKeysLikeStackChart", () => {
  it("orders by total desc then name", () => {
    const m = {
      zebra: { BLOCKER: 1, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 },
      alpha: { BLOCKER: 5, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 },
      beta: { BLOCKER: 5, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 },
    };
    expect(sortModuleKeysLikeStackChart(m)).toEqual(["alpha", "beta", "zebra"]);
  });
});

describe("treeChartLabelsUpToDepth", () => {
  it("filters by depth and sorts", () => {
    const m = {
      a: { BLOCKER: 1, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 },
      "a/b": { BLOCKER: 1, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 },
      "a/b/c": { BLOCKER: 1, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 },
    };
    expect(treeChartLabelsUpToDepth(m, 2)).toEqual(["a", "a/b"]);
  });
});

describe("chartModuleLabelsForScope", () => {
  it("global uses tree depth order up to chartModuleMaxDepth", () => {
    const m = {
      x: { BLOCKER: 1, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 },
      "x/y/z": { BLOCKER: 1, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 },
    };
    expect(chartModuleLabelsForScope("global", m)).toEqual(["x", "x/y/z"]);
  });
});
