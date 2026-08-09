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
  ChevronRight,
  CircleDollarSign,
  Clock3,
  CreditCard,
  Database,
  Eye,
  FlaskConical,
  Gauge,
  Globe2,
  Layers3,
  LayoutDashboard,
  LockKeyhole,
  MapPin,
  Play,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  ShieldAlert,
  Sparkles,
  TableProperties,
  TrendingDown,
  UsersRound,
  X,
  Zap,
} from "lucide-react";
import {
  LEGITIMATE_TRANSACTIONS,
  strategyAt,
  TOTAL_TRANSACTIONS,
  type StrategyPoint,
} from "../lib/strategy";

type Transaction = {
  id: string;
  timestamp: string;
  merchant: string;
  category: string;
  country: string;
  amount: number;
  probability: number;
  actualFraud: boolean;
  device: string;
  cardPresent: boolean;
  factors: Array<{ label: string; contribution: number; value: string }>;
};

type AttackScenario = {
  id: string;
  name: string;
  description: string;
  probability: number;
  amount: number;
  icon: typeof ShieldAlert;
  signal: string;
};

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

const TRANSACTIONS: Transaction[] = [
  { id: "FL-290874", timestamp: "Today, 10:42:18", merchant: "Nova Electronics", category: "Electronics", country: "Romania", amount: 1849.2, probability: 0.93, actualFraud: true, device: "New device", cardPresent: false, factors: [
    { label: "New device", contribution: 0.18, value: "First seen 3 minutes ago" },
    { label: "Amount vs. customer average", contribution: 0.16, value: "4.3× usual purchase" },
    { label: "Transaction velocity", contribution: 0.13, value: "6 purchases in the last hour" },
    { label: "International purchase", contribution: 0.11, value: "First purchase in Romania" },
    { label: "Card not present", contribution: 0.07, value: "Online checkout" },
    { label: "Account age", contribution: -0.04, value: "Card active for 6.2 years" },
  ] },
  { id: "FL-290873", timestamp: "Today, 10:41:52", merchant: "Metro Fuel #184", category: "Fuel", country: "United States", amount: 4.99, probability: 0.88, actualFraud: true, device: "Known device", cardPresent: false, factors: [
    { label: "Card-testing sequence", contribution: 0.24, value: "8 small attempts in 11 minutes" },
    { label: "Previous declines", contribution: 0.18, value: "5 recent declines" },
    { label: "Merchant velocity", contribution: 0.12, value: "Repeated authorization attempts" },
    { label: "Low amount", contribution: -0.05, value: "$4.99 transaction" },
  ] },
  { id: "FL-290867", timestamp: "Today, 10:37:09", merchant: "CloudStay Hotels", category: "Travel", country: "Spain", amount: 672.4, probability: 0.76, actualFraud: true, device: "New device", cardPresent: false, factors: [
    { label: "Impossible travel", contribution: 0.23, value: "4,012 miles in 38 minutes" },
    { label: "New country", contribution: 0.15, value: "No prior spend in Spain" },
    { label: "New device", contribution: 0.12, value: "Unrecognized browser" },
    { label: "Established travel spend", contribution: -0.07, value: "Travel used 6 times before" },
  ] },
  { id: "FL-290854", timestamp: "Today, 10:28:43", merchant: "Green Basket", category: "Grocery", country: "United States", amount: 86.31, probability: 0.38, actualFraud: false, device: "Known device", cardPresent: true, factors: [
    { label: "Spending above average", contribution: 0.08, value: "1.6× usual purchase" },
    { label: "Known device", contribution: -0.09, value: "Used for 14 months" },
    { label: "Card physically present", contribution: -0.08, value: "Chip transaction" },
    { label: "Established merchant", contribution: -0.06, value: "19 prior visits" },
  ] },
  { id: "FL-290841", timestamp: "Today, 10:19:06", merchant: "Eastline Pharmacy", category: "Healthcare", country: "United States", amount: 34.72, probability: 0.17, actualFraud: false, device: "Known device", cardPresent: true, factors: [
    { label: "Card physically present", contribution: -0.11, value: "Chip transaction" },
    { label: "Near home", contribution: -0.09, value: "1.7 miles from home" },
    { label: "Normal purchase amount", contribution: -0.06, value: "0.8× usual purchase" },
  ] },
  { id: "FL-290829", timestamp: "Today, 10:11:27", merchant: "LuxTime Market", category: "Luxury goods", country: "Singapore", amount: 2890, probability: 0.84, actualFraud: true, device: "New device", cardPresent: false, factors: [
    { label: "Dormant card", contribution: 0.21, value: "No activity for 143 days" },
    { label: "High-value purchase", contribution: 0.18, value: "8.9× usual purchase" },
    { label: "New country", contribution: 0.14, value: "First purchase in Singapore" },
    { label: "New device", contribution: 0.11, value: "First-seen mobile device" },
  ] },
  { id: "FL-290812", timestamp: "Today, 09:58:41", merchant: "Rail & Roast", category: "Dining", country: "United States", amount: 18.26, probability: 0.08, actualFraud: false, device: "Known device", cardPresent: true, factors: [
    { label: "Established merchant", contribution: -0.12, value: "31 prior visits" },
    { label: "Normal time of day", contribution: -0.06, value: "Matches weekday pattern" },
    { label: "Card physically present", contribution: -0.06, value: "Contactless payment" },
  ] },
  { id: "FL-290798", timestamp: "Today, 09:44:15", merchant: "Streamline Media", category: "Digital services", country: "United States", amount: 15.99, probability: 0.03, actualFraud: false, device: "Known device", cardPresent: false, factors: [
    { label: "Recurring payment", contribution: -0.16, value: "Billed monthly for 22 months" },
    { label: "Normal purchase amount", contribution: -0.08, value: "Matches prior charges" },
    { label: "Known device", contribution: -0.04, value: "Trusted account token" },
  ] },
];

const MODELS = [
  { name: "XGBoost", version: "v1.0", precision: 0.517, recall: 0.242, f1: 0.330, prAuc: 0.249, cost: 5746, latency: "1.7 ms", training: "0.42 s", best: true },
  { name: "Logistic Regression", version: "v1.0", precision: 0.500, recall: 0.148, f1: 0.229, prAuc: 0.231, cost: 5805, latency: "0.8 ms", training: "0.52 s", best: false },
];

const PR_CURVE = [
  { recall: 0.05, xgboost: 0.600, logistic: 0.667 }, { recall: 0.15, xgboost: 0.633, logistic: 0.500 },
  { recall: 0.30, xgboost: 0.345, logistic: 0.292 }, { recall: 0.45, xgboost: 0.143, logistic: 0.177 },
  { recall: 0.60, xgboost: 0.076, logistic: 0.082 }, { recall: 0.75, xgboost: 0.055, logistic: 0.057 },
  { recall: 0.85, xgboost: 0.022, logistic: 0.026 }, { recall: 0.93, xgboost: 0.014, logistic: 0.019 },
  { recall: 0.98, xgboost: 0.012, logistic: 0.012 },
];

const ATTACKS: AttackScenario[] = [
  { id: "card-testing", name: "Card testing", description: "Eight tiny authorizations across two merchants within 11 minutes.", probability: 0.88, amount: 4.99, icon: CreditCard, signal: "Velocity + repeated declines" },
  { id: "velocity", name: "Velocity burst", description: "A sudden burst of high-frequency purchases after normal activity.", probability: 0.79, amount: 428.6, icon: Zap, signal: "12 transactions in one hour" },
  { id: "takeover", name: "Account takeover", description: "New device, new country, and a purchase far above customer average.", probability: 0.94, amount: 1849.2, icon: LockKeyhole, signal: "Device + location + amount" },
  { id: "travel", name: "Impossible travel", description: "Purchases occur thousands of miles apart within the same hour.", probability: 0.76, amount: 672.4, icon: Globe2, signal: "4,012 miles in 38 minutes" },
  { id: "dormant", name: "Dormant-card attack", description: "A previously inactive card suddenly makes a luxury purchase.", probability: 0.84, amount: 2890, icon: Clock3, signal: "143 inactive days" },
  { id: "merchant", name: "Merchant anomaly", description: "Spend appears in a category with no customer history.", probability: 0.57, amount: 511.8, icon: MapPin, signal: "First use of merchant category" },
];

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
  const [transactionSearch, setTransactionSearch] = useState("");
  const [transactionFilter, setTransactionFilter] = useState<"all" | "flagged" | "approved">("all");
  const [selectedTransaction, setSelectedTransaction] = useState<Transaction | null>(null);
  const [attackRuns, setAttackRuns] = useState<Record<string, { detected: boolean; at: string }>>({});
  const [runningAttack, setRunningAttack] = useState<string | null>(null);

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
  const filteredTransactions = TRANSACTIONS.filter((transaction) => {
    const matchesSearch = `${transaction.id} ${transaction.merchant} ${transaction.country} ${transaction.category}`.toLowerCase().includes(transactionSearch.toLowerCase());
    const isFlagged = transaction.probability >= threshold;
    return matchesSearch && (transactionFilter === "all" || (transactionFilter === "flagged" ? isFlagged : !isFlagged));
  });

  function runAttack(attack: AttackScenario) {
    setRunningAttack(attack.id);
    window.setTimeout(() => {
      setAttackRuns((runs) => ({ ...runs, [attack.id]: { detected: attack.probability >= threshold, at: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) } }));
      setRunningAttack(null);
    }, 650);
  }

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
          <a href="#transactions"><TableProperties size={18} />Transactions</a>
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
              <div className="model-pill"><span>Live model</span><strong>XGBoost v1.0</strong><ChevronDown size={14} /></div>
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

          <section id="transactions" className="product-section">
            <div className="section-heading-row">
              <div><span className="section-kicker">Investigate</span><h2>Transaction explorer</h2><p>Inspect model decisions and translate technical signals into business-readable evidence.</p></div>
              <div className="section-stat"><span>Flagged at {threshold.toFixed(2)}</span><strong>{integer.format(current.flagged)}</strong><small>of {integer.format(TOTAL_TRANSACTIONS)} test transactions</small></div>
            </div>
            <article className="panel explorer-panel">
              <div className="table-toolbar">
                <label className="table-search"><Search size={15} /><input aria-label="Search transactions" placeholder="Search transaction, merchant, country…" value={transactionSearch} onChange={(event) => setTransactionSearch(event.target.value)} /></label>
                <div className="segmented-control" role="group" aria-label="Transaction decision filter">
                  {(["all", "flagged", "approved"] as const).map((filter) => <button key={filter} className={transactionFilter === filter ? "active" : ""} onClick={() => setTransactionFilter(filter)}>{filter[0].toUpperCase() + filter.slice(1)}</button>)}
                </div>
                <span className="result-count">{filteredTransactions.length} shown</span>
              </div>
              <div className="transaction-table-wrap">
                <table className="transaction-table">
                  <thead><tr><th>Transaction</th><th>Merchant</th><th>Amount</th><th>Risk score</th><th>Decision</th><th>Actual</th><th><span className="sr-only">Open explanation</span></th></tr></thead>
                  <tbody>
                    {filteredTransactions.map((transaction) => {
                      const flagged = transaction.probability >= threshold;
                      return <tr key={transaction.id} onClick={() => setSelectedTransaction(transaction)}>
                        <td><strong>{transaction.id}</strong><small>{transaction.timestamp}</small></td>
                        <td><strong>{transaction.merchant}</strong><small>{transaction.category} · {transaction.country}</small></td>
                        <td className="amount-cell">{money.format(transaction.amount)}</td>
                        <td><div className="risk-cell"><span><i style={{ width: `${transaction.probability * 100}%` }} /></span><b className={transaction.probability >= .7 ? "high" : transaction.probability >= .35 ? "medium" : "low"}>{(transaction.probability * 100).toFixed(0)}%</b></div></td>
                        <td><span className={`decision-badge ${flagged ? "flagged" : "approved"}`}>{flagged ? "Flagged" : "Approved"}</span></td>
                        <td><span className={`actual-badge ${transaction.actualFraud ? "fraud" : "legit"}`}>{transaction.actualFraud ? "Fraud" : "Legitimate"}</span></td>
                        <td><button aria-label={`Explain ${transaction.id}`}><ChevronRight size={16} /></button></td>
                      </tr>;
                    })}
                  </tbody>
                </table>
              </div>
            </article>
          </section>

          <section id="models" className="product-section">
            <div className="section-heading-row">
              <div><span className="section-kicker">Validate</span><h2>Model comparison</h2><p>Same time-based holdout set. Probabilities calibrated on a separate validation window.</p></div>
              <div className="validation-chip"><CheckCircle2 size={15} /><div><strong>No temporal leakage</strong><small>Train → validation → test</small></div></div>
            </div>
            <div className="model-grid">
              <article className="panel model-table-panel">
                <div className="mini-heading"><div><span className="section-label">Performance</span><h3>Holdout metrics</h3></div><span className="date-window">May 14–Jun 06, 2025</span></div>
                <div className="model-table-wrap">
                  <table className="model-table">
                    <thead><tr><th>Model</th><th>Precision</th><th>Recall</th><th>F1</th><th>PR-AUC</th><th>Strategy cost</th><th>Latency</th></tr></thead>
                    <tbody>{MODELS.map((model) => <tr key={model.name} className={model.best ? "best" : ""}>
                      <td><div className="model-name"><span className={model.best ? "champion" : ""}>{model.name === "XGBoost" ? <Sparkles size={14} /> : <BrainCircuit size={14} />}</span><div><strong>{model.name}</strong><small>{model.version}{model.best ? " · Champion" : ""}</small></div></div></td>
                      <td>{(model.precision * 100).toFixed(1)}%</td><td>{(model.recall * 100).toFixed(1)}%</td><td>{(model.f1 * 100).toFixed(1)}%</td><td><strong>{model.prAuc.toFixed(3)}</strong></td><td>{money.format(model.cost)}</td><td>{model.latency}</td>
                    </tr>)}</tbody>
                  </table>
                </div>
                <div className="model-note"><ShieldCheck size={15} /><span>On the untouched test window, XGBoost captures more fraud at a slightly lower expected cost: <strong>{money.format(MODELS[1].cost - MODELS[0].cost)} saved</strong> versus the transparent baseline.</span></div>
              </article>
              <article className="panel pr-panel">
                <div className="mini-heading"><div><span className="section-label">Imbalanced evaluation</span><h3>Precision–recall curve</h3></div><span className="pr-score">AP <b>0.249</b></span></div>
                <div className="pr-chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={PR_CURVE} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                      <defs><linearGradient id="prFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#129668" stopOpacity={.18}/><stop offset="100%" stopColor="#129668" stopOpacity={0}/></linearGradient></defs>
                      <CartesianGrid stroke="#e9edea" strokeDasharray="4 4" />
                      <XAxis dataKey="recall" domain={[0, 1]} tickFormatter={(value) => `${Math.round(Number(value) * 100)}%`} tick={{ fill: "#849089", fontSize: 9 }} axisLine={false} tickLine={false} />
                      <YAxis domain={[0, 1]} tickFormatter={(value) => `${Math.round(Number(value) * 100)}%`} tick={{ fill: "#849089", fontSize: 9 }} axisLine={false} tickLine={false} />
                      <Area type="monotone" dataKey="xgboost" name="XGBoost" stroke="#119668" fill="url(#prFill)" strokeWidth={2.3} />
                      <Line type="monotone" dataKey="logistic" name="Logistic Regression" stroke="#87949f" strokeDasharray="5 4" strokeWidth={1.6} dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                <div className="pr-legend"><span><i />XGBoost</span><span><i />Logistic Regression</span><small>Recall →</small></div>
              </article>
            </div>
          </section>

          <section id="attacks" className="product-section attack-section">
            <div className="section-heading-row">
              <div><span className="section-kicker">Stress test</span><h2>Attack pattern lab</h2><p>Inject explainable fraud scenarios and test whether the current strategy catches them.</p></div>
              <div className="threshold-context"><Gauge size={15} /><span>Testing at <strong>{threshold.toFixed(2)}</strong> threshold</span></div>
            </div>
            <div className="attack-grid">
              {ATTACKS.map((attack) => {
                const Icon = attack.icon;
                const run = attackRuns[attack.id];
                const isRunning = runningAttack === attack.id;
                return <article key={attack.id} className={`attack-card ${run ? (run.detected ? "detected" : "missed") : ""}`}>
                  <div className="attack-top"><div className="attack-icon"><Icon size={18} /></div>{run && <span className={`run-result ${run.detected ? "detected" : "missed"}`}>{run.detected ? <><CheckCircle2 size={12} />Detected</> : <><ShieldAlert size={12} />Missed</>}</span>}</div>
                  <h3>{attack.name}</h3><p>{attack.description}</p>
                  <div className="signal-row"><Activity size={13} /><span>{attack.signal}</span></div>
                  <div className="attack-score"><span>Simulated risk</span><strong>{(attack.probability * 100).toFixed(0)}%</strong></div>
                  <button onClick={() => runAttack(attack)} disabled={isRunning}>{isRunning ? <><RefreshCw className="spin" size={14} />Running…</> : run ? <><RefreshCw size={14} />Run again</> : <><Play size={14} fill="currentColor" />Inject attack</>}</button>
                </article>;
              })}
            </div>
          </section>

          <section id="data" className="data-provenance">
            <div className="provenance-icon"><Database size={22} /></div>
            <div><span>Dual-dataset design</span><strong>Real benchmark for validity. Synthetic strategy set for explainability.</strong><p>284,807 anonymized European card transactions validate the model; 75,000 clearly labeled simulated transactions power readable features and attack scenarios.</p></div>
            <div className="provenance-metrics"><div><strong>0.172%</strong><span>real-set fraud rate</span></div><div><strong>1.10%</strong><span>strategy-set fraud rate</span></div><div><strong>12</strong><span>readable features</span></div></div>
          </section>

          <footer><div className="brand footer-brand"><div className="brand-mark"><ShieldCheck size={18} /></div><div><strong>FraudLens</strong><span>Explainable fraud strategy intelligence</span></div></div><p>Simulated strategy data is clearly labeled. Model metrics shown on a fixed time-based holdout set.</p><a href="#strategy">Back to simulator <ArrowUpRight size={13} /></a></footer>
        </div>
      </main>

      {selectedTransaction && (
        <div className="drawer-backdrop" onClick={() => setSelectedTransaction(null)}>
          <aside className="explanation-drawer" aria-label="Transaction explanation" onClick={(event) => event.stopPropagation()}>
            <div className="drawer-header"><div><span>Decision explanation</span><strong>{selectedTransaction.id}</strong></div><button aria-label="Close explanation" onClick={() => setSelectedTransaction(null)}><X size={19} /></button></div>
            <div className="risk-hero"><div className={`risk-ring ${selectedTransaction.probability >= .7 ? "high" : selectedTransaction.probability >= .35 ? "medium" : "low"}`}><strong>{(selectedTransaction.probability * 100).toFixed(0)}%</strong><span>fraud risk</span></div><div><span className={`decision-badge ${selectedTransaction.probability >= threshold ? "flagged" : "approved"}`}>{selectedTransaction.probability >= threshold ? "Flagged for review" : "Approved"}</span><h2>{money.format(selectedTransaction.amount)}</h2><p>{selectedTransaction.merchant}<br />{selectedTransaction.country} · {selectedTransaction.timestamp}</p></div></div>
            <div className="drawer-callout"><Eye size={16} /><p><strong>Why this score?</strong>The model combined {selectedTransaction.factors.length} strongest signals. Contributions show how each feature moved risk from the calibrated baseline.</p></div>
            <div className="factor-section"><div className="factor-heading"><span>Risk factors</span><small>SHAP contribution</small></div>{selectedTransaction.factors.map((factor) => <div key={factor.label} className="factor-row"><div className={`factor-direction ${factor.contribution > 0 ? "up" : "down"}`}>{factor.contribution > 0 ? <ArrowUpRight size={15} /> : <ArrowDownRight size={15} />}</div><div className="factor-copy"><strong>{factor.label}</strong><small>{factor.value}</small></div><div className={`factor-value ${factor.contribution > 0 ? "up" : "down"}`}>{factor.contribution > 0 ? "+" : ""}{Math.round(factor.contribution * 100)} pts</div></div>)}</div>
            <div className="transaction-context"><span>Transaction context</span><div><small>Device</small><strong>{selectedTransaction.device}</strong></div><div><small>Channel</small><strong>{selectedTransaction.cardPresent ? "Card present" : "Card not present"}</strong></div><div><small>Category</small><strong>{selectedTransaction.category}</strong></div><div><small>Known outcome</small><strong>{selectedTransaction.actualFraud ? "Confirmed fraud" : "Legitimate"}</strong></div></div>
            <p className="explanation-footnote"><Layers3 size={13} /> SHAP values explain this model prediction; they do not establish causation.</p>
          </aside>
        </div>
      )}
    </div>
  );
}
