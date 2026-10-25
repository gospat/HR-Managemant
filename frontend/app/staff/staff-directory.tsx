"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowLeft, ArrowUpRight, Search, Plus, Users, X } from "lucide-react";

type Staff = {
  id: number;
  name: string;
  email: string;
  staff_number: string | null;
  department: string | null;
  category: string | null;
  faculty: string | null;
  rank: string;
  active: boolean;
};
type Session = {
  authenticated: boolean;
  can_view_staff: boolean;
  can_add_staff: boolean;
  csrf: string;
};
type Results = {
  count: number;
  next: string | null;
  previous: string | null;
  results: Staff[];
};
type Options = {
  companies: { id: number; company: string }[];
  departments: { id: number; department: string; company_ids: number[] }[];
  faculties: { id: number; name: string; company_id: number }[];
};
const empty: Results = { count: 0, next: null, previous: null, results: [] };
const REQUEST_TIMEOUT_MS = 8000;

export default function StaffDirectory() {
  const [session, setSession] = useState<Session | null>(null);
  const [data, setData] = useState<Results>(empty);
  const [options, setOptions] = useState<Options | null>(null);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [company, setCompany] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [success, setSuccess] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    setLoading(true);
    setError("");
    fetch("/university-api/session/", {
      cache: "no-store",
      signal: controller.signal,
    })
      .then(async (r) => {
        if (!r.ok) throw new Error("Unable to connect to the HR service.");
        return (await r.json()) as Session;
      })
      .then((value) => {
        if (active) setSession(value);
      })
      .catch((e) => {
        if (!active) return;
        setError(
          e.name === "AbortError"
            ? "Unable to reach the HR service right now. Please refresh and try again."
            : e.message,
        );
      })
      .finally(() => {
        window.clearTimeout(timer);
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      window.clearTimeout(timer);
      controller.abort();
    };
  }, []);

  useEffect(() => {
    if (!session) return;
    if (!session.authenticated || !session.can_view_staff) {
      setLoading(false);
      return;
    }
    let active = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    setLoading(true);
    setError("");
    const params = new URLSearchParams({
      q: query,
      category,
      page: String(page),
    });
    fetch(`/university-api/staff/?${params}`, {
      cache: "no-store",
      signal: controller.signal,
    })
      .then(async (r) => {
        if (!r.ok)
          throw new Error(
            r.status === 403
              ? "Your session expired or access was denied. Please sign in again."
              : "Unable to load staff records. Please try again.",
          );
        return (await r.json()) as Results;
      })
      .then((value) => {
        if (active) setData(value);
      })
      .catch((e) => {
        if (!active) return;
        setError(
          e.name === "AbortError"
            ? "Staff records took too long to load. Please refresh and try again."
            : e.message,
        );
      })
      .finally(() => {
        window.clearTimeout(timer);
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [session, query, category, page, refresh]);

  async function signOut() {
    try {
      const response = await fetch("/university-api/session/", {
        method: "DELETE",
        headers: { "X-CSRFToken": session?.csrf || "" },
      });
      if (!response.ok)
        throw new Error("Unable to sign out. Please try again.");
      setSession({
        authenticated: false,
        can_view_staff: false,
        can_add_staff: false,
        csrf: "",
      });
      setData(empty);
      setError("");
      setSuccess("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to sign out.");
    }
  }

  async function openCreate() {
    setFormError("");
    setSuccess("");
    try {
      const r = await fetch("/university-api/staff/options/", {
        cache: "no-store",
      });
      if (!r.ok) throw new Error("Unable to load staff registration options.");
      const value: Options = await r.json();
      if (!value.companies.length)
        throw new Error(
          "Create your institution in HR administration before adding staff.",
        );
      setOptions(value);
      setCompany(String(value.companies[0].id));
      dialog.current?.showModal();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to open registration.");
    }
  }

  async function createStaff(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setFormError("");
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    const body = {
      ...values,
      company_id: Number(company),
      department_id: values.department_id ? Number(values.department_id) : null,
      faculty_id: values.faculty_id ? Number(values.faculty_id) : null,
    };
    try {
      const r = await fetch("/university-api/staff/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": session?.csrf || "",
        },
        body: JSON.stringify(body),
      });
      const result = await r.json();
      if (!r.ok)
        throw new Error(
          Object.entries(result)
            .map(
              ([key, value]) =>
                `${key}: ${Array.isArray(value) ? value.join(" ") : String(value)}`,
            )
            .join(" "),
        );
      form.reset();
      dialog.current?.close();
      setPage(1);
      setSearch("");
      setQuery("");
      setCategory("");
      setRefresh((n) => n + 1);
      setSuccess(
        "Staff record created. Login remains disabled until an administrator securely activates the account.",
      );
    } catch (e) {
      setFormError(
        e instanceof Error ? e.message : "Unable to create staff record.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="directory">
      <header>
        <a href="/" className="back">
          <ArrowLeft size={16} /> Bells University of Technology
        </a>
        {session?.authenticated ? (
          <button className="sign-in sign-out" onClick={signOut}>
            Sign out <ArrowUpRight size={15} />
          </button>
        ) : (
          <a className="sign-in" href="/login/?next=/staff">
            Staff sign in <ArrowUpRight size={15} />
          </a>
        )}
      </header>
      <section className="directory-content">
        <div className="eyebrow">PEOPLE & CULTURE</div>
        <div className="directory-title">
          <div>
            <h1>Staff directory</h1>
            <p>Teaching and non-teaching staff, together in one place.</p>
          </div>
          {session?.can_add_staff && (
            <button className="primary" onClick={openCreate}>
              <Plus size={17} /> Add staff member
            </button>
          )}
        </div>
        {error && (
          <p className="alert error" role="alert">
            {error}
          </p>
        )}
        {success && (
          <p className="alert success" role="status">
            {success}
          </p>
        )}
        {!session && loading && (
          <p role="status">Connecting to your workspace…</p>
        )}
        {session && !session.authenticated && (
          <div className="empty-state">
            <Users size={35} />
            <h2>Sign in to view your people</h2>
            <p>Staff records are available only to authorized HR users.</p>
            <a className="primary" href="/login/?next=/staff">
              Sign in securely <ArrowUpRight size={17} />
            </a>
          </div>
        )}
        {session?.authenticated && !session.can_view_staff && (
          <div className="empty-state">
            <h2>HR access required</h2>
            <p>
              Ask your university administrator for staff directory permission.
            </p>
          </div>
        )}
        {session?.authenticated && session.can_view_staff && (
          <>
            <div className="directory-tools">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  setQuery(search.trim());
                  setPage(1);
                }}
              >
                <label htmlFor="search" className="sr-only">
                  Search staff
                </label>
                <Search size={17} />
                <input
                  id="search"
                  value={search}
                  maxLength={100}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search name, staff number or email"
                />
                <button type="submit">Search</button>
              </form>
              <label className="filter-label">
                Category
                <select
                  value={category}
                  onChange={(e) => {
                    setCategory(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">All staff</option>
                  <option value="teaching">Teaching</option>
                  <option value="non_teaching">Non-teaching</option>
                </select>
              </label>
            </div>
            <div className="records-panel" aria-busy={loading}>
              <div className="records-heading">
                <strong>
                  {loading
                    ? "Loading records…"
                    : `${data.count.toLocaleString()} staff member${data.count === 1 ? "" : "s"}`}
                </strong>
                <span>25 per page</span>
              </div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Staff member</th>
                      <th>Staff number</th>
                      <th>Category</th>
                      <th>Department / faculty</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {!loading &&
                      !error &&
                      data.results.map((staff) => (
                        <tr key={staff.id}>
                          <td>
                            <strong>
                              <a
                                className="staff-name-link"
                                href={`/staff/${staff.id}`}
                              >
                                {staff.name}
                              </a>
                            </strong>
                            <span>{staff.email}</span>
                            {staff.rank && <small>{staff.rank}</small>}
                          </td>
                          <td>{staff.staff_number || "—"}</td>
                          <td>
                            <span className="pill">
                              {staff.category === "teaching"
                                ? "Teaching"
                                : staff.category === "non_teaching"
                                  ? "Non-teaching"
                                  : "Unclassified"}
                            </span>
                          </td>
                          <td>
                            {staff.department || "—"}
                            {staff.faculty && <span>{staff.faculty}</span>}
                          </td>
                          <td>
                            <span
                              className={
                                staff.active
                                  ? "status-active"
                                  : "status-archived"
                              }
                            >
                              {staff.active ? "Active" : "Archived"}
                            </span>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              {!loading && !error && data.results.length === 0 && (
                <div className="empty-state">
                  <Users size={30} />
                  <h2>
                    {query || category
                      ? "No matching staff"
                      : "Your directory is ready"}
                  </h2>
                  <p>
                    {query || category
                      ? "Try another search or staff category."
                      : "Add your first staff member to begin."}
                  </p>
                </div>
              )}
              <div className="pagination">
                <button
                  disabled={loading || !data.previous}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Previous
                </button>
                <span>Page {page}</span>
                <button
                  disabled={loading || !data.next}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </section>
      <dialog ref={dialog} className="staff-dialog">
        <div className="dialog-heading">
          <div>
            <div className="eyebrow">STAFF REGISTRATION</div>
            <h2>Add a staff member</h2>
          </div>
          <button
            className="icon-button"
            aria-label="Close registration"
            onClick={() => dialog.current?.close()}
          >
            <X size={20} />
          </button>
        </div>
        <p>
          Register employment details. Account activation is handled separately.
        </p>
        <form onSubmit={createStaff}>
          <div className="form-grid">
            <label>
              First name
              <input
                name="first_name"
                required
                maxLength={100}
                autoComplete="given-name"
              />
            </label>
            <label>
              Last name
              <input
                name="last_name"
                required
                maxLength={100}
                autoComplete="family-name"
              />
            </label>
            <label>
              Work email
              <input
                name="email"
                type="email"
                required
                maxLength={254}
                autoComplete="email"
              />
            </label>
            <label>
              Phone number
              <input
                name="phone"
                type="tel"
                required
                maxLength={20}
                autoComplete="tel"
              />
            </label>
            <label>
              Staff number
              <input name="staff_number" required maxLength={50} />
            </label>
            <label>
              Staff category
              <select name="category" aria-label="Staff category" required>
                <option value="teaching">Teaching</option>
                <option value="non_teaching">Non-teaching</option>
              </select>
            </label>
            <label>
              Institution
              <select
                aria-label="Institution"
                name="company_id"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
              >
                {options?.companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.company}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Department
              <select
                key={`department-${company}`}
                name="department_id"
                aria-label="Department"
              >
                <option value="">Not assigned</option>
                {options?.departments
                  .filter((d) => d.company_ids.includes(Number(company)))
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
                key={`faculty-${company}`}
                name="faculty_id"
                aria-label="Faculty or directorate"
              >
                <option value="">Not assigned</option>
                {options?.faculties
                  .filter((f) => f.company_id === Number(company))
                  .map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Rank / designation
              <input
                name="rank"
                maxLength={100}
                placeholder="e.g. Lecturer II"
              />
            </label>
          </div>
          {formError && (
            <p role="alert" className="alert error">
              {formError}
            </p>
          )}
          <div className="dialog-actions">
            <button
              type="button"
              className="secondary"
              onClick={() => dialog.current?.close()}
            >
              Cancel
            </button>
            <button className="primary" disabled={saving}>
              {saving ? "Saving…" : "Create staff record"}
            </button>
          </div>
        </form>
      </dialog>
    </main>
  );
}
