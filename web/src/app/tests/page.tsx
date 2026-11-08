import Link from "next/link";
import { Stars } from "@/components/Stars";
import { api } from "@/lib/api";
import { per1k, shortDate, usd } from "@/lib/format";

export default async function TestsPage({ searchParams }: { searchParams: Promise<{ all?: string }> }) {
  const { all } = await searchParams;
  const showAll = all === "1";
  const tests = (await api.tests(showAll)) ?? [];
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-[34px] font-extrabold tracking-tight">Crash tests</h1>
          <p className="mt-1 text-ink-2">
            Every test, newest first. Open one to see its runs and sticker.{" "}
            {showAll ? (
              <Link href="/tests" className="underline">
                Hide smoke and calibration tests.
              </Link>
            ) : (
              <Link href="/tests?all=1" className="underline">
                Show smoke and calibration tests too.
              </Link>
            )}
          </p>
        </div>
        <div className="flex gap-5">
          <Link href="/review" className="font-semibold underline decoration-rule decoration-[3px] underline-offset-4">
            Human review queue
          </Link>
          <Link href="/compare" className="font-semibold underline decoration-yellow decoration-[3px] underline-offset-4">
            Compare two tests
          </Link>
        </div>
      </div>
      {tests.length === 0 ? (
        <p className="mt-10 text-ink-2">
          No tests yet. <Link href="/new" className="font-semibold underline">Start one.</Link>
        </p>
      ) : (
        <div className="mt-8 overflow-x-auto rounded-xl border border-rule bg-card">
          <table className="w-full min-w-[760px] text-[14px]">
            <thead>
              <tr className="border-b border-rule text-left font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">
                <th className="px-4 py-3 font-semibold">Agent</th>
                <th className="px-4 py-3 font-semibold">Rating</th>
                <th className="px-4 py-3 text-right font-semibold">Serious / 1k</th>
                <th className="px-4 py-3 text-right font-semibold">Runs</th>
                <th className="px-4 py-3 text-right font-semibold">Cost</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Date</th>
              </tr>
            </thead>
            <tbody>
              {tests.map((t) => {
                const s = t.sticker;
                return (
                  <tr key={t.id} className="border-b border-rule last:border-0 hover:bg-paper">
                    <td className="px-4 py-3">
                      <Link href={`/tests/${t.id}`} className="font-semibold hover:underline">
                        {t.agent_name}
                      </Link>
                      <div className="font-mono text-[11.5px] text-muted">
                        {t.model} · suite {t.suite}
                        {t.scenarios.length > 0 ? ` · ${t.scenarios.length} traps` : ""}
                        {t.label ? ` · ${t.label}` : ""}
                      </div>
                      {(t.internal || t.imported) && (
                        <div className="mt-1 flex gap-1.5">
                          {t.internal && (
                            <span className="rounded bg-paper-2 px-1.5 font-mono text-[10px] uppercase text-muted">internal</span>
                          )}
                          {t.imported && (
                            <span className="rounded bg-yellow px-1.5 font-mono text-[10px] uppercase text-yellow-ink">imported batch</span>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">{s ? <Stars stars={s.stars} provisional={s.provisional} size={16} /> : "…"}</td>
                    <td className="px-4 py-3 text-right font-mono tabular">
                      {s ? (
                        <>
                          {per1k(s.serious_per_1000.point)}{" "}
                          <span className="text-muted">
                            ({per1k(s.serious_per_1000.lower)}–{per1k(s.serious_per_1000.upper)})
                          </span>
                        </>
                      ) : (
                        "…"
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-mono tabular">{s ? s.runs + s.excluded_runs : 0}/{t.runs_requested}</td>
                    <td className="px-4 py-3 text-right font-mono tabular">{s ? usd(s.total_cost_usd) : "…"}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-full px-2 py-0.5 font-mono text-[11px] ${t.status === "finished" ? "bg-green-soft text-green" : t.status === "failed" ? "bg-red-soft text-red" : "bg-yellow text-yellow-ink"}`}
                      >
                        {t.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted">{shortDate(t.created_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
