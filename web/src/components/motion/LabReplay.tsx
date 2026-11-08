"use client";

import Link from "next/link";
import { AnimatePresence, motion, useInView, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";

export type ReplayRun = { id: string; tag: string; title: string; incident: boolean; serious: boolean; cost: number };
export type ReplayTest = {
  id: string;
  label: string;
  agent: string;
  model: string;
  stars: number;
  seriousPer1k: number;
  upperPer1k: number;
  runs: ReplayRun[];
};

const STEP = 0.085; // seconds between run starts: several microVMs are in flight at once
const BOOT = 0.45; // boot and agent work, compressed
const RESOLVE = 0.25;

type Phase = "queued" | "running" | "clean" | "incident";

function phaseAt(i: number, t: number, run: ReplayRun): Phase {
  const start = i * STEP;
  if (t < start) return "queued";
  if (t < start + BOOT) return "running";
  return run.incident ? "incident" : "clean";
}

/**
 * Replays real crash tests: every tile is one stored run, landing in the order it was graded,
 * compressed to a few seconds. Nothing here is simulated except the timing.
 */
export function LabReplay({ tests }: { tests: ReplayTest[] }) {
  const [which, setWhich] = useState(0);
  // Start finished, so the server-rendered page shows the real outcome; the replay restarts on view.
  const [t, setT] = useState(Number.POSITIVE_INFINITY);
  const [epoch, setEpoch] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: false, margin: "-120px" });
  const reduce = useReducedMotion();
  const test = tests[which];
  const total = test.runs.length * STEP + BOOT + RESOLVE;

  useEffect(() => {
    if (reduce) {
      setT(total);
      return;
    }
    if (!inView) return;
    setT(0);
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const s = (now - t0) / 1000;
      setT(s);
      if (s < total) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, reduce, epoch, which, total]);

  const phases = useMemo(() => test.runs.map((r, i) => phaseAt(i, t, r)), [test, t]);
  const done = phases.filter((p) => p === "clean" || p === "incident").length;
  const incidents = phases.filter((p) => p === "incident").length;
  const inFlight = phases.filter((p) => p === "running").length;
  const spend = test.runs.reduce((a, r, i) => a + (phases[i] === "clean" || phases[i] === "incident" ? r.cost : 0), 0);
  const finished = done === test.runs.length;

  return (
    <div ref={ref} className="relative">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div role="tablist" aria-label="Choose a crash test to replay" className="flex rounded-lg border border-lab-rule p-0.5 font-mono text-[12px]">
          {tests.map((x, i) => (
            <button
              key={x.id}
              role="tab"
              aria-selected={i === which}
              onClick={() => {
                setWhich(i);
                setEpoch((e) => e + 1);
              }}
              className={`rounded-md px-3 py-1.5 transition ${i === which ? "bg-yellow font-semibold text-ink" : "text-lab-muted hover:text-lab-ink"}`}
            >
              {x.label}
            </button>
          ))}
        </div>
        <dl className="grid grid-cols-4 gap-5 text-right font-mono">
          {[
            ["Runs", `${done}/${test.runs.length}`],
            ["In flight", String(inFlight)],
            ["Incidents", String(incidents)],
            ["Spend", `$${spend.toFixed(3)}`],
          ].map(([k, v]) => (
            <div key={k}>
              <dt className="text-[10px] uppercase tracking-[0.14em] text-lab-muted">{k}</dt>
              <dd className={`font-display text-[22px] font-extrabold tabular ${k === "Incidents" && incidents ? "text-[#ff6b5e]" : "text-lab-ink"}`}>{v}</dd>
            </div>
          ))}
        </dl>
      </div>

      <div className="mt-3 h-1 overflow-hidden rounded-full bg-lab-3">
        <div className="h-full bg-yellow" style={{ width: `${(done / test.runs.length) * 100}%` }} />
      </div>

      <ul className="mt-5 grid grid-cols-8 gap-1.5 sm:grid-cols-12 lg:grid-cols-16" aria-label={`${test.runs.length} runs of ${test.agent}`}>
        {test.runs.map((r, i) => {
          const p = phases[i];
          return (
            <li key={`${test.id}-${r.id}`}>
              <Link
                href={`/runs/${r.id}`}
                title={`${r.title}: ${r.incident ? (r.serious ? "serious incident" : "incident") : "clean"}`}
                className="block"
              >
                <motion.span
                  className={`relative grid aspect-square place-items-center overflow-hidden rounded-[5px] border font-mono text-[8.5px] font-semibold tracking-wide sm:text-[9px] ${
                    p === "queued"
                      ? "border-dashed border-lab-rule text-transparent"
                      : p === "running"
                        ? "border-yellow/70 bg-yellow/10 text-yellow"
                        : p === "incident"
                          ? "border-[#ff6b5e] bg-[#3a1210] text-[#ffb3ab]"
                          : "border-[#1f4a35] bg-[#0f2219] text-[#5fd39a]"
                  }`}
                  animate={
                    p === "incident" && !reduce
                      ? { scale: [1, 1.28, 1], boxShadow: ["0 0 0 0 rgba(255,107,94,0)", "0 0 0 6px rgba(255,107,94,.35)", "0 0 0 0 rgba(255,107,94,0)"] }
                      : { scale: 1 }
                  }
                  transition={{ duration: 0.55 }}
                >
                  {p === "running" && !reduce && (
                    <motion.span
                      className="absolute inset-x-0 bottom-0 h-full origin-bottom bg-yellow/20"
                      initial={{ scaleY: 0 }}
                      animate={{ scaleY: 1 }}
                      transition={{ duration: BOOT, ease: "linear" }}
                    />
                  )}
                  <span className="relative max-w-full truncate px-0.5 tracking-tight">{r.tag}</span>
                </motion.span>
              </Link>
            </li>
          );
        })}
      </ul>

      <div className="mt-5 flex min-h-[44px] flex-wrap items-center justify-between gap-3">
        <p className="font-mono text-[11.5px] text-lab-muted">
          Every tile is one real run in its own microVM: <span className="text-[#5fd39a]">clean</span>,{" "}
          <span className="text-[#ff6b5e]">incident</span>. Replayed at 30× speed. Click any tile for its step-by-step replay.
        </p>
        <AnimatePresence mode="wait">
          {finished ? (
            <motion.div
              key="result"
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-3"
            >
              <span className="font-display text-[20px] font-extrabold tracking-wide text-yellow" aria-label={`${test.stars} stars`}>
                {"★".repeat(test.stars)}
                <span className="text-lab-rule">{"★".repeat(5 - test.stars)}</span>
              </span>
              <span className="font-mono text-[12px] text-lab-ink">
                {Math.round(test.seriousPer1k)} serious / 1k · at most {Math.round(test.upperPer1k)}
              </span>
              <button
                onClick={() => setEpoch((e) => e + 1)}
                className="rounded-md border border-lab-rule px-2.5 py-1 font-mono text-[11px] text-lab-muted hover:border-yellow hover:text-lab-ink"
              >
                Replay
              </button>
              <Link href={`/tests/${test.id}`} className="font-mono text-[11px] text-yellow underline underline-offset-4">
                Open test
              </Link>
            </motion.div>
          ) : (
            <motion.span key="running" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="font-mono text-[11px] text-lab-muted">
              {test.agent} · {test.model}
            </motion.span>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
