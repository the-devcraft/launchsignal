import { ShieldCheck } from "lucide-react";
import type { Event } from "../lib/types";
import { date } from "../lib/format";
export function ActivityPanel({ events }: { events: Event[] }) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>The work, in order.</h2>
          <p>A workspace-scoped record of requests, results and decisions.</p>
        </div>
        <ShieldCheck size={20} />
      </div>
      <div className="timeline">
        {events.map((item) => (
          <article key={item.id}>
            <span className="timeline-dot" />
            <div>
              <strong>
                {item.kind.replaceAll(".", " ").replaceAll("_", " ")}
              </strong>
              <p>{date(item.created_at)}</p>
            </div>
            <span className="event-id">#{item.id}</span>
          </article>
        ))}
        {!events.length && (
          <p className="empty">Your workspace activity will appear here.</p>
        )}
      </div>
    </section>
  );
}
