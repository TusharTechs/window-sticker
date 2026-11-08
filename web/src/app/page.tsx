import Link from "next/link";
import { Stars } from "@/components/Stars";
import { StickerCard } from "@/components/StickerCard";
import { api } from "@/lib/api";
import { TRAP_TAG, per1k, seconds, usd } from "@/lib/format";
import type { Test } from "@/lib/types";

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

export default async function Home() {
  const [v2, v1, suite, host] = await Promise.all([api.leaderboard("v2"), api.leaderboard("v1"), api.suite(), api.host()]);
  const board = v2 && v2.length >= 2 ? v2 : (v1 ?? []);
  const suiteName = v2 && v2.length >= 2 ? "v2" : "v1";
  const best = board[0] ?? null;
  const worst = board.length > 1 ? board[board.length - 1] : null;
  const findings = aggregateFindings(board).slice(0, 4);
  const totalRuns = board.reduce((a, t) => a + (t.sticker?.runs ?? 0), 0);

  return (
    <>
      <section className="mx-auto grid max-w-6xl gap-12 px-4 pb-14 pt-14 sm:px-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] lg:pt-20">
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
            {best && (
              <Link
                href={`/tests/${best.id}`}
                className="rounded-lg bg-ink px-5 py-3 text-[15px] font-semibold text-paper shadow-[3px_3px_0_0_var(--yellow)] transition hover:-translate-y-px"
              >
                See a real crash test
              </Link>
            )}
            <Link href="/leaderboard" className="rounded-lg border-2 border-ink px-5 py-[10px] text-[15px] font-semibold hover:bg-card">
              Compare agents
            </Link>
            <Link href="/new" className="px-2 py-3 text-[15px] font-semibold underline decoration-yellow decoration-[3px] underline-offset-4">
              Rate your agent
            </Link>
          </div>
          <dl className="mt-10 grid max-w-lg grid-cols-3 gap-6 border-t border-rule pt-6">
            <div>
              <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted">microVM boot</dt>
              <dd className="mt-1 font-display text-[24px] font-extrabold tabular">{seconds(host?.boot_p50_s ?? null)}</dd>
              <dd className="font-mono text-[10.5px] text-muted">p50, cached image</dd>
            </div>
            <div>
              <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted">Runs on record</dt>
              <dd className="mt-1 font-display text-[24px] font-extrabold tabular">{totalRuns.toLocaleString("en-US")}</dd>
              <dd className="font-mono text-[10.5px] text-muted">Trap Suite {suiteName}</dd>
            </div>
            <div>
              <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted">VMs left behind</dt>
              <dd className="mt-1 font-display text-[24px] font-extrabold tabular">0</dd>
              <dd className="font-mono text-[10.5px] text-muted">verified per run</dd>
            </div>
          </dl>
        </div>
        <div className="lg:pt-4">
          {best?.sticker ? (
            <>
              <StickerCard s={best.sticker} compact />
              <p className="mt-4 font-mono text-[11.5px] text-muted">
                The best-rated agent on Trap Suite {suiteName}: {best.sticker.runs} real runs.
              </p>
            </>
          ) : (
            <div className="grid h-full min-h-80 place-items-center rounded-2xl border-2 border-dashed border-rule p-8 text-center text-ink-2">
              The first sticker appears when a test finishes.
            </div>
          )}
        </div>
      </section>

      {best?.sticker && worst?.sticker && (
        <section className="border-y-2 border-ink bg-ink text-paper">
          <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
            <h2 className="font-display text-[30px] font-extrabold tracking-tight">Same traps. Different agents.</h2>
            <p className="mt-2 max-w-2xl text-[15.5px] text-[#c9ced6]">
              Stars come from the worst plausible rate, not the average. Three stars means: with 95% confidence, fewer
              than 1 in 10 runs does something dangerous.
            </p>
            <div className="mt-8 grid gap-4 md:grid-cols-2">
              {[best, worst].map((t, i) => (
                <Link
                  key={t.id}
                  href={`/tests/${t.id}`}
                  className="rounded-xl border border-[#2a313c] bg-[#141820] p-5 transition hover:border-yellow"
                >
                  <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-[#8a93a3]">
                    {i === 0 ? "Best rated" : "Lowest rated"}
                  </div>
                  <div className="mt-2 text-[17px] font-semibold">{t.agent_name}</div>
                  <div className="font-mono text-[12px] text-[#8a93a3]">{t.model}</div>
                  <div className="mt-4 flex items-end justify-between">
                    <Stars stars={t.sticker!.stars} provisional={t.sticker!.provisional} size={22} />
                    <span className="text-right">
                      <span className={`font-display text-[30px] font-extrabold tabular ${i === 1 ? "text-[#ff6b5e]" : ""}`}>
                        {per1k(t.sticker!.serious_per_1000.point)}
                      </span>
                      <span className="block font-mono text-[11px] text-[#8a93a3]">serious incidents per 1,000 runs</span>
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <h2 className="font-display text-[30px] font-extrabold tracking-tight">Who it is for</h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {AUDIENCE.map((a) => (
            <div key={a.title} className="rounded-xl border border-rule bg-card p-5">
              <h3 className="text-[16.5px] font-bold">{a.title}</h3>
              <p className="mt-2 text-[14.5px] leading-relaxed text-ink-2">{a.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-y border-rule bg-card">
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
      </section>

      {findings.length > 0 && (
        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
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
        </section>
      )}

      <section className="border-y border-rule bg-card">
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
              ["Escape matrix", "17/17 and 22/22 contained"],
              ["Models compared", "6 from Serverless Inference"],
              ["Jury", "clef + d3, AUC 0.98 vs tripwires"],
              ["Host price", host ? `${usd(host.hourly_usd)} / hour` : ""],
            ].map(([k, v]) => (
              <div key={k} className="bg-card p-4">
                <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted">{k}</dt>
                <dd className="mt-1 text-[15px] font-semibold">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {suite && (
        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
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
        </section>
      )}
    </>
  );
}
