"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { wsUrl } from "@/lib/api";
import { TRAP_TAG, seconds, usd } from "@/lib/format";
import type { LiveEvent, RunSummary, Test } from "@/lib/types";

type TileState = "booting" | "working" | "clean" | "incident" | "error";

type Tile = {
  runId: string;
  scenario: string;
  state: TileState;
  host?: string;
  boot?: number;
  steps: number;
  cost: number;
  lastTool?: string;
  hit?: string;
  success?: boolean;
  fresh?: boolean;
};

type ScenarioMeta = Record<string, { category: string; title: string }>;

function fromRun(r: RunSummary): Tile {
  return {
    runId: r.id,
    scenario: r.scenario_id,
    state: !r.graded ? "error" : r.incident ? "incident" : "clean",
    host: r.host_id,
    boot: r.boot_s,
    steps: 0,
    cost: r.cost_usd,
    success: r.task_success,
  };
}

const STATE_STYLE: Record<TileState, string> = {
  booting: "border-lab-rule bg-lab-2",
  working: "border-[#3d4a5c] bg-lab-3",
  clean: "border-[#1f5a3a] bg-[#0f1f17]",
  incident: "border-red bg-[#2a0f0d]",
  error: "border-[#5a4a1f] bg-[#1f1a0f]",
};

const STATE_LABEL: Record<TileState, string> = {
  booting: "booting",
  working: "working",
  clean: "clean",
  incident: "INCIDENT",
  error: "excluded",
};

export function LiveGrid({
  test,
  initialRuns,
  scenarios,
}: {
  test: Test;
  initialRuns: RunSummary[];
  scenarios: ScenarioMeta;
}) {
  const [tiles, setTiles] = useState<Map<string, Tile>>(
    () => new Map(initialRuns.map((r) => [r.id, fromRun(r)])),
  );
  const [feed, setFeed] = useState<LiveEvent[]>([]);
  const [status, setStatus] = useState(test.status);
  const live = status === "queued" || status === "running";
  const lastId = useRef(0);
  const router = useRouter();
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!live) return;
    let ws: WebSocket | null = null;
    let closed = false;
    // The sticker below is server-rendered; re-render it as runs are graded (at most every 2s).
    const refreshSticker = () => {
      if (refreshTimer.current) return;
      refreshTimer.current = setTimeout(() => {
        refreshTimer.current = null;
        router.refresh();
      }, 2000);
    };
    const connect = () => {
      ws = new WebSocket(wsUrl(`/api/tests/${test.id}/events?after=${lastId.current}`));
      ws.onmessage = (msg) => {
        const e = JSON.parse(msg.data) as LiveEvent;
        lastId.current = e.id;
        setFeed((f) => [e, ...f].slice(0, 12));
        if (e.kind === "run.verdict" || e.kind === "test.sticker") refreshSticker();
        if (e.kind === "test.finished" || e.kind === "test.sticker") setStatus("finished");
        if (e.kind === "test.started") setStatus("running");
        const runId = e.run_id ?? (e.payload.run_id as string | undefined);
        if (!runId) return;
        setTiles((prev) => {
          const next = new Map(prev);
          const t: Tile = next.get(runId) ?? {
            runId,
            scenario: (e.payload.scenario as string) ?? "",
            state: "booting",
            steps: 0,
            cost: 0,
            fresh: true,
          };
          const p = e.payload;
          if (e.kind === "sandbox.ready") {
            t.state = "working";
            t.boot = p.boot_s as number;
            t.host = p.host as string;
          } else if (e.kind === "agent.step") {
            const step = p.step as { tool_call?: { name: string; arguments: Record<string, unknown> }; cost_usd?: number };
            t.steps += 1;
            t.cost += step.cost_usd ?? 0;
            const call = step.tool_call;
            if (call) {
              const arg = (call.arguments.command ?? call.arguments.path ?? "") as string;
              t.lastTool = `${call.name} ${arg}`.slice(0, 80);
            }
          } else if (e.kind === "tripwire") {
            const hit = p.hit as { evidence: string; near_miss: boolean };
            if (!hit.near_miss) t.hit = hit.evidence;
          } else if (e.kind === "run.verdict") {
            const v = p.verdict as { incident: boolean; task_success: boolean };
            t.state = v.incident ? "incident" : "clean";
            t.success = v.task_success;
          } else if (e.kind === "run.error") {
            t.state = "error";
          }
          next.set(runId, { ...t });
          return next;
        });
      };
      ws.onclose = () => {
        if (!closed) setTimeout(connect, 1500);
      };
    };
    connect();
    return () => {
      closed = true;
      ws?.close();
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
    };
  }, [live, test.id, router]);

  const [showAll, setShowAll] = useState(false);
  const list = useMemo(() => [...tiles.values()], [tiles]);
  // A finished test leads with what went wrong; clean runs fold away behind one button.
  const RANK: Record<TileState, number> = { incident: 0, error: 1, booting: 2, working: 2, clean: 3 };
  const ordered = live ? list : [...list].sort((a, b) => RANK[a.state] - RANK[b.state]);
  const firstScreen = Math.max(12, Math.ceil(ordered.filter((t) => t.state !== "clean").length / 6) * 6);
  const shown = live || showAll ? ordered : ordered.slice(0, firstScreen);
  const done = list.filter((t) => t.state === "clean" || t.state === "incident" || t.state === "error").length;
  const incidents = list.filter((t) => t.state === "incident").length;
  const cost = list.reduce((a, t) => a + t.cost, 0);
  const placeholders = Math.max(0, test.runs_requested - list.length);

  return (
    <section className="bg-lab text-lab-ink">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.16em] text-lab-muted">
              {live && <span className="pulse-dot h-2 w-2 rounded-full bg-yellow" />}
              {live ? "Live" : status} · {test.worker ?? "worker"} · Vultr VX1 · {test.environment_title ?? "Debian 12, full toolchain"}
            </div>
            <h1 className="mt-2 font-display text-[28px] font-extrabold leading-tight">{test.agent_name}</h1>
            <p className="mt-1 font-mono text-[12px] text-lab-muted">
              {test.model} · config {test.agent_fingerprint} · {test.id}
            </p>
          </div>
          <dl className="grid grid-cols-3 gap-6 text-right">
            <div>
              <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-lab-muted">Runs</dt>
              <dd className="font-display text-[26px] font-extrabold tabular">
                {done}
                <span className="text-lab-muted">/{test.runs_requested}</span>
              </dd>
            </div>
            <div>
              <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-lab-muted">Incidents</dt>
              <dd className={`font-display text-[26px] font-extrabold tabular ${incidents ? "text-[#ff6b5e]" : ""}`}>
                {incidents}
              </dd>
            </div>
            <div>
              <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-lab-muted">Spend</dt>
              <dd className="font-display text-[26px] font-extrabold tabular">{usd(cost)}</dd>
            </div>
          </dl>
        </div>

        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-lab-3">
          <div
            className="h-full bg-yellow transition-all duration-500"
            style={{ width: `${(done / Math.max(1, test.runs_requested)) * 100}%` }}
          />
        </div>

        <ul className="mt-6 grid grid-cols-2 gap-2.5 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6" aria-label="Runs">
          {shown.map((t) => {
            const meta = scenarios[t.scenario];
            return (
              <li key={t.runId} className={t.fresh ? "tile-in" : ""}>
                <Link
                  href={`/runs/${t.runId}`}
                  className={`block h-full rounded-lg border p-3 transition hover:-translate-y-0.5 ${STATE_STYLE[t.state]} ${t.state === "incident" ? "verdict-flash" : ""}`}
                >
                  <div className="flex items-center justify-between font-mono text-[10.5px] font-semibold tracking-wider">
                    <span className="text-lab-muted">{meta ? (TRAP_TAG[meta.category] ?? meta.category) : t.scenario}</span>
                    <span
                      className={
                        t.state === "incident"
                          ? "text-[#ff6b5e]"
                          : t.state === "clean"
                            ? "text-[#5fd39a]"
                            : t.state === "error"
                              ? "text-[#e0b25b]"
                              : "text-lab-muted"
                      }
                    >
                      {STATE_LABEL[t.state]}
                    </span>
                  </div>
                  <div className="mt-2 truncate text-[12.5px] text-lab-ink" title={meta?.title}>
                    {meta?.title ?? t.scenario}
                  </div>
                  <div className="mt-2 min-h-[30px] font-mono text-[10.5px] leading-snug text-lab-muted">
                    {t.state === "incident" && t.hit ? (
                      <span className="line-clamp-2 text-[#ffb3ab]">{t.hit}</span>
                    ) : t.lastTool ? (
                      <span className="line-clamp-2">$ {t.lastTool}</span>
                    ) : (
                      <span>{t.runId}</span>
                    )}
                  </div>
                  <div className="mt-2 flex justify-between font-mono text-[10px] text-lab-muted tabular">
                    <span>boot {seconds(t.boot)}</span>
                    <span>{usd(t.cost)}</span>
                  </div>
                </Link>
              </li>
            );
          })}
          {Array.from({ length: placeholders }).map((_, i) => (
            <li
              key={`p${i}`}
              className="grid min-h-[118px] place-items-center rounded-lg border border-dashed border-lab-rule font-mono text-[10.5px] text-lab-muted"
            >
              queued
            </li>
          ))}
        </ul>

        {shown.length < ordered.length && (
          <button
            type="button"
            onClick={() => setShowAll(true)}
            className="mt-4 rounded-lg border border-lab-rule px-4 py-2 font-mono text-[12px] text-lab-ink hover:border-yellow"
          >
            Show all {ordered.length} runs ({ordered.length - shown.length} more, all clean)
          </button>
        )}

        {live && feed.length > 0 && (
          <ol className="mt-6 space-y-1 font-mono text-[11.5px] text-lab-muted" aria-live="polite">
            {feed.slice(0, 6).map((e) => (
              <li key={e.id} className="truncate">
                <span className="text-lab-ink">{e.kind}</span> {e.run_id ?? ""}
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
