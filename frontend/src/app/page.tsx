"use client";

import type {
  User,
  Workspace,
  Project,
  Run,
  Finding,
  Invoice,
  Event,
  Session,
} from "../lib/types";
import { api, setCSRF } from "../lib/api";
import { LoginScreen } from "../components/login";
import { BillingPanel } from "../components/billing";
import { ActivityPanel } from "../components/activity";
import { FindingsPanel } from "../components/findings";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Check,
  CircleDollarSign,
  Command,
  ExternalLink,
  Globe2,
  Layers3,
  LayoutDashboard,
  LogOut,
  Plus,
  Radar,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react";

export default function Page() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [spaces, setSpaces] = useState<Workspace[]>([]);
  const [workspace, setWorkspace] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState("");
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState("");
  const [findings, setFindings] = useState<Finding[]>([]);
  const [members, setMembers] = useState<{ id: number; name: string }[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [view, setView] = useState("overview");
  const [busy, setBusy] = useState(false);
  const [source, setSource] = useState("fixture");
  const [fixture, setFixture] = useState("baseline");
  const [modal, setModal] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const generation = useRef(0);
  const runGeneration = useRef(0);
  const findingGeneration = useRef(0);
  useEffect(() => {
    runGeneration.current++;
  }, [workspace, project]);
  useEffect(() => {
    findingGeneration.current++;
  }, [workspace, selected]);
  const currentSpace = spaces.find((x) => x.workspace_id === workspace);
  const currentProject = projects.find((x) => x.id === project);
  const currentRun = runs.find((x) => x.id === selected);
  const canWrite = currentSpace?.role !== "viewer";

  const loadSpaces = useCallback(async () => {
    const result = await api<Workspace[]>("workspaces");
    setSpaces(result);
    setWorkspace(result[0]?.workspace_id || "");
  }, []);

  useEffect(() => {
    api<Session>("auth/session")
      .then(async (session) => {
        setCSRF(session.csrf_token);
        setUser(session.user);
        if (session.user) await loadSpaces();
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [loadSpaces]);

  useEffect(() => {
    if (!workspace) return;
    const stamp = ++generation.current;
    setMembers([]);
    api<{ id: number; name: string }[]>(`workspaces/${workspace}/members`)
      .then((items) => {
        if (generation.current === stamp) setMembers(items);
      })
      .catch((e) => {
        if (generation.current === stamp) setError(e.message);
      });
    setProjects([]);
    setProject("");
    setRuns([]);
    setSelected("");
    setFindings([]);
    setError("");
    api<Project[]>(`workspaces/${workspace}/projects`)
      .then((items) => {
        if (generation.current !== stamp) return;
        setProjects(items);
        setProject(items[0]?.id || "");
      })
      .catch((e) => {
        if (generation.current === stamp) setError(e.message);
      });
  }, [workspace]);

  const refresh = useCallback(async () => {
    if (!workspace || !project) return;
    const stamp = generation.current;
    const runStamp = runGeneration.current;
    const items = await api<Run[]>(
      `workspaces/${workspace}/projects/${project}/runs`,
    );
    if (generation.current !== stamp || runGeneration.current !== runStamp)
      return;
    setRuns(items);
    setSelected((old) =>
      items.some((x) => x.id === old) ? old : items[0]?.id || "",
    );
  }, [workspace, project]);

  useEffect(() => {
    setRuns([]);
    setSelected("");
    setFindings([]);
    refresh().catch((e) => setError(e.message));
    const timer = setInterval(
      () => refresh().catch((e) => setError(e.message)),
      3000,
    );
    return () => clearInterval(timer);
  }, [refresh]);

  const loadFindings = useCallback(async () => {
    if (!workspace || !selected) {
      setFindings([]);
      return;
    }
    const stamp = generation.current;
    const findingStamp = findingGeneration.current;
    const items = await api<Finding[]>(
      `workspaces/${workspace}/runs/${selected}/findings`,
    );
    if (
      generation.current === stamp &&
      findingGeneration.current === findingStamp
    )
      setFindings(items);
  }, [workspace, selected]);
  useEffect(() => {
    loadFindings().catch((e) => setError(e.message));
  }, [loadFindings, currentRun?.status]);

  useEffect(() => {
    if (!workspace) return;
    let active = true;
    setInvoices([]);
    setEvents([]);
    if (view === "billing")
      api<Invoice[]>(`workspaces/${workspace}/billing`)
        .then((x) => {
          if (active) setInvoices(x);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    if (view === "activity")
      api<Event[]>(`workspaces/${workspace}/activity`)
        .then((x) => {
          if (active) setEvents(x);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    return () => {
      active = false;
    };
  }, [workspace, view]);
  useEffect(() => {
    if (modal) dialog.current?.showModal();
    else dialog.current?.close();
  }, [modal]);

  async function loginUser(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const data = new FormData(event.currentTarget);
    try {
      const session = await api<Session>("auth/login", {
        method: "POST",
        body: JSON.stringify({
          username: data.get("username"),
          password: data.get("password"),
        }),
      });
      setCSRF(session.csrf_token);
      setUser(session.user);
      await loadSpaces();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function requestAudit() {
    if (!project) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ id: string }>(
        `workspaces/${workspace}/projects/${project}/runs`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: JSON.stringify({ source, fixture }),
        },
      );
      setSelected(result.id);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function changeAction(
    item: Finding,
    state: string,
    assignee: number | null = item.action.assignee_id,
  ) {
    setError("");
    setBusy(true);
    try {
      await api(`workspaces/${workspace}/findings/${item.id}/action`, {
        method: "PATCH",
        body: JSON.stringify({
          state,
          version: item.action.version,
          assignee_id: assignee,
        }),
      });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      try {
        await loadFindings();
      } catch (e) {
        setError((e as Error).message);
      }
      setBusy(false);
    }
  }
  async function addProject(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      const created = await api<Project>(`workspaces/${workspace}/projects`, {
        method: "POST",
        body: JSON.stringify({
          name: data.get("name"),
          site_url: data.get("url"),
        }),
      });
      setProjects((old) => [{ ...created, run_count: 0 }, ...old]);
      setProject(created.id);
      setModal(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (loading)
    return (
      <main className="loading">
        <Radar size={28} />
        <p>Opening your workspace…</p>
      </main>
    );
  if (!user)
    return <LoginScreen onSubmit={loginUser} busy={busy} error={error} />;

  const open = findings.filter((x) => x.action.state !== "resolved").length;
  const resolved = findings.length - open;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link href="/" className="brand">
          <span className="brand-mark">
            <Layers3 size={21} />
          </span>
          LaunchSignal
        </Link>
        <label className="space-select">
          <span>WORKSPACE</span>
          <select
            aria-label="Workspace"
            disabled={busy}
            value={workspace}
            onChange={(e) => setWorkspace(e.target.value)}
          >
            {spaces.map((x) => (
              <option key={x.workspace_id} value={x.workspace_id}>
                {x.workspace__name}
              </option>
            ))}
          </select>
        </label>
        <span className="nav-label">WORKSPACE</span>
        <nav>
          {[
            ["overview", "Overview", LayoutDashboard],
            ["audits", "Audit runs", Radar],
            ["billing", "Billing", CircleDollarSign],
            ["activity", "Activity", Activity],
          ].map(([key, label, Icon]) => {
            const Component = Icon as typeof Radar;
            return (
              <button
                className={view === key ? "active" : ""}
                key={key as string}
                onClick={() => {
                  setView(key as string);
                  setError("");
                }}
              >
                <Component size={18} />
                {label as string}
                {key === "audits" && (
                  <span className="nav-count">{runs.length}</span>
                )}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-note">
          <ShieldCheck size={21} />
          <strong>Every action has a trail.</strong>
          <p>
            Shared context. Clear ownership.
            <br />
            Fewer loose ends.
          </p>
        </div>
        <div className="account">
          <span className="avatar">
            {user.name
              .split(" ")
              .map((x) => x[0])
              .join("")
              .slice(0, 2)}
          </span>
          <div>
            <strong>{user.name}</strong>
            <small>{currentSpace?.role || "Member"}</small>
          </div>
          <button
            aria-label="Sign out"
            disabled={busy}
            onClick={async () => {
              try {
                await api("auth/logout", { method: "POST" });
                setUser(null);
                setWorkspace("");
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            <LogOut size={16} />
          </button>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <span>
            {currentSpace?.workspace__name}
            <span className="slash">/</span>
            <strong>
              {view === "overview"
                ? "Overview"
                : view === "audits"
                  ? "Audit runs"
                  : view === "billing"
                    ? "Billing"
                    : "Activity"}
            </strong>
          </span>
          <div className="top-meta">
            <span className="environment">
              <i />
              Local workspace
            </span>
            <span className="shortcut">
              <Command size={12} /> focused work
            </span>
          </div>
        </header>
        <div className="content">
          {error && (
            <div role="alert" className="error global-error">
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={15} />
              </button>
            </div>
          )}
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                {view === "billing"
                  ? "COMMERCIAL CLARITY"
                  : "FROM INSIGHT TO ACTION"}
              </span>
              <h1>
                {view === "overview"
                  ? "Make the next move count."
                  : view === "audits"
                    ? "A clearer picture of every page."
                    : view === "billing"
                      ? "The numbers, accounted for."
                      : "Nothing gets lost in the handoff."}
              </h1>
              <p>
                {view === "billing"
                  ? "Invoice status and payment evidence for this workspace."
                  : "See what needs attention. Give it an owner. Keep it moving."}
              </p>
            </div>
            {canWrite && (
              <button className="secondary" onClick={() => setModal(true)}>
                <Plus size={16} />
                Add website
              </button>
            )}
          </div>
          {(view === "overview" || view === "audits") && (
            <>
              <div className="project-toolbar">
                <label>
                  <Globe2 size={16} />
                  <select
                    aria-label="Website"
                    disabled={busy}
                    value={project}
                    onChange={(e) => {
                      setProject(e.target.value);
                      setError("");
                    }}
                  >
                    {projects.map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.name}
                      </option>
                    ))}
                  </select>
                </label>
                {currentProject && (
                  <a
                    href={currentProject.site_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {new URL(currentProject.site_url).hostname}
                    <ExternalLink size={12} />
                  </a>
                )}
                <span className="toolbar-spacer" />
                <button
                  className="icon-button"
                  aria-label="Refresh audit runs"
                  onClick={() => refresh().catch((e) => setError(e.message))}
                >
                  <RefreshCw size={16} />
                </button>
              </div>
              {!project ? (
                <div className="empty">
                  <Globe2 size={34} />
                  <h2>A clean slate.</h2>
                  <p>
                    Add your first website to start turning findings into
                    actions.
                  </p>
                </div>
              ) : (
                <>
                  <section className="stats">
                    <article>
                      <span>PAGE HEALTH</span>
                      <div>
                        {currentRun?.score ?? "—"}
                        <small>/ 100</small>
                      </div>
                      <p>
                        <i className="dot coral" />
                        Rule-based audit score
                      </p>
                      <Radar className="stat-icon" size={24} />
                    </article>
                    <article>
                      <span>NEEDS ATTENTION</span>
                      <div>{open.toString().padStart(2, "0")}</div>
                      <p>Open findings in selected run</p>
                      <ArrowUpRight className="stat-icon" size={24} />
                    </article>
                    <article>
                      <span>RESOLVED ACTIONS</span>
                      <div>{resolved.toString().padStart(2, "0")}</div>
                      <p>
                        <i className="dot green" />
                        Progress you can account for
                      </p>
                      <Check className="stat-icon" size={24} />
                    </article>
                    <article>
                      <span>AUDIT RUNS</span>
                      <div>{runs.length.toString().padStart(2, "0")}</div>
                      <p>
                        {
                          runs.filter(
                            (x) =>
                              x.status === "pending" || x.status === "running",
                          ).length
                        }{" "}
                        in the queue
                      </p>
                      <Activity className="stat-icon" size={24} />
                    </article>
                  </section>
                  <div className="workspace-grid">
                    <FindingsPanel
                      findings={findings}
                      runs={runs}
                      currentRun={currentRun}
                      selected={selected}
                      setSelected={setSelected}
                      members={members}
                      canWrite={canWrite && !busy}
                      changeAction={changeAction}
                    />
                    <aside className="right-column">
                      <section className="audit-card">
                        <div className="orb">
                          <Radar size={28} />
                        </div>
                        <span className="eyebrow">A FRESH PERSPECTIVE</span>
                        <h2>
                          Good decisions
                          <br />
                          start with a signal.
                        </h2>
                        <p>
                          Run a focused page audit. Keep every finding connected
                          to the work that follows.
                        </p>
                        <label>
                          Audit source
                          <select
                            aria-label="Audit source"
                            value={source}
                            onChange={(e) => setSource(e.target.value)}
                          >
                            <option value="fixture">Demo snapshot</option>
                            <option value="live">Live allowlisted page</option>
                          </select>
                        </label>
                        {source === "fixture" && (
                          <label>
                            Sample page
                            <select
                              aria-label="Sample page"
                              value={fixture}
                              onChange={(e) => setFixture(e.target.value)}
                            >
                              <option value="baseline">
                                Page with improvement opportunities
                              </option>
                              <option value="healthy">Healthy page</option>
                            </select>
                          </label>
                        )}
                        <button
                          className="primary"
                          disabled={!canWrite || busy}
                          onClick={requestAudit}
                        >
                          {busy ? "Queueing…" : "Run audit"}
                          <ArrowRight size={17} />
                        </button>
                        <small>
                          {source === "fixture"
                            ? "Fixture mode makes no external requests."
                            : "Live mode requires an operator-approved hostname."}
                        </small>
                      </section>
                      <section className="process-card">
                        <h3>A simple way forward.</h3>
                        {[
                          "Discover the issue",
                          "Prioritize the next step",
                          "Own the resolution",
                        ].map((text, i) => (
                          <div key={text}>
                            <span>{i + 1}</span>
                            {text}
                          </div>
                        ))}
                      </section>
                    </aside>
                  </div>
                </>
              )}
            </>
          )}
          {view === "billing" && <BillingPanel invoices={invoices} />}
          {view === "activity" && <ActivityPanel events={events} />}
          <footer className="footer">
            <span>
              <Layers3 size={14} /> LaunchSignal
            </span>
            <span>Clear signals. Accountable execution.</span>
          </footer>
        </div>
      </main>
      <dialog
        ref={dialog}
        onCancel={() => setModal(false)}
        onClose={() => setModal(false)}
      >
        <form onSubmit={addProject}>
          <div className="dialog-heading">
            <h2>Add a website</h2>
            <button
              type="button"
              aria-label="Close dialog"
              onClick={() => setModal(false)}
            >
              <X size={20} />
            </button>
          </div>
          <p>Give your team a shared place to work on the next improvement.</p>
          <label>
            Website name
            <input name="name" maxLength={120} required autoFocus />
          </label>
          <label>
            HTTPS URL
            <input
              name="url"
              type="url"
              placeholder="https://example.com/"
              maxLength={500}
              required
            />
          </label>
          <button className="primary" disabled={busy}>
            {busy ? "Adding…" : "Add website"}
            <Plus size={17} />
          </button>
        </form>
      </dialog>
    </div>
  );
}
