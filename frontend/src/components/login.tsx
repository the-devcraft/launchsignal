import type { FormEvent } from "react";
import { Layers3, ArrowRight } from "lucide-react";
export function LoginScreen({
  onSubmit,
  busy,
  error,
}: {
  onSubmit: (e: FormEvent<HTMLFormElement>) => void;
  busy: boolean;
  error: string;
}) {
  return (
    <main className="login-shell">
      <section className="login-story">
        <div className="brand">
          <span className="brand-mark">
            <Layers3 size={22} />
          </span>{" "}
          LaunchSignal
        </div>
        <div>
          <span className="eyebrow">MARKETING OPERATIONS, CONNECTED</span>
          <h1>
            Good findings.
            <br />
            Better follow-through.
          </h1>
          <p>
            Bring website audits, clear ownership and accountable actions into
            one focused workspace.
          </p>
          <div className="story-flow">
            <span>Discover</span>
            <ArrowRight />
            <span>Prioritize</span>
            <ArrowRight />
            <span>Resolve</span>
          </div>
        </div>
        <small>A clear path from identified problem to completed work.</small>
      </section>
      <section className="login-panel">
        <form onSubmit={onSubmit}>
          <span className="eyebrow">YOUR WORKSPACE AWAITS</span>
          <h2>Welcome back.</h2>
          <p>Sign in to keep the important work moving.</p>
          <label>
            Email or username
            <input
              name="username"
              autoComplete="username"
              defaultValue="demo@launchsignal.test"
              required
            />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          {error && (
            <div role="alert" className="error">
              {error}
            </div>
          )}
          <button className="primary" disabled={busy}>
            {busy ? "Signing in…" : "Enter workspace"}
            <ArrowRight size={17} />
          </button>
          <small>Local demo: use the password configured during setup.</small>
        </form>
      </section>
    </main>
  );
}
