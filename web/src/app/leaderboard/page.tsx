import Link from "next/link";
import { Stars } from "@/components/Stars";
import { api } from "@/lib/api";
import { pct, per1k, usd } from "@/lib/format";
import type { Test } from "@/lib/types";

/** Safety (upper bound of serious incidents) against cost per safe success. */
function Scatter({ tests }: { tests: Test[] }) {
  const pts = tests.filter((t) => t.sticker && t.sticker.cost_per_success_usd != null);
  if (pts.length === 0) return null;
  const W = 640;
  const H = 300;
  const pad = { l: 56, r: 20, t: 16, b: 44 };
  const maxX = Math.max(...pts.map((t) => t.sticker!.cost_per_success_usd!)) * 1.25;
  const maxY = Math.max(250, ...pts.map((t) => t.sticker!.serious_per_1000.upper)) * 1.1;
  const x = (v: number) => pad.l + (v / maxX) * (W - pad.l - pad.r);
  const y = (v: number) => H - pad.b - (v / maxY) * (H - pad.t - pad.b);
  const ticksY = [0, maxY / 4, maxY / 2, (3 * maxY) / 4].map((v) => Math.round(v / 10) * 10);
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
        {pts.map((t) => {
          const s = t.sticker!;
          const cx = x(s.cost_per_success_usd!);
          return (
            <g key={t.id}>
              <line x1={cx} x2={cx} y1={y(s.serious_per_1000.lower)} y2={y(s.serious_per_1000.upper)} stroke="var(--ink)" strokeWidth="2" />
              <circle cx={cx} cy={y(s.serious_per_1000.point)} r="6" fill="var(--yellow)" stroke="var(--ink)" strokeWidth="2" />
              <text x={cx + 10} y={y(s.serious_per_1000.point) + 4} fontSize="11.5" fill="var(--ink)">
                {s.agent.name.replace("Reference coding agent ", "")}
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

export default async function LeaderboardPage() {
  const tests = (await api.leaderboard()) ?? [];
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <h1 className="font-display text-[34px] font-extrabold tracking-tight">Safety per dollar</h1>
      <p className="mt-2 max-w-2xl text-ink-2">
        The newest finished test for each agent configuration on Trap Suite v1, ranked by the worst plausible
        serious-incident rate, then by cost per safe success. Same traps, same lab, models from the Vultr Serverless
        Inference catalogue.
      </p>
      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_1.1fr]">
        <ol className="space-y-3">
          {tests.map((t, i) => {
            const s = t.sticker!;
            return (
              <li key={t.id}>
                <Link href={`/tests/${t.id}`} className="flex items-center gap-4 rounded-xl border border-rule bg-card p-4 hover:border-ink">
                  <span className="font-display text-[26px] font-extrabold text-muted tabular">{i + 1}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-semibold">{t.agent_name}</span>
                    <span className="block font-mono text-[11.5px] text-muted">
                      {t.model} · {s.runs} runs
                    </span>
                  </span>
                  <span className="text-right">
                    <Stars stars={s.stars} provisional={s.provisional} size={15} />
                    <span className="mt-1 block font-mono text-[11.5px] text-ink-2 tabular">
                      ≤{per1k(s.serious_per_1000.upper)}/1k · {pct(s.task_success.point)} safe · {usd(s.cost_per_success_usd)}
                    </span>
                  </span>
                </Link>
              </li>
            );
          })}
          {tests.length === 0 && <li className="text-ink-2">No finished tests yet.</li>}
        </ol>
        <Scatter tests={tests} />
      </div>
    </div>
  );
}
