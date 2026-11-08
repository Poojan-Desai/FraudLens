import evaluation from "../public/evaluation.json";

export { evaluation };
export type ModelKey = keyof typeof evaluation.models;
export const TOTAL_TRANSACTIONS = evaluation.windows.test.rows;
export const FRAUD_TRANSACTIONS = evaluation.windows.test.fraud_rows;
export const LEGITIMATE_TRANSACTIONS = TOTAL_TRANSACTIONS - FRAUD_TRANSACTIONS;
export const DEFAULT_MODEL: ModelKey = "xgboost";

export type StrategyPoint = {
  threshold: number; recall: number; precision: number;
  truePositives: number; falsePositives: number; falseNegatives: number; trueNegatives: number;
  totalCost: number; missedLoss: number; frictionCost: number; reviewCost: number;
  fraudDetected: number; fraudMissed: number; flagged: number;
};

export const POLICY_OBJECTIVES = ["cost", "f1", "f2"] as const;
export type PolicyObjective = (typeof POLICY_OBJECTIVES)[number];
export const POLICY_LABELS: Record<PolicyObjective, string> = {
  cost: "Cost-focused", f1: "Balanced F1", f2: "Recall-focused F2",
};

/** F-beta from counts; F2 weights recall four times as much as precision. */
export function fBeta(point: StrategyPoint, beta: number): number {
  if (!Number.isFinite(beta) || beta <= 0) throw new RangeError("beta must be positive and finite");
  // Divide by beta squared for beta >= 1 to avoid overflow for finite beta.
  const weight = beta >= 1 ? (1 / beta) ** 2 : beta * beta;
  const numerator = (1 + weight) * point.truePositives;
  const denominator = numerator + (beta >= 1 ? point.falseNegatives + weight * point.falsePositives : weight * point.falseNegatives + point.falsePositives);
  return denominator ? numerator / denominator : 0;
}

type StoredPoint = (typeof evaluation.models.xgboost.test_thresholds)[number];

function pricePoint(point: StoredPoint, friction: number, review: number, recovery: number, capacity: number): StrategyPoint {
  if (![friction, review, recovery, capacity].every(Number.isFinite) || friction < 0 || review < 0 || recovery < 0 || recovery > 100 || capacity < 0 || !Number.isInteger(capacity)) {
    throw new RangeError("Costs and capacity must be nonnegative; recovery must be 0–100 percent");
  }
  const missedLoss = point.fraud_missed * (1 - recovery / 100);
  const frictionCost = point.false_positives * friction;
  const reviewCost = Math.min(point.flagged, capacity) * review;
  const overflow = Math.max(0, point.flagged - capacity) * 1.65;
  return {
    threshold: point.threshold, recall: point.recall, precision: point.precision,
    truePositives: point.true_positives, falsePositives: point.false_positives,
    falseNegatives: point.false_negatives, trueNegatives: point.true_negatives,
    totalCost: Math.floor((missedLoss + frictionCost + reviewCost + overflow) * 100 + 0.5 + 1e-7) / 100,
    missedLoss, frictionCost, reviewCost, fraudDetected: point.fraud_detected,
    fraudMissed: point.fraud_missed, flagged: point.flagged,
  };
}

/** Explore actual test scores on the exported 0.01 grid; never choose policy here. */
export function strategyAt(threshold: number, friction: number, review: number, recovery: number, capacity: number, model: ModelKey = DEFAULT_MODEL): StrategyPoint {
  const index = Math.round(threshold * 100) - 1;
  if (!Number.isFinite(threshold) || index < 0 || index >= 99 || Math.abs((index + 1) / 100 - threshold) > 1e-9) {
    throw new RangeError("threshold must be on the evaluated 0.01–0.99 grid");
  }
  return pricePoint(evaluation.models[model].test_thresholds[index], friction, review, recovery, capacity);
}

/** Policy selection uses selection-window scores only, including changed costs. */
export function findOptimalStrategy(friction: number, review: number, recovery: number, capacity: number, model: ModelKey = DEFAULT_MODEL): StrategyPoint {
  return selectStrategyPolicy("cost", friction, review, recovery, capacity, model);
}

/** All presets select on selection aggregates, never on test performance.
 * F1/F2 maximize their score, irrespective of cost or capacity. Ties prefer
 * the higher threshold. The caller then reports test sensitivity separately.
 */
export function selectStrategyPolicy(objective: PolicyObjective, friction: number, review: number, recovery: number, capacity: number, model: ModelKey = DEFAULT_MODEL): StrategyPoint {
  if (!POLICY_OBJECTIVES.includes(objective)) throw new RangeError("unsupported policy objective");
  const curve = evaluation.models[model].selection_thresholds.map((point) => pricePoint(point, friction, review, recovery, capacity));
  const score = (point: StrategyPoint) => objective === "cost" ? -point.totalCost : fBeta(point, objective === "f1" ? 1 : 2);
  return curve.reduce((best, point) => score(point) > score(best) || (score(point) === score(best) && point.threshold > best.threshold) ? point : best);
}

/** An inspectable comparison, not a new model or an independent evaluation. */
export function compareStrategyPolicies(friction: number, review: number, recovery: number, capacity: number, model: ModelKey = DEFAULT_MODEL) {
  return POLICY_OBJECTIVES.map(objective => {
    const selection = selectStrategyPolicy(objective, friction, review, recovery, capacity, model);
    return { objective, label: POLICY_LABELS[objective], selection,
      test: strategyAt(selection.threshold, friction, review, recovery, capacity, model) };
  });
}
