export type User = { id: number; name: string };
export type Workspace = {
  workspace_id: string;
  workspace__name: string;
  role: string;
};
export type Project = {
  id: string;
  name: string;
  site_url: string;
  run_count: number;
};
export type Run = {
  id: string;
  status: string;
  source: string;
  fixture: string;
  score: number | null;
  attempts: number;
  error_code: string;
  created_at: string;
  duration_ms: number | null;
};
export type Finding = {
  id: string;
  title: string;
  severity: string;
  explanation: string;
  recommendation: string;
  action: { state: string; version: number; assignee_id: number | null };
};
export type Invoice = {
  provider_id: string;
  currency: string;
  amount_due: number;
  amount_paid: number;
  status: string;
};
export type Event = { id: number; kind: string; created_at: string };
export type Session = { user: User | null; csrf_token: string };
