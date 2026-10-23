"use client";
import { useEffect, useState } from "react";
import styles from "./promotions.module.css";

type Policy = {
  id: number;
  module: string;
  version: string;
  active: boolean;
  provisional: boolean;
  configuration: Record<string, unknown>;
};
type Promotion = {
  evidence: string;
  id: number;
  employee: string;
  source_rank: string;
  proposed_rank: string;
  effective_date: string;
  revision: number;
  status: string;
  provisional_policy: boolean;
  events: { action: string; reason: string; created_at: string }[];
};
type Staff = { id: number; name: string; rank: string; category: string };

export default function PromotionsPage() {
  const [cases, setCases] = useState<Promotion[]>([]);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [canAdopt, setCanAdopt] = useState(false);
  const [permissions, setPermissions] = useState<Record<string, boolean>>({});
  const [csrf, setCsrf] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [staff, setStaff] = useState<Staff[]>([]);
  const [selected, setSelected] = useState("");
  const [policy, setPolicy] = useState("");
  const [rank, setRank] = useState("");
  const [effective, setEffective] = useState("");
  const [evidence, setEvidence] = useState("");
  const [reason, setReason] = useState("");
  const [next, setNext] = useState<string | null>(null);
  const [previous, setPrevious] = useState<string | null>(null);
  async function load(url = "/university-api/promotions/") {
    const localUrl = new URL(url, window.location.origin);
    const [session, rows, policyRows] = await Promise.all([
      fetch("/university-api/session/", { credentials: "same-origin" }).then(
        (r) => r.json(),
      ),
      fetch(localUrl.pathname + localUrl.search, {
        credentials: "same-origin",
      }).then(async (r) => {
        const body = await r.json();
        if (!r.ok)
          throw Error(body.detail || "Unable to load promotion requests.");
        return body;
      }),
      fetch("/university-api/policies/", { credentials: "same-origin" }).then(
        async (r) => (r.ok ? r.json() : { results: [] }),
      ),
    ]);
    setCsrf(session.csrf);
    setCases(rows.results);
    setPermissions(rows.permissions);
    setPolicies(policyRows.results);
    setCanAdopt(Boolean(policyRows.can_adopt));
    setNext(rows.next);
    setPrevious(rows.previous);
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!query.trim()) {
      setStaff([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      fetch(`/university-api/staff/?q=${encodeURIComponent(query)}`, {
        signal: controller.signal,
        credentials: "same-origin",
      })
        .then(async (r) => {
          if (r.ok) setStaff((await r.json()).results);
        })
        .catch((e) => {
          if (e.name !== "AbortError") setError("Unable to search staff.");
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);
  async function post(url: string, body: unknown) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify(body),
      });
      const result = await response.json();
      if (!response.ok)
        throw Error(result.detail || "The request could not be saved.");
      await load();
      setNotice("The request was saved and recorded in its audit history.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to save the request.");
    } finally {
      setBusy(false);
    }
  }
  const current = staff.find((s) => s.id === Number(selected));
  const activePolicy = policies.find((p) => p.id === Number(policy));
  const ranks = (activePolicy?.configuration[`${current?.category}_ranks`] ||
    []) as string[];
  return (
    <main className={styles.portal}>
      <a href="/">← HR overview</a>
      <h1>Staff promotions</h1>
      <p>
        Submit evidence, obtain an independent recommendation and Registrar
        approval, then apply the approved rank on its effective date.
      </p>
      <p>
        <strong>Provisional policies:</strong> example university rules require
        explicit adoption by an authorized administrator. Promotion does not
        change salary automatically.
      </p>
      {error && (
        <p role="alert">
          {error} <a href="/login/?next=/promotions">Sign in</a>
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {permissions.add_promotionrequest && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            post("/university-api/promotions/", {
              employee_id: Number(selected),
              policy_id: Number(policy),
              proposed_rank: rank,
              effective_date: effective,
              evidence,
            });
          }}
        >
          <h2>New request</h2>
          <label>
            Find staff
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Name or staff number"
            />
          </label>
          <label>
            Staff member
            <select
              aria-label="Staff member"
              required
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              <option value="">Choose staff</option>
              {staff.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} — {s.rank}
                </option>
              ))}
            </select>
          </label>
          <label>
            Adopted promotion policy
            <select
              aria-label="Adopted promotion policy"
              required
              value={policy}
              onChange={(e) => setPolicy(e.target.value)}
            >
              <option value="">Choose policy</option>
              {policies
                .filter((p) => p.active && p.module === "promotions")
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.version}
                    {p.provisional ? " (provisional)" : ""}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Proposed rank
            <select
              aria-label="Proposed rank"
              required
              value={rank}
              onChange={(e) => setRank(e.target.value)}
            >
              <option value="">Choose rank</option>
              {ranks.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </label>
          <label>
            Effective date
            <input
              required
              type="date"
              value={effective}
              onChange={(e) => setEffective(e.target.value)}
            />
          </label>
          <label>
            Evidence and justification
            <textarea
              required
              maxLength={4000}
              value={evidence}
              onChange={(e) => setEvidence(e.target.value)}
            />
          </label>
          <button disabled={busy || !csrf}>Submit for review</button>
        </form>
      )}
      <h2>Requests</h2>
      <label>
        Reason for the next decision
        <textarea
          maxLength={1000}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Explain your recommendation, decision or application."
        />
      </label>
      {cases.length === 0 && <p>No promotion requests are available.</p>}
      {cases.map((c) => (
        <section
          key={c.id}
          style={{
            border: "1px solid #d1d5db",
            padding: 20,
            marginTop: 16,
            borderRadius: 12,
          }}
        >
          <h3>{c.employee}</h3>
          <p>
            {c.source_rank} → {c.proposed_rank} · Effective {c.effective_date} ·{" "}
            <strong>{c.status}</strong>
          </p>
          <p>{c.evidence}</p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {[
              [
                "recommend",
                permissions.review_promotion && c.status === "submitted",
              ],
              [
                "approve",
                permissions.approve_promotion && c.status === "recommended",
              ],
              [
                "reject",
                permissions.approve_promotion &&
                  ["submitted", "recommended", "approved"].includes(c.status),
              ],
              ["apply", permissions.apply_promotion && c.status === "approved"],
            ]
              .filter(([, allowed]) => allowed)
              .map(([action]) => (
                <button
                  key={String(action)}
                  disabled={busy || !reason.trim()}
                  onClick={() =>
                    post(`/university-api/promotions/${c.id}/action/`, {
                      action,
                      revision: c.revision,
                      reason,
                    })
                  }
                >
                  {String(action)}
                </button>
              ))}
          </div>
          <details>
            <summary>Audit history</summary>
            <ul>
              {c.events.map((event, i) => (
                <li key={i}>
                  {event.action}: {event.reason}
                </li>
              ))}
            </ul>
          </details>
        </section>
      ))}
      <nav aria-label="Promotion request pages">
        <button
          disabled={!previous || busy}
          onClick={() =>
            previous && load(previous).catch((e) => setError(e.message))
          }
        >
          Previous
        </button>
        <button
          disabled={!next || busy}
          onClick={() => next && load(next).catch((e) => setError(e.message))}
        >
          Next
        </button>
      </nav>
      <h2>Policy templates</h2>
      {policies.map((p) => (
        <section key={p.id}>
          <h3>
            {p.module} · {p.version}
          </h3>
          <p>
            {p.active ? "Adopted" : "Awaiting adoption"}
            {p.provisional ? " · Provisional template" : ""}
          </p>
          <details>
            <summary>Review policy values</summary>
            <dl>
              {Object.entries(p.configuration).map(([name, value]) => (
                <div key={name}>
                  <dt>{name.replaceAll("_", " ")}</dt>
                  <dd>
                    {Array.isArray(value)
                      ? value.join(", ")
                      : String(value ?? "Requires configuration")}
                  </dd>
                </div>
              ))}
            </dl>
          </details>
          {canAdopt && !p.active && (
            <button
              disabled={busy}
              onClick={() =>
                post(`/university-api/policies/${p.id}/adopt/`, {})
              }
            >
              Adopt reviewed template
            </button>
          )}
        </section>
      ))}
      <p>
        <a href="/admin/university_governance/universitypolicy/">
          Policy administration
        </a>
      </p>
    </main>
  );
}
