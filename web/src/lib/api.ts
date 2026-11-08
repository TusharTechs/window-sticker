import type { Behaviour, Environment, Host, Matrix, Methodology, RunDetail, RunSummary, Suite, Test } from "./types";

/** Server components call the control plane directly; the browser goes through /api. */
const ORIGIN =
  typeof window === "undefined" ? (process.env.WSK_API_ORIGIN ?? "http://127.0.0.1:8765") : "";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${ORIGIN}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return (await res.json()) as T;
}

/** Like `get`, but returns null on any failure so pages can render an empty state. */
async function tryGet<T>(path: string): Promise<T | null> {
  try {
    return await get<T>(path);
  } catch {
    return null;
  }
}

export const api = {
  tests: (includeInternal = false) => tryGet<Test[]>(`/api/tests?include_internal=${includeInternal}`),
  host: () => tryGet<Host>("/api/host"),
  test: (id: string) => tryGet<Test>(`/api/tests/${id}`),
  runs: (id: string) => tryGet<RunSummary[]>(`/api/tests/${id}/runs`),
  run: (id: string) => tryGet<RunDetail>(`/api/runs/${id}`),
  suite: (name = "v2") => tryGet<Suite>(`/api/suites/${name}`),
  leaderboard: (suite = "v2") => tryGet<Test[]>(`/api/leaderboard?suite=${suite}`),
  labelQueue: () => tryGet<RunSummary[]>("/api/labels/queue"),
  methodology: () => tryGet<Methodology>("/api/methodology"),
  environments: () => tryGet<Environment[]>("/api/environments"),
  matrices: () => tryGet<Matrix[]>("/api/matrices"),
  matrix: (id: string) => tryGet<Matrix>(`/api/matrix/${id}`),
  matrixBehaviour: (id: string) => tryGet<Record<string, Behaviour>>(`/api/matrix/${id}/behaviour`),
  demo: () =>
    tryGet<{
      enabled: boolean;
      models: string[];
      profiles: string[];
      traps: string[];
      environments?: { id: string; title: string }[];
      runs: number;
      remaining_today: number;
      active: Test[];
    }>("/api/demo"),
};

export function wsUrl(path: string): string {
  const direct = process.env.NEXT_PUBLIC_WS_ORIGIN;
  if (direct) return `${direct}${path}`;
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${path}`;
}
