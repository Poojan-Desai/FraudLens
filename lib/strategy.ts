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
  const curve = evaluation.models[model].selection_thresholds.map((point) => pricePoint(point, friction, review, recovery, capacity));
  return curve.reduce((best, point) => point.totalCost < best.totalCost || (Math.abs(point.totalCost - best.totalCost) < 1e-8 && point.threshold > best.threshold) ? point : best);
}
