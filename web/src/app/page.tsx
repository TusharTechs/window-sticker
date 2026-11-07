import Link from "next/link";
import { StickerCard } from "@/components/StickerCard";
import { api } from "@/lib/api";
import { TRAP_TAG, seconds, usd } from "@/lib/format";
import type { Test } from "@/lib/types";

function pickHero(tests: Test[]): Test | null {
  const finished = tests.filter((t) => t.status === "finished" && t.sticker);
  return finished.find((t) => !t.sticker!.provisional) ?? finished[0] ?? null;
}

const STEPS = [
  {
    n: "01",
    title: "Fork a microVM",
    body: "Every run gets a fresh libkrun microVM with its own kernel on a Vultr VX1 host. Network: deny all. The only door out is a logging proxy.",
  },
  {
    n: "02",
    title: "Plant one trap",
    body: "A real task, with a trap inside the workspace: a poisoned README, a ticket that slips in an SSH key, a rogue package index. Fake credentials are minted per run.",
  },
  {
    n: "03",
    title: "Let the agent work",
    body: "The agent's brain stays outside; only its tool calls run inside the VM. Every command, file change and connection attempt is recorded.",
  },
  {
    n: "04",
    title: "Grade, then destroy",
    body: "Mechanical tripwires decide what they can. Two Vultr decision models judge the rest. The VM is destroyed and its absence verified.",
  },
];

export default async function Home() {
  const [tests, suite] = await Promise.all([api.tests(), api.suite()]);
  const hero = pickHero(tests ?? []);
  const s = hero?.sticker ?? null;
  const findings = s?.breakdown.filter((b) => b.incidents > 0).sort((a, b) => b.incidents / b.runs - a.incidents / a.runs) ?? [];

  return (
    <>
      <section className="mx-auto grid max-w-6xl gap-12 px-4 pb-16 pt-14 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:pt-20">
        <div className="flex flex-col justify-center">
          <p className="mb-5 inline-flex w-fit items-center gap-2 rounded-full border border-ink/15 bg-card px-3 py-1 font-mono text-[11.5px] uppercase tracking-[0.14em] text-ink-2">
            <span className="h-1.5 w-1.5 rounded-full bg-yellow ring-2 ring-ink/80" />
            Crash-test lab for AI agents
          </p>
          <h1 className="font-display text-[44px] font-extrabold leading-[1.02] tracking-tight sm:text-[58px]">
            Every AI agent should ship with a crash-test rating.
          </h1>
          <p className="mt-6 max-w-xl text-[17.5px] leading-relaxed text-ink-2">
            Window Sticker runs your agent dozens of times in throwaway microVMs on Vultr, against a published suite
            of traps. Then it prints what it measured: how often the agent does something dangerous, how often it
            finishes the job, and what each safe success costs.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/new"
              className="rounded-lg bg-ink px-5 py-3 text-[15px] font-semibold text-paper shadow-[3px_3px_0_0_var(--yellow)] transition hover:-translate-y-px"
            >
              Crash-test an agent
            </Link>
            {hero && (
              <Link
                href={`/tests/${hero.id}`}
                className="rounded-lg border-2 border-ink px-5 py-[10px] text-[15px] font-semibold hover:bg-card"
              >
                Open this test
              </Link>
            )}
          </div>
          {s && (
            <dl className="mt-10 grid max-w-lg grid-cols-3 gap-6 border-t border-rule pt-6">
              <div>
                <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted">Median boot</dt>
                <dd className="mt-1 font-display text-[24px] font-extrabold tabular">{seconds(s.median_boot_s)}</dd>
              </div>
              <div>
                <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted">Cost per run</dt>
                <dd className="mt-1 font-display text-[24px] font-extrabold tabular">
                  {usd(s.total_cost_usd / Math.max(1, s.runs + s.excluded_runs))}
                </dd>
              </div>
              <div>
                <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted">VMs left behind</dt>
                <dd className="mt-1 font-display text-[24px] font-extrabold tabular">
                  {s.teardown_verified ? "0" : "?"}
                </dd>
              </div>
            </dl>
          )}
        </div>
        <div className="lg:pt-4">
          {s ? (
            <>
              <StickerCard s={s} compact />
              <p className="mt-4 font-mono text-[11.5px] text-muted">
                A real sticker from {s.runs + s.excluded_runs} runs. {hero?.label}
              </p>
            </>
          ) : (
            <div className="grid h-full min-h-80 place-items-center rounded-2xl border-2 border-dashed border-rule p-8 text-center text-ink-2">
              No finished tests yet. Run one to print the first sticker.
            </div>
          )}
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

      {findings.length > 0 && s && (
        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <h2 className="font-display text-[30px] font-extrabold tracking-tight">What it has found so far</h2>
          <p className="mt-2 max-w-2xl text-ink-2">
            From the test above: {s.agent.name}, model <code className="font-mono text-[14px]">{s.agent.model}</code>.
          </p>
          <ul className="mt-8 grid gap-4 md:grid-cols-2">
            {findings.map((f) => (
              <li key={f.scenario} className="rounded-xl border-2 border-ink bg-card p-5">
                <div className="flex items-baseline justify-between gap-4">
                  <span className="rounded bg-red-soft px-2 py-0.5 font-mono text-[11px] font-semibold text-red">
                    {TRAP_TAG[f.category] ?? f.category}
                  </span>
                  <span className="font-display text-[28px] font-extrabold tabular">
                    {f.incidents}/{f.runs}
                  </span>
                </div>
                <p className="mt-3 text-[16px] font-semibold">{f.title}</p>
                <p className="mt-1 text-[14px] text-ink-2">runs ended in an incident on this trap.</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {suite && (
        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="font-display text-[30px] font-extrabold tracking-tight">Trap Suite {suite.name}</h2>
              <p className="mt-2 max-w-2xl text-ink-2">
                Twelve scenarios, each a legitimate task with one trap. Published as YAML so anyone can see exactly
                what an agent was tested against.
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
