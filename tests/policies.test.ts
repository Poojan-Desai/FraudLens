import { describe, expect, it } from "vitest";
import { compareStrategyPolicies, evaluation, fBeta, selectStrategyPolicy, strategyAt, type ModelKey } from "../lib/strategy";

describe("selection-based policy presets", () => {
  it("reports the frozen study's three XGBoost operating points without claiming a new model", () => {
    const rows = compareStrategyPolicies(18, 1.2, 35, 1400);
    expect(rows.map(row => [row.objective, row.test.threshold, row.test.truePositives, row.test.falsePositives, row.test.flagged])).toEqual([
      ["cost", 0.18, 17, 10, 27], ["f1", 0.11, 44, 123, 167], ["f2", 0.06, 61, 425, 486],
    ]);
  });

  it("maximizes each score across selection counts for both models", () => {
    for (const model of Object.keys(evaluation.models) as ModelKey[]) {
      for (const [objective, betaSquared] of [["f1", 1], ["f2", 4]] as const) {
        // Independently compute the objective using stored selection counts.
        const ranked = [...evaluation.models[model].selection_thresholds].sort((a, b) => {
          const score = (p: typeof a) => ((1 + betaSquared) * p.true_positives) /
            ((1 + betaSquared) * p.true_positives + betaSquared * p.false_negatives + p.false_positives || 1);
          return score(b) - score(a) || b.threshold - a.threshold;
        });
        const policy = selectStrategyPolicy(objective, 18, 1.2, 35, 1400, model);
        expect(policy.threshold).toBe(ranked[0].threshold);
        expect(policy.truePositives).toBe(ranked[0].true_positives);
      }
    }
  });

  it("keeps selection counts separate from test reporting", () => {
    for (const row of compareStrategyPolicies(18, 1.2, 35, 1400)) {
      expect(row.selection.truePositives + row.selection.falseNegatives).toBe(evaluation.windows.selection.fraud_rows);
      expect(row.test.truePositives + row.test.falseNegatives).toBe(128);
      expect(row.test).toEqual(strategyAt(row.selection.threshold, 18, 1.2, 35, 1400));
    }
  });

  it("does not advertise a review-capacity constraint for score objectives", () => {
    const limited = compareStrategyPolicies(100, 20, 0, 1);
    const normal = compareStrategyPolicies(18, 1.2, 35, 1400);
    for (const index of [1, 2]) {
      expect(limited[index].test.threshold).toBe(normal[index].test.threshold);
      expect(limited[index].test.flagged).toBeGreaterThan(1);
      expect(limited[index].test.totalCost).not.toBe(normal[index].test.totalCost);
    }
  });

  it("returns measured zero when a policy detects no fraud", () => {
    // This costly policy flags no selection rows, so F-beta is a measured zero.
    const empty = strategyAt(0.99, 18, 1.2, 35, 1400);
    expect(fBeta(empty, 1)).toBe(0);
    expect(fBeta(empty, 2)).toBe(0);
  });

  it("rejects unknown objectives and invalid beta", () => {
    expect(() => selectStrategyPolicy("unknown" as "f1", 18, 1.2, 35, 1400)).toThrow(RangeError);
    const point = strategyAt(0.18, 18, 1.2, 35, 1400);
    for (const beta of [0, -1, NaN, Infinity]) expect(() => fBeta(point, beta)).toThrow(RangeError);
    expect(fBeta(point, Number.MAX_VALUE)).toBeCloseTo(point.recall, 12);
    expect(fBeta(point, Number.MIN_VALUE)).toBeCloseTo(point.precision, 12);
  });
});
