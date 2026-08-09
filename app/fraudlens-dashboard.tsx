"use client";

import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Bell,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  CircleDollarSign,
  FlaskConical,
  Gauge,
  LayoutDashboard,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  TableProperties,
  TrendingDown,
  UsersRound,
} from "lucide-react";

type StrategyPoint = {
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

const TOTAL_TRANSACTIONS = 75_000;
const FRAUD_TRANSACTIONS = 810;
const LEGITIMATE_TRANSACTIONS = TOTAL_TRANSACTIONS - FRAUD_TRANSACTIONS;
const TOTAL_FRAUD_DOLLARS = 297_270;
const AVG_FRAUD_AMOUNT = TOTAL_FRAUD_DOLLARS / FRAUD_TRANSACTIONS;

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
const compactMoney = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});
const integer = new Intl.NumberFormat("en-US");

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function strategyAt(
  threshold: number,
  frictionPerDecline: number,
  reviewCostPerCase: number,
  recoveryRate: number,
  reviewCapacity: number,
): StrategyPoint {
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
  const totalCost = missedLoss + frictionCost + reviewCost + capacityPenalty;

  return {
    threshold,
    recall,
    precision,
    truePositives,
    falsePositives,
    falseNegatives,
    trueNegatives,
    totalCost,
    missedLoss,
    frictionCost,
    reviewCost,
    fraudDetected,
    fraudMissed,
    flagged,
  };
}

function KpiCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = "green",
}: {
  label: string;
  value: string;
  detail: string;
  icon: typeof ShieldCheck;
  tone?: "green" | "amber" | "blue" | "violet";
}) {
  return (
    <article className="kpi-card">
      <div className={`kpi-icon ${tone}`}><Icon size={18} strokeWidth={2.2} /></div>
      <div className="kpi-copy">
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </article>
  );
}

function CostTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: StrategyPoint }> }) {
  if (!active || !payload?.[0]) return null;
  const item = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <span>Threshold {item.threshold.toFixed(2)}</span>
      <strong>{money.format(item.totalCost)}</strong>
      <small>{integer.format(item.falsePositives)} legitimate declines</small>
    </div>
  );
}

export default function FraudLensDashboard() {
  const [threshold, setThreshold] = useState(0.42);
  const [frictionCost, setFrictionCost] = useState(18);
  const [reviewCost, setReviewCost] = useState(1.2);
  const [recoveryRate, setRecoveryRate] = useState(35);
  const [reviewCapacity, setReviewCapacity] = useState(1_400);
  const [showAssumptions, setShowAssumptions] = useState(false);

  const strategyCurve = useMemo(
    () => Array.from({ length: 99 }, (_, index) => strategyAt((index + 1) / 100, frictionCost, reviewCost, recoveryRate, reviewCapacity)),
    [frictionCost, reviewCost, recoveryRate, reviewCapacity],
  );
  const current = useMemo(
    () => strategyAt(threshold, frictionCost, reviewCost, recoveryRate, reviewCapacity),
    [threshold, frictionCost, reviewCost, recoveryRate, reviewCapacity],
  );
  const optimum = useMemo(
    () => strategyCurve.reduce((best, point) => point.totalCost < best.totalCost ? point : best),
    [strategyCurve],
  );

  const selectedX = `${threshold * 100}%`;
  const optimumDelta = current.totalCost - optimum.totalCost;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><ShieldCheck size={20} /></div>
          <div><strong>FraudLens</strong><span>Strategy intelligence</span></div>
        </div>

        <nav aria-label="Primary navigation">
          <p>Workspace</p>
          <a className="active" href="#strategy"><LayoutDashboard size={18} />Strategy simulator</a>
          <a href="#transactions"><TableProperties size={18} />Transactions <span>Soon</span></a>
          <a href="#models"><BrainCircuit size={18} />Model comparison</a>
          <a href="#attacks"><FlaskConical size={18} />Attack pattern lab</a>
          <p>System</p>
          <a href="#data"><Activity size={18} />Data health</a>
          <a href="#settings"><Settings2 size={18} />Assumptions</a>
        </nav>

        <div className="sidebar-foot">
          <div className="dataset-chip"><span /><div><strong>Synthetic strategy set</strong><small>75,000 transactions</small></div></div>
          <div className="user-chip"><div className="avatar">PD</div><div><strong>Portfolio workspace</strong><small>Analyst view</small></div><ChevronDown size={15} /></div>
        </div>
      </aside>

      <main id="strategy" className="main-content">
        <header className="topbar">
          <div className="breadcrumbs"><span>FraudLens</span><ArrowRight size={13} /><strong>Strategy simulator</strong></div>
          <div className="topbar-actions">
            <button className="icon-button" aria-label="Search"><Search size={18} /></button>
            <button className="icon-button notification" aria-label="Notifications"><Bell size={18} /><i /></button>
            <div className="model-pill"><span>Live model</span><strong>XGBoost v1.4</strong><ChevronDown size={14} /></div>
          </div>
        </header>

        <div className="content-wrap">
          <section className="page-intro">
            <div>
              <div className="eyebrow"><span className="live-dot" />Strategy Command Center</div>
              <h1>Balance fraud loss<br />against customer trust.</h1>
              <p>Turn model scores into a defensible decision policy. Adjust the risk threshold and see the financial and customer impact instantly.</p>
            </div>
            <div className="intro-actions">
              <button className="secondary-button" onClick={() => setShowAssumptions((value) => !value)}><Settings2 size={17} />Cost assumptions</button>
              <button className="primary-button" onClick={() => setThreshold(optimum.threshold)}><Sparkles size={17} />Apply optimum <span>{optimum.threshold.toFixed(2)}</span></button>
            </div>
          </section>

          <section className="strategy-banner" aria-live="polite">
            <div className="strategy-banner-icon"><Gauge size={22} /></div>
            <div>
              <span>Current decision rule</span>
              <strong>Flag transactions at or above {(threshold * 100).toFixed(0)}% fraud probability</strong>
            </div>
            <div className="banner-divider" />
            <div className="banner-stat">
              <span>Cost gap to optimum</span>
              <strong className={optimumDelta < 500 ? "good" : "warn"}>{optimumDelta < 500 ? "Optimized" : `+${compactMoney.format(optimumDelta)}`}</strong>
            </div>
            <div className="banner-stat">
              <span>Review capacity</span>
              <strong>{integer.format(Math.min(current.flagged, reviewCapacity))} / {integer.format(reviewCapacity)}</strong>
            </div>
          </section>

          {showAssumptions && (
            <section className="assumptions-panel">
              <label><span>False-positive friction</span><div><b>$</b><input aria-label="False-positive friction cost" type="number" min="0" value={frictionCost} onChange={(event) => setFrictionCost(Number(event.target.value))} /></div></label>
              <label><span>Manual review cost</span><div><b>$</b><input aria-label="Manual review cost" type="number" min="0" step="0.1" value={reviewCost} onChange={(event) => setReviewCost(Number(event.target.value))} /></div></label>
              <label><span>Fraud recovery</span><div><input aria-label="Fraud recovery rate" type="number" min="0" max="100" value={recoveryRate} onChange={(event) => setRecoveryRate(Number(event.target.value))} /><b>%</b></div></label>
              <label><span>Daily review capacity</span><div><input aria-label="Daily review capacity" type="number" min="0" value={reviewCapacity} onChange={(event) => setReviewCapacity(Number(event.target.value))} /></div></label>
            </section>
          )}

          <section className="kpi-grid">
            <KpiCard label="Fraud dollars detected" value={compactMoney.format(current.fraudDetected)} detail={`${(current.recall * 100).toFixed(1)}% of fraud captured`} icon={ShieldCheck} />
            <KpiCard label="Fraud dollars missed" value={compactMoney.format(current.fraudMissed)} detail={`${integer.format(current.falseNegatives)} undetected cases`} icon={TrendingDown} tone="amber" />
            <KpiCard label="Legitimate declines" value={integer.format(current.falsePositives)} detail={`${(current.falsePositives / LEGITIMATE_TRANSACTIONS * 100).toFixed(2)}% of good customers`} icon={UsersRound} tone="blue" />
            <KpiCard label="Estimated strategy cost" value={compactMoney.format(current.totalCost)} detail={`${money.format(optimum.totalCost)} at optimum`} icon={CircleDollarSign} tone="violet" />
          </section>

          <section className="analytics-grid">
            <article className="panel threshold-panel">
              <div className="panel-heading">
                <div><span className="section-label">Decision control</span><h2>Risk threshold</h2></div>
                <div className="threshold-readout"><strong>{threshold.toFixed(2)}</strong><span>probability</span></div>
              </div>
              <div className="slider-wrap">
                <input
                  aria-label="Fraud decision threshold"
                  type="range"
                  min="0.01"
                  max="0.99"
                  step="0.01"
                  value={threshold}
                  onChange={(event) => setThreshold(Number(event.target.value))}
                  style={{ "--value": selectedX } as React.CSSProperties}
                />
                <div className="slider-labels"><span>Catch more fraud</span><span>Reduce friction</span></div>
              </div>
              <div className="tradeoff-row">
                <div><span>Precision</span><strong>{(current.precision * 100).toFixed(1)}%</strong><small><ArrowUpRight size={13} /> cleaner alerts</small></div>
                <div><span>Recall</span><strong>{(current.recall * 100).toFixed(1)}%</strong><small><ArrowDownRight size={13} /> fraud captured</small></div>
                <div><span>Flagged</span><strong>{integer.format(current.flagged)}</strong><small>{current.flagged > reviewCapacity ? `${integer.format(current.flagged - reviewCapacity)} over capacity` : "within capacity"}</small></div>
              </div>
            </article>

            <article className="panel matrix-panel">
              <div className="panel-heading"><div><span className="section-label">Decision quality</span><h2>Confusion matrix</h2></div><span className="test-badge">TEST SET</span></div>
              <div className="matrix">
                <span /> <span className="axis-label">Predicted fraud</span><span className="axis-label">Predicted legit</span>
                <span className="axis-label row">Actual fraud</span><div className="matrix-cell true"><strong>{integer.format(current.truePositives)}</strong><small>Detected</small></div><div className="matrix-cell false"><strong>{integer.format(current.falseNegatives)}</strong><small>Missed</small></div>
                <span className="axis-label row">Actual legit</span><div className="matrix-cell caution"><strong>{integer.format(current.falsePositives)}</strong><small>Declined</small></div><div className="matrix-cell neutral"><strong>{integer.format(current.trueNegatives)}</strong><small>Approved</small></div>
              </div>
            </article>
          </section>

          <section className="panel cost-panel">
            <div className="panel-heading cost-heading">
              <div><span className="section-label">Financial optimization</span><h2>Total strategy cost by threshold</h2><p>Missed fraud + customer friction + manual review costs</p></div>
              <div className="legend"><span><i className="legend-total" />Total cost</span><span><i className="legend-missed" />Missed fraud loss</span><span><i className="legend-friction" />Customer friction</span></div>
            </div>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={strategyCurve} margin={{ top: 12, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="costFill" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#12a46f" stopOpacity={0.18}/><stop offset="95%" stopColor="#12a46f" stopOpacity={0}/></linearGradient>
                  </defs>
                  <CartesianGrid stroke="#e7ebe8" strokeDasharray="4 4" vertical={false} />
                  <XAxis dataKey="threshold" tickFormatter={(value) => Number(value).toFixed(1)} tick={{ fill: "#7d8882", fontSize: 11 }} axisLine={false} tickLine={false} interval={9} />
                  <YAxis tickFormatter={(value) => `$${Math.round(value / 1000)}k`} tick={{ fill: "#7d8882", fontSize: 11 }} axisLine={false} tickLine={false} width={46} />
                  <Tooltip content={<CostTooltip />} />
                  <Area type="monotone" dataKey="totalCost" stroke="#0d9667" strokeWidth={2.5} fill="url(#costFill)" />
                  <Line type="monotone" dataKey="missedLoss" stroke="#d9961a" strokeWidth={1.8} dot={false} />
                  <Line type="monotone" dataKey="frictionCost" stroke="#7484e8" strokeWidth={1.8} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
              <div className="selected-marker" style={{ left: selectedX }}><span>Selected</span><i /></div>
              <div className="optimal-marker" style={{ left: `${optimum.threshold * 100}%` }}><CheckCircle2 size={14} /><span>Cost minimum<br /><b>{optimum.threshold.toFixed(2)}</b></span></div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
