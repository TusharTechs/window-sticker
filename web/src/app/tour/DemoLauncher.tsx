"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { RunSummary, Test } from "@/lib/types";

type DemoInfo = {
  enabled: boolean;
  models: string[];
  profiles: string[];
  traps: string[];
  environments?: { id: string; title: string }[];
  runs: number;
  remaining_today: number;
  active: Test[];
};

const PROFILE_LABEL: Record<string, string> = {
  none: "No guardrails",
  "prompt-only": "Prompt guardrail",
  hardened: "Hardened (7 guardrails)",
};

/** Start a real, small crash test and watch its microVMs come back one by one. */
export function DemoLauncher({ info, trapTitles }: { info: DemoInfo | null; trapTitles: Record<string, string> }) {
  const [model, setModel] = useState(info?.models[0] ?? "");
  const [profile, setProfile] = useState("none");
  const [environment, setEnvironment] = useState(info?.environments?.[0]?.id ?? "debian");
  const [testId, setTestId] = useState<string | null>(info?.active[0]?.id ?? null);
  const [test, setTest] = useState<Test | null>(info?.active[0] ?? null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const started = useRef<number | null>(null);
  const [elapsed, setElapsed] = useState(0);

  const poll = useCallback(async (id: string) => {
    const [t, r] = await Promise.all([
      fetch(`/api/tests/${id}`).then((x) => (x.ok ? x.json() : null)),
      fetch(`/api/tests/${id}/runs`).then((x) => (x.ok ? x.json() : [])),
    ]);
    if (t) setTest(t);
    setRuns(r);
    return t as Test | null;
  }, []);

  useEffect(() => {
    if (!testId) return;
    let stop = false;
    started.current ??= Date.now();
    const loop = async () => {
      while (!stop) {
        const t = await poll(testId).catch(() => null);
        if (t && !["queued", "running"].includes(t.status)) break;
        await new Promise((res) => setTimeout(res, 2000));
      }
    };
    void loop();
    const tick = setInterval(() => setElapsed(Math.round((Date.now() - (started.current ?? Date.now())) / 1000)), 1000);
    return () => {
      stop = true;
      clearInterval(tick);
    };
  }, [testId, poll]);

  async function start() {
    setStarting(true);
    setError(null);
    try {
      const res = await fetch("/api/demo", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ model, profile, environment }),
      });
      const body = await res.json().catch(() => ({}));
      if (res.status === 409 && body?.detail?.active?.length) {
        setError("Two live demos are already running. Here is one of them, live.");
        started.current = Date.now();
        setTestId(body.detail.active[0]);
        return;
      }
      if (!res.ok) {
        setError(typeof body?.detail === "string" ? body.detail : "The lab could not start a demo right now.");
        return;
      }
      started.current = Date.now();
      setRuns([]);
      setTest(body);
      setTestId(body.id);
    } finally {
      setStarting(false);
    }
  }

  if (!info?.enabled) {
    return <p className="text-ink-2">The live demo is switched off. The replays above use the same real runs.</p>;
  }

  const total = test?.runs_requested ?? info.runs;
  const finished = runs.length;
  const done = test && !["queued", "running"].includes(test.status);
  const incidents = runs.filter((r) => r.incident).length;

  return (
    <div className="overflow-hidden rounded-2xl border-2 border-ink bg-lab text-lab-ink shadow-[6px_6px_0_0_var(--ink)]">
      <div className="hazard-tape h-1.5" aria-hidden="true" />
      <div className="p-5 sm:p-6">
        {!testId && (
          <div className="grid gap-5 md:grid-cols-[1fr_1fr_1.4fr] md:items-end">
            <label className="block">
              <span className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-lab-muted">Model (Vultr Serverless Inference)</span>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="mt-1.5 block w-full rounded-lg border border-lab-rule bg-lab-2 px-3 py-2.5 text-[14px] text-lab-ink"
              >
                {info.models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-lab-muted">Machine (microVM image)</span>
              <select
                value={environment}
                onChange={(e) => setEnvironment(e.target.value)}
                className="mt-1.5 block w-full rounded-lg border border-lab-rule bg-lab-2 px-3 py-2.5 text-[14px] text-lab-ink"
              >
                {(info.environments ?? [{ id: "debian", title: "Debian 12" }]).map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.title}
                  </option>
                ))}
              </select>
            </label>
            <fieldset>
              <legend className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-lab-muted">Guardrails</legend>
              <div className="mt-1.5 flex rounded-lg border border-lab-rule p-0.5 text-[12.5px]">
                {info.profiles.map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setProfile(p)}
                    aria-pressed={profile === p}
                    className={`flex-1 rounded-md px-2 py-2 transition ${profile === p ? "bg-yellow font-semibold text-ink" : "text-lab-muted hover:text-lab-ink"}`}
                  >
                    {PROFILE_LABEL[p] ?? p}
                  </button>
                ))}
              </div>
            </fieldset>
          </div>
        )}
        {!testId && (
          <button
            type="button"
            onClick={start}
            disabled={starting}
            className="mt-5 w-full rounded-lg bg-yellow px-5 py-3 font-semibold text-ink shadow-[3px_3px_0_0_#fffdf8] transition hover:-translate-y-px disabled:opacity-60 sm:w-auto"
          >
            {starting ? "Starting…" : "Start a live crash test"}
          </button>
        )}

        {!testId && (
          <p className="mt-4 font-mono text-[11.5px] text-lab-muted">
            {info.runs} real runs, two on each of: {info.traps.map((t) => trapTitles[t] ?? t).join(" · ")}. Usually under a
            minute. {info.remaining_today} demos left today.
          </p>
        )}

        {error && <p className="mt-4 rounded-md border border-[#5a3a12] bg-[#2a1d08] px-3 py-2 text-[13.5px] text-[#ffd98a]">{error}</p>}

        {testId && (
          <div>
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.16em] text-lab-muted">
                  {!done && <span className="pulse-dot h-2 w-2 rounded-full bg-yellow" />}
                  {done ? "Finished" : test?.status === "queued" ? "Queued for the next free microVMs" : "Live on the Vultr VX1 host"} · {elapsed}s
                </div>
                <div className="mt-1 text-[16px] font-semibold">
                  {test?.agent_name}{" "}
                  <span className="font-mono text-[12px] text-lab-muted">
                    · {test?.model} · {test?.environment_title ?? "Debian 12"}
                  </span>
                </div>
              </div>
              <div className="flex gap-6 text-right font-mono">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.14em] text-lab-muted">Graded</div>
                  <div className="font-display text-[24px] font-extrabold tabular">
                    {finished}/{total}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-[0.14em] text-lab-muted">Incidents</div>
                  <div className={`font-display text-[24px] font-extrabold tabular ${incidents ? "text-[#ff6b5e]" : ""}`}>{incidents}</div>
                </div>
              </div>
            </div>

            <ul className="mt-5 grid grid-cols-2 gap-2.5 sm:grid-cols-3">
              {Array.from({ length: total }).map((_, i) => {
                const r = runs[i];
                return (
                  <li key={r?.id ?? `slot-${i}`}>
                    <AnimatePresence mode="wait">
                      {r ? (
                        <motion.div key="done" initial={{ rotateX: 90, opacity: 0 }} animate={{ rotateX: 0, opacity: 1 }} transition={{ duration: 0.45 }}>
                          <Link
                            href={`/runs/${r.id}`}
                            className={`block rounded-lg border p-3 transition hover:-translate-y-0.5 ${r.incident ? "border-[#ff6b5e] bg-[#2a0f0d]" : "border-[#1f4a35] bg-[#0f2219]"}`}
                          >
                            <div className="flex justify-between font-mono text-[10.5px] font-semibold">
                              <span className="text-lab-muted">run {i + 1}</span>
                              <span className={r.incident ? "text-[#ff6b5e]" : "text-[#5fd39a]"}>{r.incident ? "INCIDENT" : "CLEAN"}</span>
                            </div>
                            <div className="mt-1.5 truncate text-[12.5px]">{trapTitles[r.scenario_id] ?? r.scenario_id}</div>
                            <div className="mt-1.5 font-mono text-[10.5px] text-yellow underline underline-offset-2">open the replay →</div>
                          </Link>
                        </motion.div>
                      ) : (
                        <motion.div
                          key="pending"
                          className="grid min-h-[86px] place-items-center rounded-lg border border-dashed border-lab-rule font-mono text-[11px] text-lab-muted"
                          animate={done ? {} : { opacity: [0.5, 1, 0.5] }}
                          transition={{ duration: 1.6, repeat: Infinity }}
                        >
                          {test?.status === "running" ? "microVM working…" : "waiting"}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </li>
                );
              })}
            </ul>

            {done && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mt-5 flex flex-wrap items-center gap-4">
                <p className="text-[14.5px]">
                  {incidents === 0
                    ? "No incidents this time. Six runs is a demo, not a rating: the leaderboard uses 48 to 96."
                    : `${incidents} of ${total} runs did something the lab had to stop. Open one to see exactly what, and why it went nowhere.`}
                </p>
                <Link href={`/tests/${testId}`} className="font-mono text-[12px] text-yellow underline underline-offset-4">
                  Open the full test
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    setTestId(null);
                    setTest(null);
                    setRuns([]);
                    started.current = null;
                  }}
                  className="font-mono text-[12px] text-lab-muted underline underline-offset-4"
                >
                  Try another setup
                </button>
              </motion.div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
