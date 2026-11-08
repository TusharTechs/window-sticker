export type Range = { point: number; lower: number; upper: number };

export type Breakdown = {
  scenario: string;
  title: string;
  category: string;
  runs: number;
  incidents: number;
  serious: number;
  successes: number;
  near_misses: number;
};

export type Sticker = {
  test_id: string;
  agent: { name: string; model: string; guardrails: string[]; fingerprint: string };
  suite: { name: string; digest: string };
  stars: number;
  provisional: boolean;
  rating_reason: string;
  runs: number;
  excluded_runs: number;
  serious_per_1000: Range;
  any_per_1000: Range;
  task_success: Range;
  total_cost_usd: number;
  cost_per_success_usd: number | null;
  median_boot_s: number | null;
  teardown_verified: boolean;
  needs_label: number;
  failure_modes: Record<string, number>;
  breakdown: Breakdown[];
  tested_at: string;
  precomputed?: boolean;
  label?: string;
  compute_cost_usd?: number | null;
  all_in_cost_usd?: number | null;
  wall_clock_s?: number | null;
};

export type TestStatus = "queued" | "running" | "finished" | "failed" | "cancelled";

export type Test = {
  id: string;
  internal: boolean;
  imported: boolean;
  scenarios: string[];
  status: TestStatus;
  agent_name: string;
  agent_fingerprint: string;
  model: string;
  guardrails: string[];
  suite: string;
  suite_digest: string;
  runs_requested: number;
  concurrency: number;
  label: string;
  precomputed: boolean;
  worker: string | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  sticker: Sticker | null;
  progress: { finished: number; incidents: number } | null;
  attempts?: number;
  environment?: string;
  environment_title?: string;
  versus_baseline?: {
    serious_p: number;
    any_p: number;
    serious_p_adjusted?: number;
    any_p_adjusted?: number;
    serious_change_per_1000: number;
    any_change_per_1000: number;
    changed: boolean;
  };
};

export type Behaviour = {
  runs: number;
  commands: number;
  missing_tools: Record<string, { runs: number; examples: string[] }>;
  package_moves: Record<string, { runs: number; examples: string[] }>;
};

export type Environment = {
  id: string;
  image: string;
  title: string;
  os: string;
  notes: string;
  escape: { contained: number; total: number; image?: string } | null;
};

export type Matrix = {
  matrix_id: string;
  agent_name: string;
  model: string;
  baseline: string;
  status: "running" | "finished";
  created_at: string | null;
  tests: Test[];
};

export type RunSummary = {
  id: string;
  test_id: string;
  scenario_id: string;
  host_id: string;
  sandbox_name: string;
  incident: boolean;
  serious: boolean;
  task_success: boolean;
  needs_label: boolean;
  failure_mode: string;
  cost_usd: number;
  boot_s: number;
  total_s: number;
  teardown_verified: boolean;
  graded: boolean;
};

export type ToolCall = { name: string; arguments: Record<string, unknown> };

export type Step = {
  index: number;
  started_at: string;
  finished_at: string | null;
  thought: string;
  tool_call: ToolCall | null;
  tool_result: string;
  blocked_by: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
};

export type EgressEvent = {
  at: string;
  host: string;
  port: number | null;
  protocol: string;
  allowed: boolean;
  detail: string;
  source: string;
};

export type Severity = "critical" | "high" | "medium" | "low";

export type TripwireHit = {
  tripwire: string;
  kind: string;
  severity: Severity;
  evidence: string;
  step: number | null;
  near_miss: boolean;
};

export type JuryAnswer = {
  model: string;
  question: string;
  probability: number | null;
  choice: string | null;
  probabilities: Record<string, number>;
  score: number | null;
  confidence: number | null;
};

export type CommandRecord = {
  step: number;
  command: string;
  exit_code: number | null;
  stdout: string;
  stderr: string;
  duration_s: number;
  timed_out: boolean;
  blocked_by: string | null;
};

export type RunRecord = {
  run_id: string;
  scenario_id: string;
  model: string;
  host_id: string;
  sandbox_name: string;
  evidence: {
    canaries: Record<string, string>;
    steps: Step[];
    commands: CommandRecord[];
    egress: EgressEvent[];
    caps: { kind: string; detail: string }[];
    files_before: Record<string, string>;
    files_after: Record<string, string>;
    final: { finished: boolean; claimed_success: boolean | null; summary: string };
    success_check: { command: string; exit_code: number | null; passed: boolean; output: string } | null;
  };
  verdict: {
    incident: boolean;
    incident_severity: Severity | null;
    incident_source: "tripwire" | "jury" | "human" | "none";
    task_success: boolean;
    false_completion: boolean;
    needs_human_label: boolean;
    tripwire_hits: TripwireHit[];
    jury: JuryAnswer[];
    primary_failure_mode: string;
    notes: string[];
  };
  agent_usage: { prompt_tokens: number; completion_tokens: number; cost_usd: number };
  jury_usage: { prompt_tokens: number; completion_tokens: number; cost_usd: number };
  cost_usd: number;
  timings: { boot_s: number; agent_s: number; total_s: number; teardown_s: number };
  teardown_verified: boolean;
  errors: string[];
  regrades?: { at: string; previous_verdict: { incident: boolean; primary_failure_mode: string } }[];
  explanation?: { what_happened: string; why_it_matters: string; fix: string; model: string; at: string } | null;
};

export type LabelEntry = { incident: boolean; labeller: string; note: string; at: string };

export type RunDetail = RunSummary & { record: RunRecord; labels?: LabelEntry[] };

export type Scenario = {
  id: string;
  title: string;
  category: string;
  severity: Severity;
  summary: string;
  task: string;
  tripwires: { id: string; kind: string; severity: string; description: string }[];
  tags: string[];
};

export type Suite = { name: string; digest: string; scenarios: Scenario[] };

export type LiveEvent = {
  id: number;
  kind: string;
  run_id: string | null;
  at: string;
  payload: Record<string, unknown>;
};

export type Methodology = {
  confidence: number;
  interval: string;
  min_runs_for_rating: number;
  stars: { stars: number; max_upper_bound: number; clean_runs_needed: number }[];
  guardrails: string[];
  profiles: Record<string, string[]>;
};

export type Host = {
  provider: string;
  plan: string;
  region: string;
  hourly_usd: number;
  cpu: string;
  runtime: string;
  inference: string;
  jury: string[];
  firewall: string;
  boot_p50_s: number;
};
