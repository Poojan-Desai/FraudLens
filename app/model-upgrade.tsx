import modelComparison from "../public/model-comparison.json";

type BudgetResult = {
  alerts: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  precision: number;
  recall: number;
};

type ModelResult = {
  average_precision: number;
  budgets: Record<string, BudgetResult>;
  selection_cost_policy: {
    threshold: number;
    true_positives: number;
    total_cost: number;
  };
};

export type ModelComparisonReport = {
  plan_id: string;
  frozen_plan_sha256: string;
  primary_budget: number;
  fresh_evaluation: { rows: number; fraud_rows: number; description: string };
  models: { incumbent: ModelResult; challenger: ModelResult };
  model_specs: Record<"incumbent" | "challenger", {
    candidate: { max_depth: number; n_estimators: number; min_child_weight: number; reg_lambda: number };
    resolved_scale_pos_weight: number;
  }>;
  comparison: {
    promotion_gate_passed: boolean;
    average_precision_delta: number;
    average_precision_relative_change: number;
    primary_budget_recall_delta: number;
    intervals: {
      requested_replicates: number;
      average_precision_delta_95: { lower: number; upper: number };
      primary_budget_recall_delta_95: { lower: number; upper: number };
    };
  };
  limitations: string[];
};

const integer = new Intl.NumberFormat("en-US");
const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const percent = (value: number, digits = 1) => `${(value * 100).toFixed(digits)}%`;
const signed = (value: number, digits: number) => `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;

/** Keep a success claim conditional on the frozen gate and its displayed evidence. */
export function hasValidatedRankingGain(report: ModelComparisonReport): boolean {
  const old = report.models.incumbent;
  const next = report.models.challenger;
  const key = String(report.primary_budget);
  const oldBudget = old.budgets[key];
  const nextBudget = next.budgets[key];
  const lower = report.comparison.intervals.average_precision_delta_95.lower;
  return report.comparison.promotion_gate_passed &&
    Number.isFinite(lower) && lower > 0 &&
    next.average_precision > old.average_precision &&
    Boolean(oldBudget && nextBudget && oldBudget.alerts === nextBudget.alerts &&
      nextBudget.recall >= oldBudget.recall);
}

export default function ModelUpgrade({ report = modelComparison }: { report?: ModelComparisonReport }) {
  const old = report.models.incumbent;
  const next = report.models.challenger;
  const key = String(report.primary_budget);
  const primaryOld = old.budgets[key];
  const validated = hasValidatedRankingGain(report);
  const apInterval = report.comparison.intervals.average_precision_delta_95;
  const recallInterval = report.comparison.intervals.primary_budget_recall_delta_95;
  const costWorse = next.selection_cost_policy.total_cost > old.selection_cost_policy.total_cost;
  const budgets = Object.keys(old.budgets).sort((left, right) => Number(left) - Number(right));

  return <section className="model-upgrade" id="model-upgrade" aria-labelledby="model-upgrade-heading" data-comparison-status={validated ? "validated" : "inconclusive"}>
    <div className="upgrade-heading">
      <div>
        <span className="eyebrow">Frozen model comparison · fresh synthetic replication</span>
        <h1 id="model-upgrade-heading">Measure the model,<br />then the policy.</h1>
      </div>
      <span className={`upgrade-status ${validated ? "passed" : "inconclusive"}`}>
        {validated ? "Validated synthetic ranking" : "Inconclusive comparison"}
      </span>
    </div>
    <p className="upgrade-intro">Both frozen, calibrated XGBoost models scored the same {integer.format(report.fresh_evaluation.rows)} fresh synthetic transactions, including {integer.format(report.fresh_evaluation.fraud_rows)} labeled fraud cases. The challenger was chosen on separate development data. The generator, features and preprocessing are unchanged. This is a saved evaluation, with no live inference.</p>

    <div className="upgrade-metrics">
      <article>
        <span>Average precision · incumbent → challenger</span>
        <strong>{old.average_precision.toFixed(3)} → {next.average_precision.toFixed(3)}</strong>
        <p>{signed(report.comparison.average_precision_delta, 5)} AP ({signed(report.comparison.average_precision_relative_change * 100, 1)}% relative). AP measures ranking across precision and recall, not percentage correct.</p>
      </article>
      <article>
        <span>95% interval for the AP difference</span>
        <strong>{signed(apInterval.lower, 5)} to {signed(apInterval.upper, 5)}</strong>
        <p>{integer.format(report.comparison.intervals.requested_replicates)} paired row-bootstrap resamples, conditional on these fitted models. Training uncertainty is not included.</p>
      </article>
      <article>
        <span>Recall difference at the primary budget</span>
        <strong>{signed(report.comparison.primary_budget_recall_delta * 100, 2)} percentage points</strong>
        <p>95% interval: {signed(recallInterval.lower * 100, 2)} to {signed(recallInterval.upper * 100, 2)} percentage points.</p>
      </article>
    </div>

    <div className="upgrade-budget-heading">
      <h2>Same {percent(report.primary_budget, 0)} review budget. Both models get {integer.format(primaryOld.alerts)} alerts.</h2>
      <p>Rank the complete batch, then review exactly the highest-scored {integer.format(primaryOld.alerts)} transactions per model. This batch top-k procedure is not a live threshold policy. The legacy slider below does not change these results.</p>
    </div>
    <div className="upgrade-models">
      {(["incumbent", "challenger"] as const).map((name) => {
        const result = report.models[name].budgets[key];
        const spec = report.model_specs[name];
        return <article key={name} className={`upgrade-model ${name}`} data-model={name}>
          <span className="upgrade-model-label">{name === "incumbent" ? "Incumbent · original recipe" : "Challenger · frozen proposal"}</span>
          <strong className="upgrade-found">{`${integer.format(result.true_positives)} / ${integer.format(report.fresh_evaluation.fraud_rows)}`}</strong>
          <span className="upgrade-found-caption">labeled fraud cases found · {percent(result.recall)} recall</span>
          <div className="upgrade-recall-bar" aria-hidden="true"><span style={{ width: percent(result.recall, 3) }} /></div>
          <dl>
            <div><dt>Alerts</dt><dd>{integer.format(result.alerts)}</dd></div>
            <div><dt>False alerts</dt><dd>{integer.format(result.false_positives)}</dd></div>
            <div><dt>Precision</dt><dd>{percent(result.precision)}</dd></div>
            <div><dt>Fraud missed</dt><dd>{integer.format(result.false_negatives)}</dd></div>
          </dl>
          <p>Depth {spec.candidate.max_depth} · {spec.candidate.n_estimators} trees · class weight {spec.resolved_scale_pos_weight.toFixed(2)} · min child weight {spec.candidate.min_child_weight} · L2 {spec.candidate.reg_lambda}</p>
        </article>;
      })}
    </div>

    <aside className="upgrade-cost-caveat" aria-label="Separate cost-policy outcome">
      <h2>{costWorse ? "The selection-chosen cost policy regressed." : "The cost policy is a separate outcome."}</h2>
      <p>At each model’s selection-chosen threshold, the challenger has {currency.format(next.selection_cost_policy.total_cost)} modeled cost and finds {integer.format(next.selection_cost_policy.true_positives)} fraud cases (threshold {next.selection_cost_policy.threshold.toFixed(2)}); the incumbent has {currency.format(old.selection_cost_policy.total_cost)} modeled cost and finds {integer.format(old.selection_cost_policy.true_positives)} (threshold {old.selection_cost_policy.threshold.toFixed(2)}). These thresholds were not retuned after the final evaluation. Costs use illustrative assumptions and whole-window capacity. A ranking gain does not establish a better operating policy or realized savings.</p>
    </aside>

    <div className="upgrade-table-wrap" role="region" tabIndex={0} aria-label="All predeclared review budgets, scroll horizontally for all columns">
      <table>
        <caption>All predeclared review budgets on the same fresh replication · incumbent → challenger</caption>
        <thead><tr><th scope="col">Budget</th><th scope="col">Alerts per model</th><th scope="col">Fraud found</th><th scope="col">Recall</th><th scope="col">False alerts</th><th scope="col">Precision</th></tr></thead>
        <tbody>{budgets.map((budget) => {
          const previous = old.budgets[budget];
          const current = next.budgets[budget];
          return <tr key={budget} data-budget={budget} className={budget === key ? "primary-budget" : undefined}>
            <th scope="row">{percent(Number(budget), Number(budget) < .01 ? 1 : 0)}{budget === key ? " · primary" : ""}</th>
            <td>{previous.alerts === current.alerts ? integer.format(previous.alerts) : `${integer.format(previous.alerts)} → ${integer.format(current.alerts)}`}</td>
            <td>{integer.format(previous.true_positives)} → {integer.format(current.true_positives)}</td>
            <td>{percent(previous.recall)} → {percent(current.recall)}</td>
            <td>{integer.format(previous.false_positives)} → {integer.format(current.false_positives)}</td>
            <td>{percent(previous.precision)} → {percent(current.precision)}</td>
          </tr>;
        })}</tbody>
      </table>
    </div>
    <p className="upgrade-scope">This is an independent draw from the same known stationary synthetic mechanism; timestamps restart. It is not real-payment or future-time validation. The original 17-of-128 cost-focused result belongs to a separate, previously exposed study, retained below as a legacy sandbox.</p>
    <details className="upgrade-evidence">
      <summary>Inspect the frozen model-comparison evidence</summary>
      <p>Plan <code>{report.plan_id}</code>. Frozen-plan SHA-256: <code>{report.frozen_plan_sha256}</code>. <a href="/model-comparison.json" download>Download model comparison report</a>.</p>
      <p>The promotion gate requires a positive lower 95% AP-difference bound and a nonnegative primary-budget recall point difference. A failed gate is displayed as inconclusive.</p>
      <ul>{report.limitations.map((limit) => <li key={limit}>{limit}</li>)}</ul>
    </details>
  </section>;
}
