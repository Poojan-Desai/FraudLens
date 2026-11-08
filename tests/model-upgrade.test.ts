import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import ModelUpgrade, { hasValidatedRankingGain, type ModelComparisonReport } from "../app/model-upgrade";
import report from "../public/model-comparison.json";

describe("frozen model comparison presentation", () => {
  it("shows paired fresh outcomes and every predeclared budget without changing legacy evidence", () => {
    const html = renderToStaticMarkup(createElement(ModelUpgrade));
    expect(html).toContain('data-comparison-status="validated"');
    expect(html).toContain("150,000");
    expect(html).toContain("604 / 1,545");
    expect(html).toContain("650 / 1,545");
    expect(html).toContain("2,396");
    expect(html).toContain("2,350");
    expect(html.match(/data-budget=/g)).toHaveLength(4);
    expect(html).toContain("previously exposed study");
    expect(html).toContain("no live inference");
  });

  it("makes the measured cost-policy regression visible alongside ranking gains", () => {
    const html = renderToStaticMarkup(createElement(ModelUpgrade));
    expect(html).toContain("The selection-chosen cost policy regressed.");
    expect(html).toContain("$84,405.00");
    expect(html).toContain("$81,248.93");
    expect(html).toContain("threshold 0.66");
    expect(html).toContain("threshold 0.18");
    expect(html).toContain("not retuned after the final evaluation");
  });

  it("labels a failed gate inconclusive", () => {
    const failed: ModelComparisonReport = structuredClone(report);
    failed.comparison.promotion_gate_passed = false;
    const html = renderToStaticMarkup(createElement(ModelUpgrade, { report: failed }));
    expect(html).toContain('data-comparison-status="inconclusive"');
    expect(html).not.toContain("Validated synthetic ranking");
  });

  it("does not repeat a success flag when the displayed interval or workload contradicts it", () => {
    const inconsistent: ModelComparisonReport = structuredClone(report);
    inconsistent.comparison.intervals.average_precision_delta_95.lower = -0.01;
    expect(hasValidatedRankingGain(inconsistent)).toBe(false);
    const differentBudgets: ModelComparisonReport = structuredClone(report);
    differentBudgets.models.challenger.budgets["0.02"].alerts -= 1;
    expect(hasValidatedRankingGain(differentBudgets)).toBe(false);
  });
});
