export type StrategyPoint = {
  threshold: number;
  recall: number;
  precision: number;
  truePositives: number;
  falsePositives: number;
  falseNegatives: number;
  trueNegatives: number;
  totalCost: number;
  missedLoss: number;
  frictionCost: number;
  reviewCost: number;
  fraudDetected: number;
  fraudMissed: number;
  flagged: number;
};

export const TOTAL_TRANSACTIONS = 75_000;
export const FRAUD_TRANSACTIONS = 823;
export const LEGITIMATE_TRANSACTIONS = TOTAL_TRANSACTIONS - FRAUD_TRANSACTIONS;
export const TOTAL_FRAUD_DOLLARS = 77_707.43;
const AVG_FRAUD_AMOUNT = TOTAL_FRAUD_DOLLARS / FRAUD_TRANSACTIONS;

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function strategyAt(
  threshold: number,
  frictionPerDecline: number,
  reviewCostPerCase: number,
  recoveryRate: number,
  reviewCapacity: number,
): StrategyPoint {
  if (threshold < 0 || threshold > 1) throw new RangeError("threshold must be between 0 and 1");
  const recall = clamp(0.985 - Math.pow(threshold, 1.38) * 0.88, 0.08, 0.98);
  const falsePositiveRate = 0.076 * Math.pow(1 - threshold, 3.2) + 0.00005;
  const truePositives = Math.round(FRAUD_TRANSACTIONS * recall);
  const falseNegatives = FRAUD_TRANSACTIONS - truePositives;
  const falsePositives = Math.round(LEGITIMATE_TRANSACTIONS * falsePositiveRate);
  const trueNegatives = LEGITIMATE_TRANSACTIONS - falsePositives;
  const flagged = truePositives + falsePositives;
  const precision = truePositives / Math.max(1, flagged);
  const fraudDetected = truePositives * AVG_FRAUD_AMOUNT;
  const fraudMissed = falseNegatives * AVG_FRAUD_AMOUNT;
  const missedLoss = fraudMissed * (1 - recoveryRate / 100);
  const frictionCost = falsePositives * frictionPerDecline;
  const reviewed = Math.min(flagged, reviewCapacity);
  const reviewCost = reviewed * reviewCostPerCase;
  const capacityPenalty = Math.max(0, flagged - reviewCapacity) * 1.65;

  return {
    threshold,
    recall,
    precision,
    truePositives,
    falsePositives,
    falseNegatives,
    trueNegatives,
    totalCost: missedLoss + frictionCost + reviewCost + capacityPenalty,
    missedLoss,
    frictionCost,
    reviewCost,
    fraudDetected,
    fraudMissed,
    flagged,
  };
}

export function findOptimalStrategy(
  frictionPerDecline: number,
  reviewCostPerCase: number,
  recoveryRate: number,
  reviewCapacity: number,
) {
  const curve = Array.from({ length: 99 }, (_, index) =>
    strategyAt((index + 1) / 100, frictionPerDecline, reviewCostPerCase, recoveryRate, reviewCapacity),
  );
  return curve.reduce((best, point) => point.totalCost < best.totalCost ? point : best);
}
