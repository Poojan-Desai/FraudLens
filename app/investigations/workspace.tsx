"use client";

import { FormEvent, useRef, useState } from "react";
import Link from "next/link";

type Status = "pending" | "reviewed" | "confirmed_fraud" | "legitimate";
type Identity = { actor: string; role: "viewer" | "analyst" | "admin" };
type Case = {
  id: string;
  transaction_id: string;
  status: Status;
  version: number;
  updated_at: string;
  audit_integrity: string;
  training_label_eligible: false;
  snapshot: {
    timestamp: string;
    amount: number;
    country: string;
    merchant_category: string;
    fraud_probability: number;
    threshold: number;
    model_version: string;
    source: string;
    features: Record<string, string | boolean | number>;
    reason_codes: string[];
  };
  history?: {
    version: number;
    actor: string;
    action: string;
    status: string;
    timestamp: string;
    note: string;
    event_hash: string;
  }[];
};
const statuses: Status[] = [
  "pending",
  "reviewed",
  "confirmed_fraud",
  "legitimate",
];
const label = (value: string) => value.replaceAll("_", " ");
const dollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export default function InvestigationWorkspace() {
  const [token, setToken] = useState("");
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [items, setItems] = useState<Case[]>([]);
  const [selected, setSelected] = useState<Case | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const base = "http://127.0.0.1:8000/api/v1/cases";

  async function request(path: string, method = "GET", body?: unknown) {
    const response = await fetch(`${base}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
      credentials: "omit",
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(
        typeof payload.detail === "string"
          ? payload.detail
          : `Request rejected (${response.status}). Check the supplied fields.`,
      );
    }
    return response.json();
  }

  async function loadQueue(nextOffset = offset) {
    const data = await request(
      `?${new URLSearchParams({ search, ...(filter ? { status: filter } : {}), limit: "20", offset: String(nextOffset) })}`,
    );
    return {
      items: data.items as Case[],
      hasMore: data.has_more as boolean,
      offset: nextOffset,
    };
  }

  async function perform(work: (current: number) => Promise<void>) {
    const current = generation.current;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await work(current);
    } catch (failure) {
      if (generation.current === current)
        setError(
          failure instanceof Error
            ? failure.message
            : "Local API unavailable. Start the documented demo backend and retry.",
        );
    } finally {
      if (generation.current === current) setBusy(false);
    }
  }

  function showQueue(data: {
    items: Case[];
    hasMore: boolean;
    offset: number;
  }) {
    setItems(data.items);
    setHasMore(data.hasMore);
    setOffset(data.offset);
  }

  async function connect(event: FormEvent) {
    event.preventDefault();
    await perform(async (current) => {
      const user = await request("/identity");
      const queue = await loadQueue(0);
      if (generation.current === current) {
        setIdentity(user);
        showQueue(queue);
      }
    });
  }

  function disconnect() {
    generation.current += 1;
    setIdentity(null);
    setToken("");
    setSelected(null);
    setItems([]);
    setNote("");
    setBusy(false);
    setError("");
    setMessage("");
  }

  async function openCase(item: Case) {
    await perform(async (current) => {
      const detail = await request(`/${item.id}`);
      if (generation.current === current) {
        setSelected(detail);
        if (selected?.id !== item.id) setNote("");
      }
    });
  }

  async function act(status?: Status) {
    if (!selected) return;
    await perform(async (current) => {
      const detail = await request(`/${selected.id}/actions`, "POST", {
        expected_version: selected.version,
        action: status ? "transition" : "note",
        ...(status ? { status } : {}),
        note,
      });
      if (generation.current === current) {
        setSelected(detail);
        setNote("");
        setMessage(`Saved version ${detail.version}; action history verified.`);
      }
      const queue = await loadQueue();
      if (generation.current === current) showQueue(queue);
    });
  }

  async function exportCase() {
    if (!selected) return;
    await perform(async (current) => {
      const data = await request(`/${selected.id}/export`);
      if (generation.current !== current) return;
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = `fraudlens-case-${selected.id}.json`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setMessage(
        "Sanitized report downloaded; investigator identities and note text omitted.",
      );
    });
  }

  const writable = identity?.role !== "viewer";
  const transitions: Status[] = !selected
    ? []
    : selected.status === "pending"
      ? ["reviewed"]
      : selected.status === "reviewed"
        ? ["pending", "confirmed_fraud", "legitimate"]
        : identity?.role === "admin"
          ? ["reviewed"]
          : [];

  return (
    <main className="investigation-shell">
      <header className="investigation-top">
        <Link href="/">← Strategy evidence</Link>
        <span>FraudLens / Local investigations</span>
      </header>
      <div className="investigation-title">
        <div>
          <span className="section-label">Evidence & decisions</span>
          <h1>Investigation workspace</h1>
          <p>
            Investigate saved synthetic scores with versioned decisions and a
            verified action history.
          </p>
        </div>
        {identity && (
          <button className="secondary-button" onClick={disconnect}>
            Disconnect {identity.actor}
          </button>
        )}
      </div>
      <p className="investigation-disclosure">
        Local demonstration. No bank data or live model service. Investigator
        outcomes remain separate from ground-truth labels and are excluded from
        training. Displayed reasons describe observed features; they are not
        SHAP or causal explanations.
      </p>
      {!identity ? (
        <section className="panel investigation-connect">
          <h2>Connect to your local case store</h2>
          <p>
            Run the README investigation demo, then paste its analyst token. The
            token stays in this page’s memory and is cleared on disconnect or
            reload.
          </p>
          <form onSubmit={connect}>
            <label>
              Local analyst, viewer or administrator token
              <input
                aria-label="Case access token"
                type="password"
                autoComplete="off"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                required
                minLength={32}
                maxLength={200}
              />
            </label>
            <button className="primary-button" disabled={busy}>
              {busy ? "Connecting…" : "Connect case store"}
            </button>
          </form>
          <small>
            API: http://127.0.0.1:8000. Credentials are never included in the
            static site.
          </small>
        </section>
      ) : (
        <>
          <section className="panel investigation-search">
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void perform(async (current) => {
                  const queue = await loadQueue(0);
                  if (generation.current === current) showQueue(queue);
                });
              }}
            >
              <label>
                Transaction ID
                <input
                  aria-label="Search case transaction ID"
                  value={search}
                  maxLength={80}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="EVAL-…"
                />
              </label>
              <label>
                Status
                <select
                  aria-label="Filter case status"
                  value={filter}
                  onChange={(event) => setFilter(event.target.value)}
                >
                  <option value="">All statuses</option>
                  {statuses.map((status) => (
                    <option key={status} value={status}>
                      {label(status)}
                    </option>
                  ))}
                </select>
              </label>
              <button className="secondary-button" disabled={busy}>
                Search cases
              </button>
            </form>
            <small>
              Signed in as {identity.actor} · {identity.role}. {items.length}{" "}
              cases on this page.
            </small>
          </section>
          <div className="investigation-grid">
            <section
              className="panel investigation-queue"
              aria-label="Case queue"
            >
              <h2>Case queue</h2>
              {!items.length && (
                <p>
                  No matching cases. Import the verified study or broaden your
                  filters.
                </p>
              )}
              <ul>
                {items.map((item) => (
                  <li key={item.id}>
                    <button
                      disabled={busy}
                      aria-pressed={selected?.id === item.id}
                      onClick={() => void openCase(item)}
                    >
                      <strong>{item.transaction_id}</strong>
                      <span>
                        {label(item.status)} · v{item.version}
                      </span>
                      <small>
                        {dollars.format(item.snapshot.amount)} ·{" "}
                        {(item.snapshot.fraud_probability * 100).toFixed(1)}%
                        risk
                      </small>
                    </button>
                  </li>
                ))}
              </ul>
              <div className="investigation-paging">
                <button
                  className="secondary-button"
                  disabled={busy || offset === 0}
                  onClick={() =>
                    void perform(async (current) => {
                      const queue = await loadQueue(Math.max(0, offset - 20));
                      if (generation.current === current) showQueue(queue);
                    })
                  }
                >
                  Previous
                </button>
                <button
                  className="secondary-button"
                  disabled={busy || !hasMore}
                  onClick={() =>
                    void perform(async (current) => {
                      const queue = await loadQueue(offset + 20);
                      if (generation.current === current) showQueue(queue);
                    })
                  }
                >
                  Next
                </button>
              </div>
            </section>
            <section
              className="panel investigation-detail"
              aria-label="Case detail"
            >
              {!selected ? (
                <>
                  <h2>Select a flagged transaction</h2>
                  <p>
                    Review its preserved score, policy threshold and features
                    before recording a decision.
                  </p>
                </>
              ) : (
                <>
                  <div className="panel-heading">
                    <div>
                      <span className="section-label">
                        {label(selected.status)} · version {selected.version}
                      </span>
                      <h2>{selected.transaction_id}</h2>
                    </div>
                    <button
                      className="secondary-button"
                      disabled={busy}
                      onClick={() => void openCase(selected)}
                    >
                      Reload case
                    </button>
                  </div>
                  <dl className="case-facts">
                    <div>
                      <dt>Risk score</dt>
                      <dd>
                        {(selected.snapshot.fraud_probability * 100).toFixed(2)}
                        %
                      </dd>
                    </div>
                    <div>
                      <dt>Flag threshold</dt>
                      <dd>{selected.snapshot.threshold.toFixed(2)}</dd>
                    </div>
                    <div>
                      <dt>Amount</dt>
                      <dd>{dollars.format(selected.snapshot.amount)}</dd>
                    </div>
                    <div>
                      <dt>Audit history</dt>
                      <dd>{selected.audit_integrity}</dd>
                    </div>
                  </dl>
                  <p>
                    {selected.snapshot.country} ·{" "}
                    {label(selected.snapshot.merchant_category)} ·{" "}
                    {new Date(selected.snapshot.timestamp).toLocaleString()}
                  </p>
                  <small className="case-model">
                    Model {selected.snapshot.model_version} ·{" "}
                    {label(selected.snapshot.source)}
                  </small>
                  <h3>Observed signals</h3>
                  <ul>
                    {selected.snapshot.reason_codes.map((reason, index) => (
                      <li key={index}>{reason}</li>
                    ))}
                  </ul>
                  <details>
                    <summary>Transaction feature snapshot</summary>
                    <dl className="case-features">
                      {Object.entries(selected.snapshot.features).map(
                        ([name, value]) => (
                          <div key={name}>
                            <dt>{label(name)}</dt>
                            <dd>{String(value)}</dd>
                          </div>
                        ),
                      )}
                    </dl>
                  </details>
                  {writable && (
                    <div className="case-actions">
                      <label>
                        Investigator note
                        <textarea
                          aria-label="Investigator note"
                          value={note}
                          maxLength={2000}
                          onChange={(event) => setNote(event.target.value)}
                          placeholder="Record your evidence and reasoning (at least 3 characters)."
                        />
                      </label>
                      <div className="case-action-buttons">
                        <button
                          className="secondary-button"
                          disabled={busy || note.trim().length < 3}
                          onClick={() => void act()}
                        >
                          Add note
                        </button>
                        {transitions.map((status) => (
                          <button
                            key={status}
                            className="primary-button"
                            disabled={busy || note.trim().length < 3}
                            onClick={() => void act(status)}
                          >
                            Mark {label(status)}
                          </button>
                        ))}
                      </div>
                      <small>
                        Pending → reviewed → confirmed fraud / legitimate.
                        Administrators may reopen resolved cases. Every write
                        checks the displayed version.
                      </small>
                    </div>
                  )}
                  <div className="panel-heading">
                    <h3>Action history</h3>
                    {writable && (
                      <button
                        className="secondary-button"
                        disabled={busy}
                        onClick={() => void exportCase()}
                      >
                        Export sanitized report
                      </button>
                    )}
                  </div>
                  <ol className="case-history">
                    {selected.history?.map((event) => (
                      <li key={event.version}>
                        <strong>
                          v{event.version} · {label(event.action)} →{" "}
                          {label(event.status)}
                        </strong>
                        <small>
                          {event.actor} ·{" "}
                          {new Date(event.timestamp).toLocaleString()}
                        </small>
                        <p>{event.note}</p>
                        <code title={event.event_hash}>
                          SHA-256 {event.event_hash.slice(0, 16)}…
                        </code>
                      </li>
                    ))}
                  </ol>
                </>
              )}
            </section>
          </div>
        </>
      )}
      {busy && <p role="status">Loading local case evidence…</p>}
      {error && (
        <p className="investigation-error" role="alert">
          {error}{" "}
          {error.includes("reload") || error.includes("changed")
            ? "Your note is retained. Reload the case, inspect the new history and submit again."
            : "Check the local API and credentials, then retry."}
        </p>
      )}
      {message && (
        <p className="investigation-success" role="status">
          {message}
        </p>
      )}
    </main>
  );
}
