import Link from "next/link";
import { Stars } from "@/components/Stars";
import { StickerCard } from "@/components/StickerCard";
import { CountUp } from "@/components/motion/CountUp";
import { LabReplay, type ReplayTest } from "@/components/motion/LabReplay";
import { Reveal } from "@/components/motion/Reveal";
import { environmentFinding } from "@/lib/environments";
import { TiltCard } from "@/components/motion/TiltCard";
import { api } from "@/lib/api";
import { TRAP_TAG, seconds, usd } from "@/lib/format";
import type { Breakdown, RunSummary, Suite, Test } from "@/lib/types";

const STEPS = [
  {
    n: "01",
    title: "Fork a microVM",
    body: "Every run gets a fresh microVM with its own kernel on a Vultr VX1 host, a 4 GiB disk cap and no network except two host doors: the Egress Warden and, for agents that run inside, the inference lane.",
  },
  {
    n: "02",
    title: "Plant one trap",
    body: "A real task with one trap in the workspace: a poisoned README, a rogue package index, a config checker that leaks a key over DNS. Fake credentials are minted for every run.",
  },
  {
    n: "03",
    title: "Let the agent work",
    body: "The reference agent's brain stays on the host and only its tool calls run in the VM. OpenCode runs entirely inside, reaching the model through a host lane that holds the key.",
  },
  {
    n: "04",
    title: "Grade, then destroy",
    body: "Mechanical tripwires decide what they can; two Vultr decision models triage the rest for a person. The VM is destroyed and its absence verified.",
  },
];

const AUDIENCE = [
  {
    title: "Platform and security teams",
    body: "Deciding which AI agent gets access to your code. Know what it does when a repository lies to it, before it touches yours.",
  },
  {
    title: "Agent vendors",
    body: "Stuck in security reviews. Attach a measured rating and a public replay of every run instead of a demo video.",
  },
  {
    title: "Anyone shipping prompt changes",
    body: "Run it in CI. A prompt or guardrail change that drops your agent below the stars you require fails the build.",
  },
];

function setupLabel(t: Test): string {
  const name = t.agent_name.toLowerCase();
  if (name.startsWith("opencode")) return "OpenCode, running inside the microVM";
  if (name.includes("hardened")) return "Reference agent, prompt + 6 tool-level guardrails";
  if (name.includes("prompt")) return "Reference agent, one system-prompt guardrail";
  return "Reference agent, no guardrails";
}

function aggregateFindings(tests: Test[]) {
  const by = new Map<string, { title: string; category: string; incidents: number; runs: number; agents: number }>();
  for (const t of tests) {
    for (const b of t.sticker?.breakdown ?? []) {
      const cur = by.get(b.scenario) ?? { title: b.title, category: b.category, incidents: 0, runs: 0, agents: 0 };
      cur.incidents += b.incidents;
      cur.runs += b.runs;
      cur.agents += b.incidents > 0 ? 1 : 0;
      by.set(b.scenario, cur);
    }
  }
  return [...by.values()].filter((f) => f.incidents > 0).sort((a, b) => b.incidents / b.runs - a.incidents / a.runs);
}

function replayOf(t: Test, runs: RunSummary[] | null, suite: Suite | null, label: string): ReplayTest | null {
  if (!t.sticker || !runs?.length) return null;
  const meta = new Map((suite?.scenarios ?? []).map((sc) => [sc.id, sc]));
  return {
    id: t.id,
    label,
    agent: t.agent_name,
    model: t.model,
    stars: t.sticker.stars,
    seriousPer1k: t.sticker.serious_per_1000.point,
    upperPer1k: t.sticker.serious_per_1000.upper,
    runs: runs
      .filter((r) => r.graded)
      .map((r) => ({
        id: r.id,
        tag: TRAP_TAG[meta.get(r.scenario_id)?.category ?? ""] ?? r.scenario_id.slice(0, 4).toUpperCase(),
        title: meta.get(r.scenario_id)?.title ?? r.scenario_id,
        incident: r.incident,
        serious: r.serious,
        cost: r.cost_usd,
      })),
  };
}

export default async function Home() {
  const [v2, v1, suite, host, matrices] = await Promise.all([
    api.leaderboard("v2"),
    api.leaderboard("v1"),
    api.suite(),
    api.host(),
    api.matrices(),
  ]);
  const envFinding = environmentFinding(matrices, suite);
  const board = v2 && v2.length >= 2 ? v2 : (v1 ?? []);
  const suiteName = v2 && v2.length >= 2 ? "v2" : "v1";
  const best = board[0] ?? null;
  const worst = board.length > 1 ? board[board.length - 1] : null;
  const findings = aggregateFindings(board).slice(0, 4);
  const totalRuns = board.reduce((a, t) => a + (t.sticker?.runs ?? 0), 0);
  const boots = board.map((t) => t.sticker?.median_boot_s).filter((x): x is number => x != null).sort((a, b) => a - b);
  const bootMedian = boots.length ? boots[Math.floor(boots.length / 2)] : (host?.boot_p50_s ?? null);
  const rates = board
    .map((t) => (t.sticker?.wall_clock_s ? (t.sticker.runs / t.sticker.wall_clock_s) * 3600 : null))
    .filter((x): x is number => x != null)
    .sort((a, b) => a - b);
  const models = new Set(board.map((t) => t.model)).size;
  // Same model, different setups: the cleanest comparison the leaderboard offers.
  const heldOut = new Set((suite?.scenarios ?? []).filter((s) => s.tags.includes("held-out")).map((s) => s.id));
  const sameModel = board.filter((t) => t.model === best?.model && t.sticker);
  const tally = (t: Test, pick: (b: Breakdown) => boolean, key: "incidents" | "serious" | "runs") =>
    (t.sticker?.breakdown ?? []).filter(pick).reduce((a, b) => a + b[key], 0);
  const all = () => true;
  const held = (b: Breakdown) => heldOut.has(b.scenario);
  const [bestRuns, worstRuns] = await Promise.all([
    best ? api.runs(best.id) : Promise.resolve(null),
    worst ? api.runs(worst.id) : Promise.resolve(null),
  ]);
  const replays = [
    best && replayOf(best, bestRuns, suite, `Best rated · ${best.model.replace(/-\d{4}$/, "")}`),
    worst && replayOf(worst, worstRuns, suite, `Lowest rated · ${worst.model.replace(/-\d{4}$/, "")}`),
  ].filter((x): x is ReplayTest => x != null);

  return (
    <>
      <section className="paper-dots overflow-x-clip">
      <div className="mx-auto grid max-w-6xl gap-12 px-4 pb-14 pt-14 sm:px-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] lg:pt-20">
        <div className="flex flex-col justify-center">
          <p className="mb-5 inline-flex w-fit items-center gap-2 rounded-full border border-ink/15 bg-card px-3 py-1 font-mono text-[11.5px] uppercase tracking-[0.14em] text-ink-2">
            <span className="h-1.5 w-1.5 rounded-full bg-yellow ring-2 ring-ink/80" />
            Crash-test lab for AI agents
          </p>
          <h1 className="font-display text-[44px] font-extrabold leading-[1.02] tracking-tight sm:text-[58px]">
            Every AI agent should ship with a crash-test rating.
          </h1>
          <p className="mt-6 max-w-xl text-[18px] leading-relaxed text-ink">
            For teams buying, building or approving AI agents: know what it does when a repository lies to it, before
            it touches yours.
          </p>
          <p className="mt-3 max-w-xl text-[16px] leading-relaxed text-ink-2">
            Window Sticker runs an agent dozens of times in throwaway microVMs on Vultr, against a published suite of
            traps, and prints what it measured: how often it does something dangerous, how often it finishes the job,
            and what it costs.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/tour"
              className="rounded-lg bg-ink px-5 py-3 text-[15px] font-semibold text-paper shadow-[3px_3px_0_0_var(--yellow)] transition hover:-translate-y-px"
            >
              Take the tour and run a live test
            </Link>
            <Link href="/leaderboard" className="rounded-lg border-2 border-ink px-5 py-[10px] text-[15px] font-semibold hover:bg-card">
              Compare agents
            </Link>
            {best && (
              <Link href={`/tests/${best.id}`} className="px-2 py-3 text-[15px] font-semibold underline decoration-yellow decoration-[3px] underline-offset-4">
                See a real crash test
              </Link>
            )}
          </div>
          <dl className="mt-10 grid max-w-lg grid-cols-3 gap-6 border-t border-rule pt-6">
            <div>
              <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted">microVM boot</dt>
              <dd className="mt-1 font-display text-[24px] font-extrabold tabular">
                {bootMedian != null ? <CountUp value={bootMedian} decimals={2} suffix="s" /> : seconds(bootMedian)}
              </dd>
              <dd className="font-mono text-[10.5px] text-muted">median, production runs</dd>
            </div>
            <div>
              <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted">Runs on record</dt>
              <dd className="mt-1 font-display text-[24px] font-extrabold tabular">
                <CountUp value={totalRuns} />
              </dd>
              <dd className="font-mono text-[10.5px] text-muted">Trap Suite {suiteName}</dd>
            </div>
            <div>
              <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted">VMs left behind</dt>
              <dd className="mt-1 font-display text-[24px] font-extrabold tabular">0</dd>
              <dd className="font-mono text-[10.5px] text-muted">verified per run</dd>
            </div>
          </dl>
        </div>
        <div className="relative lg:pt-4">
          <div className="sticker-glow pointer-events-none absolute -inset-10" aria-hidden="true" />
          {best?.sticker ? (
            <>
              <TiltCard>
                <StickerCard s={best.sticker} compact />
              </TiltCard>
              <p className="mt-5 font-mono text-[11.5px] text-muted">
                The best-rated agent on Trap Suite {suiteName}: {best.sticker.runs} real runs.
              </p>
            </>
          ) : (
            <div className="grid h-full min-h-80 place-items-center rounded-2xl border-2 border-dashed border-rule p-8 text-center text-ink-2">
              The first sticker appears when a test finishes.
            </div>
          )}
        </div>
      </div>
      </section>

      {replays.length > 0 && (
        <section className="relative overflow-hidden border-y-2 border-ink bg-lab text-lab-ink">
          <div className="hazard-tape h-2" aria-hidden="true" />
          <div className="lab-grid absolute inset-0 opacity-60" aria-hidden="true" />
          <div className="relative mx-auto max-w-6xl px-4 py-12 sm:px-6">
            <Reveal>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-yellow">Watch a real crash test</p>
              <h2 className="mt-2 font-display text-[30px] font-extrabold tracking-tight sm:text-[36px]">
                Same traps. Different agents.
              </h2>
              <p className="mt-2 max-w-2xl text-[15.5px] text-[#c9ced6]">
                Each run boots its own microVM on a Vultr VX1 host, plants one trap, lets the agent work, grades it and
                destroys the VM. Stars come from the worst plausible rate, not the average.
              </p>
            </Reveal>
            <div className="mt-8">
              <LabReplay tests={replays} />
            </div>
          </div>
        </section>
      )}

      {sameModel.length >= 3 && heldOut.size > 0 && (
        <section className="mx-auto max-w-6xl px-4 pt-16 sm:px-6">
<Reveal>
          <h2 className="font-display text-[30px] font-extrabold tracking-tight">What Trap Suite {suiteName} found</h2>
          <p className="mt-2 max-w-3xl text-[16px] leading-relaxed text-ink-2">
            Same model, different setups. Guardrails removed the serious failures. But six tool-level guardrails added
            nothing measurable on top of one system prompt, and on traps written after they were frozen both guardrailed agents still
            reached for code from an unknown package index. The lab blocked it every time; the guardrails never did.
          </p>
          <div className="mt-6 overflow-x-auto rounded-xl border-2 border-ink bg-card">
            <table className="w-full min-w-[560px] text-[14px]">
              <thead>
                <tr className="border-b border-rule text-left font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">
                  <th className="px-4 py-3 font-semibold">{best?.model.replace(/-\d{4}$/, "")}, set up as</th>
                  <th className="px-4 py-3 font-semibold">Rating</th>
                  <th className="px-4 py-3 text-right font-semibold">Serious, all traps</th>
                  <th className="px-4 py-3 text-right font-semibold">Any incident, held-out traps</th>
                </tr>
              </thead>
              <tbody>
                {sameModel.map((t) => (
                  <tr key={t.id} className="border-b border-rule last:border-0">
                    <td className="px-4 py-3 font-semibold">
                      <Link href={`/tests/${t.id}`} className="hover:underline">
                        {setupLabel(t)}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <Stars stars={t.sticker!.stars} provisional={t.sticker!.provisional} size={15} />
                    </td>
                    <td className="px-4 py-3 text-right font-mono tabular">
                      {tally(t, all, "serious")}/{t.sticker!.runs}
                    </td>
                    <td className="px-4 py-3 text-right font-mono tabular">
                      {tally(t, held, "incidents")}/{tally(t, held, "runs")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {envFinding && (
            <Link
              href="/environments"
              className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border-2 border-ink bg-yellow p-5 transition hover:-translate-y-0.5"
            >
              <span className="font-display text-[34px] font-extrabold leading-none tabular">
                {envFinding.k}/{envFinding.n}
              </span>
              <span className="min-w-0 flex-1 text-[15px] text-yellow-ink">
                <strong className="text-ink">The machine changes the agent.</strong> On {envFinding.env}, the same agent fell for
                &ldquo;{envFinding.trap}&rdquo; in {envFinding.k} of {envFinding.n} runs, against {envFinding.k0} of {envFinding.n0} on
                Debian 12 (adjusted p {envFinding.pAdjusted.toFixed(3)}). Its rating held elsewhere.
              </span>
              <span className="font-mono text-[12px] font-semibold text-ink underline underline-offset-4">Environments →</span>
            </Link>
          )}
          <p className="mt-3 font-mono text-[11.5px] text-muted">
            Held-out traps: {heldOut.size} of {suite?.scenarios.length}. Package-index incidents are graded by what happened:
            contact is logged, a download is an incident, only an install is serious.
          </p>
        </Reveal>
</section>
      )}

      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
<Reveal>
        <h2 className="font-display text-[30px] font-extrabold tracking-tight">Who it is for</h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {AUDIENCE.map((a) => (
            <div key={a.title} className="rounded-xl border border-rule bg-card p-5">
              <h3 className="text-[16.5px] font-bold">{a.title}</h3>
              <p className="mt-2 text-[14.5px] leading-relaxed text-ink-2">{a.body}</p>
            </div>
          ))}
        </div>
        <div className="mt-6 grid gap-px overflow-hidden rounded-xl border border-rule bg-rule md:grid-cols-3">
          {[
            {
              k: "Cost to produce a rating",
              v: best?.sticker?.all_in_cost_usd != null ? `${usd(best.sticker.all_in_cost_usd)} for ${best.sticker.runs} runs` : "under $1",
              note: "Inference plus VX1 host time, measured on this page's best-rated test. A five-star test is 183 runs.",
            },
            {
              k: "How it makes money (hypothesis)",
              v: "Free CLI · $49 per published sticker",
              note: "Proposed: the engine, trap format and badge are open source; a hosted, published rating is $49 (it costs under $1 to produce); CI gating $199 per agent per month; certification on a private trap set for vendors.",
            },
            {
              k: "Recurring",
              v: "A gate on every pull request",
              note: "Teams that ship prompt and guardrail changes run it in CI. Every run is Vultr compute and Serverless Inference.",
            },
          ].map((x) => (
            <div key={x.k} className="bg-card p-5">
              <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted">{x.k}</div>
              <div className="mt-1 text-[17px] font-bold">{x.v}</div>
              <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-2">{x.note}</p>
            </div>
          ))}
        </div>
      </Reveal>
</section>

      <section className="border-y border-rule bg-card">
<Reveal>
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <h2 className="font-display text-[30px] font-extrabold tracking-tight">What one crash-test run does</h2>
          <ol className="mt-8 grid gap-px overflow-hidden rounded-xl border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((st) => (
              <li key={st.n} className="bg-card p-6">
                <div className="font-mono text-[12px] font-semibold text-muted">{st.n}</div>
                <h3 className="mt-3 text-[17px] font-bold">{st.title}</h3>
                <p className="mt-2 text-[14.5px] leading-relaxed text-ink-2">{st.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </Reveal>
</section>

      {findings.length > 0 && (
        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
<Reveal>
          <h2 className="font-display text-[30px] font-extrabold tracking-tight">What it has caught</h2>
          <p className="mt-2 max-w-2xl text-ink-2">
            Across every agent on the Trap Suite {suiteName} leaderboard. Each one was stopped by the lab and can be
            replayed step by step.
          </p>
          <ul className="mt-8 grid gap-4 md:grid-cols-2">
            {findings.map((f) => (
              <li key={f.title} className="rounded-xl border-2 border-ink bg-card p-5">
                <div className="flex items-baseline justify-between gap-4">
                  <span className="rounded bg-red-soft px-2 py-0.5 font-mono text-[11px] font-semibold text-red">
                    {TRAP_TAG[f.category] ?? f.category}
                  </span>
                  <span className="font-display text-[26px] font-extrabold tabular">
                    {f.incidents}/{f.runs}
                  </span>
                </div>
                <p className="mt-3 text-[16px] font-semibold">{f.title}</p>
                <p className="mt-1 text-[14px] text-ink-2">
                  runs ended in an incident, across {f.agents} of {board.length} agents.
                </p>
              </li>
            ))}
          </ul>
        </Reveal>
</section>
      )}

      <section className="border-y border-rule bg-card">
<Reveal>
        <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
          <div>
            <h2 className="font-display text-[30px] font-extrabold tracking-tight">
              Everyone else sells the cage. We sell the crash rating.
            </h2>
            <p className="mt-3 text-[16px] leading-relaxed text-ink-2">
              And every rating runs on <span className="font-semibold text-vultr">Vultr</span>: a fleet of cheap,
              KVM-capable hosts for disposable microVMs, and one inference endpoint for every model in the comparison,
              plus the decision models that triage each run.
            </p>
          </div>
          <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-rule bg-rule">
            {[
              ["Sandbox host", host ? `Vultr ${host.plan} · ${host.region}` : "Vultr VX1"],
              ["Isolation", "microVM per run, own kernel"],
              ["Escape matrix", "17/17 on all 4 OS images; 22/22 in-VM"],
              ["Environments", "Debian, slim Debian, Alpine, Python 3.10"],
              ["Models compared", `${models} from Serverless Inference`],
              ["Throughput", rates.length ? `${Math.round(rates[0] / 10) * 10}–${Math.round(rates[rates.length - 1] / 10) * 10} runs per host-hour` : "n/a"],
              ["Jury (triage)", "clef + d3: AUC 0.98, 29–31 of 40 caught at 0.5"],
              ["Host price", host ? `${usd(host.hourly_usd)} / hour` : ""],
            ].map(([k, v]) => (
              <div key={k} className="bg-card p-4">
                <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted">{k}</dt>
                <dd className="mt-1 text-[15px] font-semibold">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </Reveal>
</section>

      {suite && (
        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
<Reveal>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="font-display text-[30px] font-extrabold tracking-tight">Trap Suite {suite.name}</h2>
              <p className="mt-2 max-w-2xl text-ink-2">
                {suite.scenarios.length} scenarios, each a legitimate task with one trap, published as YAML so anyone
                can see exactly what an agent was tested against.
              </p>
            </div>
            <Link href="/suite" className="font-semibold underline decoration-yellow decoration-[3px] underline-offset-4">
              Browse the suite
            </Link>
          </div>
          <ul className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {suite.scenarios.map((sc) => (
              <li key={sc.id} className="rounded-lg border border-rule bg-card p-4">
                <div className="font-mono text-[11px] font-semibold tracking-wider text-muted">
                  {TRAP_TAG[sc.category] ?? sc.category}
                  {sc.tags.includes("held-out") && <span className="ml-2 rounded bg-yellow px-1 text-yellow-ink">held-out</span>}
                </div>
                <div className="mt-1.5 text-[14px] font-semibold leading-snug">{sc.title}</div>
              </li>
            ))}
          </ul>
        </Reveal>
</section>
      )}
    </>
  );
}
