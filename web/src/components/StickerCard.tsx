import { Stars } from "./Stars";
import { TargetMark } from "./Logo";
import type { Range, Sticker } from "@/lib/types";
import { FAILURE_LABEL, GUARDRAIL_LABEL, pct, per1k, shortDate, usd } from "@/lib/format";

/** A point estimate with its confidence interval, drawn on a 0..max scale. */
export function IntervalBar({
  range,
  max,
  tone = "red",
  label,
}: {
  range: Range;
  max: number;
  tone?: "red" | "green" | "ink";
  label: string;
}) {
  const x = (v: number) => `${Math.min(100, Math.max(0, (v / max) * 100))}%`;
  const color = tone === "red" ? "var(--red)" : tone === "green" ? "var(--green)" : "var(--ink)";
  return (
    <div className="relative h-6" role="img" aria-label={label}>
      <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-rule" />
      <div
        className="absolute top-1/2 h-2 -translate-y-1/2 rounded-full opacity-25"
        style={{ left: x(range.lower), width: `calc(${x(range.upper)} - ${x(range.lower)})`, background: color }}
      />
      <div
        className="absolute top-1/2 h-4 w-px -translate-y-1/2"
        style={{ left: x(range.lower), background: color }}
      />
      <div
        className="absolute top-1/2 h-4 w-px -translate-y-1/2"
        style={{ left: x(range.upper), background: color }}
      />
      <div
        className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-card"
        style={{ left: x(range.point), background: color }}
      />
    </div>
  );
}

function Cell({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="px-5 py-4">
      <div className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.14em] text-muted">{label}</div>
      <div className="mt-1 font-display text-[26px] font-extrabold leading-none tabular">{value}</div>
      <div className="mt-1.5 font-mono text-[11.5px] text-muted tabular">{sub}</div>
    </div>
  );
}

export function StickerCard({ s, compact = false }: { s: Sticker; compact?: boolean }) {
  const serious = s.serious_per_1000;
  const scaleMax = Math.max(100, Math.ceil((serious.upper * 1.15) / 50) * 50);
  const modes = Object.entries(s.failure_modes).sort((a, b) => b[1] - a[1]);

  return (
    <article className="overflow-hidden rounded-2xl border-2 border-ink bg-card shadow-[6px_6px_0_0_var(--ink)]">
      <header className="flex items-center justify-between bg-ink px-5 py-3 text-paper">
        <div className="flex items-center gap-2.5">
          <TargetMark size={22} />
          <span className="font-display text-[15px] font-extrabold uppercase tracking-[0.16em]">
            Window Sticker
          </span>
        </div>
        <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#9aa4b2]">
          AI agent crash test
        </span>
      </header>
      <div className="hazard h-1.5" aria-hidden="true" />

      <div className="border-b border-rule px-5 pb-4 pt-5">
        <h3 className="font-display text-[22px] font-extrabold leading-tight">{s.agent.name}</h3>
        <p className="mt-1 font-mono text-[12px] text-muted">
          model <span className="text-ink-2">{s.agent.model}</span> · config{" "}
          <span className="text-ink-2">{s.agent.fingerprint}</span>
        </p>
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {s.agent.guardrails.length === 0 ? (
            <span className="rounded-md border border-rule px-2 py-0.5 font-mono text-[11px] text-muted">
              no guardrails
            </span>
          ) : (
            s.agent.guardrails.map((g) => (
              <span key={g} className="rounded-md border border-ink/20 bg-paper px-2 py-0.5 text-[11.5px]">
                {GUARDRAIL_LABEL[g] ?? g}
              </span>
            ))
          )}
        </div>
      </div>

      <div className="grid border-b border-rule sm:grid-cols-[1fr_1.2fr]">
        <div className="border-b border-rule px-5 py-5 sm:border-b-0 sm:border-r">
          <div className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.14em] text-muted">
            Safety rating
          </div>
          <div className="mt-3">
            <Stars stars={s.stars} provisional={s.provisional} size={30} />
          </div>
          <p className="mt-3 text-[13px] leading-snug text-ink-2">{s.rating_reason}</p>
        </div>
        <div className="px-5 py-5">
          <div className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.14em] text-muted">
            Serious incidents
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span
              className={`font-display text-[46px] font-extrabold leading-none tabular ${serious.point > 0 ? "text-red" : ""}`}
            >
              {per1k(serious.point)}
            </span>
            <span className="text-[13px] text-ink-2">per 1,000 runs</span>
          </div>
          <div className="mt-3">
            <IntervalBar
              range={serious}
              max={scaleMax}
              label={`95% confidence interval ${per1k(serious.lower)} to ${per1k(serious.upper)} per 1,000`}
            />
            <div className="mt-0.5 flex justify-between font-mono text-[10.5px] text-muted tabular">
              <span>0</span>
              <span>
                95% CI {per1k(serious.lower)}–{per1k(serious.upper)}
              </span>
              <span>{scaleMax}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-rule [&>*]:border-rule [&>*:nth-child(odd)]:border-r [&>*:nth-child(-n+2)]:border-b">
        <Cell
          label="Any incident"
          value={`${per1k(s.any_per_1000.point)}/1k`}
          sub={`CI ${per1k(s.any_per_1000.lower)}–${per1k(s.any_per_1000.upper)}`}
        />
        <Cell
          label="Safe success"
          value={pct(s.task_success.point)}
          sub={`CI ${pct(s.task_success.lower)}–${pct(s.task_success.upper)}`}
        />
        <Cell label="Cost / safe success" value={usd(s.cost_per_success_usd)} sub="measured inference" />
        <Cell label="Test cost" value={usd(s.total_cost_usd)} sub={`${s.runs} graded runs`} />
      </div>

      {!compact && (
        <div className="border-b border-rule px-5 py-4">
          <div className="mb-2 flex items-center justify-between font-mono text-[10.5px] font-semibold uppercase tracking-[0.14em] text-muted">
            <span>By trap</span>
            <span>incidents / runs</span>
          </div>
          <ul className="space-y-1.5">
            {s.breakdown.map((b) => {
              const frac = b.runs ? b.incidents / b.runs : 0;
              return (
                <li key={b.scenario} className="grid grid-cols-[1fr_120px_52px] items-center gap-3 text-[13px]">
                  <span className="truncate" title={b.title}>
                    {b.title}
                  </span>
                  <span className="h-2 overflow-hidden rounded-full bg-paper-2">
                    <span className="block h-full rounded-full bg-red" style={{ width: `${frac * 100}%` }} />
                  </span>
                  <span className="text-right font-mono tabular">
                    {b.incidents}/{b.runs}
                  </span>
                </li>
              );
            })}
          </ul>
          {modes.length > 0 && (
            <p className="mt-3 text-[12.5px] text-ink-2">
              Most common failure: <strong>{FAILURE_LABEL[modes[0][0]] ?? modes[0][0]}</strong> ({modes[0][1]})
            </p>
          )}
        </div>
      )}

      <footer className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3 font-mono text-[11px] text-muted">
        <span>
          Trap Suite {s.suite.name} · {s.suite.digest}
        </span>
        <span>{s.runs} graded · {s.excluded_runs} excluded</span>
        <span>{shortDate(s.tested_at)}</span>
        <span className={s.teardown_verified ? "text-green" : "text-red"}>
          {s.teardown_verified ? "✓ every microVM destroyed" : "teardown unverified"}
        </span>
        {s.precomputed && <span className="rounded bg-yellow px-1.5 text-yellow-ink">precomputed batch</span>}
      </footer>
    </article>
  );
}
