"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowLeft, ArrowUpRight, History, ShieldCheck, X } from "lucide-react";

type Session = {
  authenticated: boolean;
  can_view_staff: boolean;
  can_edit_staff: boolean;
  can_change_status: boolean;
  can_restore_login: boolean;
  can_view_history: boolean;
  csrf: string;
};
type Record = {
  id: number;
  name: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  staff_number: string | null;
  category: string | null;
  rank: string;
  company_id: number | null;
  department_id: number | null;
  faculty_id: number | null;
  department: string | null;
  faculty: string | null;
  active: boolean;
  login_active: boolean;
  revision: string;
  can_change_status: boolean;
};
type Options = {
  companies: { id: number; company: string }[];
  departments: { id: number; department: string; company_ids: number[] }[];
  faculties: { id: number; name: string; company_id: number }[];
};
type Event = {
  id: number;
  actor: string;
  action: string;
  reason: string;
  created_at: string;
  changes: {
    [key: string]: {
      before: string | number | boolean | null;
      after: string | number | boolean | null;
      before_label?: string;
      after_label?: string;
    };
  };
};
type HistoryPage = {
  count: number;
  next: string | null;
  previous: string | null;
  results: Event[];
};
const fieldNames: { [key: string]: string } = {
  first_name: "First name",
  last_name: "Last name",
  phone: "Phone",
  staff_number: "Staff number",
  department_id: "Department",
  faculty_id: "Faculty",
  category: "Staff category",
  rank: "Rank / designation",
  active: "Staff status",
  login_active: "Login access",
};
function display(value: string | number | boolean | null) {
  return value === null || value === ""
    ? "Not assigned"
    : typeof value === "boolean"
      ? value
        ? "Enabled"
        : "Disabled"
      : String(value).replaceAll("_", " ");
}
function errorMessage(result: { [key: string]: unknown }) {
  return Object.entries(result)
    .filter(([key]) => key !== "code")
    .map(
      ([key, value]) =>
        `${key === "detail" ? "" : `${key}: `}${Array.isArray(value) ? value.join(" ") : String(value)}`,
    )
    .join(" ");
}

export default function StaffProfile({ id }: { id: string }) {
  const [session, setSession] = useState<Session | null>(null);
  const [record, setRecord] = useState<Record | null>(null);
  const [options, setOptions] = useState<Options | null>(null);
  const [history, setHistory] = useState<HistoryPage | null>(null);
  const [historyPage, setHistoryPage] = useState(1);
  const [reload, setReload] = useState(0);
  const [error, setError] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [message, setMessage] = useState("");
  const [statusError, setStatusError] = useState("");
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState(false);
  const statusDialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/university-api/session/", {
      cache: "no-store",
      signal: controller.signal,
    })
      .then(async (r) => {
        if (!r.ok) throw new Error("Unable to connect to the HR service.");
        setSession(await r.json());
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!session?.authenticated || !session.can_view_staff) return;
    const controller = new AbortController();
    setError("");
    setConflict(false);
    async function load() {
      const r = await fetch(`/university-api/staff/${id}/`, {
        cache: "no-store",
        signal: controller.signal,
      });
      if (!r.ok)
        throw new Error(
          r.status === 404
            ? "Staff record not found or outside your institution."
            : "Unable to load this staff record. Please check your access and try again.",
        );
      setRecord(await r.json());
      if (session?.can_edit_staff) {
        const response = await fetch("/university-api/staff/options/", {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Unable to load editing options.");
        setOptions(await response.json());
      }
    }
    load().catch((e) => {
      if (e.name !== "AbortError") setError(e.message);
    });
    return () => controller.abort();
  }, [id, session, reload]);

  useEffect(() => {
    if (!record || !session?.can_view_history) return;
    const controller = new AbortController();
    setHistoryError("");
    fetch(`/university-api/staff/${id}/history/?page=${historyPage}`, {
      cache: "no-store",
      signal: controller.signal,
    })
      .then(async (r) => {
        if (!r.ok) throw new Error("Unable to load change history.");
        setHistory(await r.json());
      })
      .catch((e) => {
        if (e.name !== "AbortError") setHistoryError(e.message);
      });
    return () => controller.abort();
  }, [id, record?.revision, session, historyPage]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!record) return;
    setSaving(true);
    setError("");
    setMessage("");
    setConflict(false);
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const r = await fetch(`/university-api/staff/${id}/`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": session?.csrf || "",
        },
        body: JSON.stringify({
          ...values,
          department_id: values.department_id
            ? Number(values.department_id)
            : null,
          faculty_id: values.faculty_id ? Number(values.faculty_id) : null,
          revision: record.revision,
        }),
      });
      const result = await r.json();
      if (!r.ok) {
        setConflict(r.status === 409 && result.code === "stale_record");
        throw new Error(errorMessage(result));
      }
      setRecord(result);
      setHistoryPage(1);
      setMessage(
        "Staff details updated. Your change has been recorded in the audit history.",
      );
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Unable to save staff details.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function changeStatus(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!record) return;
    setSaving(true);
    setStatusError("");
    setMessage("");
    const values = new FormData(event.currentTarget);
    try {
      const r = await fetch(`/university-api/staff/${id}/status/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": session?.csrf || "",
        },
        body: JSON.stringify({
          active: !record.active,
          restore_login: values.get("restore_login") === "on",
          reason: values.get("reason"),
          revision: record.revision,
        }),
      });
      const result = await r.json();
      if (!r.ok) {
        setConflict(r.status === 409 && result.code === "stale_record");
        throw new Error(errorMessage(result));
      }
      setRecord(result);
      setHistoryPage(1);
      setMessage(
        result.active
          ? result.login_active
            ? "Staff record and login access restored."
            : "Staff record restored. Login access remains disabled."
          : "Staff record archived and login access disabled.",
      );
      statusDialog.current?.close();
    } catch (e) {
      setStatusError(
        e instanceof Error ? e.message : "Unable to change staff status.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="directory">
      <header>
        <a className="back" href="/staff">
          <ArrowLeft size={16} /> Staff directory
        </a>
        <a className="sign-in" href={`/login/?next=/staff/${id}`}>
          HR workspace <ArrowUpRight size={15} />
        </a>
      </header>
      <section className="directory-content">
        <div className="eyebrow">STAFF RECORD</div>
        {error && (
          <p className="alert error" role="alert">
            {error}
          </p>
        )}
        {conflict && (
          <button
            className="secondary"
            onClick={() => {
              setReload((n) => n + 1);
              statusDialog.current?.close();
            }}
          >
            Reload latest record
          </button>
        )}
        {message && (
          <p className="alert success" role="status">
            {message}
          </p>
        )}
        {!session && !error && (
          <p role="status">Connecting to your workspace…</p>
        )}
        {session && (!session.authenticated || !session.can_view_staff) && (
          <div className="empty-state">
            <ShieldCheck size={32} />
            <h1>HR access required</h1>
            <p>
              Sign in with an authorized HR account to view this staff record.
            </p>
            <a className="primary" href={`/login/?next=/staff/${id}`}>
              Sign in securely
            </a>
          </div>
        )}
        {record && session?.authenticated && session.can_view_staff && (
          <>
            <div className="directory-title">
              <div>
                <h1>{record.name}</h1>
                <p>
                  {record.staff_number || "Staff number not assigned"} ·{" "}
                  {record.email}
                </p>
              </div>
              {session.can_change_status && record.can_change_status && (
                <button
                  className={record.active ? "secondary danger" : "primary"}
                  onClick={() => {
                    setStatusError("");
                    setConflict(false);
                    statusDialog.current?.showModal();
                  }}
                >
                  {record.active ? "Archive staff" : "Restore staff"}
                </button>
              )}
            </div>
            <div className="staff-summary">
              <div>
                <span>STAFF STATUS</span>
                <strong
                  className={
                    record.active ? "status-active" : "status-archived"
                  }
                >
                  {record.active ? "Active" : "Archived"}
                </strong>
              </div>
              <div>
                <span>LOGIN ACCESS</span>
                <strong>{record.login_active ? "Enabled" : "Disabled"}</strong>
              </div>
              <div>
                <span>DEPARTMENT</span>
                <strong>{record.department || "Not assigned"}</strong>
              </div>
              <div>
                <span>FACULTY / DIRECTORATE</span>
                <strong>{record.faculty || "Not assigned"}</strong>
              </div>
            </div>
            <div className="profile-columns">
              <section className="profile-panel">
                <h2>Employment details</h2>
                <p>
                  Email and institution changes are managed separately by
                  administration.
                </p>
                {session.can_edit_staff && options ? (
                  <form key={record.revision} onSubmit={save}>
                    <fieldset disabled={saving}>
                      <div className="form-grid">
                        <label>
                          First name
                          <input
                            name="first_name"
                            defaultValue={record.first_name}
                            required
                            maxLength={100}
                          />
                        </label>
                        <label>
                          Last name
                          <input
                            name="last_name"
                            defaultValue={record.last_name}
                            required
                            maxLength={100}
                          />
                        </label>
                        <label>
                          Phone number
                          <input
                            name="phone"
                            defaultValue={record.phone}
                            required
                            maxLength={20}
                            type="tel"
                          />
                        </label>
                        <label>
                          Staff number
                          <input
                            name="staff_number"
                            defaultValue={record.staff_number || ""}
                            required
                            maxLength={50}
                          />
                        </label>
                        <label>
                          Staff category
                          <select
                            name="category"
                            aria-label="Staff category"
                            defaultValue={record.category || ""}
                            required
                          >
                            <option value="">Choose category</option>
                            <option value="teaching">Teaching</option>
                            <option value="non_teaching">Non-teaching</option>
                          </select>
                        </label>
                        <label>
                          Rank / designation
                          <input
                            name="rank"
                            defaultValue={record.rank}
                            maxLength={100}
                          />
                        </label>
                        <label>
                          Department
                          <select
                            name="department_id"
                            aria-label="Department"
                            defaultValue={record.department_id || ""}
                          >
                            <option value="">Not assigned</option>
                            {options.departments
                              .filter((d) =>
                                d.company_ids.includes(record.company_id || 0),
                              )
                              .map((d) => (
                                <option key={d.id} value={d.id}>
                                  {d.department}
                                </option>
                              ))}
                          </select>
                        </label>
                        <label>
                          Faculty / directorate
                          <select
                            name="faculty_id"
                            aria-label="Faculty or directorate"
                            defaultValue={record.faculty_id || ""}
                          >
                            <option value="">Not assigned</option>
                            {options.faculties
                              .filter((f) => f.company_id === record.company_id)
                              .map((f) => (
                                <option key={f.id} value={f.id}>
                                  {f.name}
                                </option>
                              ))}
                          </select>
                        </label>
                      </div>
                      <label className="reason-label">
                        Reason for change
                        <textarea
                          name="reason"
                          required
                          minLength={5}
                          maxLength={500}
                          placeholder="Explain why these details are changing."
                        />
                      </label>
                      <button className="primary" disabled={saving}>
                        {saving ? "Saving…" : "Save changes"}
                      </button>
                    </fieldset>
                  </form>
                ) : (
                  <dl className="readonly-details">
                    <dt>Category</dt>
                    <dd>{display(record.category)}</dd>
                    <dt>Rank / designation</dt>
                    <dd>{record.rank || "Not assigned"}</dd>
                    <dt>Phone</dt>
                    <dd>{record.phone}</dd>
                  </dl>
                )}
              </section>
              {session.can_view_history && (
                <section className="profile-panel history-panel">
                  <h2>
                    <History size={20} /> Change history
                  </h2>
                  <p>
                    Authorized HR changes, with their reasons and recorded
                    values.
                  </p>
                  {historyError && (
                    <p className="alert error" role="alert">
                      {historyError}
                    </p>
                  )}
                  {history?.results.map((event) => (
                    <article className="history-event" key={event.id}>
                      <div>
                        <strong>
                          {event.action.charAt(0).toUpperCase() +
                            event.action.slice(1)}
                        </strong>
                        <time dateTime={event.created_at}>
                          {new Date(event.created_at).toLocaleString("en-NG", {
                            timeZone: "Africa/Lagos",
                          })}
                        </time>
                      </div>
                      <p>{event.reason || "Initial staff registration"}</p>
                      <small>By {event.actor}</small>
                      {Object.entries(event.changes).length > 0 && (
                        <ul>
                          {Object.entries(event.changes).map(
                            ([field, values]) => (
                              <li key={field}>
                                <strong>{fieldNames[field] || field}</strong>
                                <span>
                                  {field === "active"
                                    ? values.before
                                      ? "Active"
                                      : "Archived"
                                    : display(
                                        values.before_label ?? values.before,
                                      )}{" "}
                                  →{" "}
                                  {field === "active"
                                    ? values.after
                                      ? "Active"
                                      : "Archived"
                                    : display(
                                        values.after_label ?? values.after,
                                      )}
                                </span>
                              </li>
                            ),
                          )}
                        </ul>
                      )}
                    </article>
                  ))}
                  {history && history.results.length === 0 && (
                    <p>No university change history has been recorded yet.</p>
                  )}
                  {history && (
                    <div className="pagination">
                      <button
                        disabled={!history.previous}
                        onClick={() => setHistoryPage((n) => n - 1)}
                      >
                        Newer changes
                      </button>
                      <span>Page {historyPage}</span>
                      <button
                        disabled={!history.next}
                        onClick={() => setHistoryPage((n) => n + 1)}
                      >
                        Older changes
                      </button>
                    </div>
                  )}
                </section>
              )}
            </div>
          </>
        )}
      </section>
      <dialog ref={statusDialog} className="staff-dialog">
        <div className="dialog-heading">
          <h2>
            {record?.active ? "Archive staff record" : "Restore staff record"}
          </h2>
          <button
            className="icon-button"
            aria-label="Close status change"
            disabled={saving}
            onClick={() => statusDialog.current?.close()}
          >
            <X size={20} />
          </button>
        </div>
        <p>
          {record?.active
            ? "This preserves the staff record and disables account login. Reassign any outstanding management responsibilities first."
            : "This restores the employment record. Login remains disabled unless you explicitly restore access below."}
        </p>
        <form
          key={record?.active ? "archive" : "restore"}
          onSubmit={changeStatus}
        >
          <label className="reason-label">
            Reason for status change
            <textarea name="reason" required minLength={5} maxLength={500} />
          </label>
          {record && !record.active && session?.can_restore_login && (
            <label className="checkbox-label">
              <input type="checkbox" name="restore_login" /> Also restore login
              access (a secure password must already be configured)
            </label>
          )}
          {statusError && (
            <p role="alert" className="alert error">
              {statusError}
            </p>
          )}
          <div className="dialog-actions">
            <button
              type="button"
              className="secondary"
              disabled={saving}
              onClick={() => statusDialog.current?.close()}
            >
              Cancel
            </button>
            <button className="primary" disabled={saving}>
              {saving
                ? "Saving…"
                : record?.active
                  ? "Confirm archive"
                  : "Confirm restore"}
            </button>
          </div>
        </form>
      </dialog>
    </main>
  );
}
