import type { Metadata } from "next";
import Link from "next/link";
import { Stars } from "@/components/Stars";
import { Reveal } from "@/components/motion/Reveal";
import { api } from "@/lib/api";
import { environmentFinding } from "@/lib/environments";
import { configLabel, per1k, pct, seconds, usd } from "@/lib/format";
import type { Behaviour, Environment, Matrix, Suite, Test } from "@/lib/types";

export const metadata: Metadata = {
  title: "Environments · Window Sticker",
  description: "The same AI agent, the same traps, on different operating systems and toolchains. Does its safety change with the machine?",
};

const OS_BADGE: Record<string, string> = {
  debian: "DEB 12",
  "debian-slim": "DEB SLIM",
  alpine: "ALPINE",
  "debian11-py310": "DEB 11",
};

function Verdict({ t }: { t: Test }) {
  const v = t.versus_baseline;
  if (!v) return <span className="font-mono text-[11.5px] text-muted">baseline</span>;
  if (v.changed) {
    const worse = v.serious_change_per_1000 > 0 || v.any_change_per_1000 > 0;
    return (
      <span className={`rounded px-2 py-0.5 font-mono text-[11px] font-semibold ${worse ? "bg-red-soft text-red" : "bg-green-soft text-green"}`}>
        {worse ? "evidence it is worse" : "evidence it is better"} · adjusted p {Math.min(v.serious_p_adjusted ?? v.serious_p, v.any_p_adjusted ?? v.any_p).toPrecision(2)}
      </span>
    );
  }
  return (
    <span className="font-mono text-[11.5px] text-ink-2">
      no significant change · adjusted p {Math.min(v.serious_p_adjusted ?? v.serious_p, v.any_p_adjusted ?? v.any_p).toPrecision(2)}
    </span>
  );
}

/** The biggest trap-level shift against the baseline machine, in words. */
function finding(m: Matrix, suite: Suite | null): string | null {
  const base = m.tests.find((t) => t.environment === m.baseline)?.sticker;
  if (!base) return null;
  let best: { env: string; trap: string; k: number; n: number; k0: number; n0: number; d: number } | null = null;
  for (const t of m.tests) {
    if (t.environment === m.baseline || !t.sticker || t.status !== "finished") continue;
    for (const b of t.sticker.breakdown) {
      const b0 = base.breakdown.find((x) => x.scenario === b.scenario);
      if (!b0 || !b.runs || !b0.runs) continue;
      const d = b.incidents / b.runs - b0.incidents / b0.runs;
      if (!best || d > best.d) best = { env: t.environment_title ?? "", trap: b.scenario, k: b.incidents, n: b.runs, k0: b0.incidents, n0: b0.runs, d };
    }
  }
  if (!best || best.d <= 0) return null;
  const title = suite?.scenarios.find((s) => s.id === best!.trap)?.title ?? best.trap;
  return `Largest shift: on ${best.env}, "${title}" caught the agent in ${best.k} of ${best.n} runs, against ${best.k0} of ${best.n0} on Debian 12.`;
}

const TOOL_LABEL: Record<string, string> = { tomllib: "Python's tomllib", toml: "the toml package" };

function BehaviourPanel({ m, behaviour }: { m: Matrix; behaviour: Record<string, Behaviour> | null }) {
  if (!behaviour) return null;
  return (
    <div className="border-t border-rule px-4 py-4">
      <div className="mb-3 font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">What the agent did differently on each machine</div>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        {m.tests.map((t) => {
          const b = behaviour[t.environment ?? ""];
          if (!b) return null;
          const missing = Object.entries(b.missing_tools).sort((x, y) => y[1].runs - x[1].runs);
          const moves = Object.entries(b.package_moves).sort((x, y) => y[1].runs - x[1].runs);
          return (
            <div key={t.id} className="rounded-lg border border-rule bg-paper p-3 text-[13px]">
              <div className="font-semibold">{t.environment_title}</div>
              <div className="font-mono text-[10.5px] text-muted">{b.runs} runs · {b.commands} commands</div>
              <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.1em] text-muted">Reached for, not installed</div>
              {missing.length === 0 ? (
                <p className="text-ink-2">Nothing missing.</p>
              ) : (
                <ul className="mt-0.5 space-y-0.5">
                  {missing.map(([tool, v]) => (
                    <li key={tool}>
                      <a href={`/runs/${v.examples[0]}`} className="underline decoration-rule underline-offset-2 hover:decoration-ink">
                        {TOOL_LABEL[tool] ?? tool}
                      </a>{" "}
                      <span className="font-mono text-[11px] text-muted">in {v.runs} runs</span>
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.1em] text-muted">Package moves</div>
              {moves.length === 0 ? (
                <p className="text-ink-2">None.</p>
              ) : (
                <ul className="mt-0.5 space-y-0.5">
                  {moves.map(([label, v]) => (
                    <li key={label}>
                      <a href={`/runs/${v.examples[0]}`} className="underline decoration-rule underline-offset-2 hover:decoration-ink">
                        {label}
                      </a>{" "}
                      <span className="font-mono text-[11px] text-muted">in {v.runs} runs</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MatrixTable({ m, suite, behaviour }: { m: Matrix; suite: Suite | null; behaviour: Record<string, Behaviour> | null }) {
  const headline = m.status === "finished" ? finding(m, suite) : null;
  const scenarios = suite?.scenarios ?? [];
  const finished = m.tests.filter((t) => t.status === "finished").length;
  return (
    <article className="overflow-hidden rounded-2xl border-2 border-ink bg-card shadow-[6px_6px_0_0_var(--ink)]">
      <header className="flex flex-wrap items-center justify-between gap-3 bg-ink px-5 py-3 text-paper">
        <div>
          <div className="font-display text-[17px] font-extrabold">{configLabel({ agent_name: m.agent_name, model: m.model })}</div>
          <div className="font-mono text-[11px] text-[#9aa4b2]">
            {m.agent_name} · matrix {m.matrix_id}
          </div>
        </div>
        <span className={`rounded-full px-2.5 py-0.5 font-mono text-[11px] ${m.status === "finished" ? "bg-green-soft text-green" : "bg-yellow text-yellow-ink"}`}>
          {m.status === "finished" ? "finished" : `running · ${finished}/${m.tests.length} environments done`}
        </span>
      </header>
      {headline && (
        <p className="border-b border-rule bg-yellow/30 px-5 py-3 text-[14.5px] font-medium">{headline}</p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-[14px]">
          <thead>
            <tr className="border-b border-rule text-left font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">
              <th className="px-4 py-3 font-semibold">Environment</th>
              <th className="px-4 py-3 font-semibold">Rating</th>
              <th className="px-4 py-3 text-right font-semibold">Serious / 1k</th>
              <th className="px-4 py-3 text-right font-semibold">Any / 1k</th>
              <th className="px-4 py-3 text-right font-semibold">Safe success</th>
              <th className="px-4 py-3 text-right font-semibold">Boot</th>
              <th className="px-4 py-3 font-semibold">Versus Debian 12</th>
            </tr>
          </thead>
          <tbody>
            {m.tests.map((t) => {
              const s = t.sticker;
              return (
                <tr key={t.id} className="border-b border-rule last:border-0 hover:bg-paper">
                  <td className="px-4 py-3">
                    <Link href={`/tests/${t.id}`} className="flex items-center gap-2 font-semibold hover:underline">
                      <span className="rounded bg-ink px-1.5 py-0.5 font-mono text-[10px] text-yellow">{OS_BADGE[t.environment ?? ""] ?? t.environment}</span>
                      {t.environment_title}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{s ? <Stars stars={s.stars} provisional={s.provisional} size={14} /> : <span className="text-muted">{t.status}</span>}</td>
                  <td className="px-4 py-3 text-right font-mono tabular">
                    {s ? (
                      <>
                        {per1k(s.serious_per_1000.point)} <span className="text-muted">({per1k(s.serious_per_1000.lower)}–{per1k(s.serious_per_1000.upper)})</span>
                      </>
                    ) : (
                      "…"
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular">{s ? per1k(s.any_per_1000.point) : "…"}</td>
                  <td className="px-4 py-3 text-right font-mono tabular">{s ? pct(s.task_success.point) : "…"}</td>
                  <td className="px-4 py-3 text-right font-mono tabular">{s ? seconds(s.median_boot_s) : "…"}</td>
                  <td className="px-4 py-3">{s && t.status === "finished" ? <Verdict t={t} /> : <span className="text-muted">…</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <BehaviourPanel m={m} behaviour={behaviour} />
      {scenarios.length > 0 && m.tests.some((t) => t.sticker) && (
        <div className="overflow-x-auto border-t border-rule px-4 py-4">
          <div className="mb-2 font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">Incidents by trap and environment</div>
          <table className="w-full border-collapse text-[12px]">
            <thead>
              <tr>
                <th className="px-2 py-1 text-left font-mono text-[10.5px] text-muted">Trap</th>
                {m.tests.map((t) => (
                  <th key={t.id} className="px-1 py-1 text-center font-mono text-[10px] text-muted">
                    {OS_BADGE[t.environment ?? ""] ?? t.environment}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {scenarios.map((sc) => {
                const cells = m.tests.map((t) => t.sticker?.breakdown.find((b) => b.scenario === sc.id));
                if (!cells.some((c) => c && c.incidents > 0)) return null;
                return (
                  <tr key={sc.id} className="border-t border-rule">
                    <td className="max-w-[260px] truncate px-2 py-1.5" title={sc.title}>
                      {sc.title}
                    </td>
                    {cells.map((b, i) => {
                      const f = b && b.runs ? b.incidents / b.runs : 0;
                      return (
                        <td key={i} className="p-0.5">
                          <span
                            className="grid h-7 min-w-12 place-items-center rounded font-mono tabular"
                            style={{
                              background: !b ? "transparent" : f === 0 ? "var(--paper-2)" : `color-mix(in srgb, var(--red) ${Math.round(20 + f * 80)}%, var(--card))`,
                              color: f > 0.45 ? "white" : "var(--ink)",
                            }}
                          >
                            {b ? `${b.incidents}/${b.runs}` : "·"}
                          </span>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-2 font-mono text-[11px] text-muted">Traps where nothing happened in any environment are hidden.</p>
        </div>
      )}
    </article>
  );
}

export default async function EnvironmentsPage() {
  const [envs, matrices, suite] = await Promise.all([api.environments(), api.matrices(), api.suite("v2")]);
  const list: Environment[] = envs ?? [];
  // Finished matrices first; full-suite matrices before focused follow-ups.
  const shown = [...(matrices ?? [])]
    .sort(
      (a, b) =>
        Number(a.status !== "finished") - Number(b.status !== "finished") ||
        (b.tests[0]?.runs_requested ?? 0) - (a.tests[0]?.runs_requested ?? 0),
    )
    .slice(0, 4);
  const envFinding = environmentFinding(matrices, suite);
  const done = shown.flatMap((m) => m.tests).filter((t) => t.status === "finished");
  const allRuns = done.reduce((a, t) => a + (t.sticker?.runs ?? 0), 0);
  const inference = done.reduce((a, t) => a + (t.sticker?.total_cost_usd ?? 0), 0);
  const behaviours = await Promise.all(shown.map((m) => (m.status === "finished" ? api.matrixBehaviour(m.matrix_id) : Promise.resolve(null))));

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <Reveal>
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted">Environment matrix</p>
        <h1 className="mt-2 font-display text-[38px] font-extrabold leading-[1.05] tracking-tight sm:text-[48px]">
          Same agent. Same traps. Different machines.
        </h1>
        <p className="mt-4 max-w-3xl text-[17px] leading-relaxed text-ink-2">
          A rating measured on one machine does not automatically hold on another. Agents improvise when the tools they
          expect are missing: no <code className="font-mono">curl</code>, no <code className="font-mono">bash</code>, no
          built-in TOML parser. The environment matrix boots the same microVM test on several operating systems and
          toolchains, then tests whether the agent&apos;s behaviour measurably changed.
        </p>
        {allRuns > 0 && (
          <p className="mt-3 font-mono text-[12px] text-muted">
            {allRuns} runs across {list.length} environments on one Vultr VX1 host · {usd(inference)} of Serverless Inference
          </p>
        )}
      </Reveal>

      {envFinding && (
        <div className="mt-8 grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border-2 border-ink bg-yellow p-5">
            <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-yellow-ink">The machine changes the agent</div>
            <div className="mt-2 flex items-baseline gap-3">
              <span className="font-display text-[40px] font-extrabold leading-none tabular">
                {envFinding.k}/{envFinding.n}
              </span>
              <span className="font-mono text-[13px] text-yellow-ink">
                vs {envFinding.k0}/{envFinding.n0} on Debian 12 · adjusted p {envFinding.pAdjusted.toFixed(3)}
              </span>
            </div>
            <p className="mt-2 text-[14.5px]">
              On {envFinding.env}, the same agent fell for &ldquo;{envFinding.trap}&rdquo; far more often
              {envFinding.serious > 0 ? `, ${envFinding.serious} times by installing the package` : ""}.
            </p>
          </div>
          <div className="rounded-xl border-2 border-ink bg-card p-5">
            <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted">But the ratings held</div>
            <p className="mt-2 text-[14.5px] text-ink-2">
              Across all 16 traps, no machine changed either configuration&apos;s incident rate measurably, and the hardened
              setup kept zero serious incidents everywhere. The escape matrix is 17/17 contained on every image. The agent
              adapted to missing tools without becoming less safe overall.
            </p>
          </div>
        </div>
      )}

      <Reveal>
        <ul className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {list.map((e) => (
            <li key={e.id} className="rounded-xl border border-rule bg-card p-4">
              <div className="flex items-center justify-between">
                <span className="rounded bg-ink px-1.5 py-0.5 font-mono text-[10px] text-yellow">{OS_BADGE[e.id] ?? e.id}</span>
                <code className="font-mono text-[11px] text-muted">{e.image}</code>
              </div>
              <div className="mt-2 font-semibold">{e.title}</div>
              <div className="font-mono text-[11px] text-muted">{e.os}</div>
              <p className="mt-2 text-[13.5px] text-ink-2">{e.notes}</p>
              {e.escape && (
                <p className="mt-2 inline-flex items-center gap-1.5 rounded bg-green-soft px-2 py-0.5 font-mono text-[11px] font-semibold text-green">
                  escape matrix {e.escape.contained}/{e.escape.total} contained
                </p>
              )}
            </li>
          ))}
        </ul>
      </Reveal>

      <div className="mt-12 space-y-10">
        {shown.length === 0 && <p className="text-ink-2">No environment matrix has run yet.</p>}
        {shown.map((m) => (
          <Reveal key={m.matrix_id}>
            <MatrixTable m={m} suite={suite} behaviour={behaviours[shown.indexOf(m)]} />
          </Reveal>
        ))}
      </div>

      <Reveal>
        <section className="mt-12 rounded-xl border border-rule bg-card p-5 text-[14.5px] text-ink-2">
          <h2 className="font-semibold text-ink">How to read it</h2>
          <ul className="mt-2 list-disc space-y-1.5 pl-5">
            <li>Each row is a full crash test: same agent configuration, same traps, same number of runs, a different image booted in the microVM.</li>
            <li>&ldquo;Versus Debian 12&rdquo; is Fisher&apos;s exact test on serious and on any incidents against the Debian 12 row, with Holm&apos;s correction because several machines are compared at once. A small adjusted p is evidence that the machine changed the agent&apos;s behaviour; this is an exploratory comparison.</li>
            <li>Power and noise: 48 runs per machine and 3 per trap catch large shifts, not small ones. The same configuration on the same Debian 12 image scored 1 and 2 serious incidents in 48 runs in two separate tests; differences of that size are noise.</li>
            <li>The harness itself is checked to behave the same everywhere: file snapshots use the guest&apos;s isolated Python, so BusyBox and GNU userlands produce identical evidence.</li>
            <li>Cross-environment tests are kept off the main leaderboard, which compares agents on one fixed machine.</li>
          </ul>
        </section>
      </Reveal>
    </div>
  );
}
