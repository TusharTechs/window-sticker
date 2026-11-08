import Link from "next/link";
import { Stars } from "@/components/Stars";
import { api } from "@/lib/api";
import { configLabel, pct, per1k, usd } from "@/lib/format";
import { fisherP, seriousCount } from "@/lib/stats";
import type { Suite, Test } from "@/lib/types";

const SUITES = ["v2", "v1"] as const;

/** Safety (upper bound of serious incidents) against cost per safe success. */
function Scatter({ tests }: { tests: Test[] }) {
  const pts = tests.filter((t) => t.sticker && t.sticker.cost_per_success_usd != null);
  if (pts.length === 0) return null;
  const W = 640;
  const H = 320;
  const pad = { l: 56, r: 170, t: 16, b: 44 };
  const maxX = Math.max(...pts.map((t) => t.sticker!.cost_per_success_usd!)) * 1.15;
  const maxY = Math.max(250, ...pts.map((t) => t.sticker!.serious_per_1000.upper)) * 1.1;
  const x = (v: number) => pad.l + (v / maxX) * (W - pad.l - pad.r);
  const y = (v: number) => H - pad.b - (v / maxY) * (H - pad.t - pad.b);
  const ticksY = [0, maxY / 4, maxY / 2, (3 * maxY) / 4].map((v) => Math.round(v / 10) * 10);

  // Labels sit in a column on the right, pushed apart so they never overlap, with a leader line to their point.
  const labels = pts
    .map((t) => ({ t, py: y(t.sticker!.serious_per_1000.point), px: x(t.sticker!.cost_per_success_usd!) }))
    .sort((a, b) => a.py - b.py);
  let last = -Infinity;
  const placed = labels.map((l) => {
    const ly = Math.max(l.py, last + 15);
    last = ly;
    return { ...l, ly };
  });
  const overflow = last - (H - pad.b);
  if (overflow > 0) for (const p of placed) p.ly -= overflow;

  return (
    <figure className="rounded-xl border border-rule bg-card p-4">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Serious incident rate against cost per safe success">
        {ticksY.map((v) => (
          <g key={v}>
            <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} stroke="var(--rule)" />
            <text x={pad.l - 8} y={y(v) + 4} textAnchor="end" fontSize="11" fill="var(--muted)" fontFamily="var(--font-mono)">
              {v}
            </text>
          </g>
        ))}
        <text x={pad.l} y={H - 10} fontSize="11" fill="var(--muted)" fontFamily="var(--font-mono)">
          cost per safe success → (lower is cheaper)
        </text>
        <text x={14} y={pad.t + 4} fontSize="11" fill="var(--muted)" fontFamily="var(--font-mono)" transform={`rotate(-90 14 ${pad.t + 4})`} textAnchor="end">
          serious / 1k (95% CI)
        </text>
        {placed.map(({ t, px, py, ly }) => {
          const s = t.sticker!;
          return (
            <g key={t.id}>
              <line x1={px} x2={px} y1={y(s.serious_per_1000.lower)} y2={y(s.serious_per_1000.upper)} stroke="var(--ink)" strokeWidth="2" opacity="0.55" />
              <line x1={px + 7} x2={W - pad.r + 6} y1={py} y2={ly} stroke="var(--rule)" strokeDasharray="2 2" />
              <circle cx={px} cy={py} r="6" fill="var(--yellow)" stroke="var(--ink)" strokeWidth="2" />
              <text x={W - pad.r + 10} y={ly + 4} fontSize="11.5" fill="var(--ink)">
                {configLabel(t)}
              </text>
            </g>
          );
        })}
      </svg>
      <figcaption className="mt-2 text-[12.5px] text-muted">
        Bars are 95% confidence intervals. Lower and further left is better: safer and cheaper per task done safely.
      </figcaption>
    </figure>
  );
}

/** Group rows into tiers: a row joins the current tier unless Fisher's exact test separates it from the tier's leader. */
function tiers(tests: Test[]): number[] {
  const out: number[] = [];
  let tier = 0;
  let leader: Test | null = null;
  for (const t of tests) {
    const s = t.sticker!;
    if (leader) {
      const l = leader.sticker!;
      const p = fisherP(
        seriousCount(l.serious_per_1000.point, l.runs),
        l.runs,
        seriousCount(s.serious_per_1000.point, s.runs),
        s.runs,
      );
      if (p < 0.05) {
        tier += 1;
        leader = t;
      }
    } else leader = t;
    out.push(tier);
  }
  return out;
}

function Heatmap({ tests, suite }: { tests: Test[]; suite: Suite | null }) {
  const scenarios = suite?.scenarios ?? [];
  if (!scenarios.length || !tests.length) return null;
  const heldOut = new Set(scenarios.filter((s) => s.tags.includes("held-out")).map((s) => s.id));
  return (
    <section className="mt-12">
      <h2 className="font-display text-[24px] font-extrabold tracking-tight">Which traps catch which agents</h2>
      <p className="mt-1 max-w-2xl text-[14.5px] text-ink-2">
        Incidents out of runs, per agent and trap. Darker is worse.
        {heldOut.size > 0 &&
          " Columns marked H are held-out traps written after the hardened guardrails were frozen, so no guardrail was tuned against them."}
      </p>
      <div className="mt-5 overflow-x-auto rounded-xl border border-rule bg-card">
        <table className="w-full border-collapse text-[12px]">
          <thead>
            <tr>
              <th className="sticky left-0 bg-card px-3 py-2 text-left font-mono text-[10.5px] font-semibold uppercase tracking-[0.12em] text-muted">
                Agent
              </th>
              {scenarios.map((sc, i) => (
                <th key={sc.id} title={sc.title} className="px-1 py-2 text-center font-mono text-[10.5px] font-semibold text-muted">
                  {String(i + 1).padStart(2, "0")}
                  {heldOut.has(sc.id) && <span className="block text-[9px] text-ink">H</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tests.map((t) => {
              const by = new Map((t.sticker?.breakdown ?? []).map((b) => [b.scenario, b]));
              return (
                <tr key={t.id} className="border-t border-rule">
                  <td className="sticky left-0 whitespace-nowrap bg-card px-3 py-1.5 font-medium">
                    <Link href={`/tests/${t.id}`} className="hover:underline">
                      {configLabel(t)}
                    </Link>
                  </td>
                  {scenarios.map((sc) => {
                    const b = by.get(sc.id);
                    if (!b) return <td key={sc.id} className="px-1 py-1.5 text-center text-muted">·</td>;
                    const f = b.runs ? b.incidents / b.runs : 0;
                    return (
                      <td key={sc.id} className="p-0.5" title={`${sc.title}: ${b.incidents}/${b.runs}`}>
                        <span
                          className="grid h-7 min-w-9 place-items-center rounded font-mono tabular"
                          style={{
                            background: f === 0 ? "var(--paper-2)" : `color-mix(in srgb, var(--red) ${Math.round(20 + f * 80)}%, var(--card))`,
                            color: f > 0.45 ? "white" : f === 0 ? "var(--muted)" : "var(--ink)",
                          }}
                        >
                          {b.incidents}/{b.runs}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <ol className="mt-3 grid gap-x-6 gap-y-0.5 font-mono text-[11px] text-muted sm:grid-cols-2 lg:grid-cols-4">
        {scenarios.map((sc, i) => (
          <li key={sc.id}>
            {String(i + 1).padStart(2, "0")} {sc.title}
          </li>
        ))}
      </ol>
    </section>
  );
}

export default async function LeaderboardPage({ searchParams }: { searchParams: Promise<{ suite?: string }> }) {
  const { suite: wanted } = await searchParams;
  const suiteName = SUITES.includes(wanted as (typeof SUITES)[number]) ? wanted! : "v2";
  const [tests, suite] = await Promise.all([api.leaderboard(suiteName), api.suite(suiteName)]);
  const rows = tests ?? [];
  const tier = tiers(rows);
  const tiedWithTop = tier.filter((x) => x === 0).length;
  /** Index of the row that leads the tier above row i: the one Fisher's test was run against. */
  const leaderRank = (i: number) => tier.indexOf(tier[i - 1]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-[34px] font-extrabold tracking-tight">Safety per dollar</h1>
          <p className="mt-2 max-w-2xl text-ink-2">
            The strongest finished test for each agent configuration on Trap Suite {suiteName}, ranked by the worst
            plausible serious-incident rate, then by cost per safe success. Same traps, same lab, every model from
            Vultr Serverless Inference.
          </p>
        </div>
        <nav aria-label="Trap suite" className="flex rounded-lg border-2 border-ink p-0.5 font-mono text-[12.5px]">
          {SUITES.map((s) => (
            <Link
              key={s}
              href={`/leaderboard?suite=${s}`}
              className={`rounded-md px-3 py-1.5 font-semibold ${s === suiteName ? "bg-ink text-paper" : "text-ink-2 hover:bg-paper-2"}`}
            >
              Suite {s}
              {s === "v1" && <span className="ml-1 font-normal opacity-70">frozen</span>}
            </Link>
          ))}
        </nav>
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="min-w-0">
          <ol className="space-y-3">
            {rows.map((t, i) => {
              const s = t.sticker!;
              const newTier = i > 0 && tier[i] !== tier[i - 1];
              return (
                <li key={t.id}>
                  {newTier && (
                    <div className="mb-3 flex items-center gap-3 font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted">
                      <span className="h-px flex-1 bg-ink/30" />
                      measurably worse than #{leaderRank(i) + 1} (Fisher p &lt; 0.05)
                      <span className="h-px flex-1 bg-ink/30" />
                    </div>
                  )}
                  <Link href={`/tests/${t.id}`} className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-rule bg-card p-4 hover:border-ink">
                    <span className="font-display text-[26px] font-extrabold text-muted tabular">{i + 1}</span>
                    <span className="min-w-0 flex-1 basis-44">
                      <span className="block truncate font-semibold">{configLabel(t)}</span>
                      <span className="block truncate font-mono text-[11.5px] text-muted">
                        {t.agent_name} · {s.runs} runs
                        {t.imported && " · imported batch"}
                        {(t.attempts ?? 1) > 1 && ` · first of ${t.attempts} tests`}
                      </span>
                    </span>
                    <span className="shrink-0 text-right">
                      <Stars stars={s.stars} provisional={s.provisional} size={15} />
                      <span className="mt-1 block font-mono text-[11.5px] text-ink-2 tabular">
                        ≤{per1k(s.serious_per_1000.upper)}/1k · {pct(s.task_success.point)} safe · {usd(s.cost_per_success_usd)}
                      </span>
                    </span>
                  </Link>
                </li>
              );
            })}
            {rows.length === 0 && (
              <li className="rounded-xl border-2 border-dashed border-rule p-6 text-ink-2">
                No finished tests on Trap Suite {suiteName} yet.{" "}
                {suiteName === "v2" && (
                  <Link href="/leaderboard?suite=v1" className="underline">
                    See the v1 leaderboard.
                  </Link>
                )}
              </li>
            )}
          </ol>
          {rows.length > 1 && tiedWithTop > 1 && (
            <p className="mt-4 text-[13px] text-ink-2">
              The top {tiedWithTop} are statistically tied: their intervals overlap and Fisher&apos;s exact test cannot
              separate them at this sample size. Order within a group is by the upper bound, then cost.
            </p>
          )}
        </div>
        <Scatter tests={rows} />
      </div>

      <Heatmap tests={rows} suite={suite} />
    </div>
  );
}
