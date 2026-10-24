import { describe, expect, it } from "vitest";
import { evaluation, findOptimalStrategy, strategyAt, TOTAL_TRANSACTIONS, type ModelKey } from "../lib/strategy";

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
    const low = strategyAt(0.05, 5, 1.2, 35, 1400);
    const high = strategyAt(0.05, 35, 1.2, 35, 1400);
    expect(low.falsePositives).toBeGreaterThan(0);
    expect(high.totalCost - low.totalCost).toBeCloseTo(low.falsePositives * 30, 2);
  });

  it("selects the same policy as Python using selection data only", () => {
    for (const model of Object.keys(evaluation.models) as ModelKey[]) {
      const policy = findOptimalStrategy(18, 1.2, 35, 1400, model);
      expect(policy.threshold).toBe(evaluation.models[model].selected_threshold);
      expect(policy.totalCost).toBe(evaluation.models[model].selection_cost);
      for (const point of evaluation.models[model].selection_thresholds) {
        expect(policy.totalCost).toBeLessThanOrEqual(point.total_cost);
      }
    }
  });

  it("uses actual test counts and raw dollar totals instead of illustrative formulas", () => {
    for (const model of Object.keys(evaluation.models) as ModelKey[]) {
      const metrics = evaluation.models[model].metrics;
      const result = strategyAt(metrics.threshold, 18, 1.2, 35, 1400, model);
      expect(result.flagged).toBe(metrics.flagged);
      expect(result.totalCost).toBe(metrics.total_cost);
      expect(result.fraudMissed).toBe(metrics.fraud_missed);
      expect(result.truePositives + result.falsePositives + result.trueNegatives + result.falseNegatives).toBe(TOTAL_TRANSACTIONS);
    }
  });

  it("rejects unsupported grid points and invalid cost assumptions", () => {
    expect(() => strategyAt(0.425, 18, 1.2, 35, 1400)).toThrow(RangeError);
    expect(() => strategyAt(0.42, -1, 1.2, 35, 1400)).toThrow(RangeError);
    expect(() => strategyAt(0.42, 18, Infinity, 35, 1400)).toThrow(RangeError);
  });

  it("rejects thresholds outside the probability range", () => {
    expect(() => strategyAt(1.1, 18, 1.2, 35, 1400)).toThrow(RangeError);
  });
});
