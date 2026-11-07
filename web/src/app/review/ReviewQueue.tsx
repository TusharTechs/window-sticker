"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usd } from "@/lib/format";
import type { RunSummary } from "@/lib/types";

export function ReviewQueue({ initial, titles }: { initial: RunSummary[]; titles: Record<string, string> }) {
  const [queue, setQueue] = useState(initial);
  const [token, setToken] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      setToken(window.localStorage.getItem("wsk.token") ?? "");
      setName(window.localStorage.getItem("wsk.reviewer") ?? "");
    } catch {
      /* storage unavailable */
    }
  }, []);

  async function label(run: RunSummary, incident: boolean) {
    setError(null);
    try {
      window.localStorage.setItem("wsk.token", token);
      window.localStorage.setItem("wsk.reviewer", name);
    } catch {
      /* not fatal */
    }
    const res = await fetch(`/api/runs/${run.id}/label`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ incident, labeller: name || "reviewer" }),
    });
    if (!res.ok) {
      setError((await res.json().catch(() => ({}))).detail ?? res.statusText);
      return;
    }
    setQueue((q) => q.filter((r) => r.id !== run.id));
  }

  const input = "rounded-lg border border-rule bg-card px-3 py-2 text-[14px] focus:border-ink focus:outline-none focus:ring-2 focus:ring-yellow";

  return (
    <div className="mt-8 space-y-6">
      <div className="flex flex-wrap gap-3">
        <input className={input} placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} />
        <input
          className={input}
          type="password"
          autoComplete="off"
          placeholder="Access token"
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
      </div>
      {error && <p className="rounded-md bg-red-soft px-3 py-2 text-[14px] text-red">{error}</p>}
      {queue.length === 0 ? (
        <p className="rounded-xl border border-rule bg-card p-6 text-ink-2">
          Nothing to review. Every graded run is settled by tripwires or an agreeing jury.
        </p>
      ) : (
        <ul className="space-y-3">
          {queue.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-4 rounded-xl border border-rule bg-card p-4">
              <div className="min-w-0 flex-1">
                <Link href={`/runs/${r.id}`} className="font-semibold hover:underline">
                  {titles[r.scenario_id] ?? r.scenario_id}
                </Link>
                <div className="font-mono text-[11.5px] text-muted">
                  {r.id} · {r.test_id} · {usd(r.cost_usd)}
                </div>
              </div>
              <Link href={`/runs/${r.id}`} className="text-[14px] underline decoration-yellow decoration-2 underline-offset-4">
                Replay
              </Link>
              <button
                onClick={() => label(r, true)}
                className="rounded-lg border-2 border-red px-3 py-1.5 text-[14px] font-semibold text-red hover:bg-red-soft"
              >
                Incident
              </button>
              <button
                onClick={() => label(r, false)}
                className="rounded-lg border-2 border-green px-3 py-1.5 text-[14px] font-semibold text-green hover:bg-green-soft"
              >
                Not an incident
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
