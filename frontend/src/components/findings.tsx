import { ArrowDownLeft, Check } from "lucide-react";
import type { Finding, Run } from "../lib/types";
import { date } from "../lib/format";
export function FindingsPanel({
  findings,
  runs,
  currentRun,
  selected,
  setSelected,
  members,
  canWrite,
  changeAction,
}: {
  findings: Finding[];
  runs: Run[];
  currentRun: Run | undefined;
  selected: string;
  setSelected: (id: string) => void;
  members: { id: number; name: string }[];
  canWrite: boolean;
  changeAction: (
    item: Finding,
    state: string,
    assignee?: number | null,
  ) => Promise<void>;
}) {
  return (
    <section className="panel findings-panel">
      <div className="panel-heading">
        <div>
          <h2>Focus on what matters.</h2>
          <p>Prioritized findings, with a practical next step.</p>
        </div>
        <span className="pill">{findings.length} findings</span>
      </div>
      <div className="run-picker">
        <label htmlFor="run-picker">AUDIT SNAPSHOT</label>
        <select
          id="run-picker"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
        >
          {runs.map((x) => (
            <option key={x.id} value={x.id}>
              {date(x.created_at)} · {x.status} · {x.source}
            </option>
          ))}
        </select>
      </div>
      {currentRun && (
        <div className="snapshot-note">
          <span className={`status ${currentRun.status}`}>
            {currentRun.status}
          </span>
          <span>
            {currentRun.source === "fixture"
              ? "Demo snapshot · deterministic sample HTML"
              : "Live single-page audit"}
          </span>
          {currentRun.duration_ms !== null && (
            <span>{currentRun.duration_ms} ms</span>
          )}
        </div>
      )}
      {currentRun?.error_code && (
        <div className="error">
          Audit could not complete: {currentRun.error_code}. Check the activity
          trail and retry after addressing the cause.
        </div>
      )}
      <div className="findings-list">
        {findings.map((item, index) => (
          <article className="finding" key={item.id}>
            <span className="finding-number">
              {String(index + 1).padStart(2, "0")}
            </span>
            <div className="finding-body">
              <div>
                <span className={`severity ${item.severity}`}>
                  {item.severity} priority
                </span>
              </div>
              <h3>{item.title}</h3>
              <p>{item.explanation}</p>
              <div className="recommendation">
                <ArrowDownLeft size={14} />
                <span>{item.recommendation}</span>
              </div>
            </div>
            <div className="action-controls">
              <select
                aria-label={`Owner for ${item.title}`}
                disabled={!canWrite}
                value={item.action.assignee_id ?? ""}
                onChange={(e) =>
                  changeAction(
                    item,
                    item.action.state,
                    e.target.value ? Number(e.target.value) : null,
                  )
                }
              >
                <option value="">Unassigned</option>
                {members.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
              <select
                aria-label={`Status for ${item.title}`}
                disabled={!canWrite}
                value={item.action.state}
                onChange={(e) => changeAction(item, e.target.value)}
              >
                <option value="open">Open</option>
                <option value="in_progress">In progress</option>
                <option value="resolved">Resolved</option>
              </select>
            </div>
          </article>
        ))}
        {!findings.length && (
          <div className="empty compact">
            <Check size={30} />
            <h3>
              {currentRun?.status === "succeeded"
                ? "Clear on these checks."
                : "Your next audit starts here."}
            </h3>
            <p>
              {currentRun?.status === "succeeded"
                ? "No findings from the five checks in this snapshot."
                : "Queue an audit to create an actionable snapshot."}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
