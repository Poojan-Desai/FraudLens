import { describe, expect, it } from "vitest";
import { findOptimalStrategy, strategyAt } from "../lib/strategy";

describe("fraud strategy engine", () => {
  it("keeps probability metrics bounded", () => {
    const result = strategyAt(0.42, 18, 1.2, 35, 1400);
    expect(result.precision).toBeGreaterThanOrEqual(0);
    expect(result.precision).toBeLessThanOrEqual(1);
    expect(result.recall).toBeGreaterThanOrEqual(0);
    expect(result.recall).toBeLessThanOrEqual(1);
  });

  it("never flags more transactions after increasing the threshold", () => {
    const flagged = [0.1, 0.3, 0.5, 0.8].map((threshold) => strategyAt(threshold, 18, 1.2, 35, 1400).flagged);
    expect(flagged).toEqual([...flagged].sort((a, b) => b - a));
  });

  it("recalculates cost when customer friction changes", () => {
    const low = strategyAt(0.42, 5, 1.2, 35, 1400);
    const high = strategyAt(0.42, 35, 1.2, 35, 1400);
    expect(high.totalCost).toBeGreaterThan(low.totalCost);
  });

  it("returns the lowest-cost point from the evaluated curve", () => {
    const optimum = findOptimalStrategy(18, 1.2, 35, 1400);
    for (let step = 1; step < 100; step += 1) {
      expect(optimum.totalCost).toBeLessThanOrEqual(strategyAt(step / 100, 18, 1.2, 35, 1400).totalCost);
    }
  });

  it("rejects thresholds outside the probability range", () => {
    expect(() => strategyAt(1.1, 18, 1.2, 35, 1400)).toThrow(RangeError);
  });
});
